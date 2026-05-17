#!/usr/bin/env python3
"""
ingest.py — Galp Vault v2 ingestion pipeline orchestrator.

Part of:   90 System/_ingestion_pipeline/
Plan:      99 Workspace/_plan_ingestion_pipeline_v2_2026-05-13.html  (S04)
Contract:  90 System/_ingestion_contract.md
Discipline:.claude/rules/ingestion-pipeline-discipline.md

CLI:
  ingest.py [--root ROOT] [--dry-run] [--report-only] [--verbose]
            [--allow-cloud-ocr] [--max-api-calls N]
            [--recover RUN_ID] [--rollback RUN_ID]

See README.md in this directory for install, run modes, and troubleshooting.

Lifecycle (normal run):
  1. Assign run_id (UUID4 first 8 hex chars for display; full UUID in manifest)
  2. Acquire _drop/.lock via O_CREAT|O_EXCL; stale >30 min auto-takeover
  3. Scan _drop/ sorted by mtime ascending (oldest first)
  4. Per file: size guard → SHA-256 → dedup → extension check → supersession query
  5. Write INTENT entry to manifest BEFORE extraction (crash-safety anchor)
  6. Copy binary to staging/<run_id>/ ; dispatch to handler
  7. Write extracted .md to staging/<run_id>/
  8. COMMIT: move original → _originals/; move .md → 00 Inbox/; write COMMITTED_ marker
  9. Post-run: daily note, _auto_writes.md, _ingestion_log.md; tidy quarantine dirs
 10. Release lock (unlink _drop/.lock) in finally block

Authored: 2026-05-13 (S04 of v2 ingestion plan)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Ensure the handlers package is importable when this script is run directly.
# This script lives at: <vault>/90 System/_ingestion_pipeline/ingest.py
# Handlers live at:     <vault>/90 System/_ingestion_pipeline/handlers/
# ---------------------------------------------------------------------------
_PIPELINE_DIR = Path(__file__).resolve().parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))


# ===========================================================================
# Constants
# ===========================================================================

PIPELINE_SUBDIR    = "90 System/_ingestion_pipeline"
STAGING_SUBDIR     = PIPELINE_SUBDIR + "/_staging"
MANIFEST_REL       = PIPELINE_SUBDIR + "/_manifest.jsonl"
ORIGINALS_SUBDIR   = "99 Workspace/_originals"
QUARANTINE_SUBDIR  = "99 Workspace/_inbox_quarantine"
REJECTED_SUBDIR    = "99 Workspace/_inbox_rejected"      # IN-01: scope-gate rejects
INBOX_SUBDIR       = "00 Inbox"
DROP_SUBDIR        = "00 Inbox/_drop"
INGESTION_LOG_REL  = "99 Workspace/_ingestion_log.md"
AUTO_WRITES_REL    = "99 Workspace/_auto_writes.md"
SUPERSESSION_Q_REL = "99 Workspace/_ingestion_supersession_queue.md"
RECOMMENDATIONS_OPEN_REL = "99 Workspace/_recommendations_open.jsonl"
PURPOSE_REL        = "90 System/_purpose.md"             # IN-01: scope-gate source

# AL-06 closed-loop constants — must stay in sync with _closed_loop_contract.md
LINK_CANDIDATES_T2_THRESHOLD = 5     # ≥ this many candidates → emit T2 row
LINK_CANDIDATES_CATEGORY     = "link-candidates-review"
LINK_CANDIDATES_TIER         = 2
LINK_CANDIDATES_TASK         = "galp-vault-inbox-ingest"
LINK_CANDIDATES_EXPIRY_DAYS  = 14    # T2 expiry per closed-loop contract §3
RECOMMENDATIONS_BACKPRESSURE = 20    # contract §5: pause emission if OPEN > 20
# SEMANTIC_SOFT_THRESHOLD imported lazily from handlers.semantic at call site
# (avoids circular import and allows graceful failure if semantic.py is absent)
SEMANTIC_SOFT_THRESHOLD = 0.80   # mirrors handlers/semantic.py — must stay in sync
DAILY_SUBDIR       = "80 Daily"

FILE_SIZE_LIMIT        = 100 * 1024 * 1024   # 100 MB per file
RUN_SIZE_LIMIT         = 1024 * 1024 * 1024  # 1 GB per run
LOCK_STALE_SECS        = 30 * 60             # 30 min → stale lock auto-takeover
SUPERSESSION_WINDOW    = 90                  # days
QUARANTINE_TIDY_DAYS   = 30

# Files to always skip when scanning _drop/
SKIP_NAMES = frozenset({".lock", ".gitkeep", ".DS_Store", "Thumbs.db"})

# Extension → handler type (contract §2)
HANDLER_MAP: dict[str, str] = {
    ".md":   "md",
    ".txt":  "txt",
    ".pdf":  "pdf",
    ".docx": "docx",
    ".doc":  "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".xls":  "xlsx",
    ".png":  "image",
    ".jpg":  "image",
    ".jpeg": "image",
    ".webp": "image",
    ".heic": "image",
    ".heif": "image",
    ".gif":  "image",
    ".bmp":  "image",
    ".tiff": "image",
    ".tif":  "image",
}


# ===========================================================================
# IN-01 — Scope classifier (purpose.md gate)
# ===========================================================================
# Model used for the scope check.  Haiku is chosen for speed + low cost;
# the check is a simple binary IN/OUT decision on <1 KB of text.
CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"

# Character limit for the content preview passed to the classifier.
CLASSIFIER_PREVIEW_CHARS = 500


def load_purpose(root: Path) -> Optional[str]:
    """Read 90 System/_purpose.md and return its full text, or None on failure.

    Strips YAML frontmatter (between leading --- delimiters) and returns
    only the markdown body, which contains the scope prose.
    On any read/parse error the function returns None; the caller treats
    None as "classifier disabled — pass all files through".
    """
    purpose_path = root / PURPOSE_REL
    if not purpose_path.exists():
        return None
    try:
        raw = purpose_path.read_text(encoding="utf-8")
    except Exception:
        return None
    # Strip YAML frontmatter if present
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return raw.strip()


def _read_text_preview(src: Path, max_chars: int = CLASSIFIER_PREVIEW_CHARS) -> str:
    """Return up to max_chars of the file's text content, or '' on failure.

    Safe for binary files — decoding errors are silently ignored.
    """
    try:
        raw_bytes = src.read_bytes()
        text = raw_bytes[:max_chars * 4].decode("utf-8", errors="ignore")
        return text[:max_chars]
    except Exception:
        return ""


def classify_scope(
    filename: str,
    content_preview: str,
    purpose_text: str,
    *,
    verbose: bool = False,
) -> tuple[bool, str]:
    """Call Haiku to decide if the file is IN or OUT of scope.

    Returns (in_scope: bool, reason: str).
    On any API error the function returns (True, "classifier_unavailable")
    so the file is processed normally (fail-open: conservative policy —
    false rejection is harder to recover from than false acceptance).

    The classifier is given:
      - The vault purpose statement (scope definition)
      - The filename
      - Up to 500 chars of text preview (if extractable)

    It must respond with a JSON object:  {"in_scope": true/false, "reason": "<one-line>"}
    The reason is recorded in the rejected/ log regardless of direction.
    """
    try:
        import anthropic
    except ImportError:
        vlog("[classifier] anthropic not installed — skipping scope check", verbose)
        return True, "classifier_unavailable: anthropic_not_installed"

    prompt = (
        "You are a vault-scope classifier for a professional knowledge base.\n\n"
        "VAULT PURPOSE (scope definition):\n"
        f"{purpose_text}\n\n"
        "FILE TO CLASSIFY:\n"
        f"  Filename: {filename}\n"
        f"  Content preview (first {CLASSIFIER_PREVIEW_CHARS} chars):\n"
        f"  ---\n  {content_preview or '(binary — no text preview available)'}\n  ---\n\n"
        "Decide whether this file is IN-SCOPE or OUT-OF-SCOPE for this vault.\n"
        "Respond with ONLY a JSON object on a single line:\n"
        '  {"in_scope": true, "reason": "one-line reason"}\n'
        "or\n"
        '  {"in_scope": false, "reason": "one-line reason"}\n'
        "Be conservative: when in doubt, classify as in_scope: true."
    )

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=CLASSIFIER_MODEL,
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = (response.content[0].text if response.content else "").strip()
        # Parse JSON — find the first { ... } block in the response
        import re as _re
        m = _re.search(r'\{[^}]+\}', raw_text)
        if not m:
            vlog(f"[classifier] unparseable response: {raw_text!r}", verbose)
            return True, "classifier_parse_error"
        import json as _json
        obj = _json.loads(m.group())
        in_scope = bool(obj.get("in_scope", True))
        reason = str(obj.get("reason", "")).strip()[:120]
        vlog(
            f"[classifier] {filename!r} → {'IN_SCOPE' if in_scope else 'OUT_OF_SCOPE'}: {reason}",
            verbose,
        )
        return in_scope, reason
    except Exception as exc:
        vlog(f"[classifier] API error ({exc}) — defaulting in_scope=True", verbose)
        return True, f"classifier_api_error: {type(exc).__name__}"


def reject_file(
    src: Path,
    sha256: str,
    reason: str,
    rejected_dir: Path,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> str:
    """Move src to rejected/<date>/<sha8>_<name>.  Returns vault-relative path.

    Unlike quarantine, rejected files failed the scope gate (not a file
    integrity issue).  They can be manually re-admitted to _drop/ if the
    classification was wrong.
    """
    date_str = today_str()
    sha8 = sha256[:8] if sha256 else "00000000"
    dest_dir = rejected_dir / date_str
    dest = dest_dir / f"{sha8}_{src.name}"
    vault_rel = f"99 Workspace/_inbox_rejected/{date_str}/{sha8}_{src.name}"

    vlog(f"  [reject] {src.name} reason={reason}", verbose)
    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
    return vault_rel


# ===========================================================================
# Supersession stem (contract §7.1 — verbatim regex + algorithm)
# ===========================================================================

_SUPERSESSION_STRIP = re.compile(
    r"""(?ix)                               # case-insensitive, verbose
    (
        [_\-\s]+v\d+(?:\.\d+)*             # _v2  -v3  v1.2
      | [_\-\s]+ver\d+(?:\.\d+)*           # _ver2
      | [_\-\s]+vPreread\d*                # _vPreread01
      | [_\-\s]+preread\d*                 # _preread2
      | [_\-\s]+rev\d+                     # _rev3
      | [_\-\s]+draft\d*                   # _draft  _draft2
      | [_\-\s]+final                      # _final  -final
      | [_\-\s]+clean                      # _clean
      | [_\-\s]+\d{4}[_\-]?\d{2}[_\-]?\d{2}  # _20260417  -2026-04-17
      | [_\-\s]+\d{6,8}                    # _260417  _20260417
      | [_\-\s]+\(\d+\)                    # _(2)   (3)
      | [_\-\s]+copy\d*                    # _copy  copy2
    )+
    \s*$                                   # at end of stem
    """,
)


def supersession_stem(filename: str) -> str:
    """Compute the supersession stem for dedup/version queries (contract §7.1)."""
    stem = Path(filename).stem
    prev = None
    while prev != stem:
        prev = stem
        stem = _SUPERSESSION_STRIP.sub("", stem).strip(" _-")
    return stem.lower()


# ===========================================================================
# Utility helpers
# ===========================================================================

def now_utc() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def vlog(msg: str, verbose: bool) -> None:
    if verbose:
        print(msg, flush=True)


def derive_title(filename: str) -> str:
    """Human-readable title from filename stem (used if no user title)."""
    stem = Path(filename).stem
    title = re.sub(r"[_\-]+", " ", stem).strip()
    title = re.sub(r"\s+", " ", title)
    return title[:120] if title else stem


def derive_slug(filename: str) -> str:
    """URL-safe slug for the output .md filename."""
    try:
        from slugify import slugify  # python-slugify
        return slugify(Path(filename).stem, max_length=80)
    except ImportError:
        stem = Path(filename).stem.lower()
        slug = re.sub(r"[^\w\s-]", "", stem)
        slug = re.sub(r"[\s_-]+", "-", slug)
        return slug[:80].strip("-")


def file_mtime_utc(path: Path) -> Optional[str]:
    try:
        mt = path.stat().st_mtime
        return datetime.fromtimestamp(mt, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


# ===========================================================================
# Manifest store
# ===========================================================================

@dataclass
class ManifestEntry:
    run_id:                str
    sha256:                str
    source_filename:       str
    supersession_stem_val: str
    extracted_at:          str
    status:                str          # intent | committed | quarantined | rolled_back
    md_path:               Optional[str]  = None  # vault-relative
    original_path:         Optional[str]  = None  # vault-relative
    quarantine_reason:     Optional[str]  = None
    supersedes:            list           = field(default_factory=list)
    committed_at:          Optional[str]  = None
    manifest_offset:       Optional[int]  = None
    text_sha256:           Optional[str]  = None  # CH-03: SHA-256 of normalised body

    def to_dict(self) -> dict:
        return {
            "run_id":            self.run_id,
            "sha256":            self.sha256,
            "source_filename":   self.source_filename,
            "supersession_stem": self.supersession_stem_val,
            "extracted_at":      self.extracted_at,
            "status":            self.status,
            "md_path":           self.md_path,
            "original_path":     self.original_path,
            "quarantine_reason": self.quarantine_reason,
            "supersedes":        self.supersedes,
            "committed_at":      self.committed_at,
            "manifest_offset":   self.manifest_offset,
            "text_sha256":       self.text_sha256,   # CH-03
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ManifestEntry":
        return cls(
            run_id=d.get("run_id", ""),
            sha256=d.get("sha256", ""),
            source_filename=d.get("source_filename", ""),
            supersession_stem_val=d.get("supersession_stem", ""),
            extracted_at=d.get("extracted_at", ""),
            status=d.get("status", ""),
            md_path=d.get("md_path"),
            original_path=d.get("original_path"),
            quarantine_reason=d.get("quarantine_reason"),
            supersedes=d.get("supersedes", []),
            committed_at=d.get("committed_at"),
            manifest_offset=d.get("manifest_offset"),
            text_sha256=d.get("text_sha256"),   # CH-03
        )


class ManifestStore:
    """In-memory view of the manifest JSON-lines file with append helper.

    Dedup queries use FULL SHA-256 (contract §3 / ingestion-pipeline-discipline.md).
    Supersession queries use supersession_stem within a time window.
    """

    def __init__(self, manifest_path: Path) -> None:
        self._path = manifest_path
        self._entries: list[ManifestEntry] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    self._entries.append(ManifestEntry.from_dict(json.loads(line)))
                except (json.JSONDecodeError, Exception):
                    pass  # corrupt line — skip silently

    # ── Dedup (contract §3: full SHA-256, never prefix) ───────────────────────

    def has_sha(self, sha256: str) -> bool:
        """True if any committed entry exists with this full SHA-256."""
        return any(
            e.sha256 == sha256 and e.status == "committed"
            for e in self._entries
        )

    def has_text_sha(self, text_sha256: str, exclude_sha: Optional[str] = None) -> bool:
        """True if a committed entry has matching text_sha256 but different binary sha256.

        Contract §5 (CH-03): Tier-2 content-dedup check.

        Parameters
        ----------
        text_sha256 : str
            SHA-256 of the normalised extracted text (contract §5 text_sha256 field).
        exclude_sha : str | None
            Binary sha256 of the *current* file being processed. Entries with this
            binary sha are excluded — they are handled by the Tier-1 exact-duplicate
            path (``has_sha``) which already fired before we reach this check.

        Returns
        -------
        bool
            True if an existing *committed* entry has the same ``text_sha256``
            *and* a different binary ``sha256`` (content-duplicate from a different
            binary source). False otherwise — including when ``text_sha256`` is None
            or empty (no hash available, e.g. image with no OCR text).
        """
        if not text_sha256:
            return False
        for e in self._entries:
            if e.status != "committed":
                continue
            if not e.text_sha256:
                continue
            if e.text_sha256 != text_sha256:
                continue
            # Same text hash — check binary differs from the current file
            if exclude_sha and e.sha256 == exclude_sha:
                continue
            return True
        return False

    # ── Supersession query (contract §7.2) ────────────────────────────────────

    def query_by_stem(
        self, stem: str, window_days: int = SUPERSESSION_WINDOW
    ) -> list[ManifestEntry]:
        """Committed entries with matching stem within the window (newest first)."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=window_days)
        results = []
        for e in self._entries:
            if e.status != "committed":
                continue
            if e.supersession_stem_val != stem:
                continue
            try:
                ts = datetime.fromisoformat(e.extracted_at.replace("Z", "+00:00"))
                if ts >= cutoff:
                    results.append(e)
            except ValueError:
                pass
        results.sort(key=lambda e: e.extracted_at, reverse=True)
        return results

    # ── Run-scoped queries (for recover / rollback) ───────────────────────────

    def committed_for_run(self, run_id: str) -> list[ManifestEntry]:
        return [e for e in self._entries if e.run_id == run_id and e.status == "committed"]

    def intent_only_for_run(self, run_id: str) -> list[ManifestEntry]:
        """Intent entries that have no corresponding committed/quarantined entry."""
        resolved_shas = {
            e.sha256 for e in self._entries
            if e.run_id == run_id and e.status in ("committed", "quarantined")
        }
        return [
            e for e in self._entries
            if e.run_id == run_id
            and e.status == "intent"
            and e.sha256 not in resolved_shas
        ]

    # ── Append ────────────────────────────────────────────────────────────────

    def append(self, entry: ManifestEntry, dry_run: bool = False) -> int:
        """Append entry. Returns byte offset of the written line (0 in dry-run)."""
        self._entries.append(entry)
        if dry_run:
            return 0
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry.to_dict(), ensure_ascii=False) + "\n"
        offset = self._path.stat().st_size if self._path.exists() else 0
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line)
        return offset


