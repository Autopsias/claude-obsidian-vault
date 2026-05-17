#!/usr/bin/env python3
"""
audit_contradictions.py — kb-curator Karpathy Lint Mode 1.

Surfaces pairs of typed notes that look like they're saying contradictory
things about the same subject. Proposal-only output; never edits source
notes. Full design in:
  .claude/skills/kb-curator/references/lint-contradictions.md

Pipeline (4 steps):
  1. Load file-level embeddings for type:source + type:decision notes
     from Smart Connections .ajson files. Respect P-4 bitemporal:
     skip is_latest_version: false.
  2. Cosine-similarity top-K of all pairs above threshold (default 0.85),
     capped at --top-k pairs and --per-doc-cap fan-out per document.
  3. (Optional) Adjudicate each candidate pair with claude-haiku-4-5 via
     the Anthropic SDK. Flag pairs with contradiction:true AND
     confidence ≥ 0.7.
  4. Emit proposal markdown to 99 Workspace/_lint_contradictions_<DATE>.md.

If anthropic SDK is missing or ANTHROPIC_API_KEY unset, Step 3 is skipped
and candidates emit as `adjudication: PENDING` with the full Haiku prompt
rendered into the proposal for downstream interactive adjudication.

Usage
-----
  python3 audit_contradictions.py --root /path/to/vault
  python3 audit_contradictions.py --root /path/to/vault --top-k 50 --threshold 0.88
  python3 audit_contradictions.py --root /path/to/vault --dry-run   # no proposal file written

Exit
----
  0  success (proposal written, or zero candidates)
  1  pipeline error (embedding load failure, etc.)
  2  configuration error (vault not found, .smart-env missing)
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

try:
    import numpy as np
except ImportError:
    print("ERROR: numpy is required. pip install numpy --break-system-packages", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLD     = 0.85
DEFAULT_TOP_K         = 200
DEFAULT_PER_DOC_CAP   = 5
DEFAULT_HAIKU_CONF    = 0.7
DEFAULT_TRUNCATE_CHARS = 8000
DEFAULT_HAIKU_MODEL   = "claude-haiku-4-5-20251001"
EXPECTED_EMBED_MODEL  = "TaylorAI/bge-micro-v2"
EXPECTED_EMBED_DIM    = 384

TYPED_ZONE_ROOTS = (
    "10 People", "20 Companies", "30 Projects",
    "40 Meetings", "50 Sources", "60 Concepts", "70 Decisions",
)
INCLUDE_TYPES = frozenset({"source", "decision"})

SKIP_DIRS = frozenset({
    ".git", ".obsidian", ".smart-env", ".claude",
    "_archive", "_archives", "_skill_packages", "_skill_resources",
    "_log_archive", "_session_handoff_archive",
    "node_modules", "__pycache__",
})

FRONTMATTER_RE   = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
SIMPLE_FIELD_RE  = re.compile(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*?)\s*$")

SYSTEM_PROMPT = (
    "You are an expert knowledge-base auditor. You compare two notes from a\n"
    "knowledge vault and decide whether they make CONTRADICTORY factual claims\n"
    "about the same subject. A contradiction means one note asserts X while\n"
    "the other asserts not-X about the SAME entity, decision, fact, or\n"
    "commitment. Two notes covering different aspects of the same topic, or\n"
    "evolving over time within bitemporal versioning, are NOT contradictions.\n"
    "Return ONLY a JSON object — no preamble, no markdown fences. Schema:\n"
    "{\"contradiction\": boolean, \"confidence\": number between 0 and 1, "
    "\"evidence\": string or null}\n"
    "- contradiction: true only if both notes are currently authoritative and disagree.\n"
    "- confidence: your calibrated certainty in the contradiction call.\n"
    "- evidence: a single short quote pair (max 240 chars total) anchoring the\n"
    "  contradiction, or null."
)


# ---------------------------------------------------------------------------
# Frontmatter parsing (lifted-pattern from audit_bitemporal.py)
# ---------------------------------------------------------------------------

def parse_frontmatter(text):
    """Return dict of top-level scalar fields or None if no frontmatter."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    body = m.group(1)
    out = {}
    for line in body.splitlines():
        if not line or line.startswith("#"):
            continue
        if line.startswith((" ", "\t", "-")):
            continue
        fm = SIMPLE_FIELD_RE.match(line)
        if not fm:
            continue
        key, val = fm.group(1), fm.group(2)
        if val.startswith(('"', "'")) and val.endswith(('"', "'")) and len(val) >= 2:
            val = val[1:-1]
        out[key] = val
    return out


