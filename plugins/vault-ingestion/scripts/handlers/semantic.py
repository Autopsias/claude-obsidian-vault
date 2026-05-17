"""
handlers/semantic.py — Semantic-neighbour soft-warning for the v2 ingestion pipeline.

Contract: 90 System/_ingestion_contract.md §7.5
Plan:     99 Workspace/_plan_ingestion_dedup_hardening_2026-05-16.html (S04)

Purpose
-------
At ingest, after content extraction and content-hash (Tier-2) dedup passes,
query the Smart Connections semantic index for the top-k nearest existing vault
notes by cosine similarity to the newly extracted text.

This implements the §7.5 "Semantic-neighbour soft-warning protocol":
  - NEVER blocks ingest — purely advisory.
  - Results written to pipeline.semantic_neighbors.
  - Threshold ≥ 0.80 surfaced in _ingestion_supersession_queue.md (soft-duplicate
    candidate block, distinct from hard supersession entries).

Approach — direct index read (no MCP shell)
-------------------------------------------
The pipeline runs as a Python subprocess, not inside the Claude MCP shell.
`mcp__smart-connections__lookup` is unavailable to subprocess code. Instead, this
module replicates the lookup by reading the Smart Connections substrate directly:

  1. Load source-level embeddings from .smart-env/multi/*.ajson
     (key format: "smart_sources:<vault-rel-path>" → {path: ..., embeddings: {<model_key>: {vec: [...]}}})
  2. Embed the query text via sentence-transformers using the pinned model
     (TaylorAI/bge-micro-v2, 384 dims — same model Smart Connections uses).
  3. Compute cosine similarity against all loaded embeddings.
  4. Return top-k results sorted by score descending.

This is equivalent to what mcp__smart-connections__lookup does internally.
The pinned model key and dimension are cross-referenced with:
  - 90 System/_smoke_test_retrieval.py (PINNED_MODEL_KEY, PINNED_DIM)
  - 90 System/_retrieval_contract.md (substrate pin)

Graceful-failure contract (§7.5)
---------------------------------
Any failure (sentence-transformers not installed, .smart-env/ absent, numpy
missing, index empty, any exception) returns [] and appends a warning string.
The caller writes [] to pipeline.semantic_neighbors and adds
"semantic_lookup_unavailable" to pipeline.warnings. Ingest is never blocked.

Authored: 2026-05-16 (S04 of dedup-hardening plan)
"""
from __future__ import annotations

import json
import sys
import warnings as _warnings
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# Pinned substrate constants — must match _smoke_test_retrieval.py + _retrieval_contract.md
# ──────────────────────────────────────────────────────────────────────────────
PINNED_MODEL_KEY = "TaylorAI/bge-micro-v2"
PINNED_DIM = 384

# Soft-warning threshold — scores ≥ this value surface in the supersession queue.
# Imported by ingest.py (single source of truth lives here).
SEMANTIC_SOFT_THRESHOLD = 0.80

# See-also threshold — scores ≥ this value get promoted from
# `pipeline.semantic_neighbors` frontmatter to BODY wikilinks under a
# `## See also` section. Higher than SEMANTIC_SOFT_THRESHOLD because a
# body wikilink is structural (graph-visible) and noisier than a queue
# alert. Locked at 0.85 per LD-03 (S03 of Next-Wave plan v2.1, 2026-05-16).
SEMANTIC_SEE_ALSO_THRESHOLD = 0.85

# Idempotent re-render markers — wrap the `## See also` block so re-ingest /
# re-enrich never double-appends. Detection is by exact marker string.
SEE_ALSO_OPEN  = "<!-- pipeline:see-also -->"
SEE_ALSO_CLOSE = "<!-- /pipeline:see-also -->"

# .smart-env lives at vault root.  ingest.py resolves vault root at runtime and
# passes it to query_neighbors() via the `vault_root` parameter.
SMART_ENV_MULTI_REL = ".smart-env/multi"


# ──────────────────────────────────────────────────────────────────────────────
# .ajson parser — identical logic to _smoke_test_retrieval.py
# ──────────────────────────────────────────────────────────────────────────────