# ===========================================================================
# Lock management
# ===========================================================================

class LockError(Exception):
    pass


def acquire_lock(drop_dir: Path, verbose: bool = False) -> Path:
    """Acquire _drop/.lock using O_CREAT|O_EXCL.

    If the file exists and is stale (mtime > LOCK_STALE_SECS), it is removed
    and we take over.  If a fresh lock is held, LockError is raised.
    """
    lock_path = drop_dir / ".lock"
    pid_info = f"{os.getpid()}\n{now_utc()}\n".encode()

    def _create() -> Path:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(fd, pid_info)
        os.close(fd)
        vlog(f"[lock] acquired {lock_path}", verbose)
        return lock_path

    try:
        return _create()
    except FileExistsError:
        pass

    # Lock exists — check staleness
    try:
        age = time.time() - lock_path.stat().st_mtime
    except FileNotFoundError:
        # Race: disappeared between our open and stat — try again once
        return _create()

    if age > LOCK_STALE_SECS:
        vlog(f"[lock] stale lock ({age / 60:.1f} min) — taking over", verbose)
        # Cowork mount blocks unlink — swallow PermissionError and try to
        # overwrite via truncate+rewrite (O_CREAT|O_EXCL won't work if file
        # still exists, so we overwrite it and then call _create again via
        # a fresh open; if that also fails, raise LockError)
        try:
            lock_path.unlink(missing_ok=True)
        except PermissionError:
            # File still exists; overwrite it with our PID/timestamp so
            # anyone else reading it sees a fresh lock
            try:
                lock_path.write_text(
                    json.dumps({"pid": os.getpid(), "ts": now_utc()})
                )
                return lock_path
            except Exception as exc:
                raise LockError(f"stale lock at {lock_path} — cannot remove or overwrite: {exc}") from exc
        return _create()

    raise LockError(
        f"_drop/.lock is held by another process (age {age / 60:.1f} min). "
        f"Wait or delete {lock_path} if the process is dead."
    )


