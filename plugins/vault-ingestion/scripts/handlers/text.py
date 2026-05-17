"""
handlers/text.py — .md and .txt ingestion handlers.

Contract: 90 System/_ingestion_contract.md
  §5  — namespacing rule + user-fields-always-win collision policy
  §9  — auto-write scope; quarantine path

HT-01 deliverable (S02):
  - .md handler: EARLY EXIT on provenance:ingestion-pipeline → quarantine
  - .md handler: frontmatter merge, user fields always win
  - .txt handler: frontmatter prepend, body byte-identical

Both handlers are idempotent and stateless; all I/O decisions are made
by the caller (pipeline orchestrator). Handlers return a HandlerResult
namedtuple — they do NOT write files themselves.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import textwrap
from dataclasses import dataclass, field
from datetime import timezone, datetime
from pathlib import Path
from typing import Optional

import frontmatter  # python-frontmatter

# ──────────────────────────────────────────────────────────────────────────────
# Content-hash helpers (contract §5 text_sha256 — CH-01)
# ──────────────────────────────────────────────────────────────────────────────

def text_normalize(text: str) -> str:
    """Normalise extracted text for content-hash dedup (contract §5 text_sha256).

    Steps (applied in order):
    1. Normalise line endings to ``\\n`` (replace ``\\r\\n`` and bare ``\\r``).
    2. Strip per-line trailing whitespace.
    3. Collapse runs of non-newline whitespace (spaces, tabs) inside each line
       to a single space.
    4. Lowercase the entire string.
    5. Strip leading/trailing whitespace from the whole string.

    The result is deterministic across platform, editor, and minor re-export
    differences — two files with the same prose but different encodings of
    whitespace or casing will produce the same normalised string and therefore
    the same ``text_sha256``.

    Returns
    -------
    str
        Normalised text. Empty string if input is empty.
    """
    if not text:
        return ""
    # 1. Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 2+3. Per-line: strip trailing whitespace; collapse inner whitespace runs
    lines = []
    for line in text.split("\n"):
        line = line.rstrip()
        line = re.sub(r"[ \t]+", " ", line)
        lines.append(line)
    text = "\n".join(lines)
    # 4. Lowercase
    text = text.lower()
    # 5. Strip whole string
    return text.strip()


def compute_text_sha256(text: str) -> str:
    """SHA-256 of the normalised text (contract §5 ``pipeline.text_sha256``).

    Parameters
    ----------
    text : str
        Raw extracted body text (before normalisation).

    Returns
    -------
    str
        64-char lowercase hex digest. SHA-256 of ``text_normalize(text)``
        encoded as UTF-8. Empty-string input yields the SHA-256 of b"".
    """
    normalised = text_normalize(text)
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# Return type
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class HandlerResult:
    """Outcome of a handler call.

    Attributes
    ----------
    success : bool
        True if extraction completed; False if quarantined or failed.
    quarantine : bool
        True → caller must move the source file to _inbox_quarantine/.
    quarantine_reason : str | None
        Short machine-readable reason string (e.g. "already_ingested").
    body : str | None
        Extracted markdown body (None when quarantined or failed).
    frontmatter_top : dict
        Top-level frontmatter fields (legacy §1–§4 + §6.2 bitemporal).
        User values in the source file are preserved as-is.
    pipeline_namespace : dict
        Everything that goes under pipeline: in the output .md.
        Caller merges this into the output frontmatter.
    warnings : list[str]
        Non-fatal issues; forwarded into pipeline.warnings.
    """

    success: bool
    quarantine: bool = False
    quarantine_reason: Optional[str] = None
    body: Optional[str] = None
    frontmatter_top: dict = field(default_factory=dict)
    pipeline_namespace: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

# Fields that are user-visible top-level (§1 + §3 + §6.2 of contract).
# Pipeline never overwrites a non-null user value in this set.
_USER_TOP_LEVEL_FIELDS = frozenset({
    # §1 baseline
    "title", "source_file", "original_path", "file_type",
    "extracted_at", "page_count",
    # §2 type enum
    "type",
    # §3 optional auxiliaries
    "document_type", "date", "slide_count", "participants",
    "meeting_date", "domain", "key_data",
    # §6.2 bitemporal pair (top-level, queried by Bases)
    "document_date", "is_latest_version",
    # common user fields
    "tags",
})

_PROVENANCE_VALUE = "ingestion-pipeline"


def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _merge_frontmatter(
    user_fm: dict,
    pipeline_computed: dict,
    pipeline_ns: dict,
    *,
    warnings: list[str],
) -> tuple[dict, dict]:
    """Merge user frontmatter with pipeline-computed fields.

    Rules (contract §5):
    1. User values at top-level are NEVER overwritten.
    2. Pipeline-computed values that collide with a non-null user top-level
       field are suppressed (dropped silently — they are recomputable).
    3. `tags` collision: user top-level tags preserved; pipeline tags go
       into pipeline_ns["tags"].
    4. The pipeline: namespace is always written fresh. Any user edit inside
       pipeline: is overwritten with a warning.
    5. Keys in user_fm that are not in _USER_TOP_LEVEL_FIELDS are preserved
       as-is (pass-through).

    Returns
    -------
    top : dict
        Merged top-level frontmatter (user wins everywhere).
    ns : dict
        pipeline: namespace dict (always fresh, from pipeline_ns arg).
    """
    top: dict = {}

    # 1. Start with pipeline-computed top-level values
    for k, v in pipeline_computed.items():
        if k in _USER_TOP_LEVEL_FIELDS:
            top[k] = v

    # 2. User values win — overwrite anything pipeline computed
    for k, v in user_fm.items():
        if k == "pipeline":
            # User edited inside pipeline: → warn, do not preserve
            warnings.append("user_edit_in_pipeline_ns")
            continue
        if k in _USER_TOP_LEVEL_FIELDS:
            if v is not None:
                top[k] = v  # user wins
        else:
            # Pass-through non-standard user fields unchanged
            top[k] = v

    # 3. tags special-case: if user has top-level tags, keep them;
    #    pipeline's fresh tags go into pipeline_ns
    if "tags" in user_fm and user_fm["tags"] is not None:
        top["tags"] = user_fm["tags"]
        pipeline_ns["tags"] = pipeline_ns.get("tags", [])
    # if user has no tags, pipeline may write them at top-level (legacy compat)

    return top, pipeline_ns


# ──────────────────────────────────────────────────────────────────────────────
# .md handler
# ──────────────────────────────────────────────────────────────────────────────

def handle_md(
    source_path: Path,
    *,
    pipeline_computed: dict,
    pipeline_ns: dict,
) -> HandlerResult:
    """Ingest a .md file.

    Parameters
    ----------
    source_path : Path
        Path to the .md file in _drop/ (or staging).
    pipeline_computed : dict
        Top-level fields the pipeline computed for this run (title, type,
        extracted_at, file_type, …). User values win on collision.
    pipeline_ns : dict
        The pipeline: namespace dict the pipeline assembled (run_id, sha256,
        extractor, …). Always written fresh; any user edits overwritten.

    Returns
    -------
    HandlerResult
    """
    warnings: list[str] = []

    # ── Read + parse ───────────────────────────────────────────────────────
    raw = source_path.read_text(encoding="utf-8", errors="replace")
    try:
        post = frontmatter.loads(raw)
    except Exception as exc:
        return HandlerResult(
            success=False,
            quarantine=True,
            quarantine_reason="frontmatter_parse_error",
            warnings=[f"frontmatter_parse_error: {exc}"],
        )

    user_fm: dict = dict(post.metadata)
    body: str = post.content

    # ── HT-01 EARLY EXIT: re-ingest guard ────────────────────────────────
    # Contract §5 rule 4: if provenance: ingestion-pipeline is already
    # present, refuse with 'already_ingested' → quarantine.
    existing_provenance = user_fm.get("provenance") or (
        user_fm.get("pipeline", {}) or {}
    ).get("provenance")
    if existing_provenance == _PROVENANCE_VALUE:
        return HandlerResult(
            success=False,
            quarantine=True,
            quarantine_reason="already_ingested",
            warnings=["already_ingested: file carries provenance:ingestion-pipeline"],
        )

    # ── Merge frontmatter ─────────────────────────────────────────────────
    top, ns = _merge_frontmatter(
        user_fm,
        pipeline_computed,
        pipeline_ns,
        warnings=warnings,
    )

    # ── Stamp provenance + content hash in pipeline namespace ────────────────
    ns["provenance"] = _PROVENANCE_VALUE
    ns["text_sha256"] = compute_text_sha256(body or "")   # CH-02
    ns["warnings"] = warnings

    return HandlerResult(
        success=True,
        body=body,
        frontmatter_top=top,
        pipeline_namespace=ns,
        warnings=warnings,
    )


# ──────────────────────────────────────────────────────────────────────────────
# .txt handler
# ──────────────────────────────────────────────────────────────────────────────

def handle_txt(
    source_path: Path,
    *,
    pipeline_computed: dict,
    pipeline_ns: dict,
) -> HandlerResult:
    """Ingest a plain-text .txt file.

    Contract §2: type = 'text-note'
    Body: unchanged (byte-identical to original, re-encoded as UTF-8 if needed).
    Frontmatter: pipeline_computed merged at top-level (user has no pre-existing
    frontmatter for a raw .txt drop, so no collision can occur).

    Parameters
    ----------
    source_path : Path
        Path to the .txt file.
    pipeline_computed : dict
        Top-level fields the pipeline computed.
    pipeline_ns : dict
        The pipeline: namespace dict.
    """
    warnings: list[str] = []

    # .txt files have no frontmatter — read body verbatim
    body = source_path.read_text(encoding="utf-8", errors="replace")

    # Top-level frontmatter = pipeline-computed values (no user fm to merge)
    top: dict = {k: v for k, v in pipeline_computed.items()}

    # Ensure type is correct for .txt
    top.setdefault("type", "text-note")
    top.setdefault("file_type", "txt")

    pipeline_ns["provenance"] = _PROVENANCE_VALUE
    pipeline_ns["text_sha256"] = compute_text_sha256(body)   # CH-02
    pipeline_ns["warnings"] = warnings

    return HandlerResult(
        success=True,
        body=body,
        frontmatter_top=top,
        pipeline_namespace=pipeline_ns,
        warnings=warnings,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Output serialiser (used by tests and orchestrator)
# ──────────────────────────────────────────────────────────────────────────────

def build_output_md(result: HandlerResult, source_file: str) -> str:
    """Render a HandlerResult into a complete ingested .md string.

    Layout (contract §4):
        ---
        <top-level frontmatter>
        pipeline:
          <pipeline namespace>
        ---
        **Open original:** [[<source_file>]]

        <body>
    """
    if not result.success:
        raise ValueError("Cannot build output from a failed HandlerResult")

    fm: dict = dict(result.frontmatter_top)
    fm["pipeline"] = result.pipeline_namespace

    post = frontmatter.Post(result.body or "", **fm)
    raw = frontmatter.dumps(post)

    # Inject "Open original" link after the closing ---
    # python-frontmatter dumps as "---\n...\n---\n<body>"
    # We insert the link line right after the closing delimiter.
    parts = raw.split("---\n", 2)
    if len(parts) == 3:
        link_line = f"**Open original:** [[{source_file}]]\n\n"
        raw = "---\n" + parts[1] + "---\n" + link_line + parts[2]

    return raw