# ---------------------------------------------------------------------------
# Step 1 — load embeddings + filter typed pool
# ---------------------------------------------------------------------------

EMBED_LINE_RE = re.compile(
    r'"smart_sources:(?P<path>[^"]+)":\s*\{(?P<body>.*)\},?\s*$'
)
VEC_RE = re.compile(
    r'"embeddings":\s*\{\s*"' + re.escape(EXPECTED_EMBED_MODEL) + r'":\s*\{\s*"vec":\s*\[(?P<vec>[^\]]+)\]'
)


def load_smart_sources(smart_env_dir):
    """Walk .smart-env/multi/*.ajson; return dict path -> np.ndarray."""
    embeddings = {}
    if not smart_env_dir.exists():
        return embeddings
    files = sorted(p for p in smart_env_dir.glob("*.ajson"))
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if not line.startswith('"smart_sources:'):
                        continue
                    m_path = EMBED_LINE_RE.match(line)
                    if not m_path:
                        continue
                    path = m_path.group("path")
                    body = m_path.group("body")
                    m_vec = VEC_RE.search(body)
                    if not m_vec:
                        continue
                    vec_str = m_vec.group("vec")
                    try:
                        vec = np.fromstring(vec_str, sep=",", dtype=np.float32)
                    except Exception:
                        continue
                    if vec.size != EXPECTED_EMBED_DIM:
                        continue
                    # Defensive re-normalize (Smart Connections emits L2-normed
                    # vectors but verify).
                    norm = float(np.linalg.norm(vec))
                    if norm == 0.0:
                        continue
                    vec = vec / norm
                    embeddings[path] = vec
        except Exception as e:
            print(f"WARN: failed to read {fp.name}: {e}", file=sys.stderr)
            continue
    return embeddings


def collect_typed_pool(vault_root):
    """Return list of dicts {path, type, document_date, is_latest_version, text}."""
    pool = []
    for zone in TYPED_ZONE_ROOTS:
        zone_root = vault_root / zone
        if not zone_root.exists():
            continue
        for fp in zone_root.rglob("*.md"):
            # skip if any path component is in SKIP_DIRS
            if any(part in SKIP_DIRS for part in fp.relative_to(vault_root).parts):
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            fm = parse_frontmatter(text)
            if not fm:
                continue
            ftype = (fm.get("type") or "").strip().strip('"').strip("'")
            if ftype not in INCLUDE_TYPES:
                continue
            ilv = (fm.get("is_latest_version") or "").strip().lower()
            # If field is set explicitly to false, skip (bitemporal-superseded).
            if ilv in ("false", "no", "0"):
                continue
            doc_date = (fm.get("document_date") or "").strip().strip('"').strip("'")
            rel = str(fp.relative_to(vault_root))
            pool.append({
                "path":     rel,
                "type":     ftype,
                "document_date": doc_date,
                "is_latest_version": ilv,
                "text":     text,
                "size":     len(text),
            })
    return pool


# ---------------------------------------------------------------------------
# Step 2 — similarity + top-K + per-doc cap
# ---------------------------------------------------------------------------