def release_lock(lock_path: Optional[Path], verbose: bool = False) -> None:
    if lock_path is None:
        return
    try:
        lock_path.unlink(missing_ok=True)
        vlog(f"[lock] released {lock_path}", verbose)
    except PermissionError:
        # Cowork sandbox blocks unlink — same delete-guard as the source
        # unlink path at line ~1069 (`source_not_removed_from_drop`). Surface
        # explicitly so the leftover .lock is visible in run output and not
        # silently swallowed — matches the discipline of the source-unlink
        # warning. Fix: 2026-05-16.
        print(
            f"[lock] WARN: lock_not_released: permission_denied at {lock_path}. "
            f"The Cowork scheduled-task wrapper should call "
            f"mcp__cowork__allow_cowork_file_delete against any path in the "
            f"vault before invoking the pipeline; the grant is folder-wide "
            f"and session-scoped.",
            file=sys.stderr,
        )
    except Exception as exc:
        # Other errors (file gone, race) — non-fatal but visible in verbose mode.
        vlog(f"[lock] release failed (non-fatal): {exc}", verbose)


# ===========================================================================
# Handler dispatch
# ===========================================================================

def dispatch_handler(
    handler_type: str,
    source_path: Path,
    pipeline_computed: dict,
    pipeline_ns: dict,
    *,
    allow_cloud_ocr: bool = False,
    max_api_calls: Optional[int] = None,
    api_calls_used: Optional[list] = None,
    staging_assets_dir: Optional[Path] = None,
):
    """Dispatch file to the correct handler. Returns HandlerResult.

    Handlers are imported lazily so that missing optional dependencies
    (e.g. python-pptx) only fail for the specific file type, not at startup.
    """
    if handler_type == "md":
        from handlers.text import handle_md
        return handle_md(source_path, pipeline_computed=pipeline_computed, pipeline_ns=pipeline_ns)

    if handler_type == "txt":
        from handlers.text import handle_txt
        return handle_txt(source_path, pipeline_computed=pipeline_computed, pipeline_ns=pipeline_ns)

    if handler_type == "pdf":
        from handlers.pdf import handle_pdf
        return handle_pdf(
            source_path,
            pipeline_computed=pipeline_computed,
            pipeline_ns=pipeline_ns,
            images_dir=staging_assets_dir,
        )

    if handler_type == "docx":
        from handlers.docx import handle_docx
        return handle_docx(
            source_path,
            pipeline_computed=pipeline_computed,
            pipeline_ns=pipeline_ns,
            images_dir=staging_assets_dir,
        )

    if handler_type == "pptx":
        from handlers.pptx import handle_pptx
        return handle_pptx(
            source_path,
            pipeline_computed=pipeline_computed,
            pipeline_ns=pipeline_ns,
            assets_dir=staging_assets_dir,
        )

    if handler_type == "xlsx":
        from handlers.xlsx import handle_xlsx
        return handle_xlsx(
            source_path,
            pipeline_computed=pipeline_computed,
            pipeline_ns=pipeline_ns,
            original_ref=pipeline_computed.get("original_path", ""),
        )

    if handler_type == "image":
        from handlers.image import handle_image
        return handle_image(
            source_path,
            pipeline_computed=pipeline_computed,
            pipeline_ns=pipeline_ns,
            allow_cloud_ocr=allow_cloud_ocr,
            max_api_calls=max_api_calls,
            api_calls_used=api_calls_used,
        )

    # Should not reach here (caller guards on HANDLER_MAP)
    from handlers.text import HandlerResult
    return HandlerResult(
        success=False,
        quarantine=True,
        quarantine_reason="unknown_handler_type",
        warnings=[f"no handler registered for type '{handler_type}'"],
    )


# ===========================================================================
# Per-file result
# ===========================================================================

@dataclass
class PerFileResult:
    filename:       str
    sha256:         str
    status:         str              # ingested | quarantined | skipped | error | rejected
    file_size:      int = 0
    reason:         Optional[str] = None
    md_path:        Optional[str] = None   # vault-relative
    original_path:  Optional[str] = None   # vault-relative
    supersedes:     list = field(default_factory=list)
    warnings:       list = field(default_factory=list)
    link_candidates_count: int = 0   # AL-06 — drives T2 emission when ≥5


# ===========================================================================
# Quarantine helper
# ===========================================================================