def _parse_ajson(path: Path) -> dict:
    """Parse a Smart Connections .ajson file into a plain dict.

    SC .ajson format: a JSON object body *without* the enclosing braces,
    with a trailing comma after the last entry. We strip the trailing comma
    and wrap in braces before parsing.
    """
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    if text.endswith(","):
        text = text[:-1]
    return json.loads("{" + text + "}")


def _iter_source_embeddings(smart_env_multi: Path) -> list[tuple[str, list[float]]]:
    """Return [(vault_rel_path, embedding_vec), ...] for all source-level records.

    Skips block-level records (key prefix "smart_blocks:"), malformed .ajson
    files, and entries without a valid embedding under the pinned model key.
    Silently skips files that fail to parse (same as smoke-test convention).
    """
    results: list[tuple[str, list[float]]] = []
    if not smart_env_multi.is_dir():
        return results
    for ajson_path in smart_env_multi.iterdir():
        if not ajson_path.name.endswith(".ajson"):
            continue
        try:
            obj = _parse_ajson(ajson_path)
        except (json.JSONDecodeError, Exception):
            continue
        for key, val in obj.items():
            if not key.startswith("smart_sources:"):
                continue
            if not isinstance(val, dict):
                continue
            rel_path = val.get("path")
            embeddings = val.get("embeddings") or {}
            model_record = embeddings.get(PINNED_MODEL_KEY) or {}
            vec = model_record.get("vec")
            if rel_path and isinstance(vec, list) and len(vec) == PINNED_DIM:
                results.append((rel_path, vec))
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Cosine similarity helpers
# ──────────────────────────────────────────────────────────────────────────────

def _topk_cosine(
    query_vec,           # numpy float32 array, shape (dim,)
    src_paths: list[str],
    src_mat_normed,      # numpy float32 array, shape (N, dim), L2-normalised rows
    k: int,
):
    """Return top-k (path, score) by cosine similarity.

    query_vec need not be pre-normalised; we normalise inline.
    Uses argpartition for speed on large indexes (21k+ sources).
    """
    import numpy as np  # guarded; caller checks import availability

    qv = query_vec / max(float(np.linalg.norm(query_vec)), 1e-12)
    sims = src_mat_normed @ qv

    n = len(src_paths)
    if k >= n:
        order = sims.argsort()[::-1]
    else:
        idx = sims.argpartition(-k)[-k:]
        order = idx[sims[idx].argsort()[::-1]]

    return [(src_paths[i], float(sims[i])) for i in order[:k]]


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def query_neighbors(
    text: str,
    *,
    top_k: int = 3,
    vault_root: Optional[Path] = None,
) -> tuple[list[dict], Optional[str]]:
    """Return top-k semantically nearest vault notes for the given extracted text.

    Parameters
    ----------
    text : str
        The extracted body text of the newly ingested file (raw, pre-normalisation).
    top_k : int
        Number of nearest neighbours to return (default: 3).
    vault_root : Path | None
        Absolute path to the vault root. If None, auto-detected as 3 levels above
        this file (handlers/ → _ingestion_pipeline/ → 90 System/ → vault root).

    Returns
    -------
    (neighbors, warning) where:
        neighbors : list[{'path': str, 'score': float}]
            Sorted by score descending. Empty list on any failure.
        warning : str | None
            Non-None when the lookup could not run or ran with degraded results.
            Caller should append this to pipeline.warnings.

    Contract (§7.5)
    ---------------
    - NEVER raises. Any exception is caught and returned as ([], warning).
    - Never blocks the caller — purely advisory.
    - Returns [] (not raises) if sentence-transformers, numpy, or the SC
      substrate index is unavailable.
    """
    if not text or not text.strip():
        # Nothing to embed — skip silently, not a warning condition.
        return [], None

    # ── Resolve vault root ────────────────────────────────────────────────────
    if vault_root is None:
        # handlers/semantic.py → handlers/ → _ingestion_pipeline/ → 90 System/ → vault
        vault_root = Path(__file__).resolve().parent.parent.parent.parent

    smart_env_multi = vault_root / SMART_ENV_MULTI_REL

    # ── Check substrate ────────────────────────────────────────────────────────
    if not smart_env_multi.is_dir():
        return [], f"semantic_lookup_unavailable: .smart-env/multi/ not found at {smart_env_multi}"

    # ── Load embeddings ────────────────────────────────────────────────────────
    try:
        pairs = _iter_source_embeddings(smart_env_multi)
    except Exception as exc:
        return [], f"semantic_lookup_unavailable: error reading SC index: {exc}"

    if not pairs:
        return [], "semantic_lookup_unavailable: SC index empty or no valid source embeddings"

    # ── numpy required ────────────────────────────────────────────────────────
    try:
        import numpy as np
    except ImportError:
        return [], "semantic_lookup_unavailable: numpy not installed (pip install numpy)"

    # ── sentence-transformers required ────────────────────────────────────────
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return [], (
            "semantic_lookup_unavailable: sentence-transformers not installed "
            "(pip install --break-system-packages sentence-transformers)"
        )

    # ── Build normalised source matrix ────────────────────────────────────────
    try:
        src_paths = [p for p, _ in pairs]
        src_mat = np.array([v for _, v in pairs], dtype=np.float32)
        norms = np.linalg.norm(src_mat, axis=1, keepdims=True)
        src_mat_normed = src_mat / np.clip(norms, 1e-12, None)
    except Exception as exc:
        return [], f"semantic_lookup_unavailable: failed to build embedding matrix: {exc}"

    # ── Embed query ────────────────────────────────────────────────────────────
    try:
        # Suppress noisy tokenizer/model warnings from transformers on stderr.
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            model = SentenceTransformer(PINNED_MODEL_KEY)
            # Truncate to first 512 tokens worth (~2000 chars) — bge-micro-v2
            # max sequence length is 512 tokens; longer inputs are silently
            # truncated by the model, but we avoid passing multi-MB strings.
            text_snippet = text[:8000]
            query_vec = model.encode(text_snippet, normalize_embeddings=False)
    except Exception as exc:
        return [], f"semantic_lookup_unavailable: failed to embed query: {exc}"

    # ── Top-k cosine ──────────────────────────────────────────────────────────
    try:
        top_pairs = _topk_cosine(query_vec, src_paths, src_mat_normed, top_k)
    except Exception as exc:
        return [], f"semantic_lookup_unavailable: cosine similarity failed: {exc}"

    neighbors = [{"path": p, "score": round(s, 6)} for p, s in top_pairs]
    return neighbors, None