def compute_candidates(pool, embeddings, threshold, top_k, per_doc_cap):
    """Return list of dicts {i, j, sim, path_i, path_j} sorted by sim desc."""
    paths_with_embed = [(idx, item) for idx, item in enumerate(pool)
                        if item["path"] in embeddings]
    missing = len(pool) - len(paths_with_embed)
    if not paths_with_embed:
        return [], missing, 0
    # Build matrix
    indices = [p[0] for p in paths_with_embed]
    M = np.stack([embeddings[pool[i]["path"]] for i in indices])  # (N, 384)
    # Cosine similarity = M @ M.T because vectors are L2-normed
    S = M @ M.T  # (N, N) float32
    N = S.shape[0]
    # Take upper triangle (i < j), where S[i,j] >= threshold
    candidates = []
    iu, ju = np.triu_indices(N, k=1)
    sims = S[iu, ju]
    mask = sims >= threshold
    above_threshold = int(mask.sum())
    iu, ju, sims = iu[mask], ju[mask], sims[mask]
    # Order by descending similarity
    order = np.argsort(-sims)
    for k in order:
        i_local = int(iu[k]); j_local = int(ju[k]); s = float(sims[k])
        i_pool = indices[i_local]; j_pool = indices[j_local]
        candidates.append({
            "i":      i_pool,
            "j":      j_pool,
            "sim":    s,
            "path_i": pool[i_pool]["path"],
            "path_j": pool[j_pool]["path"],
        })
    # Per-doc cap: keep only top per_doc_cap appearances per path
    fan_count = {}
    kept = []
    for c in candidates:
        if fan_count.get(c["path_i"], 0) >= per_doc_cap or \
           fan_count.get(c["path_j"], 0) >= per_doc_cap:
            continue
        fan_count[c["path_i"]] = fan_count.get(c["path_i"], 0) + 1
        fan_count[c["path_j"]] = fan_count.get(c["path_j"], 0) + 1
        kept.append(c)
        if len(kept) >= top_k:
            break
    return kept, missing, above_threshold


# ---------------------------------------------------------------------------
# Step 3 — Haiku adjudication (optional)
# ---------------------------------------------------------------------------

def render_user_prompt(item_a, item_b, truncate_chars):
    def _trim(t):
        # strip frontmatter for prompt brevity
        m = FRONTMATTER_RE.match(t)
        body = t[m.end():] if m else t
        body = body.lstrip("\n")
        return body[:truncate_chars]
    return (
        f"# Note A\n"
        f"Path: {item_a['path']}\n"
        f"Type: {item_a['type']}\n"
        f"Last updated: {item_a['document_date'] or '(no document_date)'}\n\n"
        f"{_trim(item_a['text'])}\n\n"
        f"# Note B\n"
        f"Path: {item_b['path']}\n"
        f"Type: {item_b['type']}\n"
        f"Last updated: {item_b['document_date'] or '(no document_date)'}\n\n"
        f"{_trim(item_b['text'])}\n\n"
        f"Are these contradictory? Respond with the JSON object only."
    )


def adjudicate_with_haiku(client, model, system_prompt, user_prompt,
                          conf_threshold, max_retries=3):
    """Return (verdict_dict_or_None, raw_text). Backoff on rate-limit."""
    delay = 1.0
    for attempt in range(max_retries):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=200,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = "".join(b.text for b in resp.content if getattr(b, "text", None))
            # Strip whitespace, common fence patterns
            stripped = raw.strip()
            if stripped.startswith("```"):
                stripped = re.sub(r"^```[a-zA-Z]*\n", "", stripped)
                stripped = re.sub(r"\n```$", "", stripped)
            try:
                verdict = json.loads(stripped)
            except Exception:
                return None, raw
            # Schema validation
            if not isinstance(verdict, dict):
                return None, raw
            for k in ("contradiction", "confidence", "evidence"):
                if k not in verdict:
                    return None, raw
            return verdict, raw
        except Exception as e:
            # crude rate-limit / transient detection
            msg = str(e).lower()
            if any(s in msg for s in ("rate", "429", "timeout", "overload")):
                time.sleep(delay)
                delay *= 2.0
                continue
            return None, f"EXCEPTION: {e!r}"
    return None, "exhausted retries"


# ---------------------------------------------------------------------------
# Step 4 — proposal output
# ---------------------------------------------------------------------------