def quarantine_file(
    src: Path,
    sha256: str,
    reason: str,
    quarantine_dir: Path,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> str:
    """Move src to quarantine/<date>/<sha8>_<name>.  Returns vault-relative path.

    REDACTED: the reason string must NEVER contain file content.
    """
    date_str = today_str()
    sha8 = sha256[:8] if sha256 else "00000000"
    dest_dir = quarantine_dir / date_str
    dest = dest_dir / f"{sha8}_{src.name}"
    vault_rel = f"99 Workspace/_inbox_quarantine/{date_str}/{sha8}_{src.name}"

    vlog(f"  [quarantine] {src.name} reason={reason}", verbose)
    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
    return vault_rel


# ===========================================================================
# Commit helper
# ===========================================================================

def commit_file(
    staged_binary: Path,
    staged_md: Path,
    originals_dir: Path,
    inbox_dir: Path,
    sha256: str,
    slug: str,
    original_filename: str,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> tuple[str, str]:
    """Move staged artifacts to final vault locations.

    Returns (original_vault_rel, md_vault_rel).

    Commit order:
      1. Binary → _originals/ (write-once; safe if re-run)
      2. .md    → 00 Inbox/
      3. COMMITTED_<sha8> marker in staging dir
    """
    sha8 = sha256[:8]
    date_str = today_str()

    orig_name = f"{sha8}_{original_filename}"
    orig_dest = originals_dir / orig_name
    orig_vault_rel = f"99 Workspace/_originals/{orig_name}"

    # Collision-safe .md name (two files with same slug on the same day)
    md_name = f"{date_str}-{slug}.md"
    md_dest = inbox_dir / md_name
    if not dry_run and md_dest.exists():
        md_name = f"{date_str}-{slug}-{sha8}.md"
        md_dest = inbox_dir / md_name
    elif dry_run:
        # In dry-run, check on disk too for the report
        if (inbox_dir / md_name).exists():
            md_name = f"{date_str}-{slug}-{sha8}.md"
    md_vault_rel = f"00 Inbox/{md_name}"

    vlog(f"  [commit] binary → {orig_vault_rel}", verbose)
    vlog(f"  [commit] .md    → {md_vault_rel}", verbose)

    if not dry_run:
        originals_dir.mkdir(parents=True, exist_ok=True)
        inbox_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: original (write-once — skip if somehow already there)
        if not orig_dest.exists():
            shutil.move(str(staged_binary), str(orig_dest))
        else:
            # Cowork mount blocks unlink — swallow PermissionError silently
            try:
                staged_binary.unlink(missing_ok=True)
            except PermissionError:
                pass

        # Step 2: .md
        shutil.move(str(staged_md), str(md_dest))

        # Step 3: commit marker (for --recover)
        marker = staged_binary.parent / f"COMMITTED_{sha8}"
        marker.touch()

    return orig_vault_rel, md_vault_rel


# ===========================================================================
# Supersession queue
# ===========================================================================

def queue_supersession(
    prior_entries: list[ManifestEntry],
    new_sha: str,
    new_filename: str,
    queue_path: Path,
    *,
    dry_run: bool = False,
) -> None:
    """Append a supersession alert to the queue file for Ricardo's review."""
    if not prior_entries:
        return
    ts = now_utc()
    new_sha_short = new_sha[:16]
    lines = [
        f"\n## Supersession — {ts}\n\n",
        f"**New file:** `{new_filename}` (SHA: `{new_sha_short}…`)\n\n",
        f"Prior version(s) queued for `is_latest_version: false` update:\n\n",
    ]
    for e in prior_entries:
        lines.append(f"- `{e.md_path or 'UNKNOWN'}` (SHA: `{e.sha256[:16]}…`)\n")
    lines.append(
        "\nReview, then approve via `python ingest.py --apply-queue` "
        "after confirming the supersession is correct.\n"
        "_(Note: supersession demotion is trigger-only — never auto-applied.)_\n"
    )
    if not dry_run:
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        with queue_path.open("a", encoding="utf-8") as f:
            f.write("".join(lines))


# ===========================================================================
# Soft-duplicate queue (contract §7.5 — SN-03)
# ===========================================================================

def queue_soft_duplicate(
    new_md_path: str,
    neighbors: list[dict],
    queue_path: Path,
    *,
    dry_run: bool = False,
) -> None:
    """Append a soft-duplicate candidate block to the supersession queue file.

    Contract §7.5: threshold ≥ 0.80 surfaces as a non-blocking advisory.
    Block is visually distinct from hard supersession entries (## vs ###).
    Ricardo may act (merge, cross-link, dismiss) — no --apply-queue needed.

    Parameters
    ----------
    new_md_path : str
        Vault-relative path of the newly ingested .md file.
    neighbors : list[{'path': str, 'score': float}]
        Top-k neighbours returned by query_neighbors(), sorted by score desc.
        Caller guarantees max(score) >= SEMANTIC_SOFT_THRESHOLD.
    queue_path : Path
        Absolute path to _ingestion_supersession_queue.md.
    """
    if not neighbors:
        return
    ts = now_utc()
    top_score = max(n["score"] for n in neighbors)
    lines = [
        f"\n### Soft-duplicate candidate — {ts}\n\n",
        f"**New file:** `{new_md_path}`  \n",
        f"**Top semantic score:** {top_score:.4f} (threshold ≥ {SEMANTIC_SOFT_THRESHOLD})\n\n",
        "| Score | Nearest neighbour |\n",
        "|-------|-------------------|\n",
    ]
    for n in neighbors:
        lines.append(f"| {n['score']:.4f} | `{n['path']}` |\n")
    lines.append(
        "\n_(Soft signal — Ricardo to confirm relatedness.)_  \n"
        "_No `--apply-queue` needed — no `is_latest_version` flip required._\n"
    )
    if not dry_run:
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        with queue_path.open("a", encoding="utf-8") as f:
            f.write("".join(lines))


# ===========================================================================
# Closed-loop emission (AL-06 — Frontier Adoption S08)
# ===========================================================================

def _count_open_recommendations(path: Path) -> int:
    """Count rows with status == 'OPEN' in the recommendations queue.

    Used to enforce the §5 backpressure rule before emitting a new T2 row.
    Missing file → 0 (no queue yet). Corrupt lines are skipped silently to
    match ManifestStore._load's tolerance.
    """
    if not path.exists():
        return 0
    open_count = 0
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("status") == "OPEN":
                    open_count += 1
    except OSError:
        return 0
    return open_count


def emit_link_candidate_recommendations(
    results: list["PerFileResult"],
    *,
    recommendations_path: Path,
    auto_writes_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Emit one T2 closed-loop row per ingested file with ≥5 link candidates.

    Honours the §5 backpressure rule: if OPEN count > 20, suppresses
    emission and writes a single backpressure-marker line to
    _auto_writes.md instead. Returns the number of rows actually
    appended (0 in dry-run, 0 under backpressure, or N when emitted).
    """
    qualifying = [
        r for r in results
        if r.status == "ingested"
        and r.link_candidates_count >= LINK_CANDIDATES_T2_THRESHOLD
        and r.md_path
    ]
    if not qualifying:
        return 0

    open_count = _count_open_recommendations(recommendations_path)
    if open_count > RECOMMENDATIONS_BACKPRESSURE:
        # Per contract §5 — single backpressure marker, no emission.
        if not dry_run:
            line = (
                f"{today_str()} | note | {RECOMMENDATIONS_OPEN_REL} | "
                f"BACKLOG_PAUSED: OPEN={open_count} > {RECOMMENDATIONS_BACKPRESSURE}; "
                f"{LINK_CANDIDATES_TASK} emission suppressed "
                f"({len(qualifying)} link-candidate row(s) dropped)\n"
            )
            auto_writes_path.parent.mkdir(parents=True, exist_ok=True)
            with auto_writes_path.open("a", encoding="utf-8") as f:
                f.write(line)
        vlog(
            f"[recommendations] BACKLOG_PAUSED: OPEN={open_count} "
            f"> {RECOMMENDATIONS_BACKPRESSURE}; {len(qualifying)} row(s) suppressed",
            verbose,
        )
        return 0

    appended = 0
    if not dry_run:
        recommendations_path.parent.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    expiry  = (datetime.now(tz=timezone.utc).date() + timedelta(days=LINK_CANDIDATES_EXPIRY_DAYS)).isoformat()

    for r in qualifying:
        row = {
            "id":           f"linkcand-{r.sha256[:12]}-{int(time.time() * 1000)}",
            "source_task":  LINK_CANDIDATES_TASK,
            "emitted_at":   now_iso,
            "tier":         LINK_CANDIDATES_TIER,
            "category":     LINK_CANDIDATES_CATEGORY,
            "description":  (
                f"{r.link_candidates_count} link candidates from {r.md_path} "
                f"awaiting approval"
            )[:200],
            "target_action": (
                f"kb-curator apply-link-candidates --source \"{r.md_path}\""
            )[:200],
            "status":       "OPEN",
            "expires_at":   expiry,
            "eval_baseline": None,
        }
        if not dry_run:
            with recommendations_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        appended += 1
        vlog(
            f"[recommendations] T2 emitted: {r.link_candidates_count} candidates "
            f"from {r.md_path}",
            verbose,
        )
    return appended


# ===========================================================================
# Post-run logging
# ===========================================================================

def write_daily_note(
    daily_dir: Path,
    run_id: str,
    results: list[PerFileResult],
    *,
    dry_run: bool = False,
) -> None:
    """Append a brief ingestion summary line to today's daily note."""
    date_str = today_str()
    daily_path = daily_dir / f"{date_str}.md"
    ingested    = sum(1 for r in results if r.status == "ingested")
    quarantined = sum(1 for r in results if r.status == "quarantined")
    skipped     = sum(1 for r in results if r.status == "skipped")
    mode_tag    = " [DRY-RUN]" if dry_run else ""
    text = (
        f"\n### Ingestion `{run_id}`{mode_tag} — {now_utc()}\n"
        f"{len(results)} file(s) scanned: "
        f"**{ingested}** ingested, **{quarantined}** quarantined, **{skipped}** skipped.\n"
    )
    if not dry_run:
        daily_dir.mkdir(parents=True, exist_ok=True)
        with daily_path.open("a", encoding="utf-8") as f:
            f.write(text)


def write_auto_writes(
    path: Path,
    run_id: str,
    results: list[PerFileResult],
    *,
    dry_run: bool = False,
) -> None:
    """One summary line to _auto_writes.md (auto-write-discipline.md format)."""
    if dry_run:
        return
    ingested    = sum(1 for r in results if r.status == "ingested")
    quarantined = sum(1 for r in results if r.status == "quarantined")
    line = (
        f"{today_str()} | note | 90 System/_ingestion_pipeline/ingest.py | "
        f"pipeline run {run_id}: {ingested} ingested, {quarantined} quarantined\n"
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


def write_ingestion_log(
    path: Path,
    run_id: str,
    results: list[PerFileResult],
    *,
    dry_run: bool = False,
) -> None:
    """Per-file detail paragraph to _ingestion_log.md (append-only)."""
    if dry_run:
        return
    ingested    = sum(1 for r in results if r.status == "ingested")
    quarantined = sum(1 for r in results if r.status == "quarantined")
    skipped     = sum(1 for r in results if r.status == "skipped")
    rejected    = sum(1 for r in results if r.status == "rejected")   # IN-01

    header = (
        f"\n## Run `{run_id}` — {now_utc()}\n\n"
        f"**Mode:** live  \n"
        f"**Scanned:** {len(results)}  \n"
        f"**Ingested:** {ingested}  \n"
        f"**Quarantined:** {quarantined}  \n"
        f"**Rejected (out_of_scope):** {rejected}  \n"
        f"**Skipped:** {skipped}\n\n"
        f"| File | Status | Notes |\n"
        f"|------|--------|-------|\n"
    )
    rows = []
    for r in results:
        note = r.reason or ""
        if r.warnings:
            note = "; ".join(w for w in r.warnings[:2] if w)
        rows.append(f"| `{r.filename}` | {r.status} | {note} |\n")

    with path.open("a", encoding="utf-8") as f:
        f.write(header)
        f.writelines(rows)


# ===========================================================================
# Quarantine tidy
# ===========================================================================

def tidy_quarantine(
    quarantine_dir: Path,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Delete empty _inbox_quarantine/<YYYY-MM-DD>/ dirs older than 30 days.

    Returns count of removed directories.
    """
    if not quarantine_dir.exists():
        return 0
    cutoff = datetime.now() - timedelta(days=QUARANTINE_TIDY_DAYS)
    removed = 0
    for date_dir in sorted(quarantine_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        try:
            dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
        except ValueError:
            continue
        if dir_date >= cutoff:
            continue
        if any(date_dir.iterdir()):
            continue  # not empty
        vlog(f"[tidy] removing empty quarantine dir: {date_dir.name}", verbose)
        if not dry_run:
            date_dir.rmdir()
        removed += 1
    return removed


# ===========================================================================
# Report-only printer (--dry-run --report-only)
# ===========================================================================

def print_report(
    files: list[Path],
    manifest: ManifestStore,
    inbox_dir: Path,
    *,
    verbose: bool = False,
) -> None:
    """Print a plan of what would happen for each file in _drop/."""
    print(f"\n{'=' * 66}")
    print(f"INGESTION PLAN  {today_str()}  ({len(files)} file(s) in _drop/)")
    print(f"{'=' * 66}")
    for f in files:
        try:
            size_mb = f.stat().st_size / (1_048_576)
        except Exception:
            size_mb = 0.0

        ext = f.suffix.lower()
        handler_type = HANDLER_MAP.get(ext)

        if size_mb * 1_048_576 > FILE_SIZE_LIMIT:
            action = "QUARANTINE  (file_too_large)"
            target = "—"
        elif handler_type is None:
            action = "QUARANTINE  (unsupported_file_type)"
            target = "—"
        else:
            try:
                sha = sha256_file(f)
            except Exception:
                action = "ERROR  (sha256_failed)"
                target = "—"
                print(f"  {f.name:<52}  {size_mb:6.2f} MB  {action}")
                continue

            if manifest.has_sha(sha):
                action = "QUARANTINE  (exact_duplicate)"
                target = "—"
            else:
                stem = supersession_stem(f.name)
                priors = manifest.query_by_stem(stem)
                slug = derive_slug(f.name)
                candidate = f"{today_str()}-{slug}.md"
                if (inbox_dir / candidate).exists():
                    candidate = f"{today_str()}-{slug}-{sha[:8]}.md"
                target = f"00 Inbox/{candidate}"
                if priors:
                    action = f"INGEST  (supersedes {len(priors)} prior)"
                else:
                    action = "INGEST"

            if verbose:
                print(f"  {f.name:<52}  {size_mb:6.2f} MB  {action}")
                print(f"    sha8={sha[:8]}  ext={ext}  handler={handler_type}")
                if target != "—":
                    print(f"    → {target}")
                continue

        print(f"  {f.name:<52}  {size_mb:6.2f} MB  {action}")
    print(f"{'=' * 66}\n")


# ===========================================================================
# Per-file processor
# ===========================================================================

def process_one_file(
    src: Path,
    root: Path,
    run_id: str,
    staging_run_dir: Path,
    originals_dir: Path,
    quarantine_dir: Path,
    rejected_dir: Path,
    inbox_dir: Path,
    manifest: ManifestStore,
    supersession_q_path: Path,
    *,
    purpose_text: Optional[str] = None,
    allow_cloud_ocr: bool = False,
    max_api_calls: Optional[int] = None,
    api_calls_used: list,
    dry_run: bool = False,
    verbose: bool = False,
) -> PerFileResult:
    """Full pipeline for one file from _drop/. Returns PerFileResult."""
    filename = src.name
    vlog(f"\n[file] {filename}", verbose)

    # ── File size ──────────────────────────────────────────────────────────────
    try:
        file_size = src.stat().st_size
    except Exception:
        file_size = 0

    # ── SHA-256 ────────────────────────────────────────────────────────────────
    try:
        sha256 = sha256_file(src)
    except Exception:
        return PerFileResult(
            filename=filename, sha256="", status="error",
            file_size=file_size, reason="sha256_error",
        )

    sha8 = sha256[:8]

    # ── Per-file size guard ────────────────────────────────────────────────────
    if file_size > FILE_SIZE_LIMIT:
        size_mb = file_size / 1_048_576
        quarantine_file(src, sha256, "file_too_large", quarantine_dir, dry_run=dry_run, verbose=verbose)
        manifest.append(ManifestEntry(
            run_id=run_id, sha256=sha256, source_filename=filename,
            supersession_stem_val=supersession_stem(filename),
            extracted_at=now_utc(), status="quarantined",
            quarantine_reason="file_too_large",
        ), dry_run=dry_run)
        return PerFileResult(
            filename=filename, sha256=sha256, status="quarantined",
            file_size=file_size, reason="file_too_large",
        )

    # ── Dedup (full SHA-256 — contract §3) ────────────────────────────────────
    if manifest.has_sha(sha256):
        quarantine_file(src, sha256, "exact_duplicate", quarantine_dir, dry_run=dry_run, verbose=verbose)
        manifest.append(ManifestEntry(
            run_id=run_id, sha256=sha256, source_filename=filename,
            supersession_stem_val=supersession_stem(filename),
            extracted_at=now_utc(), status="quarantined",
            quarantine_reason="exact_duplicate",
        ), dry_run=dry_run)
        vlog(f"  [dedup] quarantined (exact_duplicate)", verbose)
        return PerFileResult(
            filename=filename, sha256=sha256, status="quarantined",
            file_size=file_size, reason="exact_duplicate",
        )

    # ── Extension / handler check ─────────────────────────────────────────────
    ext = src.suffix.lower()
    handler_type = HANDLER_MAP.get(ext)
    if handler_type is None:
        quarantine_file(src, sha256, "unsupported_file_type", quarantine_dir, dry_run=dry_run, verbose=verbose)
        manifest.append(ManifestEntry(
            run_id=run_id, sha256=sha256, source_filename=filename,
            supersession_stem_val=supersession_stem(filename),
            extracted_at=now_utc(), status="quarantined",
            quarantine_reason="unsupported_file_type",
        ), dry_run=dry_run)
        return PerFileResult(
            filename=filename, sha256=sha256, status="quarantined",
            file_size=file_size, reason="unsupported_file_type",
        )

    # ── IN-01: Scope gate — purpose.md classifier ─────────────────────────────
    # Runs after dedup + extension check (we know the file is actionable) but
    # before the INTENT manifest entry (rejected files are never committed).
    # Fail-open: if purpose_text is None or the API errors, the file passes.
    if purpose_text and not dry_run:
        content_preview = _read_text_preview(src)
        in_scope, scope_reason = classify_scope(
            filename, content_preview, purpose_text, verbose=verbose
        )
        if not in_scope:
            rejected_vault_rel = reject_file(
                src, sha256, scope_reason, rejected_dir,
                dry_run=dry_run, verbose=verbose,
            )
            manifest.append(ManifestEntry(
                run_id=run_id, sha256=sha256, source_filename=filename,
                supersession_stem_val=supersession_stem(filename),
                extracted_at=now_utc(), status="quarantined",
                quarantine_reason=f"out_of_scope: {scope_reason}",
            ), dry_run=dry_run)
            vlog(f"  [scope] REJECTED → {rejected_vault_rel}", verbose)
            return PerFileResult(
                filename=filename, sha256=sha256, status="rejected",
                file_size=file_size, reason=f"out_of_scope: {scope_reason}",
            )

    # ── Supersession check (contract §7.2) ────────────────────────────────────
    stem_val = supersession_stem(filename)
    prior_entries = manifest.query_by_stem(stem_val, window_days=SUPERSESSION_WINDOW)
    supersedes_list = [e.sha256 for e in prior_entries]
    if verbose and prior_entries:
        print(f"  [supersession] {len(prior_entries)} prior version(s) — stem: {stem_val!r}")

    # ── INTENT entry (crash-safety anchor — written BEFORE extraction) ─────────
    extracted_at = now_utc()
    mtime_str    = file_mtime_utc(src)
    intent_entry = ManifestEntry(
        run_id=run_id, sha256=sha256, source_filename=filename,
        supersession_stem_val=stem_val, extracted_at=extracted_at,
        status="intent", supersedes=supersedes_list,
    )
    intent_offset = manifest.append(intent_entry, dry_run=dry_run)

    # ── Copy to staging ────────────────────────────────────────────────────────
    staged_binary = staging_run_dir / f"{sha8}_{filename}"
    if not dry_run:
        staging_run_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(staged_binary))

    # ── Build pipeline_computed + pipeline_ns for handler ─────────────────────
    slug = derive_slug(filename)
    orig_vault_rel_planned = f"99 Workspace/_originals/{sha8}_{filename}"

    pipeline_computed = {
        "title":            derive_title(filename),
        "source_file":      filename,
        "original_path":    orig_vault_rel_planned,
        "file_type":        ext.lstrip("."),
        "extracted_at":     extracted_at,
        "page_count":       None,
        "document_date":    None,
        "is_latest_version": True,
    }

    # The handler receives a FRESH copy of pipeline_ns and mutates it.
    pipeline_ns_copy = {
        "run_id":            run_id,
        "sha256":            sha256,
        "source_file_mtime": mtime_str,
        "manifest_offset":   intent_offset,
        "supersedes":        supersedes_list,
        "superseded_by":     None,
        "warnings":          [],
    }

    # ── Dispatch to handler ────────────────────────────────────────────────────
    vlog(f"  [dispatch] handler={handler_type}", verbose)
    staging_assets_dir = (
        staging_run_dir / f"{sha8}_{src.stem}.assets"
        if not dry_run else None
    )
    handler_src = staged_binary if (not dry_run and staged_binary.exists()) else src

    try:
        result = dispatch_handler(
            handler_type,
            handler_src,
            pipeline_computed,
            pipeline_ns_copy,
            allow_cloud_ocr=allow_cloud_ocr,
            max_api_calls=max_api_calls,
            api_calls_used=api_calls_used,
            staging_assets_dir=staging_assets_dir,
        )
    except Exception:
        # Unexpected crash — quarantine the original
        if not dry_run and staged_binary.exists():
            staged_binary.unlink(missing_ok=True)
        quarantine_file(src, sha256, "handler_exception", quarantine_dir, dry_run=dry_run, verbose=verbose)
        manifest.append(ManifestEntry(
            run_id=run_id, sha256=sha256, source_filename=filename,
            supersession_stem_val=stem_val, extracted_at=extracted_at,
            status="quarantined", quarantine_reason="handler_exception",
        ), dry_run=dry_run)
        return PerFileResult(
            filename=filename, sha256=sha256, status="error",
            file_size=file_size, reason="handler_exception",
        )

    # ── Handler → quarantine ───────────────────────────────────────────────────
    if result.quarantine:
        reason = result.quarantine_reason or "handler_quarantine"
        # NOTE: reason string is REDACTED — no file content included
        quarantine_file(src, sha256, reason, quarantine_dir, dry_run=dry_run, verbose=verbose)
        if not dry_run and staged_binary.exists():
            staged_binary.unlink(missing_ok=True)
        manifest.append(ManifestEntry(
            run_id=run_id, sha256=sha256, source_filename=filename,
            supersession_stem_val=stem_val, extracted_at=extracted_at,
            status="quarantined", quarantine_reason=reason,
        ), dry_run=dry_run)
        return PerFileResult(
            filename=filename, sha256=sha256, status="quarantined",
            file_size=file_size, reason=reason, warnings=result.warnings,
        )

    # ── Enrich pipeline_ns with orchestrator fields ────────────────────────────
    # (handler may have added provenance, extractor, etc. to the copy)
    pipeline_ns_copy["run_id"]            = run_id
    pipeline_ns_copy["sha256"]            = sha256
    pipeline_ns_copy["source_file_mtime"] = mtime_str
    pipeline_ns_copy["manifest_offset"]   = intent_offset
    pipeline_ns_copy["supersedes"]        = supersedes_list

    # Ensure pipeline_namespace on result points to the enriched copy
    result.pipeline_namespace = pipeline_ns_copy

    # Also ensure key top-level fields are set correctly
    result.frontmatter_top["original_path"]     = orig_vault_rel_planned
    result.frontmatter_top["source_file"]       = filename
    result.frontmatter_top["extracted_at"]      = extracted_at
    result.frontmatter_top.setdefault("is_latest_version", True)

    # ── Tier-2 dedup: content-hash check (CH-03) ──────────────────────────────
    # Runs AFTER handler extraction so we have text_sha256.
    # Runs BEFORE commit so we never write a content-duplicate to the vault.
    # Exact binary duplicates were already caught above by has_sha(); this
    # check catches re-exports / metadata-only changes (same prose, different bytes).
    _text_sha = result.pipeline_namespace.get("text_sha256")
    if _text_sha and manifest.has_text_sha(_text_sha, exclude_sha=sha256):
        reason = "content_duplicate"
        quarantine_file(src, sha256, reason, quarantine_dir, dry_run=dry_run, verbose=verbose)
        if not dry_run and staged_binary.exists():
            try:
                staged_binary.unlink(missing_ok=True)
            except PermissionError:
                pass
        manifest.append(ManifestEntry(
            run_id=run_id, sha256=sha256, source_filename=filename,
            supersession_stem_val=stem_val, extracted_at=extracted_at,
            status="quarantined", quarantine_reason=reason,
            text_sha256=_text_sha,
        ), dry_run=dry_run)
        vlog(f"  [dedup] quarantined (content_duplicate)", verbose)
        return PerFileResult(
            filename=filename, sha256=sha256, status="quarantined",
            file_size=file_size, reason=reason, warnings=result.warnings,
        )

    # ── Tier-3: semantic-neighbour soft-warning (contract §7.5 — SN-02) ─────────
    # Runs AFTER Tier-2 content-hash check passes (file is genuinely new content).
    # Runs BEFORE commit — purely advisory, NEVER blocks.
    # Vault root is 3 levels above this script (pipeline dir → 90 System → vault).
    _extracted_text = result.body or ""
    if _extracted_text:
        try:
            from handlers.semantic import query_neighbors
            _neighbors, _sem_warning = query_neighbors(
                _extracted_text,
                top_k=3,
                vault_root=root,
            )
        except Exception as _sem_exc:
            _neighbors = []
            _sem_warning = f"semantic_lookup_unavailable: unexpected error: {_sem_exc}"
    else:
        _neighbors = []
        _sem_warning = None

    pipeline_ns_copy["semantic_neighbors"] = _neighbors
    if _sem_warning:
        pipeline_ns_copy.setdefault("warnings", []).append(_sem_warning)
        vlog(f"  [semantic] {_sem_warning}", verbose)
    elif _neighbors:
        vlog(
            f"  [semantic] top-3 scores: "
            + ", ".join(f"{n['score']:.4f}" for n in _neighbors),
            verbose,
        )

    # Surface ≥ 0.80 hits in the supersession queue as soft-duplicate candidates.
    if _neighbors:
        _top_score = max(n["score"] for n in _neighbors)
        if _top_score >= SEMANTIC_SOFT_THRESHOLD:
            # md_vault_rel not yet assigned (commit hasn't run) — use planned path.
            _planned_md_path = f"00 Inbox/{today_str()}-{slug}.md"
            queue_soft_duplicate(
                _planned_md_path,
                _neighbors,
                supersession_q_path,
                dry_run=dry_run,
            )
            vlog(
                f"  [semantic] soft-duplicate alert written (top score {_top_score:.4f})",
                verbose,
            )

    # ── LD-03: Promote semantic_neighbors to body wikilinks ───────────────────
    # Append "## See also" block wrapped in idempotent re-render markers for
    # any neighbour with score >= SEMANTIC_SEE_ALSO_THRESHOLD (0.85). Graph +
    # retrieval Step 3 then become aware of these links instead of only
    # frontmatter (which Obsidian's graph view ignores).
    try:
        from handlers.semantic import (
            format_see_also_block,
            SEMANTIC_SEE_ALSO_THRESHOLD,
        )
        _see_also = format_see_also_block(
            _neighbors,
            threshold=SEMANTIC_SEE_ALSO_THRESHOLD,
        )
        if _see_also and result.body is not None:
            result.body = (result.body or "").rstrip() + "\n\n" + _see_also + "\n"
            pipeline_ns_copy["see_also_added"] = True
        else:
            pipeline_ns_copy["see_also_added"] = False
    except Exception as _sa_exc:
        pipeline_ns_copy.setdefault("warnings", []).append(
            f"see_also_skipped: {_sa_exc}"
        )
        pipeline_ns_copy["see_also_added"] = False

    # ── LD-02: Wikilink enrichment (post-extract, pre-render) ─────────────────
    # Mutates result.body in place by wrapping first-mention of every entity
    # in the dynamic catalogue (10 People/, 20 Companies/, 60 Concepts/) +
    # the hardcoded SYSTEMS list. Idempotent — existing [[wikilinks]] are
    # masked and never double-linked. The See-Also block above is masked
    # too (via SEE_ALSO_BLOCK_RE). Failure mode: log to pipeline.warnings,
    # continue (contract §7.5 failure-mode parallel).
    _links_added = 0
    _links_enriched = False
    try:
        # enrich_links.py lives at <vault>/90 System/enrich_links.py
        # ingest.py lives at <vault>/90 System/_ingestion_pipeline/ingest.py
        _system_dir = Path(__file__).resolve().parent.parent
        if str(_system_dir) not in sys.path:
            sys.path.insert(0, str(_system_dir))
        import enrich_links as _enrich_mod
        _entities = _enrich_mod.load_catalogue(root)
        if _entities and result.body is not None:
            _new_body, _tags_added, _links_added = _enrich_mod.enrich_body(
                result.body, _entities
            )
            result.body = _new_body
            _links_enriched = True
            # Tags merge: add to existing top-level tags list if present
            if _tags_added:
                _existing_tags = result.frontmatter_top.get("tags") or []
                if isinstance(_existing_tags, str):
                    _existing_tags = [_existing_tags]
                if not isinstance(_existing_tags, list):
                    _existing_tags = list(_existing_tags)
                _merged = list(dict.fromkeys(list(_existing_tags) + list(_tags_added)))
                result.frontmatter_top["tags"] = _merged
        vlog(
            f"  [enrich] entities={len(_entities)} links_added={_links_added}",
            verbose,
        )
    except Exception as _enrich_exc:
        pipeline_ns_copy.setdefault("warnings", []).append(
            f"links_enrichment_failed: {_enrich_exc}"
        )
        _links_enriched = False
        _links_added = 0

    pipeline_ns_copy["links_enriched"] = _links_enriched
    pipeline_ns_copy["links_added"] = _links_added

    # ── AL-05: Auto-link candidates (language detection + AL-03 matcher + NER) ─
    # Runs AFTER LD-02 enrichment so offsets reflect the final body the .md
    # will commit. Failure modes are all graceful: missing catalog → no field;
    # spaCy missing / model missing → exact-only candidates; any exception →
    # logged into pipeline.warnings, ingest continues. Contract §12 (AL-04).
    _link_candidates_count = 0
    try:
        from handlers.links import populate_link_candidates
        _link_result = populate_link_candidates(
            result.body or "",
            vault_root=root,
            run_ner=True,
        )
        pipeline_ns_copy["language"] = _link_result.language
        if _link_result.catalog_used or _link_result.candidates:
            pipeline_ns_copy["link_candidates"] = _link_result.candidates
            _link_candidates_count = len(_link_result.candidates)
        # else: catalog unavailable → field omitted per §12.3
        for _w in _link_result.warnings:
            pipeline_ns_copy.setdefault("warnings", []).append(_w)
        vlog(
            f"  [link-candidates] lang={_link_result.language} "
            f"exact={_link_result.exact_count} ner={_link_result.ner_count} "
            f"final={_link_candidates_count}",
            verbose,
        )
    except Exception as _lc_exc:
        pipeline_ns_copy.setdefault("warnings", []).append(
            f"link_candidates_failed: {_lc_exc}"
        )
        pipeline_ns_copy.setdefault("language", "unknown")

    # ── Render final .md ───────────────────────────────────────────────────────
    from handlers.text import build_output_md
    output_md = build_output_md(result, filename)

    # ── Write staged .md ───────────────────────────────────────────────────────
    staged_md = staging_run_dir / f"{sha8}_{slug}.md"
    if not dry_run:
        staged_md.write_text(output_md, encoding="utf-8")

    # ── Commit ────────────────────────────────────────────────────────────────
    orig_vault_rel, md_vault_rel = commit_file(
        staged_binary, staged_md,
        originals_dir, inbox_dir,
        sha256, slug, filename,
        dry_run=dry_run, verbose=verbose,
    )

    # ── Committed entry → manifest (BEFORE unlink so recovery works) ─────────
    committed_entry = ManifestEntry(
        run_id=run_id, sha256=sha256, source_filename=filename,
        supersession_stem_val=stem_val, extracted_at=extracted_at,
        status="committed", md_path=md_vault_rel,
        original_path=orig_vault_rel, supersedes=supersedes_list,
        committed_at=now_utc(),
        text_sha256=result.pipeline_namespace.get("text_sha256"),   # CH-03
    )
    committed_offset = manifest.append(committed_entry, dry_run=dry_run)
    committed_entry.manifest_offset = committed_offset

    # ── Remove original from _drop/ ───────────────────────────────────────────
    # Non-fatal: Cowork mount blocks unlink()/rm — log a warning and continue.
    if not dry_run:
        try:
            src.unlink(missing_ok=True)
        except PermissionError:
            pipeline_ns_copy.setdefault("warnings", []).append(
                "source_not_removed_from_drop: permission_denied"
            )

    # ── Supersession queue (HARD ALERT at next bootstrap) ─────────────────────
    if prior_entries:
        queue_supersession(
            prior_entries, sha256, filename,
            supersession_q_path, dry_run=dry_run,
        )

    vlog(f"  [ok] → {md_vault_rel}", verbose)

    return PerFileResult(
        filename=filename, sha256=sha256, status="ingested",
        file_size=file_size, md_path=md_vault_rel,
        original_path=orig_vault_rel, supersedes=supersedes_list,
        warnings=result.warnings,
        link_candidates_count=_link_candidates_count,   # AL-06
    )


# ===========================================================================
# Recover mode
# ===========================================================================

def do_recover(
    run_id: str,
    root: Path,
    manifest: ManifestStore,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Resume a crashed run: commit intent-only entries whose staged files exist."""
    staging_run_dir = root / STAGING_SUBDIR / run_id
    pending = manifest.intent_only_for_run(run_id)

    if not pending:
        print(f"[recover] No pending intent entries for run {run_id}. Nothing to do.")
        return

    print(f"[recover] Found {len(pending)} uncommitted intent entries for run {run_id}.")

    originals_dir = root / ORIGINALS_SUBDIR
    inbox_dir     = root / INBOX_SUBDIR

    for entry in pending:
        sha8 = entry.sha256[:8]
        staged_binary = staging_run_dir / f"{sha8}_{entry.source_filename}"
        slug = derive_slug(entry.source_filename)

        # Find staged .md by glob
        staged_mds = list(staging_run_dir.glob(f"{sha8}_*.md")) if staging_run_dir.exists() else []
        staged_md = staged_mds[0] if staged_mds else None

        if not staged_binary.exists():
            print(f"  [recover] SKIP {entry.source_filename}: staged binary missing in {staging_run_dir}")
            continue
        if staged_md is None:
            print(f"  [recover] SKIP {entry.source_filename}: staged .md missing in {staging_run_dir}")
            continue

        orig_vault_rel, md_vault_rel = commit_file(
            staged_binary, staged_md,
            originals_dir, inbox_dir,
            entry.sha256, slug, entry.source_filename,
            dry_run=dry_run, verbose=verbose,
        )

        committed = ManifestEntry(
            run_id=run_id, sha256=entry.sha256,
            source_filename=entry.source_filename,
            supersession_stem_val=entry.supersession_stem_val,
            extracted_at=entry.extracted_at, status="committed",
            md_path=md_vault_rel, original_path=orig_vault_rel,
            supersedes=entry.supersedes, committed_at=now_utc(),
        )
        offset = manifest.append(committed, dry_run=dry_run)
        committed.manifest_offset = offset
        print(f"  [recover] committed {entry.source_filename} → {md_vault_rel}")


# ===========================================================================
# Rollback mode
# ===========================================================================

def do_rollback(
    run_id: str,
    root: Path,
    manifest: ManifestStore,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Undo a run: remove .md, return original to _drop, mark rolled_back.

    NOTE: supersession queue entries written by this run are NOT automatically
    reversed. Review 99 Workspace/_ingestion_supersession_queue.md after rollback.
    """
    committed = manifest.committed_for_run(run_id)
    if not committed:
        print(f"[rollback] No committed entries for run {run_id}.")
        return

    print(f"[rollback] Rolling back {len(committed)} file(s) from run {run_id}.")
    drop_dir = root / DROP_SUBDIR

    for entry in committed:
        # Remove ingested .md
        if entry.md_path:
            md_abs = root / entry.md_path
            if md_abs.exists():
                vlog(f"  [rollback] remove {entry.md_path}", verbose)
                if not dry_run:
                    md_abs.unlink()
            else:
                print(f"  [rollback] WARN .md not found: {entry.md_path}")

        # Return original to _drop
        if entry.original_path:
            orig_abs = root / entry.original_path
            if orig_abs.exists():
                dest = drop_dir / entry.source_filename
                vlog(f"  [rollback] restore {entry.original_path} → _drop/", verbose)
                if not dry_run:
                    drop_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(orig_abs), str(dest))
            else:
                print(f"  [rollback] WARN original not found: {entry.original_path}")

        # Append rolled_back entry
        rolled = ManifestEntry(
            run_id=run_id, sha256=entry.sha256,
            source_filename=entry.source_filename,
            supersession_stem_val=entry.supersession_stem_val,
            extracted_at=entry.extracted_at, status="rolled_back",
            md_path=entry.md_path, original_path=entry.original_path,
            committed_at=entry.committed_at,
        )
        manifest.append(rolled, dry_run=dry_run)
        print(f"  [rollback] done: {entry.source_filename}")

    print(
        "\n[rollback] NOTE: supersession queue entries are NOT reversed.\n"
        "  Review: 99 Workspace/_ingestion_supersession_queue.md"
    )


# ===========================================================================
# Main pipeline runner
# ===========================================================================

def run_pipeline(
    root: Path,
    *,
    dry_run: bool = False,
    report_only: bool = False,
    verbose: bool = False,
    allow_cloud_ocr: bool = False,
    max_api_calls: int = 0,
) -> int:
    """Execute the ingestion pipeline. Returns exit code (0 = ok, 1 = errors)."""
    run_id = str(uuid.uuid4()).replace("-", "")[:8]
    mode_tag = " [DRY-RUN]" if dry_run else ""
    print(
        f"[ingest] run={run_id}{mode_tag}  root={root}\n"
        f"         report_only={report_only}  cloud_ocr={allow_cloud_ocr}"
    )

    # ── Resolve paths ──────────────────────────────────────────────────────────
    drop_dir           = root / DROP_SUBDIR
    staging_root       = root / STAGING_SUBDIR
    staging_run_dir    = staging_root / run_id
    originals_dir      = root / ORIGINALS_SUBDIR
    quarantine_dir     = root / QUARANTINE_SUBDIR
    rejected_dir       = root / REJECTED_SUBDIR          # IN-01
    inbox_dir          = root / INBOX_SUBDIR
    manifest_path      = root / MANIFEST_REL
    ingestion_log_path = root / INGESTION_LOG_REL
    auto_writes_path   = root / AUTO_WRITES_REL
    supersession_q     = root / SUPERSESSION_Q_REL
    daily_dir          = root / DAILY_SUBDIR
    recommendations_p  = root / RECOMMENDATIONS_OPEN_REL

    # ── IN-01: Load vault purpose (scope gate) ─────────────────────────────────
    purpose_text = load_purpose(root)
    if purpose_text:
        vlog(f"[ingest] scope gate active — purpose.md loaded ({len(purpose_text)} chars)", verbose)
    else:
        vlog("[ingest] scope gate inactive — 90 System/_purpose.md not found", verbose)

    if not drop_dir.exists():
        print(f"[ingest] ERROR: _drop/ not found: {drop_dir}")
        return 1

    # ── Load manifest ──────────────────────────────────────────────────────────
    manifest = ManifestStore(manifest_path)
    vlog(f"[ingest] manifest loaded ({len(manifest._entries)} entries)", verbose)

    # ── Scan _drop/ ────────────────────────────────────────────────────────────
    files_to_process: list[Path] = sorted(
        [f for f in drop_dir.iterdir() if f.is_file() and f.name not in SKIP_NAMES],
        key=lambda p: p.stat().st_mtime,
    )

    if not files_to_process:
        print(f"[ingest] _drop/ is empty — 0 files to process.")
        return 0

    print(f"[ingest] {len(files_to_process)} file(s) found in _drop/")

    # ── Report-only: print plan and exit ──────────────────────────────────────
    # (--dry-run --report-only is the scheduled-task default mode)
    if report_only:
        print_report(files_to_process, manifest, inbox_dir, verbose=verbose)
        return 0

    # ── Acquire lock (skipped in dry-run) ─────────────────────────────────────
    lock_path: Optional[Path] = None
    if not dry_run:
        try:
            lock_path = acquire_lock(drop_dir, verbose=verbose)
        except LockError as e:
            print(f"[ingest] ERROR: {e}")
            return 1

    # ── Create staging dir ────────────────────────────────────────────────────
    if not dry_run:
        staging_run_dir.mkdir(parents=True, exist_ok=True)

    # ── Per-file processing ───────────────────────────────────────────────────
    results: list[PerFileResult] = []
    total_bytes = 0
    api_calls_used = [0]
    has_errors = False

    try:
        for src_file in files_to_process:
            per_result = process_one_file(
                src=src_file,
                root=root,
                run_id=run_id,
                staging_run_dir=staging_run_dir,
                originals_dir=originals_dir,
                quarantine_dir=quarantine_dir,
                rejected_dir=rejected_dir,          # IN-01
                inbox_dir=inbox_dir,
                manifest=manifest,
                supersession_q_path=supersession_q,
                purpose_text=purpose_text,          # IN-01
                allow_cloud_ocr=allow_cloud_ocr,
                max_api_calls=max_api_calls if max_api_calls > 0 else None,
                api_calls_used=api_calls_used,
                dry_run=dry_run,
                verbose=verbose,
            )
            results.append(per_result)

            if per_result.status == "error":
                has_errors = True

            # Accumulate processed bytes (for per-run size limit)
            total_bytes += per_result.file_size

            if total_bytes > RUN_SIZE_LIMIT:
                remaining = [
                    f for f in files_to_process
                    if f not in {src_file.parent / r.filename for r in results}
                ]
                if remaining:
                    print(
                        f"[ingest] WARN: per-run size limit "
                        f"({RUN_SIZE_LIMIT // (1024 ** 3)} GB) reached. "
                        f"{len(remaining)} file(s) deferred to next run."
                    )
                    for f in remaining:
                        results.append(PerFileResult(
                            filename=f.name, sha256="", status="skipped",
                            file_size=0, reason="per_run_size_limit_reached",
                        ))
                break

    finally:
        release_lock(lock_path, verbose=verbose)

    # ── Post-run logging ──────────────────────────────────────────────────────
    write_daily_note(daily_dir, run_id, results, dry_run=dry_run)
    write_auto_writes(auto_writes_path, run_id, results, dry_run=dry_run)
    write_ingestion_log(ingestion_log_path, run_id, results, dry_run=dry_run)

    # ── AL-06: link-candidate T2 emission (per source w/ ≥5 candidates) ───────
    # Respects closed-loop contract §5 backpressure (>20 OPEN → suppressed
    # with a single _auto_writes.md marker). Never blocks the run.
    _t2_emitted = emit_link_candidate_recommendations(
        results,
        recommendations_path=recommendations_p,
        auto_writes_path=auto_writes_path,
        dry_run=dry_run,
        verbose=verbose,
    )
    if _t2_emitted:
        print(f"[recommendations] {_t2_emitted} link-candidate T2 row(s) emitted")

    # ── Quarantine tidy (empty date dirs >30 days) ─────────────────────────────
    tidy_count = tidy_quarantine(quarantine_dir, dry_run=dry_run, verbose=verbose)
    if tidy_count:
        vlog(f"[tidy] removed {tidy_count} empty quarantine dir(s)", verbose)

    # ── Summary ──────────────────────────────────────────────────────────────
    ingested    = sum(1 for r in results if r.status == "ingested")
    quarantined = sum(1 for r in results if r.status == "quarantined")
    rejected    = sum(1 for r in results if r.status == "rejected")   # IN-01
    skipped     = sum(1 for r in results if r.status == "skipped")
    errors      = sum(1 for r in results if r.status == "error")

    print(
        f"\n{mode_tag}[ingest] run {run_id} complete: "
        f"{ingested} ingested  {quarantined} quarantined  "
        f"{rejected} rejected  {skipped} skipped  {errors} errors"
    )
    if dry_run:
        print("[ingest] DRY-RUN: no files were written or moved.")

    return 1 if (errors > 0 or has_errors) else 0


# ===========================================================================
# CLI
# ===========================================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ingest.py",
        description="Galp Vault v2 ingestion pipeline orchestrator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python ingest.py --dry-run --report-only --verbose\n"
            "  python ingest.py --verbose\n"
            "  python ingest.py --allow-cloud-ocr --max-api-calls 10\n"
            "  python ingest.py --recover a1b2c3d4\n"
            "  python ingest.py --rollback a1b2c3d4\n"
        ),
    )
    p.add_argument(
        "--root", type=Path, default=None,
        help="Vault root path. Default: auto-detected (3 levels up from this script).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Parse, plan, and extract — but write nothing. No moves, no manifest appends.",
    )
    p.add_argument(
        "--report-only", action="store_true",
        help=(
            "Scan _drop/, print a plan of would-ingest/would-quarantine, then exit. "
            "Implies --dry-run. Skips handler dispatch (fast, no extraction)."
        ),
    )
    p.add_argument(
        "--verbose", action="store_true",
        help="Extra per-file progress output.",
    )
    p.add_argument(
        "--allow-cloud-ocr", action="store_true",
        help="Enable Anthropic cloud Vision OCR for eligible images (requires config.yaml).",
    )
    p.add_argument(
        "--max-api-calls", type=int, default=0, metavar="N",
        help="Cloud API call cap per run (0 = no cap).",
    )
    p.add_argument(
        "--recover", metavar="RUN_ID",
        help="Resume a crashed run: commit intent-only entries that have staged files.",
    )
    p.add_argument(
        "--rollback", metavar="RUN_ID",
        help="Undo a committed run: remove .md, restore original to _drop, mark rolled_back.",
    )
    return p.parse_args()


def resolve_root(arg_root: Optional[Path]) -> Path:
    """Vault root: explicit arg or auto-detected 2 levels above this script."""
    if arg_root:
        return arg_root.resolve()
    # ingest.py  →  90 System/_ingestion_pipeline/  →  90 System/  →  vault root
    return Path(__file__).resolve().parent.parent.parent


def main() -> int:
    args = parse_args()
    root = resolve_root(args.root)

    # Ensure pipeline dir is on sys.path (idempotent)
    pipeline_dir = root / PIPELINE_SUBDIR
    if str(pipeline_dir) not in sys.path:
        sys.path.insert(0, str(pipeline_dir))

    vlog(f"[ingest] vault root: {root}", args.verbose)

    manifest_path = root / MANIFEST_REL
    manifest = ManifestStore(manifest_path)

    # ── Recover ────────────────────────────────────────────────────────────────
    if args.recover:
        do_recover(args.recover, root, manifest,
                   dry_run=args.dry_run, verbose=args.verbose)
        return 0

    # ── Rollback ───────────────────────────────────────────────────────────────
    if args.rollback:
        do_rollback(args.rollback, root, manifest,
                    dry_run=args.dry_run, verbose=args.verbose)
        return 0

    # ── Normal / dry-run / report-only ────────────────────────────────────────
    return run_pipeline(
        root,
        dry_run=(args.dry_run or args.report_only),  # report_only implies dry_run
        report_only=args.report_only,
        verbose=args.verbose,
        allow_cloud_ocr=args.allow_cloud_ocr,
        max_api_calls=args.max_api_calls,
    )


if __name__ == "__main__":
    sys.exit(main())
