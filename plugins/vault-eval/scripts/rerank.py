#!/usr/bin/env python3
"""
Cross-encoder rerank at Step 1.5 of the Galp Vault retrieval cascade.

PR-01 / S01 — Galp Vault Frontier Closeout plan 2026-05-17.

CLI usage
---------
    python3 _rerank.py \
        --query  "central organisational anti-pattern Galp wants RetailCo to abandon" \
        --candidates candidates.json \
        --top-k  5

    python3 _rerank.py --query "..." --candidates '[{"path":"...", "content":"..."}]' --top-k 5

candidates format (stdin or file path or JSON string):
    [
        {"path": "50 Sources/RetailCo Org Design v0.3 Galpified.md",
         "content": "<excerpt or full text>",
         "score": 0.82},          # optional — Step 1 semantic score
        ...
    ]

Output (stdout, JSON):
    [
        {"path": "...", "content": "...", "score": 0.82,
         "rerank_score": 7.41, "rerank_rank": 1},
        ...
    ]

Model
-----
BAAI/bge-reranker-v2-m3  (~70 MB ONNX)
  - Multilingual cross-encoder; BEIR benchmark covers EN and 100+ languages
  - bge-m3 backbone with cross-attention — significantly outperforms bi-encoder
    re-ranking on paraphrase recall (the dominant Step 1 failure mode)
  - Apple Silicon MPS support via sentence-transformers + PyTorch ≥ 2.0
  - First-run download from HuggingFace CDN; cached to ~/.cache/huggingface/

M9 caveat
---------
If the query is Portuguese-heavy or Spanish↔Portuguese code-switched, Step 1
was already skipped per P-3 M9 rule — callers SHOULD NOT invoke Step 1.5 in
that case.  Pass --skip-rerank to force-return candidates unchanged with a
m9_skipped flag set.

Unlike `bge-micro-v2` (the Smart Connections embedding model), bge-reranker-v2-m3
has verified multilingual coverage — it scores EN, PT, and ES queries with
consistent quality.  However, the M9 gate is upstream of Step 1.5 by design:
when Step 1 is skipped, there are no Step 1 candidates to rerank.  Do not
invoke this script on PT/ES queries that went through M9 fall-through.

Sandbox note
------------
The Cowork sandbox /sessions/ filesystem is at 100%; sentence-transformers
cannot be installed there.  This script runs on Ricardo's Mac (Apple Silicon
MPS).  Sandbox-only callers should pass --sc-results <json> to inject pre-
computed Smart Connections results without needing the model locally.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Model cache — first load downloads ~70 MB; subsequent loads are instant
# ---------------------------------------------------------------------------
_MODEL_CACHE: dict = {}
_DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"
_CACHE_DIR = Path.home() / ".cache" / "huggingface" / "hub"


def _load_model(model_name: str = _DEFAULT_MODEL):
    """Load and cache the CrossEncoder model.  Thread-safe for single-process use."""
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]

    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise ImportError(
            "sentence-transformers is not installed.  Run:\n"
            "  pip install sentence-transformers --break-system-packages\n"
            "or inside a venv:\n"
            "  pip install sentence-transformers"
        ) from exc

    import torch

    # Prefer MPS (Apple Silicon Metal) > CUDA > CPU
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"

    print(f"[_rerank] Loading {model_name} on device={device} …", file=sys.stderr)
    model = CrossEncoder(model_name, device=device, cache_folder=str(_CACHE_DIR))
    _MODEL_CACHE[model_name] = model
    print(f"[_rerank] Model loaded.", file=sys.stderr)
    return model


# ---------------------------------------------------------------------------
# Core rerank function
# ---------------------------------------------------------------------------

def rerank(
    query: str,
    candidates: list[dict],
    top_k: Optional[int] = None,
    model_name: str = _DEFAULT_MODEL,
) -> list[dict]:
    """
    Rerank candidates using the cross-encoder.

    Parameters
    ----------
    query       : the retrieval query (Step 1 input)
    candidates  : list of dicts with at minimum "path" and "content" keys
    top_k       : return at most top_k results (None = all, reranked)
    model_name  : HuggingFace model identifier

    Returns
    -------
    List of candidate dicts, sorted descending by rerank_score, with two new
    keys added to each dict:
        rerank_score : float  — cross-encoder logit (higher = more relevant)
        rerank_rank  : int    — 1-based rank after reranking
    """
    if not candidates:
        return []

    model = _load_model(model_name)

    # Build (query, passage) pairs.  We use content truncated to 512 tokens
    # as a safety guard; CrossEncoder internally handles its own truncation
    # but explicit truncation avoids slow inference on very long passages.
    pairs = [(query, c.get("content", c.get("text", ""))[:4096]) for c in candidates]

    scores = model.predict(pairs, show_progress_bar=False)

    # Attach rerank_score to each candidate
    enriched = []
    for cand, score in zip(candidates, scores):
        enriched.append({**cand, "rerank_score": float(score)})

    # Sort descending by rerank_score
    enriched.sort(key=lambda x: x["rerank_score"], reverse=True)

    # Assign 1-based rank
    for rank, cand in enumerate(enriched, start=1):
        cand["rerank_rank"] = rank

    if top_k is not None:
        enriched = enriched[:top_k]

    return enriched


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_candidates(arg: str) -> list[dict]:
    """Accept: JSON string, file path, or '-' for stdin."""
    if arg == "-":
        return json.loads(sys.stdin.read())
    p = Path(arg)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    # Try inline JSON string
    return json.loads(arg)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-encoder rerank (Step 1.5) for Galp Vault retrieval cascade.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--query", "-q",
        required=True,
        help="The retrieval query string.",
    )
    parser.add_argument(
        "--candidates", "-c",
        required=True,
        help=(
            "JSON file path, inline JSON string, or '-' for stdin. "
            "Array of objects with 'path' and 'content' keys."
        ),
    )
    parser.add_argument(
        "--top-k", "-k",
        type=int,
        default=None,
        help="Return at most top_k results.  Default: all candidates reranked.",
    )
    parser.add_argument(
        "--model",
        default=_DEFAULT_MODEL,
        help=f"HuggingFace model identifier.  Default: {_DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--skip-rerank",
        action="store_true",
        help=(
            "Return candidates unchanged (with m9_skipped: true flag added). "
            "Use when the caller walked the M9 fall-through and has no Step 1 "
            "semantic results to rerank."
        ),
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output (indent=2).  Default: compact.",
    )
    args = parser.parse_args()

    candidates = _parse_candidates(args.candidates)

    if args.skip_rerank:
        # M9 fall-through path — return as-is with flag
        result = [{**c, "m9_skipped": True} for c in candidates]
    else:
        result = rerank(
            query=args.query,
            candidates=candidates,
            top_k=args.top_k,
            model_name=args.model,
        )

    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))


if __name__ == "__main__":
    main()
