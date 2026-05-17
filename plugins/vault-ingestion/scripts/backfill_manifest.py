#!/usr/bin/env python3
"""
backfill_manifest.py — One-shot manifest backfill for pre-pipeline .md files.

Purpose:
    Walk typed zones (50 Sources/, 40 Meetings/, 30 Projects/,
    70 Decisions/, 00 Inbox/) for .md files with `original_path:` frontmatter.
    Build ManifestEntry(status='committed', run_id='backfill-YYYY-MM-DD', ...)
    and append them to _manifest.jsonl so SHA-256 dedup can detect re-drops.

Usage:
    python3 backfill_manifest.py --dry-run    # scan + report, write nothing
    python3 backfill_manifest.py --commit     # append entries to manifest

Contract:  90 System/_ingestion_contract.md §11
Plan:      99 Workspace/_plan_ingestion_dedup_hardening_2026-05-16.html §S02
Authored:  2026-05-16 (S02 of dedup hardening plan)

Algorithm (§11):
    for each .md in typed zones:
        if no original_path: frontmatter → skip (not an ingested file)
        if md_path already in manifest → skip (idempotent)
        if pipeline.sha256: present → use as-is (sidecar)
        else → resolve original_path → sha256_file()
        if original not found → classify as orphan (no write)
        build entry: status=committed, extracted_at=null, supersedes=[]
        --dry-run: collect and report; --commit: append to manifest

Orphan classifications (require Ricardo decision before commit):
    legacy_path_unresolvable — original_path points to /Downloads/Galp/ and
        the file no longer exists at that path. Flag for retro-rewrite session.
    orphan_original_missing  — non-legacy path, original binary not found.
    orphan_no_sha            — binary found but sha256 computation failed.

Idempotency: safe to run twice — existing md_paths are detected and skipped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Vault root auto-detection:
#   backfill_manifest.py  →  90 System/_ingestion_pipeline/
#                         →  90 System/
#                         →  vault root
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_VAULT_ROOT = _SCRIPT_DIR.parent.parent

MANIFEST_REL      = "90 System/_ingestion_pipeline/_manifest.jsonl"
AUTO_WRITES_REL   = "99 Workspace/_auto_writes.md"
INGESTION_LOG_REL = "99 Workspace/_ingestion_log.md"

TYPED_ZONES = [
    "50 Sources",
    "40 Meetings",
    "30 Projects",
    "70 Decisions",
    "00 Inbox",
]

LEGACY_PATH_MARKER    = "/Downloads/Galp/"   # v1 absolute paths → flag for retro-rewrite
VAULT_RELATIVE_MARKER = "99 Workspace/_originals/"


# ===========================================================================
# Frontmatter parsing (YAML via PyYAML with plain-text fallback)
# ===========================================================================

def parse_frontmatter(path: Path) -> dict:
    """Parse YAML frontmatter from a .md file.  Returns {} on any failure."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}

    if not text.startswith("---"):
        return {}

    rest = text[3:]
    end  = rest.find("\n---")
    if end == -1:
        return {}
    yaml_block = rest[:end]

    try:
        import yaml  # PyYAML
        fm = yaml.safe_load(yaml_block)
        return fm if isinstance(fm, dict) else {}
    except Exception:
        pass

    # Plain-text fallback: flat key: value pairs only (no nested pipeline: block)
    result: dict = {}
    for line in yaml_block.splitlines():
        line = line.rstrip()
        if not line or line.startswith(" ") or line.startswith("\t"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        result[k.strip()] = v.strip().strip('"').strip("'")
    return result


# ===========================================================================
# SHA-256 helper (verbatim from ingest.py)
# ===========================================================================

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ===========================================================================
# Supersession stem (verbatim from ingest.py / contract §7.1)
# ===========================================================================

_SUPERSESSION_STRIP = re.compile(
    r"""(?ix)
    (
        [_\-\s]+v\d+(?:\.\d+)*
      | [_\-\s]+ver\d+(?:\.\d+)*
      | [_\-\s]+vPreread\d*
      | [_\-\s]+preread\d*
      | [_\-\s]+rev\d+
      | [_\-\s]+draft\d*
      | [_\-\s]+final
      | [_\-\s]+clean
      | [_\-\s]+\d{4}[_\-]?\d{2}[_\-]?\d{2}
      | [_\-\s]+\d{6,8}
      | [_\-\s]+\(\d+\)
      | [_\-\s]+copy\d*
    )+
    \s*$
    """,
)


def supersession_stem(filename: str) -> str:
    """Compute supersession stem (contract §7.1) — verbatim from ingest.py."""
    stem = Path(filename).stem
    prev = None
    while prev != stem:
        prev = stem
        stem = _SUPERSESSION_STRIP.sub("", stem).strip(" _-")
    return stem.lower()


def today_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ===========================================================================
# Manifest reader — load committed md_paths and sha256s
# ===========================================================================

def load_manifest(manifest_path: Path) -> tuple[set[str], set[str]]:
    """Returns (committed_md_paths, committed_sha256s) from the manifest."""
    md_paths: set[str] = set()
    sha256s:  set[str] = set()

    if not manifest_path.exists():
        return md_paths, sha256s

    with manifest_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("status") == "committed":
                if entry.get("md_path"):
                    md_paths.add(entry["md_path"])
                if entry.get("sha256"):
                    sha256s.add(entry["sha256"])

    return md_paths, sha256s


# ===========================================================================
# File result dataclass
# ===========================================================================

@dataclass
class FileResult:
    md_path:       str             # vault-relative path of the ingested .md
    original_path: str             # as found in frontmatter (may be legacy)
    source_file:   str             # source_file field or derived from original_path
    sha256:        Optional[str]   # None if unresolvable
    stem:          str             # supersession_stem value
    disposition:   str             # will_write | skipped_already_in_manifest |
                                   # legacy_path_unresolvable | orphan_original_missing |
                                   # orphan_no_sha
    sha_source:    str             # sidecar | recomputed | unavailable
    is_legacy:     bool            # original_path contains /Downloads/Galp/
    notes:         str = ""


# ===========================================================================
# Resolve original_path to an absolute filesystem Path
# ===========================================================================

def resolve_original(original_path_str: str, vault_root: Path) -> Optional[Path]:
    """Find the binary on disk.

    Handles:
      - Absolute paths (legacy v1): /Users/…/Downloads/Galp/…
      - Vault-relative paths (v2):  99 Workspace/_originals/…
    """
    if not original_path_str:
        return None

    p = Path(original_path_str)

    if p.is_absolute():
        return p if p.exists() else None

    # Vault-relative
    resolved = vault_root / p
    return resolved if resolved.exists() else None


# ===========================================================================
# Scan typed zones and classify every .md with original_path: frontmatter
# ===========================================================================

def scan(
    vault_root: Path,
    existing_md_paths: set[str],
    existing_sha256s: set[str],
    *,
    verbose: bool = False,
) -> list[FileResult]:
    results: list[FileResult] = []

    for zone in TYPED_ZONES:
        zone_path = vault_root / zone
        if not zone_path.exists():
            if verbose:
                print(f"  [scan] zone not found, skipping: {zone}")
            continue

        md_files = sorted(zone_path.rglob("*.md"))
        if verbose:
            print(f"  [scan] {zone}: {len(md_files)} .md files found")

        for md_file in md_files:
            # Skip anything inside a hidden directory
            rel_parts = md_file.relative_to(vault_root).parts
            if any(part.startswith(".") for part in rel_parts):
                continue

            fm = parse_frontmatter(md_file)
            original_path_str = fm.get("original_path", "") or ""

            if not original_path_str:
                continue  # Not a pipeline-ingested file — skip

            try:
                md_vault_rel = str(md_file.relative_to(vault_root))
            except ValueError:
                continue

            # ── Already in manifest? ──────────────────────────────────────
            if md_vault_rel in existing_md_paths:
                results.append(FileResult(
                    md_path=md_vault_rel,
                    original_path=original_path_str,
                    source_file=fm.get("source_file", "") or Path(original_path_str).name,
                    sha256=None,
                    stem="",
                    disposition="skipped_already_in_manifest",
                    sha_source="unavailable",
                    is_legacy=LEGACY_PATH_MARKER in original_path_str,
                    notes="already in manifest — skipped (idempotent)",
                ))
                continue

            is_legacy   = LEGACY_PATH_MARKER in original_path_str
            source_file = fm.get("source_file", "") or Path(original_path_str).name
            stem        = supersession_stem(source_file) if source_file else ""

            # ── Try sidecar SHA (pipeline.sha256) ─────────────────────────
            pipeline_fm = fm.get("pipeline", {})
            sidecar_sha = ""
            if isinstance(pipeline_fm, dict):
                sidecar_sha = pipeline_fm.get("sha256", "") or ""

            if sidecar_sha:
                results.append(FileResult(
                    md_path=md_vault_rel,
                    original_path=original_path_str,
                    source_file=source_file,
                    sha256=sidecar_sha,
                    stem=stem,
                    disposition="will_write",
                    sha_source="sidecar",
                    is_legacy=is_legacy,
                    notes="SHA from pipeline.sha256 frontmatter",
                ))
                continue

            # ── Recompute SHA from binary ──────────────────────────────────
            orig_path = resolve_original(original_path_str, vault_root)

            if orig_path is None:
                # Can't find the binary
                if is_legacy:
                    disposition = "legacy_path_unresolvable"
                    notes = f"legacy absolute path not found: {original_path_str}"
                else:
                    disposition = "orphan_original_missing"
                    notes = f"binary not found: {original_path_str}"
                results.append(FileResult(
                    md_path=md_vault_rel,
                    original_path=original_path_str,
                    source_file=source_file,
                    sha256=None,
                    stem=stem,
                    disposition=disposition,
                    sha_source="unavailable",
                    is_legacy=is_legacy,
                    notes=notes,
                ))
                continue

            try:
                sha = sha256_file(orig_path)
                notes = ""
                if sha in existing_sha256s:
                    notes = "SHA already in manifest for a different md_path (same binary, different extraction)"
                results.append(FileResult(
                    md_path=md_vault_rel,
                    original_path=original_path_str,
                    source_file=source_file,
                    sha256=sha,
                    stem=stem,
                    disposition="will_write",
                    sha_source="recomputed",
                    is_legacy=is_legacy,
                    notes=notes,
                ))
            except Exception as exc:
                results.append(FileResult(
                    md_path=md_vault_rel,
                    original_path=original_path_str,
                    source_file=source_file,
                    sha256=None,
                    stem=stem,
                    disposition="orphan_no_sha",
                    sha_source="unavailable",
                    is_legacy=is_legacy,
                    notes=f"sha256 error: {exc}",
                ))

    return results


# ===========================================================================
# Build a manifest entry dict (matches ManifestEntry.to_dict() schema)
# ===========================================================================

def build_entry(r: FileResult, run_id: str) -> dict:
    """Build a dict matching ingest.py's ManifestEntry.to_dict() schema.

    Per contract §11: extracted_at=null signals a backfill-reconstructed record.
    """
    return {
        "run_id":            run_id,
        "sha256":            r.sha256,
        "source_filename":   r.source_file,
        "supersession_stem": r.stem,
        "extracted_at":      None,      # null = backfill record (§11)
        "status":            "committed",
        "md_path":           r.md_path,
        "original_path":     r.original_path,
        "quarantine_reason": None,
        "supersedes":        [],
        "committed_at":      None,
        "manifest_offset":   None,
    }


# ===========================================================================
# Print the orphan list for Ricardo's review
# ===========================================================================

def print_orphan_list(
    legacy_unresolvable: list[FileResult],
    orphan_missing: list[FileResult],
    orphan_no_sha: list[FileResult],
) -> None:
    total = len(legacy_unresolvable) + len(orphan_missing) + len(orphan_no_sha)
    if total == 0:
        print("[backfill] No orphans — all originals resolved.")
        return

    print(f"\n{'=' * 70}")
    print(f"ORPHAN LIST — {total} file(s) requiring Ricardo decision")
    print(f"{'=' * 70}")

    if legacy_unresolvable:
        print(f"\n── Legacy path unresolvable ({len(legacy_unresolvable)}) ──")
        print("  original_path points to /Downloads/Galp/ but file not found on disk.")
        print("  Action options: (a) locate binary and update original_path,")
        print("                  (b) mark as text-only (write entry without SHA — NOT RECOMMENDED),")
        print("                  (c) skip this file for now (flag for retro-rewrite session).")
        for r in legacy_unresolvable:
            print(f"\n  MD:  {r.md_path}")
            print(f"  SRC: {r.original_path}")

    if orphan_missing:
        print(f"\n── Non-legacy original missing ({len(orphan_missing)}) ──")
        print("  original_path is vault-relative but binary not found.")
        print("  Action options: (a) restore the binary, (b) delete the .md, (c) mark text-only.")
        for r in orphan_missing:
            print(f"\n  MD:  {r.md_path}")
            print(f"  SRC: {r.original_path}")

    if orphan_no_sha:
        print(f"\n── SHA computation failed ({len(orphan_no_sha)}) ──")
        for r in orphan_no_sha:
            print(f"\n  MD:  {r.md_path}")
            print(f"  SRC: {r.original_path}")
            print(f"  ERR: {r.notes}")

    print(f"\n{'=' * 70}")
    print("Decide per-file before proceeding to --commit.")
    print(f"{'=' * 70}\n")


# ===========================================================================
# Main
# ===========================================================================

def main() -> int:
    p = argparse.ArgumentParser(
        prog="backfill_manifest.py",
        description="One-shot manifest backfill for pre-pipeline .md files (contract §11).",
        epilog=(
            "Examples:\n"
            "  python3 backfill_manifest.py --dry-run --verbose\n"
            "  python3 backfill_manifest.py --commit\n"
        ),
    )
    p.add_argument("--dry-run",  action="store_true",
                   help="Scan and report; write nothing.")
    p.add_argument("--commit",   action="store_true",
                   help="Append backfill entries to _manifest.jsonl.")
    p.add_argument("--root",     type=Path, default=None,
                   help="Vault root override (default: auto-detected from script location).")
    p.add_argument("--verbose",  action="store_true",
                   help="Per-file progress output.")
    args = p.parse_args()

    if not args.dry_run and not args.commit:
        print("ERROR: must specify --dry-run or --commit.", file=sys.stderr)
        return 1
    if args.dry_run and args.commit:
        print("ERROR: --dry-run and --commit are mutually exclusive.", file=sys.stderr)
        return 1

    vault_root    = args.root.resolve() if args.root else _VAULT_ROOT
    manifest_path = vault_root / MANIFEST_REL
    mode_tag      = "DRY-RUN" if args.dry_run else "COMMIT"

    print(f"[backfill] vault root  : {vault_root}")
    print(f"[backfill] manifest    : {manifest_path}")
    print(f"[backfill] mode        : {mode_tag}\n")

    # ── Load existing manifest ────────────────────────────────────────────────
    existing_md_paths, existing_sha256s = load_manifest(manifest_path)
    print(f"[backfill] existing manifest: {len(existing_md_paths)} committed md_paths, "
          f"{len(existing_sha256s)} committed SHA-256s\n")

    # ── Scan ──────────────────────────────────────────────────────────────────
    print("[backfill] scanning typed zones…")
    results = scan(
        vault_root, existing_md_paths, existing_sha256s, verbose=args.verbose
    )

    # ── Classify ─────────────────────────────────────────────────────────────
    will_write           = [r for r in results if r.disposition == "will_write"]
    skipped              = [r for r in results if r.disposition == "skipped_already_in_manifest"]
    legacy_unresolvable  = [r for r in results if r.disposition == "legacy_path_unresolvable"]
    orphan_missing       = [r for r in results if r.disposition == "orphan_original_missing"]
    orphan_no_sha        = [r for r in results if r.disposition == "orphan_no_sha"]

    sidecar_sha_count  = sum(1 for r in will_write if r.sha_source == "sidecar")
    recomputed_count   = sum(1 for r in will_write if r.sha_source == "recomputed")
    legacy_will_write  = [r for r in will_write if r.is_legacy]
    total_orphans      = len(legacy_unresolvable) + len(orphan_missing) + len(orphan_no_sha)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'=' * 66}")
    print(f"BACKFILL SUMMARY — {today_iso()}  [{mode_tag}]")
    print(f"{'=' * 66}")
    print(f"  Total .md with original_path:             {len(results)}")
    print(f"  Already in manifest (skipped):            {len(skipped)}")
    print(f"  ── Will write:                            {len(will_write)}")
    print(f"       SHA from sidecar (pipeline.sha256):  {sidecar_sha_count}")
    print(f"       SHA recomputed from binary:           {recomputed_count}")
    print(f"       Legacy paths (flagged, will write):  {len(legacy_will_write)}")
    print(f"  ── Orphans (NOT written):                 {total_orphans}")
    print(f"       Legacy path unresolvable:            {len(legacy_unresolvable)}")
    print(f"       Non-legacy original missing:         {len(orphan_missing)}")
    print(f"       SHA computation error:               {len(orphan_no_sha)}")
    print(f"{'=' * 66}\n")

    print_orphan_list(legacy_unresolvable, orphan_missing, orphan_no_sha)

    if args.verbose and will_write:
        print("\nWILL WRITE:")
        for r in will_write:
            flag = " [LEGACY-PATH]" if r.is_legacy else ""
            dup  = " [SHA-DUP]" if "already in manifest" in r.notes else ""
            print(f"  {r.sha_source:12s}  {r.md_path}{flag}{dup}")

    # ── Dry-run exit ──────────────────────────────────────────────────────────
    if args.dry_run:
        print("[backfill] DRY-RUN complete — nothing written.")
        return 0

    # ── Commit ────────────────────────────────────────────────────────────────
    if not will_write:
        print("[backfill] Nothing to commit.")
        return 0

    run_id = f"backfill-{today_iso()}"
    print(f"[backfill] appending {len(will_write)} entries (run_id={run_id})…")

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with manifest_path.open("a", encoding="utf-8") as f:
        for r in will_write:
            entry = build_entry(r, run_id)
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            written += 1

    print(f"[backfill] {written} entries appended to manifest.")

    # ── Log to _ingestion_log.md ──────────────────────────────────────────────
    log_path = vault_root / INGESTION_LOG_REL
    log_line = (
        f"\n## Backfill run — {today_iso()}\n\n"
        f"{len(results)} candidates walked; {written} entries written; "
        f"{len(skipped)} skipped (already in manifest); "
        f"{total_orphans} orphans skipped "
        f"({len(legacy_unresolvable)} legacy_unresolvable, "
        f"{len(orphan_missing)} original_missing, "
        f"{len(orphan_no_sha)} sha_error). "
        f"Run ID: {run_id}. "
        f"See _audit_2026-05-16_manifest_backfill.md for full detail.\n"
    )
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(log_line)
        print(f"[backfill] run summary appended to {log_path.name}")
    except Exception as exc:
        print(f"[backfill] WARN: could not write to {log_path}: {exc}")

    print(f"\n[backfill] COMMIT complete — {written} entries added to manifest.")
    print(f"           Orphans NOT written: {total_orphans} (see dry-run report for decisions).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