def render_proposal(vault_root, candidates_full, summary, out_path):
    """Write proposal markdown to out_path."""
    today = date.today().isoformat()
    flagged = [c for c in candidates_full if c.get("flagged")]
    pending = [c for c in candidates_full if c.get("status") == "PENDING"]
    errors  = [c for c in candidates_full if c.get("status") == "ERROR"]
    below   = summary["above_threshold"] - len(candidates_full)
    adjudicated = "yes" if summary["haiku_used"] else "pending"

    lines = []
    lines.append("---")
    lines.append("type: audit")
    lines.append("provenance: kb-curator lint-contradictions (KP-02 — Karpathy Lint Mode 1)")
    lines.append(f"generated: {today}")
    lines.append(f"candidates_total: {len(candidates_full)}")
    lines.append(f"flagged_contradictions: {len(flagged)}")
    lines.append(f"adjudicated: {adjudicated}")
    lines.append(f"similarity_threshold: {summary['threshold']}")
    lines.append(f"top_k_cap: {summary['top_k']}")
    lines.append(f"per_doc_cap: {summary['per_doc_cap']}")
    lines.append(f"haiku_model: {summary['haiku_model']}")
    lines.append(f"embedding_model: {EXPECTED_EMBED_MODEL}")
    lines.append(f"runtime_seconds: {summary['runtime_s']:.2f}")
    lines.append(f"pool_size: {summary['pool_size']}")
    lines.append(f"pool_with_embeddings: {summary['pool_with_embeddings']}")
    lines.append("---\n")

    lines.append("# kb-curator — Contradiction Lint Proposal\n")
    lines.append(f"**Generated:** {today}  ")
    lines.append(f"**Pool:** {summary['pool_size']} typed notes "
                 f"({summary['pool_with_embeddings']} with embeddings)  ")
    lines.append(f"**Pairs above threshold ({summary['threshold']}):** "
                 f"{summary['above_threshold']}  ")
    lines.append(f"**Candidates after caps (top-K {summary['top_k']}, "
                 f"per-doc {summary['per_doc_cap']}):** {len(candidates_full)}  ")
    lines.append(f"**Adjudication:** {adjudicated}  ")
    if summary["haiku_used"]:
        lines.append(f"**Flagged contradictions (conf ≥ {summary['haiku_conf']}):** "
                     f"{len(flagged)}  ")
    lines.append(f"**Runtime:** {summary['runtime_s']:.2f}s  \n")

    # 1. Flagged contradictions
    if summary["haiku_used"]:
        lines.append("## Flagged contradictions\n")
        if not flagged:
            lines.append("_No pairs cleared the Haiku confidence threshold._\n")
        else:
            for idx, c in enumerate(flagged, 1):
                v = c["verdict"]
                lines.append(f"### #{idx} — sim {c['sim']:.3f}, conf {v['confidence']:.2f}")
                lines.append(f"- **A:** `{c['path_i']}`")
                lines.append(f"- **B:** `{c['path_j']}`")
                ev = v.get("evidence") or "(no quote pair)"
                lines.append(f"- **Evidence:** {ev}")
                lines.append("- **Suggested action:** Ricardo to reconcile — "
                             "supersede one, mark both as bitemporal versions, "
                             "or edit one to remove the conflict.\n")

    # 2. Pending adjudication
    if pending:
        lines.append("## Pending adjudication\n")
        lines.append("_Anthropic SDK / API key not available in run env. "
                     "The prompts below can be pasted into a Claude session to "
                     "produce JSON verdicts._\n")
        for idx, c in enumerate(pending, 1):
            lines.append(f"### Pending #{idx} — sim {c['sim']:.3f}")
            lines.append(f"- **A:** `{c['path_i']}`")
            lines.append(f"- **B:** `{c['path_j']}`")
            lines.append("\n<details><summary>Haiku prompt for this pair</summary>\n")
            lines.append("**System prompt:**")
            lines.append("```")
            lines.append(SYSTEM_PROMPT)
            lines.append("```")
            lines.append("**User prompt:**")
            lines.append("```")
            lines.append(c["user_prompt"])
            lines.append("```")
            lines.append("</details>\n")

    # 3. Errors
    if errors:
        lines.append("## Adjudication errors\n")
        for idx, c in enumerate(errors, 1):
            lines.append(f"### Error #{idx} — sim {c['sim']:.3f}")
            lines.append(f"- **A:** `{c['path_i']}`")
            lines.append(f"- **B:** `{c['path_j']}`")
            lines.append("- **Raw response:**")
            lines.append("```")
            lines.append(c.get("raw_response", "(no response)"))
            lines.append("```\n")

    # 4. Below-threshold telemetry
    lines.append("## Below threshold / dropped\n")
    lines.append(f"- Pairs above similarity threshold but dropped by "
                 f"top-K / per-doc cap: **{max(below, 0)}**\n")

    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="kb-curator Karpathy Lint Mode 1 — contradiction detection."
    )
    parser.add_argument("--root", metavar="PATH", default=None,
                        help="Vault root (auto-detect from cwd via CLAUDE.md).")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help="Cosine similarity threshold (default 0.85).")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K,
                        help="Max candidate pairs to keep (default 200).")
    parser.add_argument("--per-doc-cap", type=int, default=DEFAULT_PER_DOC_CAP,
                        help="Max candidate pairs per document (default 5).")
    parser.add_argument("--haiku-conf", type=float, default=DEFAULT_HAIKU_CONF,
                        help="Confidence floor for flagging (default 0.7).")
    parser.add_argument("--truncate-chars", type=int, default=DEFAULT_TRUNCATE_CHARS,
                        help="Per-note content truncation in prompts (default 8000).")
    parser.add_argument("--haiku-model", default=DEFAULT_HAIKU_MODEL,
                        help="Anthropic model id (default claude-haiku-4-5-20251001).")
    parser.add_argument("--no-haiku", action="store_true",
                        help="Skip Haiku adjudication even if SDK available.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary; do not write proposal file.")
    parser.add_argument("--out", default=None,
                        help="Override proposal output path.")
    args = parser.parse_args()

    # Resolve root
    root = args.root or os.environ.get("COWORK_ROOT")
    if root is None:
        current = Path.cwd().resolve()
        while True:
            if (current / "CLAUDE.md").exists():
                root = str(current); break
            if current.parent == current: break
            current = current.parent
    if root is None:
        print("ERROR: vault root not found. Pass --root.", file=sys.stderr)
        sys.exit(2)
    vault_root = Path(root).resolve()
    if not vault_root.exists():
        print(f"ERROR: vault root does not exist: {vault_root}", file=sys.stderr)
        sys.exit(2)

    smart_env = vault_root / ".smart-env" / "multi"
    if not smart_env.exists():
        print(f"ERROR: .smart-env/multi/ not found at {smart_env}. See "
              f".claude/rules/plugin-security-discipline.md", file=sys.stderr)
        sys.exit(2)

    t0 = time.time()
    print(f"[1/4] loading embeddings from {smart_env}...")
    embeddings = load_smart_sources(smart_env)
    print(f"      loaded {len(embeddings)} smart_sources embeddings")
    t1 = time.time()
    print(f"[1/4] collecting typed pool from {vault_root}...")
    pool = collect_typed_pool(vault_root)
    print(f"      {len(pool)} typed-zone notes (type:source + type:decision, "
          f"is_latest_version != false)")
    t2 = time.time()

    print(f"[2/4] computing similarity (threshold={args.threshold}, "
          f"top-K={args.top_k}, per-doc-cap={args.per_doc_cap})...")
    candidates, missing_embed, above_threshold = compute_candidates(
        pool, embeddings, args.threshold, args.top_k, args.per_doc_cap
    )
    print(f"      {len(candidates)} candidate pairs after caps "
          f"({above_threshold} pairs above raw threshold; "
          f"{missing_embed} pool notes have no embedding yet)")
    t3 = time.time()

    # Build candidates_full with text + prompts
    candidates_full = []
    for c in candidates:
        item_a = pool[c["i"]]; item_b = pool[c["j"]]
        user_prompt = render_user_prompt(item_a, item_b, args.truncate_chars)
        candidates_full.append({
            **c,
            "user_prompt": user_prompt,
            "status":      "PENDING",
            "flagged":     False,
            "verdict":     None,
            "raw_response": None,
        })

    # Step 3 — Haiku adjudication
    haiku_used = False
    if args.no_haiku:
        print("[3/4] Haiku step skipped (--no-haiku).")
    else:
        try:
            import anthropic
        except ImportError:
            anthropic = None
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if anthropic is None or not api_key:
            print(f"[3/4] Haiku step skipped: SDK present={anthropic is not None}, "
                  f"API key present={bool(api_key)}. Candidates remain PENDING.")
        else:
            print(f"[3/4] adjudicating {len(candidates_full)} pairs with "
                  f"{args.haiku_model}...")
            client = anthropic.Anthropic(api_key=api_key)
            for idx, c in enumerate(candidates_full, 1):
                verdict, raw = adjudicate_with_haiku(
                    client, args.haiku_model, SYSTEM_PROMPT, c["user_prompt"],
                    args.haiku_conf,
                )
                if verdict is None:
                    c["status"] = "ERROR"
                    c["raw_response"] = raw
                    continue
                c["verdict"] = verdict
                conf = verdict.get("confidence")
                try:
                    conf = float(conf)
                except Exception:
                    conf = 0.0
                if verdict.get("contradiction") is True and conf >= args.haiku_conf:
                    c["flagged"] = True
                    c["status"]  = "FLAGGED"
                else:
                    c["status"]  = "NOT_CONTRADICTION"
                if idx % 10 == 0:
                    print(f"      adjudicated {idx}/{len(candidates_full)}")
            haiku_used = True
    t4 = time.time()

    # Step 4 — render proposal
    if args.out:
        out_path = Path(args.out)
    else:
        out_path = vault_root / "99 Workspace" / f"_lint_contradictions_{date.today().isoformat()}.md"

    summary = {
        "threshold":           args.threshold,
        "top_k":               args.top_k,
        "per_doc_cap":         args.per_doc_cap,
        "haiku_model":         args.haiku_model if haiku_used else "(skipped)",
        "haiku_used":          haiku_used,
        "haiku_conf":          args.haiku_conf,
        "pool_size":           len(pool),
        "pool_with_embeddings": len(pool) - missing_embed,
        "above_threshold":     above_threshold,
        "runtime_s":           t4 - t0,
        "load_embed_s":        t1 - t0,
        "load_pool_s":         t2 - t1,
        "sim_s":               t3 - t2,
        "adjud_s":             t4 - t3,
    }

    flagged_count = sum(1 for c in candidates_full if c.get("flagged"))
    pending_count = sum(1 for c in candidates_full if c.get("status") == "PENDING")
    error_count   = sum(1 for c in candidates_full if c.get("status") == "ERROR")

    print()
    print("=" * 60)
    print(f"lint-contradictions summary")
    print(f"  pool:                  {summary['pool_size']} typed notes")
    print(f"  with embeddings:       {summary['pool_with_embeddings']}")
    print(f"  above threshold:       {summary['above_threshold']}")
    print(f"  candidates (post-cap): {len(candidates_full)}")
    print(f"  flagged:               {flagged_count}")
    print(f"  pending adjudication:  {pending_count}")
    print(f"  errors:                {error_count}")
    print(f"  runtime total:         {summary['runtime_s']:.2f}s")
    print(f"    embed load:            {summary['load_embed_s']:.2f}s")
    print(f"    pool collect:          {summary['load_pool_s']:.2f}s")
    print(f"    similarity:            {summary['sim_s']:.2f}s")
    print(f"    adjudication:          {summary['adjud_s']:.2f}s")
    print("=" * 60)

    if args.dry_run:
        print(f"DRY RUN — proposal NOT written. Would have written to {out_path}")
        return

    render_proposal(vault_root, candidates_full, summary, out_path)
    print(f"proposal written: {out_path}")


if __name__ == "__main__":
    main()