# ──────────────────────────────────────────────────────────────────────────────
# See-also block rendering (LD-03 — semantic_neighbors → body wikilinks)
# ──────────────────────────────────────────────────────────────────────────────

def _neighbor_to_wikilink(path: str) -> str:
    """Convert a vault-relative path to an Obsidian wikilink target.

    Obsidian wikilinks resolve by basename (no extension). Examples:
      "30 Projects/Peninsula.md"                    -> "Peninsula"
      "40 Meetings/2026-04-15_board_prep.md"        -> "2026-04-15_board_prep"
      "Peninsula" (already a basename)              -> "Peninsula"
    """
    if not path:
        return ""
    base = path.rsplit("/", 1)[-1]
    if base.endswith(".md"):
        base = base[:-3]
    return base


def format_see_also_block(
    neighbors: list[dict],
    *,
    threshold: float = SEMANTIC_SEE_ALSO_THRESHOLD,
) -> str:
    """Render the idempotent `## See also` block for high-score neighbours.

    Returns an empty string if no neighbour clears the threshold — caller
    then skips the append entirely (no empty block).

    Output shape (wrapped in idempotent markers so a future re-enrich pass
    can detect + replace the block without leaving orphan content):

        <!-- pipeline:see-also -->
        ## See also

        - [[Peninsula]] (score 0.92)
        - [[2026-04-15_board_prep]] (score 0.87)
        <!-- /pipeline:see-also -->

    The score is shown in parentheses for human review; tooling that wants
    to strip it can split on " (score ".
    """
    if not neighbors:
        return ""
    qualified = [n for n in neighbors if n.get("score", 0.0) >= threshold]
    if not qualified:
        return ""
    lines = [SEE_ALSO_OPEN, "## See also", ""]
    seen: set[str] = set()
    for n in qualified:
        target = _neighbor_to_wikilink(n.get("path", ""))
        if not target or target in seen:
            continue
        seen.add(target)
        score = n.get("score", 0.0)
        lines.append(f"- [[{target}]] (score {score:.2f})")
    lines.append(SEE_ALSO_CLOSE)
    return "\n".join(lines)
