#!/usr/bin/env python3
"""
curator.py — kb-curator orchestration script.

Maintains context-engineering hygiene of any project bootstrapped by the
companion cowork-preparation skill. Wraps the project's own _build_index.py
and _lint_frontmatter.py from cowork_outputs/ without modifying them. Adds
drift probes (orphan detection, log size, archive-in-working-zone, stale
index, superseded versions) on top.

Modes (mutually exclusive):
    audit            — read-only health check
    refresh-index    — runs _build_index.py for real, logs to _auto_writes.md
    propose-cleanup  — produces _cleanup_proposal_YYYY-MM-DD.md (NOT executed)
    rotate-logs      — produces _log_rotation_proposal_YYYY-MM-DD.md (NOT executed)

Project-root resolution (in order):
    1. --root /path/to/project CLI flag
    2. COWORK_ROOT environment variable
    3. Auto-detect: walk up from cwd looking for `CLAUDE.md` + `cowork_outputs/`

State file is discovered by frontmatter type (`type: state`), so this works
regardless of what the project names it (`_peninsula_current_state.md`,
`_secil_current_state.md`, `_state.md`, etc.). Same for handoff (`type: handoff`).

Usage:
    python3 curator.py audit
    python3 curator.py refresh-index --root /path/to/project
    COWORK_ROOT=/path/to/project python3 curator.py propose-cleanup
    python3 curator.py rotate-logs

Hard guardrails (enforced by NEVER calling the relevant operations):
    - No content edits to any document.
    - No edits to CLAUDE.md or any state file.
    - No deletes, ever.
    - No moves outside cowork_outputs/ — propose only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# ---- Substrate detection (sibling script) ---------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect_substrate as _detect_substrate_mod  # noqa: E402

def _detect_substrate(root: Path) -> tuple[str, list[str]]:
    """Thin wrapper around detect_substrate.detect() for use inside curator."""
    return _detect_substrate_mod.detect(str(root))

# ---- Project root resolution ----------------------------------------------

def auto_detect_root() -> Path | None:
    """Walk up from cwd looking for a folder containing CLAUDE.md (works for both FLAT and OBSIDIAN)."""
    cur = Path.cwd().resolve()
    for cand in [cur, *cur.parents]:
        if (cand / "CLAUDE.md").is_file():
            return cand
    return None

def resolve_root(cli_root: str | None) -> Path:
    if cli_root:
        root = Path(cli_root).expanduser().resolve()
    elif os.environ.get("COWORK_ROOT"):
        root = Path(os.environ["COWORK_ROOT"]).expanduser().resolve()
    else:
        root = auto_detect_root()
        if root is None:
            print("ERROR: could not auto-detect project root.", file=sys.stderr)
            print("Run from inside a project folder (CLAUDE.md + cowork_outputs/), or pass --root, or set COWORK_ROOT.", file=sys.stderr)
            sys.exit(2)
    if not root.is_dir():
        print(f"ERROR: project root not found: {root}", file=sys.stderr)
        sys.exit(2)
    # cowork_outputs/ check deferred to FLAT branch in main() — OBSIDIAN vaults
    # don't have cowork_outputs/ and must reach substrate dispatch first.
    if not (root / "CLAUDE.md").is_file():
        print(f"WARNING: no CLAUDE.md at {root} — proceeding but the project may not be bootstrapped properly.", file=sys.stderr)
    return root

# ---- Thresholds (universal across projects) -------------------------------

THRESH_HANDOFF_KB = 15
THRESH_CLAUDEMD_KB = 12
THRESH_STATE_KB = 120
THRESH_INDEX_AGE_DAYS = 7
THRESH_CLEANUP_LOG_KB = 200
THRESH_AUTO_WRITES_KB = 80
THRESH_COWORK_ITEM_COUNT = 250  # matches _guide_context_engineering.md P-10

# Promotion (P-10 routing) — file must be at least this old before promoting.
# Override per-project with COWORK_PROMOTE_AGE_DAYS env var. The cowork-
# preparation guide doesn't mandate a number; 14d is a kb-curator default.
THRESH_PROMOTE_AGE_DAYS = int(os.environ.get("COWORK_PROMOTE_AGE_DAYS", "14"))

# ---- Promotion routing map (P-10 classification) --------------------------
# Frontmatter `type:` value -> destination zone (relative to project root).
# Mirrors the table in _guide_context_engineering.md P-10. Keys are restricted
# to the canonical type vocabulary enforced by cowork_outputs/_lint_frontmatter.py
# (KNOWN_TYPES). `template` is intentionally absent — templates are identified
# by filename prefix and zone, not by frontmatter type (lint would warn).
PROMOTION_MAP = {
    "meeting_debrief":    "05_Knowledge_Base/debriefs",
    "debrief":            "05_Knowledge_Base/debriefs",
    "battleplan":         "05_Knowledge_Base/battleplans",
    "briefing":           "05_Knowledge_Base/battleplans",
    "audit":              "05_Knowledge_Base/audits",
    "analysis":           "05_Knowledge_Base/analysis",
    "strategic":          "05_Knowledge_Base/analysis",
    "sixpager":           "05_Knowledge_Base/analysis",
    "feedback_pack":      "05_Knowledge_Base/analysis",
    "adversarial_review": "05_Knowledge_Base/analysis",
    "prd":                "05_Knowledge_Base/analysis",
    "extraction":         "05_Knowledge_Base/extractions",
    "concept_note":       "05_Knowledge_Base/extractions",
    "data_companion":     "05_Knowledge_Base/extractions",
    "deepdive":           "05_Knowledge_Base/extractions",
    "deliverable":        "02_Final_Deliverables",
}

# Polished binary deliverables -> 02_Final_Deliverables/, EXCEPT when the
# filename matches a template prefix below — then -> 06_Templates/.
BINARY_PROMOTION_EXTS = {".docx", ".pptx", ".xlsx", ".pdf", ".html"}
BINARY_DESTINATION = "02_Final_Deliverables"

# Filename prefixes that indicate a brand asset / master template. Routed to
# 06_Templates/ regardless of extension. Per cowork-preparation P-10 ("Template
# / brand asset" -> 06_Templates/).
TEMPLATE_FILENAME_PREFIXES = ("template_", "master_", "brand_")
TEMPLATE_DESTINATION = "06_Templates"

# Filename prefixes that indicate "done" content (used when frontmatter is
# absent or routes nowhere). A file whose name starts with one of these AND is
# older than the promotion-age threshold is treated as promotable.
# Mirrors retrofit's TYPE_HEURISTICS plus P-10's `YYYY_NNN_*.md` audit pattern.
DONE_FILENAME_PREFIXES = ("meeting_debrief_", "battleplan_", "audit_")
AUDIT_FILENAME_REGEX = re.compile(r"^\d{4}_\d{3}_.*\.md$")  # P-10 audit extraction pattern

# Frontmatter `type:` values that should NEVER be promoted regardless of cadence.
# These are operational types tied to pinned files; if a content file is
# accidentally tagged with one, treat it as misconfigured (block, surface in
# the unclassified section).
NON_PROMOTABLE_TYPES = {
    "guide", "state", "handoff", "eval",
    "log", "cleanup-log", "archive",
}

# Cadence vocabulary alignment with cowork_outputs/_lint_frontmatter.py
# KNOWN_CADENCES = {stable, weekly, monthly, event-driven, per-session,
#                   continuous, append-only, monthly-or-on-structural-change}
#
# Promotion semantics:
# - Operational cadences (per-session, continuous, append-only) belong on
#   pinned files only. If a non-pinned file has one, it's misconfigured —
#   block it.
# - Every other recognised cadence becomes promotable once age >= threshold,
#   because doneness is signalled by age (no recent updates), not by cadence
#   label. A meeting debrief retrofitted as `cadence: event-driven` should be
#   promoted once it stops being touched — exactly what a finished debrief
#   looks like.
OPERATIONAL_CADENCES = {"per-session", "continuous", "append-only"}
PROMOTABLE_CADENCES = {
    "stable", "weekly", "monthly", "event-driven",
    "monthly-or-on-structural-change",
}

# ---- Pinned files (never propose to move) ---------------------------------

PINNED_NAMES = {
    "_session_handoff.md",
    "_index.md",
    "_index_errors.log",
    "_auto_writes.md",
    "_cleanup_log.md",
    "_retrofit_log.md",          # produced by _retrofit_frontmatter.py --apply --log
    "_build_index.py",
    "_lint_frontmatter.py",
    "_retrofit_frontmatter.py",
    "_run_retrieval_eval.py",
}
PINNED_PREFIXES = (
    "_guide_", "_eval_", "_index_",                # core operational layer
    "_audit_",                                     # daily audit reports
    "_cleanup_proposal_", "_log_rotation_proposal_",  # cleanup-mode artefacts
    "_upgrade_audit_", "_upgrade_proposal_",       # upgrade-mode artefacts (v2.2)
    "_approval_packet_",                           # ad-hoc approval packets (v2.2)
    "_automation_setup_",                          # setup-automation mode artefacts (v2.2)
    "_cleanup_dryrun_", "_revert_log_",            # dryrun + revert artefacts (v2.2)
    "_synthesis_",                                 # ad-hoc synthesis artefacts (v2.2)
    "_session_handoff_archive",                    # handoff archive folder marker
)

# ---- Helpers --------------------------------------------------------------

def kb(p: Path) -> int:
    return p.stat().st_size // 1024 if p.exists() else 0

def days_since(p: Path) -> int:
    if not p.exists():
        return -1
    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return (datetime.now(tz=timezone.utc) - mtime).days

def today_iso() -> str:
    return date.today().isoformat()

def discover_by_type(cowork_dir: Path, target_type: str,
                     filename_fallback_glob: str | None = None) -> Path | None:
    """Find first .md file in cowork_dir whose frontmatter type == target_type.

    If no match and filename_fallback_glob is provided, fall back to filename
    pattern (e.g. `_*_current_state.md`) — this handles legacy projects whose
    state file predates the `type: state` convention and uses `type: strategic`
    or similar."""
    for f in sorted(cowork_dir.glob("*.md")):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        if end == -1:
            continue
        block = text[3:end]
        for line in block.splitlines():
            s = line.strip()
            if s.startswith("type:"):
                val = s.split(":", 1)[1].strip().strip('"').strip("'")
                if val == target_type:
                    return f
                break
    if filename_fallback_glob:
        matches = sorted(cowork_dir.glob(filename_fallback_glob))
        if matches:
            return matches[0]
    return None

def is_pinned(name: str, state_file_name: str | None) -> bool:
    if name in PINNED_NAMES:
        return True
    if any(name.startswith(p) for p in PINNED_PREFIXES):
        return True
    if state_file_name and name == state_file_name:
        return True
    return False

# ---- Frontmatter + doneness ------------------------------------------------

def read_frontmatter(path: Path) -> dict | None:
    """Parse YAML-ish frontmatter from a markdown file.

    Returns dict on success, None if absent or malformed. Same forgiving
    parser style as _build_index.py — single-line key:value pairs only.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm: dict[str, str] = {}
    for line in text[3:end].splitlines():
        s = line.strip()
        if not s or s.startswith("#") or ":" not in s:
            continue
        k, _, v = s.partition(":")
        fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm

def days_old(p: Path, fm: dict | None = None) -> int:
    """Days since frontmatter `last_updated` (preferred) or filesystem mtime."""
    if fm and fm.get("last_updated"):
        try:
            d = datetime.fromisoformat(fm["last_updated"])
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return (datetime.now(tz=timezone.utc) - d).days
        except (ValueError, TypeError):
            pass
    return days_since(p)

def has_done_filename(name: str) -> bool:
    """True if filename matches a known 'done' pattern from cowork-preparation.

    Mirrors retrofit's TYPE_HEURISTICS plus P-10's `YYYY_NNN_*.md` audit pattern.
    Used as a fallback when frontmatter is absent or its cadence is unset.
    """
    if any(name.startswith(pre) for pre in DONE_FILENAME_PREFIXES):
        return True
    if AUDIT_FILENAME_REGEX.match(name):
        return True
    return False

def is_promotable(path: Path, fm: dict | None) -> tuple[bool, str]:
    """Doneness gate aligned with cowork-preparation cadence semantics.

    Core insight: age (no recent updates) is the signal a file is finished —
    not the cadence label. cowork-preparation's retrofit assigns
    `cadence: event-driven` to meeting debriefs by default, and a debrief that
    has had no follow-up events for 14+ days is exactly what a finished debrief
    looks like. So `event-driven` files ARE promotable when old enough.

    Rules (a non-pinned file is promotable when):
      1. Not flagged `archived_reference: true`.
      2. Cadence is in PROMOTABLE_CADENCES (stable, weekly, monthly, event-driven,
         monthly-or-on-structural-change), OR cadence is empty/unset and the
         filename matches a 'done' pattern (DONE_FILENAME_PREFIXES /
         AUDIT_FILENAME_REGEX).
      3. age >= THRESH_PROMOTE_AGE_DAYS.

    Vetoes (any one blocks):
      - `archived_reference: true`.
      - cadence in OPERATIONAL_CADENCES (per-session, continuous, append-only) —
        these belong on pinned files; on a non-pinned file they signal
        misconfiguration.
      - age below threshold.
      - cadence outside the canonical vocabulary AND no done-prefix fallback.
    """
    age = days_old(path, fm)
    has_done_name = has_done_filename(path.name)

    if fm is None:
        # No frontmatter — only the filename-pattern path can rescue it.
        if has_done_name and age >= THRESH_PROMOTE_AGE_DAYS:
            return True, f"done-prefix, {age}d old (no frontmatter)"
        if has_done_name:
            return False, f"done-prefix but only {age}d old"
        return False, "no frontmatter"

    if fm.get("archived_reference", "").lower() == "true":
        return False, "archived_reference flag"

    cadence = fm.get("cadence", "").lower()

    # Hard veto for operational cadences on non-pinned files.
    if cadence in OPERATIONAL_CADENCES:
        return False, f"cadence:{cadence} (operational, not promotable)"

    if age < THRESH_PROMOTE_AGE_DAYS:
        return False, f"only {age}d old (threshold {THRESH_PROMOTE_AGE_DAYS}d)"

    if cadence in PROMOTABLE_CADENCES:
        return True, f"cadence:{cadence}, {age}d old"

    # Cadence empty or unrecognised — fall back to filename pattern.
    if has_done_name:
        return True, f"done-prefix, {age}d old"

    return False, f"cadence:{cadence or '(unset)'}, no rule matched"

# Directories the cross-reference grep must skip. Mirrors the SKIP_DIRS in
# cowork-preparation's _build_index.py and _lint_frontmatter.py — same privacy
# and noise discipline (HR docs out of scope, audio binaries irrelevant, vcs
# and tooling caches not content).
GREP_SKIP_DIRS = {
    "01_Personal_HR",
    "04_Meeting_Recordings",
    ".git",
    "node_modules",
    "__pycache__",
}

def grep_references(filename: str, root: Path, pinned_names: set[str]) -> list[str]:
    """Find non-pinned .md files that mention `filename` anywhere in their text.

    Uses a word-boundary regex (re.escape on the filename + boundary check)
    rather than a naive substring match. Avoids false positives where e.g.
    `x.md` matches against `xx.md`.

    Skips the same top-level directories cowork-preparation excludes:
    01_Personal_HR/, 04_Meeting_Recordings/, .git/, node_modules/,
    __pycache__/. Privacy-critical: HR is explicitly out of scope per the
    cowork-preparation contract.
    """
    refs = []
    pattern = re.compile(rf"(?<![A-Za-z0-9_\-]){re.escape(filename)}(?![A-Za-z0-9_\-])")
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if d not in GREP_SKIP_DIRS and not d.startswith(".")
            ]
            for fname in filenames:
                if not fname.endswith(".md"):
                    continue
                if fname == filename:
                    continue
                if fname in pinned_names:
                    continue
                if any(fname.startswith(pre) for pre in PINNED_PREFIXES):
                    continue
                md_path = Path(dirpath) / fname
                try:
                    text = md_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if pattern.search(text):
                    refs.append(str(md_path.relative_to(root)))
    except OSError:
        pass
    return refs


# ---- Contract config -------------------------------------------------------

CONTRACT_FILENAME = "_cowork_contract.json"

def load_contract(root: Path) -> dict | None:
    """Read `_cowork_contract.json` from project root if present.

    Returns the parsed dict, or None if absent or unparseable. Never raises.
    """
    cf = root / CONTRACT_FILENAME
    if not cf.exists():
        return None
    try:
        import json as _json
        return _json.loads(cf.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

def apply_contract_thresholds(contract: dict | None) -> None:
    """Override the module-level threshold globals from contract.thresholds.

    Falls back to env-var or hard-coded defaults if a key is missing.
    Called once at main() entry, before any mode runs.
    """
    if not contract:
        return
    th = contract.get("thresholds", {})
    if not isinstance(th, dict):
        return
    global THRESH_PROMOTE_AGE_DAYS, THRESH_HANDOFF_KB, THRESH_CLAUDEMD_KB
    global THRESH_STATE_KB, THRESH_INDEX_AGE_DAYS, THRESH_CLEANUP_LOG_KB
    global THRESH_AUTO_WRITES_KB, THRESH_COWORK_ITEM_COUNT
    THRESH_PROMOTE_AGE_DAYS = int(th.get("promote_age_days", THRESH_PROMOTE_AGE_DAYS))
    THRESH_HANDOFF_KB = int(th.get("handoff_kb", THRESH_HANDOFF_KB))
    THRESH_CLAUDEMD_KB = int(th.get("claudemd_kb", THRESH_CLAUDEMD_KB))
    THRESH_STATE_KB = int(th.get("state_kb", THRESH_STATE_KB))
    THRESH_INDEX_AGE_DAYS = int(th.get("index_age_days", THRESH_INDEX_AGE_DAYS))
    THRESH_CLEANUP_LOG_KB = int(th.get("cleanup_log_kb", THRESH_CLEANUP_LOG_KB))
    THRESH_AUTO_WRITES_KB = int(th.get("auto_writes_kb", THRESH_AUTO_WRITES_KB))
    THRESH_COWORK_ITEM_COUNT = int(th.get("cowork_item_count", THRESH_COWORK_ITEM_COUNT))


class Project:
    def __init__(self, root: Path):
        self.root = root
        self.cowork = root / "cowork_outputs"
        self.build_index = self.cowork / "_build_index.py"
        self.lint_fm = self.cowork / "_lint_frontmatter.py"
        self.index = self.cowork / "_index.md"
        self.cleanup_log = self.cowork / "_cleanup_log.md"
        self.auto_writes = self.cowork / "_auto_writes.md"
        self.handoff = self.cowork / "_session_handoff.md"
        self.claude_md = self.root / "CLAUDE.md"
        # Discover state file by frontmatter type (project-name-agnostic)
        self.state = discover_by_type(self.cowork, "state", "_*_current_state.md")

    def cowork_root_md(self) -> list[Path]:
        return sorted(p for p in self.cowork.iterdir() if p.is_file() and p.suffix == ".md")

    def cowork_root_binaries(self) -> list[Path]:
        """Polished deliverables sitting in cowork_outputs/ (top level only)."""
        return sorted(
            p for p in self.cowork.iterdir()
            if p.is_file() and p.suffix.lower() in BINARY_PROMOTION_EXTS
        )

    def files_in_index(self) -> set[str]:
        """Pull filenames from _index.md AND any _index_*.md shard files."""
        names: set[str] = set()
        if not self.index.exists():
            return names
        text = self.index.read_text(encoding="utf-8", errors="replace")
        names.update(re.findall(r"([A-Za-z0-9_\-./]+\.md)", text))
        for shard in self.cowork.glob("_index_*.md"):
            if shard.name == "_index_errors.log":
                continue
            shard_text = shard.read_text(encoding="utf-8", errors="replace")
            names.update(re.findall(r"([A-Za-z0-9_\-./]+\.md)", shard_text))
        return names

# ---- Probes ---------------------------------------------------------------

def probe_index_age(P: Project) -> tuple[bool, str]:
    age = days_since(P.index)
    if age < 0:
        return True, "Index missing entirely (run refresh-index)"
    if age > THRESH_INDEX_AGE_DAYS:
        return True, f"Index is {age} days old (threshold: {THRESH_INDEX_AGE_DAYS}d)"
    return False, f"Index age OK ({age}d)"

def probe_orphans(P: Project) -> tuple[bool, list[str]]:
    referenced = {Path(r).name for r in P.files_in_index()}
    state_name = P.state.name if P.state else None
    orphans = []
    for f in P.cowork_root_md():
        if is_pinned(f.name, state_name):
            continue
        if f.name not in referenced:
            orphans.append(f.name)
    return (len(orphans) > 0, orphans)

def probe_log_sizes(P: Project) -> list[str]:
    flags = []
    if kb(P.cleanup_log) > THRESH_CLEANUP_LOG_KB:
        flags.append(f"_cleanup_log.md = {kb(P.cleanup_log)} KB > {THRESH_CLEANUP_LOG_KB} KB threshold")
    if kb(P.auto_writes) > THRESH_AUTO_WRITES_KB:
        flags.append(f"_auto_writes.md = {kb(P.auto_writes)} KB > {THRESH_AUTO_WRITES_KB} KB threshold")
    return flags

def probe_file_size_flags(P: Project) -> list[str]:
    flags = []
    if kb(P.handoff) > THRESH_HANDOFF_KB:
        flags.append(f"_session_handoff.md = {kb(P.handoff)} KB > {THRESH_HANDOFF_KB} KB (P-1.2)")
    if kb(P.claude_md) > THRESH_CLAUDEMD_KB:
        flags.append(f"CLAUDE.md = {kb(P.claude_md)} KB > {THRESH_CLAUDEMD_KB} KB (P-1.2)")
    if P.state and kb(P.state) > THRESH_STATE_KB:
        flags.append(f"{P.state.name} = {kb(P.state)} KB > {THRESH_STATE_KB} KB (compress soon)")
    return flags

def probe_archive_in_working(P: Project) -> list[str]:
    flags = []
    for f in P.cowork_root_md():
        if "_archive_" in f.name:
            flags.append(f"{f.name} ({kb(f)} KB) — archive file in working zone, belongs under _archive/")
    return flags

def probe_superseded_versions(P: Project) -> list[str]:
    flags = []
    versioned: dict[str, list[tuple[int, Path]]] = {}
    for f in P.cowork_root_md():
        m = re.match(r"(.+)_v(\d+)(?:\.\d+)?\.md$", f.name)
        if not m:
            continue
        stem, ver = m.group(1), int(m.group(2))
        versioned.setdefault(stem, []).append((ver, f))
    for stem, items in versioned.items():
        if len(items) < 2:
            continue
        items.sort()
        latest_ver = items[-1][0]
        for ver, f in items[:-1]:
            flags.append(f"{f.name} (v{ver}) superseded by v{latest_ver} — candidate for _archive/")
    return flags

def probe_type_other(P: Project) -> list[str]:
    """List files in working zone with frontmatter `type: other` — the unclassified backlog."""
    state_name = P.state.name if P.state else None
    hits = []
    for f in P.cowork_root_md():
        if is_pinned(f.name, state_name):
            continue
        fm = read_frontmatter(f)
        if not fm:
            continue
        if (fm.get("type", "").strip().lower() == "other"):
            hits.append(f.name)
    return hits

def probe_promotion_candidates(P: Project) -> tuple[list[str], list[str], list[str]]:
    """Return (md_candidates, binary_candidates, template_candidates).

    md_candidates: markdown files routed to 05_Knowledge_Base/* — frontmatter
        `type:` in PROMOTION_MAP, OR filename matches a done-pattern, AND
        passes is_promotable.
    binary_candidates: .docx/.pptx/.xlsx/.pdf/.html in working zone older than
        THRESH_PROMOTE_AGE_DAYS, NOT matching a template prefix.
    template_candidates: any extension, filename matching template_/master_/
        brand_ prefix, older than THRESH_PROMOTE_AGE_DAYS (md also doneness-
        gated). Routed to 06_Templates/.
    """
    state_name = P.state.name if P.state else None
    md_hits: list[str] = []
    bin_hits: list[str] = []
    tpl_hits: list[str] = []

    # Superseded set — these are archive-candidates, not promotion-candidates.
    superseded_names: set[str] = set()
    versioned_pre: dict[str, list[tuple[int, Path]]] = {}
    for f in P.cowork_root_md():
        m = re.match(r"(.+)_v(\d+)(?:\.\d+)?\.md$", f.name)
        if not m:
            continue
        stem, ver = m.group(1), int(m.group(2))
        versioned_pre.setdefault(stem, []).append((ver, f))
    for stem, items in versioned_pre.items():
        if len(items) < 2:
            continue
        items.sort()
        for ver, f in items[:-1]:
            superseded_names.add(f.name)

    def has_template_prefix(name: str) -> bool:
        return any(name.startswith(pre) for pre in TEMPLATE_FILENAME_PREFIXES)

    for f in P.cowork_root_md():
        if is_pinned(f.name, state_name):
            continue
        if "_archive_" in f.name:
            continue
        if f.name in superseded_names:
            continue
        fm = read_frontmatter(f)
        ftype = (fm or {}).get("type", "").strip().lower()
        if ftype in NON_PROMOTABLE_TYPES:
            continue
        if has_template_prefix(f.name):
            ok, _ = is_promotable(f, fm)
            if ok:
                tpl_hits.append(f.name)
            continue
        is_routable = ftype in PROMOTION_MAP or has_done_filename(f.name)
        if not is_routable:
            continue
        ok, _ = is_promotable(f, fm)
        if ok:
            md_hits.append(f.name)

    for f in P.cowork_root_binaries():
        if days_since(f) < THRESH_PROMOTE_AGE_DAYS:
            continue
        if has_template_prefix(f.name):
            tpl_hits.append(f.name)
        else:
            bin_hits.append(f.name)

    return md_hits, bin_hits, tpl_hits

def probe_lint(P: Project) -> tuple[int, int, str]:
    if not P.lint_fm.exists():
        return 0, 0, "lint script missing"
    try:
        r = subprocess.run(
            ["python3", str(P.lint_fm), "--scope", "cowork", "--root", str(P.root)],
            capture_output=True, text=True, timeout=30,
        )
        out = r.stdout + r.stderr
        errs = sum(1 for ln in out.splitlines() if "ERROR" in ln)
        warns = sum(1 for ln in out.splitlines() if "WARN" in ln)
        summary = next((ln for ln in reversed(out.splitlines()) if ln.strip()), "no output")
        return errs, warns, summary
    except subprocess.TimeoutExpired:
        return -1, -1, "lint timed out"

# ---- Mode: audit ----------------------------------------------------------

def mode_audit(P: Project) -> int:
    out_path = P.cowork / f"_audit_{today_iso()}_kb_health.md"

    age_flag, age_msg = probe_index_age(P)
    orphan_flag, orphans = probe_orphans(P)
    log_flags = probe_log_sizes(P)
    size_flags = probe_file_size_flags(P)
    archive_flags = probe_archive_in_working(P)
    super_flags = probe_superseded_versions(P)
    lint_errs, lint_warns, lint_summary = probe_lint(P)
    promo_md, promo_bin, promo_tpl = probe_promotion_candidates(P)
    other_hits = probe_type_other(P)
    pending_lessons = probe_pending_lessons(P)

    state_label = P.state.name if P.state else "(none discovered — does the project have a `type: state` file?)"

    lines = [
        "---",
        f"name: KB Health Audit — {today_iso()}",
        "description: Mechanical drift signals from kb-curator audit mode. READ-ONLY — no edits made.",
        "type: audit",
        "cadence: one-off",
        f"last_updated: {today_iso()}",
        "---",
        "",
        f"# KB Health Audit — {today_iso()}",
        "",
        f"Project root: `{P.root}`",
        f"State file detected: `{state_label}`",
        "",
        "## 1. Index freshness",
        f"- {age_msg}",
        "",
        "## 2. Index completeness (orphan check)",
    ]
    if orphan_flag:
        lines.append(f"- **{len(orphans)} orphan files** in `cowork_outputs/` not referenced by `_index.md`:")
        for o in orphans[:20]:
            lines.append(f"  - {o}")
        if len(orphans) > 20:
            lines.append(f"  - ... and {len(orphans)-20} more")
        lines.append("- **Fix:** run `kb-curator refresh-index`.")
    else:
        lines.append("- No orphans detected.")
    lines.append("")

    lines.append("## 3. Frontmatter compliance")
    lines.append(f"- Lint summary: {lint_summary}")
    lines.append(f"- Errors: {lint_errs}, Warnings: {lint_warns}")
    lines.append("")

    lines.append("## 4. File-size flags (P-1.2)")
    if size_flags:
        for f in size_flags:
            lines.append(f"- {f}")
    else:
        lines.append("- All sizes within thresholds.")
    lines.append("")

    lines.append("## 5. Log-rotation flags")
    if log_flags:
        for f in log_flags:
            lines.append(f"- {f}")
        lines.append("- **Fix:** run `kb-curator rotate-logs`.")
    else:
        lines.append("- All logs within thresholds.")
    lines.append("")

    lines.append("## 6. Archive files in working zone")
    if archive_flags:
        for f in archive_flags:
            lines.append(f"- {f}")
        lines.append("- **Fix:** include in next `kb-curator propose-cleanup`.")
    else:
        lines.append("- None.")
    lines.append("")

    lines.append("## 7. Superseded version pairs")
    if super_flags:
        for f in super_flags:
            lines.append(f"- {f}")
        lines.append("- **Fix:** include in next `kb-curator propose-cleanup`.")
    else:
        lines.append("- None.")
    lines.append("")

    lines.append("## 8. Promotion candidates (P-10 routing)")
    total_promo = len(promo_md) + len(promo_bin) + len(promo_tpl)
    if total_promo:
        lines.append(
            f"- **{total_promo} files** in working zone pass the doneness gate "
            f"({len(promo_md)} → 05_Knowledge_Base/, {len(promo_bin)} → 02_Final_Deliverables/, "
            f"{len(promo_tpl)} → 06_Templates/). All are at least "
            f"{THRESH_PROMOTE_AGE_DAYS} days old."
        )
        for n in promo_md[:10]:
            lines.append(f"  - {n} (knowledge)")
        if len(promo_md) > 10:
            lines.append(f"  - ... and {len(promo_md)-10} more knowledge")
        for n in promo_bin[:5]:
            lines.append(f"  - {n} (deliverable → 02_Final_Deliverables/)")
        if len(promo_bin) > 5:
            lines.append(f"  - ... and {len(promo_bin)-5} more deliverables")
        for n in promo_tpl[:5]:
            lines.append(f"  - {n} (template → 06_Templates/)")
        if len(promo_tpl) > 5:
            lines.append(f"  - ... and {len(promo_tpl)-5} more templates")
        lines.append("- **Fix:** run `kb-curator propose-cleanup`.")
    else:
        lines.append("- No files in working zone are ready for promotion.")
    lines.append("")

    lines.append("## 10. Reflection log: lessons ready to promote")
    if pending_lessons:
        lines.append(f"- **{len(pending_lessons)} entries** in `_reflection_log.md` carry `status: applied-twice` — ready for promotion to `_lessons.md`.")
        for e in pending_lessons[:5]:
            lines.append(f"  - {e['header']}")
        if len(pending_lessons) > 5:
            lines.append(f"  - ... and {len(pending_lessons)-5} more")
        lines.append("- **Fix:** run `kb-curator promote-lesson`.")
    else:
        lines.append("- No entries ready for promotion.")
    lines.append("")

    lines.append("## 9. Unclassified backlog (type: other)")
    if other_hits:
        lines.append(f"- **{len(other_hits)} files** carry `type: other`. Each is a deferred classification decision.")
        for n in other_hits[:10]:
            lines.append(f"  - {n}")
        if len(other_hits) > 10:
            lines.append(f"  - ... and {len(other_hits)-10} more")
        lines.append("- **Fix:** open each file and replace `type: other` with the correct canonical type (or move it to `_archive/` if no longer relevant).")
    else:
        lines.append("- None.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(tz=timezone.utc).isoformat()} by kb-curator_")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path.relative_to(P.root)}")
    print(
        f"  index_age_flag={age_flag}  orphans={len(orphans)}  log_flags={len(log_flags)}  "
        f"size_flags={len(size_flags)}  archive_flags={len(archive_flags)}  super_flags={len(super_flags)}  "
        f"lint_errs={lint_errs}  promo_md={len(promo_md)}  promo_bin={len(promo_bin)}  promo_tpl={len(promo_tpl)}  type_other={len(other_hits)}  pending_lessons={len(pending_lessons)}"
    )
    return 0

# ---- Mode: refresh-index --------------------------------------------------

def mode_refresh_index(P: Project) -> int:
    if not P.build_index.exists():
        print(f"ERROR: {P.build_index} missing", file=sys.stderr)
        return 2
    r = subprocess.run(
        ["python3", str(P.build_index)],
        capture_output=True, text=True, timeout=60, cwd=str(P.cowork),
    )
    print(r.stdout, end="")
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return r.returncode
    stamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M")
    line = f"{stamp}  rebuild  cowork_outputs/_index.md  kb-curator refresh-index\n"
    with P.auto_writes.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return 0

# ---- Mode: propose-cleanup ------------------------------------------------

def mode_propose_cleanup(P: Project) -> int:
    """Generate full P-10 cleanup proposal.

    Six categories of move are considered, in priority order:
      1. Promotion of finished .md by frontmatter `type:` -> 05_Knowledge_Base/* or 06_Templates/.
      2. Promotion of polished binary deliverables (.docx/.pptx/.xlsx/.pdf/.html) -> 02_Final_Deliverables/.
      3. Quarterly state archives matching _*_archive_*.md -> _archive/state_archives/.
      4. Superseded version pairs (*_v\\d+\\.md where higher v exists) -> _archive/superseded/.
      5. Candidates with `type:` in PROMOTION_MAP that fail the doneness gate are
         listed under "In-flight (not ready)" so the user knows what's pending.
      6. Files with no frontmatter or unrecognised type are listed under
         "Needs review" — never auto-routed.
    """
    out_path = P.cowork / f"_cleanup_proposal_{today_iso()}.md"

    state_name = P.state.name if P.state else None
    pinned_set = set(PINNED_NAMES)
    if state_name:
        pinned_set.add(state_name)

    promotions: list[tuple[str, str, str, str, str]] = []      # src, type, dst, doneness, refs
    binary_promotions: list[tuple[str, str, str, str]] = []    # src, dst, age, refs
    template_promotions: list[tuple[str, str, str, str, str]] = []  # src, kind, dst, age, refs
    archive_moves: list[tuple[str, str, str]] = []             # src, dst, why
    superseded_moves: list[tuple[str, str, str]] = []          # src, dst, why
    inflight: list[tuple[str, str, str]] = []                  # src, type, reason
    unclassified: list[tuple[str, str]] = []                   # src, reason

    # ---- Pre-pass: compute superseded set so promotion walk skips them ----
    superseded_names: set[str] = set()
    versioned_pre: dict[str, list[tuple[int, Path]]] = {}
    for f in P.cowork_root_md():
        m = re.match(r"(.+)_v(\d+)(?:\.\d+)?\.md$", f.name)
        if not m:
            continue
        stem, ver = m.group(1), int(m.group(2))
        versioned_pre.setdefault(stem, []).append((ver, f))
    for stem, items in versioned_pre.items():
        if len(items) < 2:
            continue
        items.sort()
        for ver, f in items[:-1]:
            superseded_names.add(f.name)

    def has_template_prefix(name: str) -> bool:
        return any(name.startswith(pre) for pre in TEMPLATE_FILENAME_PREFIXES)

    def name_to_done_destination(name: str) -> str:
        """Map a done-named file to its 05_Knowledge_Base/ subzone. Empty = no route."""
        if name.startswith("meeting_debrief_"):
            return f"05_Knowledge_Base/debriefs/{name}"
        if name.startswith("battleplan_"):
            return f"05_Knowledge_Base/battleplans/{name}"
        if name.startswith("audit_") or AUDIT_FILENAME_REGEX.match(name):
            return f"05_Knowledge_Base/audits/{name}"
        return ""

    # ---- 1+5+6: walk markdown in working zone (top level only) ----
    for f in P.cowork_root_md():
        # Superseded files always go to _archive/superseded/, never promotion.
        if f.name in superseded_names:
            continue
        if is_pinned(f.name, state_name):
            continue

        # State archive marker — handled in section 3 below.
        if "_archive_" in f.name:
            continue

        fm = read_frontmatter(f)
        ftype = (fm or {}).get("type", "").strip().lower()
        rel = str(f.relative_to(P.root))

        # Skip files explicitly tagged as non-promotable types — they stay put.
        if ftype in NON_PROMOTABLE_TYPES:
            continue

        # Template filename prefix wins over type-based routing — brand assets
        # in markdown form (rare but possible) route to 06_Templates/.
        if has_template_prefix(f.name):
            ok, reason = is_promotable(f, fm)
            dst = f"{TEMPLATE_DESTINATION}/{f.name}"
            if ok:
                refs = grep_references(f.name, P.root, pinned_set)
                refs_str = ", ".join(refs) if refs else "—"
                template_promotions.append((rel, "template-md", dst, reason, refs_str))
            else:
                inflight.append((rel, "template-md", reason))
            continue

        # Promotion route: type in PROMOTION_MAP
        if ftype in PROMOTION_MAP:
            ok, reason = is_promotable(f, fm)
            dst = f"{PROMOTION_MAP[ftype]}/{f.name}"
            if ok:
                refs = grep_references(f.name, P.root, pinned_set)
                refs_str = ", ".join(refs) if refs else "—"
                promotions.append((rel, ftype, dst, reason, refs_str))
            else:
                inflight.append((rel, ftype or "(none)", reason))
            continue

        # Done-pattern files without a recognised type — best-effort routing.
        if has_done_filename(f.name):
            ok, reason = is_promotable(f, fm)
            dst = name_to_done_destination(f.name)
            if ok and dst:
                refs = grep_references(f.name, P.root, pinned_set)
                refs_str = ", ".join(refs) if refs else "—"
                promotions.append((rel, ftype or "(prefix-routed)", dst, reason, refs_str))
            elif dst:
                inflight.append((rel, ftype or "(prefix-routed)", reason))
            continue

        # Unclassified — no type, no prefix.
        if not ftype:
            unclassified.append((rel, "no frontmatter or no `type:` field"))
        else:
            unclassified.append((rel, f"unrecognised type: `{ftype}`"))

    # ---- 2: walk binaries in working zone (top level only) ----
    # Templates (filename prefix template_/master_/brand_) -> 06_Templates/.
    # Everything else -> 02_Final_Deliverables/.
    for f in P.cowork_root_binaries():
        age = days_since(f)
        rel = str(f.relative_to(P.root))
        if age < THRESH_PROMOTE_AGE_DAYS:
            inflight.append((rel, f"binary{f.suffix}", f"only {age}d old"))
            continue
        refs = grep_references(f.name, P.root, pinned_set)
        refs_str = ", ".join(refs) if refs else "—"
        if has_template_prefix(f.name):
            dst = f"{TEMPLATE_DESTINATION}/{f.name}"
            template_promotions.append((rel, f"template{f.suffix}", dst, f"{age}d old", refs_str))
        else:
            dst = f"{BINARY_DESTINATION}/{f.name}"
            binary_promotions.append((rel, dst, f"{age}d old", refs_str))

    # ---- 3: quarterly state archives -> _archive/state_archives/ ----
    for f in P.cowork_root_md():
        if "_archive_" in f.name and not is_pinned(f.name, state_name):
            archive_moves.append((str(f.relative_to(P.root)),
                                  f"_archive/state_archives/{f.name}",
                                  "Quarterly archive — historical content, belongs out of working zone"))

    # ---- 4: superseded version pairs -> _archive/superseded/ ----
    versioned: dict[str, list[tuple[int, Path]]] = {}
    for f in P.cowork_root_md():
        m = re.match(r"(.+)_v(\d+)(?:\.\d+)?\.md$", f.name)
        if not m:
            continue
        stem, ver = m.group(1), int(m.group(2))
        versioned.setdefault(stem, []).append((ver, f))
    for stem, items in versioned.items():
        if len(items) < 2:
            continue
        items.sort()
        latest_ver = items[-1][0]
        for ver, f in items[:-1]:
            superseded_moves.append((str(f.relative_to(P.root)),
                                     f"_archive/superseded/{f.name}",
                                     f"Superseded by v{latest_ver}"))

    total_moves = (len(promotions) + len(binary_promotions)
                   + len(template_promotions)
                   + len(archive_moves) + len(superseded_moves))

    # ---- Build proposal document ----
    lines = [
        "---",
        f"name: Cleanup Proposal {today_iso()}",
        "description: Proposed moves from cowork_outputs/ into curated zones (P-10 routing). Generated by kb-curator. NOT EXECUTED until approved.",
        "type: proposal",
        "cadence: event-driven",
        f"last_updated: {today_iso()}",
        "---",
        "",
        f"# Cleanup Proposal — {today_iso()}",
        "",
        "Per `_guide_context_engineering.md` P-10. Generated by `kb-curator propose-cleanup`. Execution requires explicit approval per file or batch-level edits.",
        "",
        f"**Doneness threshold:** files must be at least {THRESH_PROMOTE_AGE_DAYS} days old "
        f"(override with `COWORK_PROMOTE_AGE_DAYS` env var).",
        "",
        "## Safeguards applied",
        "- No deletes. Superseded files go to `_archive/` (recoverable).",
        "- Pinned files (state, handoff, guides, evals, auto-writes, index, build script, runtime artefacts) never proposed.",
        f"- Doneness gate: cadence in PROMOTABLE_CADENCES (`stable, weekly, monthly, event-driven, monthly-or-on-structural-change`) AND age ≥ {THRESH_PROMOTE_AGE_DAYS}d, OR cadence empty + filename matches a done pattern.",
        "- Cross-reference column lists non-pinned files that mention the candidate by name. Approval bundles a reference-update for each. Skips `01_Personal_HR/`, `04_Meeting_Recordings/`, vcs/cache dirs.",
        "- Vetoes: `archived_reference: true`, cadence in OPERATIONAL_CADENCES (`per-session, continuous, append-only`), or `type:` in NON_PROMOTABLE_TYPES (`guide, state, handoff, eval, log, cleanup-log, archive`).",
        "",
    ]

    # Section: Promotions (debriefs/battleplans/audits/analysis/extractions/templates)
    lines.append("## 1. Promotions to curated zones")
    lines.append("")
    if promotions:
        lines.append("| File | Type | Destination | Doneness | Cross-refs |")
        lines.append("|------|------|-------------|----------|------------|")
        for src, ftype, dst, why, refs in promotions:
            lines.append(f"| `{src}` | `{ftype}` | `{dst}` | {why} | {refs} |")
    else:
        lines.append("_No promotion candidates passed the doneness gate._")
    lines.append("")

    # Section: Binary deliverables
    lines.append("## 2. Polished deliverables → 02_Final_Deliverables/")
    lines.append("")
    if binary_promotions:
        lines.append("| File | Destination | Age | Cross-refs |")
        lines.append("|------|-------------|-----|------------|")
        for src, dst, age, refs in binary_promotions:
            lines.append(f"| `{src}` | `{dst}` | {age} | {refs} |")
    else:
        lines.append("_No binary deliverables in working zone old enough to promote._")
    lines.append("")

    # Section: Templates / brand assets
    lines.append("## 2a. Templates / brand assets → 06_Templates/")
    lines.append("")
    lines.append("_Files whose name starts with `template_`, `master_`, or `brand_` are routed here per cowork-preparation P-10 (\"Template / brand asset\")._")
    lines.append("")
    if template_promotions:
        lines.append("| File | Kind | Destination | Age | Cross-refs |")
        lines.append("|------|------|-------------|-----|------------|")
        for src, kind, dst, age, refs in template_promotions:
            lines.append(f"| `{src}` | `{kind}` | `{dst}` | {age} | {refs} |")
    else:
        lines.append("_No template / brand assets to promote._")
    lines.append("")

    # Section: state archive moves
    lines.append("## 3. State archives → _archive/state_archives/")
    lines.append("")
    if archive_moves:
        lines.append("| File | Destination | Rationale |")
        lines.append("|------|-------------|-----------|")
        for src, dst, why in archive_moves:
            lines.append(f"| `{src}` | `{dst}` | {why} |")
    else:
        lines.append("_None._")
    lines.append("")

    # Section: superseded version pairs
    lines.append("## 4. Superseded versions → _archive/superseded/")
    lines.append("")
    if superseded_moves:
        lines.append("| File | Destination | Rationale |")
        lines.append("|------|-------------|-----------|")
        for src, dst, why in superseded_moves:
            lines.append(f"| `{src}` | `{dst}` | {why} |")
    else:
        lines.append("_None._")
    lines.append("")

    # Section: in-flight (recognised but not done)
    lines.append("## 5. In-flight — recognised type, not yet ready")
    lines.append("")
    if inflight:
        lines.append("| File | Type | Reason |")
        lines.append("|------|------|--------|")
        for src, ftype, reason in inflight:
            lines.append(f"| `{src}` | `{ftype}` | {reason} |")
        lines.append("")
        lines.append("_These will be re-proposed once cadence stabilises or the threshold is reached._")
    else:
        lines.append("_None._")
    lines.append("")

    # Section: unclassified
    lines.append("## 6. Needs review — no `type:` or unrecognised type")
    lines.append("")
    if unclassified:
        lines.append("| File | Reason |")
        lines.append("|------|--------|")
        for src, reason in unclassified:
            lines.append(f"| `{src}` | {reason} |")
        lines.append("")
        lines.append("_Add frontmatter (or run `_retrofit_frontmatter.py --apply`) so future runs can route these._")
    else:
        lines.append("_None._")
    lines.append("")

    # Pinned section
    lines.append("## Files staying put (pinned, never proposed)")
    lines.append("")
    lines.append("Per cowork-preparation P-10: state file, handoff, all `_guide_*.md`, all `_eval_*.md`, `_auto_writes.md`, `_cleanup_log.md`, `_retrofit_log.md`, `_index.md`, `_index_*.md` shards, `_build_index.py`, `_lint_frontmatter.py`, `_retrofit_frontmatter.py`, `_run_retrieval_eval.py`. Plus runtime artefacts: `_audit_*.md`, `_cleanup_proposal_*.md`, `_log_rotation_proposal_*.md`. Files with `archived_reference: true` or cadence in OPERATIONAL_CADENCES (`per-session, continuous, append-only`) also stay put.")
    lines.append("")

    # Approval
    lines.append("## Approval")
    lines.append("")
    lines.append("Trigger: \"**approve cleanup proposal**\" → execute moves with cross-reference updates in the same batch. Or line-level edits in this file before approval (delete the rows you don't want).")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(tz=timezone.utc).isoformat()} by kb-curator_")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"Wrote {out_path.relative_to(P.root)}  "
        f"({total_moves} moves proposed: "
        f"{len(promotions)} knowledge, {len(binary_promotions)} deliverables, "
        f"{len(template_promotions)} templates, "
        f"{len(archive_moves)} archives, {len(superseded_moves)} superseded; "
        f"{len(inflight)} in-flight, {len(unclassified)} need review)"
    )
    return 0

# ---- Mode: rotate-logs ----------------------------------------------------

def mode_rotate_logs(P: Project) -> int:
    out_path = P.cowork / f"_log_rotation_proposal_{today_iso()}.md"
    quarter = (date.today().month - 1) // 3 + 1
    suffix = f"{date.today().year}_Q{quarter}_through_{today_iso()}"

    moves = []
    if P.cleanup_log.exists() and kb(P.cleanup_log) > THRESH_CLEANUP_LOG_KB:
        moves.append((str(P.cleanup_log.relative_to(P.root)),
                      f"_archive/logs/_cleanup_log_{suffix}.md",
                      f"{kb(P.cleanup_log)} KB > {THRESH_CLEANUP_LOG_KB} KB threshold"))
    if P.auto_writes.exists() and kb(P.auto_writes) > THRESH_AUTO_WRITES_KB:
        moves.append((str(P.auto_writes.relative_to(P.root)),
                      f"_archive/logs/_auto_writes_{suffix}.md",
                      f"{kb(P.auto_writes)} KB > {THRESH_AUTO_WRITES_KB} KB threshold"))

    lines = [
        "---",
        f"name: Log Rotation Proposal {today_iso()}",
        "description: Proposed snapshot moves of operational logs to _archive/. NOT EXECUTED until approved.",
        "type: proposal",
        "cadence: event-driven",
        f"last_updated: {today_iso()}",
        "---",
        "",
        f"# Log Rotation Proposal — {today_iso()}",
        "",
        "Append-only logs grow unbounded by design. This proposal snapshots them to `_archive/logs/` and creates fresh files with back-pointers.",
        "",
        "## Proposed snapshots",
        "",
    ]
    if moves:
        lines.append("| Current log | Snapshot to | Reason |")
        lines.append("|-------------|-------------|--------|")
        for src, dst, why in moves:
            lines.append(f"| `{src}` | `{dst}` | {why} |")
        lines.append("")
        lines.append("## Post-snapshot setup")
        lines.append("")
        lines.append("After moves are approved and executed, create fresh `_cleanup_log.md` and `_auto_writes.md` with frontmatter and a back-pointer to the snapshot.")
    else:
        lines.append("_All logs within rotation thresholds. No action needed._")
    lines.append("")
    lines.append("## Approval")
    lines.append("")
    lines.append("Trigger: \"approve log rotation\" → execute snapshots and create fresh log files.")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(tz=timezone.utc).isoformat()} by kb-curator_")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path.relative_to(P.root)}  ({len(moves)} snapshots proposed)")
    return 0


# ---- Mode: audit-writes ---------------------------------------------------

def mode_audit_writes(P: Project) -> int:
    """Reconcile filesystem mtimes against `_auto_writes.md` log entries.

    Catches writes that happened without a log entry — meaning either Claude
    forgot (current Cowork) or a hook failed (future Cowork with hook parity).
    Read-only; produces an audit report.
    """
    out_path = P.cowork / f"_audit_writes_{today_iso()}.md"
    state_name = P.state.name if P.state else None

    # Read _auto_writes.md and extract logged paths
    logged_paths: set[str] = set()
    if P.auto_writes.exists():
        text = P.auto_writes.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            # Format per cowork-preparation: "YYYY-MM-DD | verb | path | reason"
            # Or: "YYYY-MM-DDTHH:MM | verb | path | reason"
            # Split on " | " and take the third field.
            parts = [s.strip() for s in line.split("|")]
            if len(parts) >= 3:
                # parts[2] is the path
                logged_paths.add(parts[2].lstrip("`").rstrip("`"))

    # Walk cowork_outputs/ for actual files (top-level only — same scope as autonomy boundary)
    actual: list[tuple[str, str]] = []  # (relpath, mtime_iso)
    for f in sorted(P.cowork.iterdir()):
        if not f.is_file():
            continue
        if is_pinned(f.name, state_name):
            continue
        rel = str(f.relative_to(P.root))
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).date().isoformat()
        actual.append((rel, mtime))

    # Find unlogged
    unlogged = []
    for rel, mtime in actual:
        # Match either "cowork_outputs/foo.md" or "foo.md" forms
        bare = rel.split("/", 1)[1] if "/" in rel else rel
        if rel not in logged_paths and bare not in logged_paths:
            unlogged.append((rel, mtime))

    lines = [
        "---",
        f"name: Auto-writes Reconciliation — {today_iso()}",
        "description: Diff between cowork_outputs/ filesystem state and `_auto_writes.md`. Surfaces writes that were never logged.",
        "type: audit",
        "cadence: one-off",
        f"last_updated: {today_iso()}",
        "---",
        "",
        f"# Auto-writes Reconciliation — {today_iso()}",
        "",
        f"Project root: `{P.root}`",
        f"Files in `cowork_outputs/` (non-pinned): **{len(actual)}**",
        f"Distinct paths in `_auto_writes.md`: **{len(logged_paths)}**",
        f"Unlogged files: **{len(unlogged)}**",
        "",
    ]
    if unlogged:
        lines.append("## Unlogged files (no `_auto_writes.md` entry)")
        lines.append("")
        lines.append("| File | mtime |")
        lines.append("|------|-------|")
        for rel, mtime in unlogged:
            lines.append(f"| `{rel}` | {mtime} |")
        lines.append("")
        lines.append("**Action:** open each file and append a back-dated entry to `_auto_writes.md`:")
        lines.append("")
        lines.append("```")
        lines.append("YYYY-MM-DD | write | <path> | reconciled by kb-curator audit-writes (no original log)")
        lines.append("```")
    else:
        lines.append("All files in `cowork_outputs/` are accounted for in the log. Audit trail is complete.")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(tz=timezone.utc).isoformat()} by kb-curator_")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path.relative_to(P.root)}  unlogged={len(unlogged)}/{len(actual)}")
    return 0


# ---- Mode: revert ---------------------------------------------------------

def mode_revert(P: Project, revert_id: str | None = None) -> int:
    """Generate a revert proposal for a cleanup batch from `_cleanup_log.md`.

    NOT EXECUTED — only produces a proposal file. The user reviews and approves
    via the same `approve cleanup proposal` flow.

    Match logic: if `revert_id` is a date (YYYY-MM-DD), match the heading
    `## YYYY-MM-DD — Cleanup batch N`. If `revert_id` is `latest`, take the
    last batch in the log.
    """
    if revert_id is None:
        print("ERROR: --revert-id required (date YYYY-MM-DD or 'latest')", file=sys.stderr)
        return 2
    if not P.cleanup_log.exists():
        print(f"ERROR: {P.cleanup_log} not found", file=sys.stderr)
        return 2

    text = P.cleanup_log.read_text(encoding="utf-8", errors="replace")
    # Find batch boundaries: lines starting with "## "
    blocks = []
    current_header = None
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current_header is not None:
                blocks.append((current_header, current_lines))
            current_header = line
            current_lines = []
        else:
            if current_header is not None:
                current_lines.append(line)
    if current_header is not None:
        blocks.append((current_header, current_lines))

    if not blocks:
        print("ERROR: no cleanup batches found in _cleanup_log.md", file=sys.stderr)
        return 2

    # Pick target block
    target = None
    if revert_id == "latest":
        target = blocks[-1]
    else:
        for h, body in blocks:
            if revert_id in h:
                target = (h, body)
                break
        if target is None:
            print(f"ERROR: no batch matching id '{revert_id}' in _cleanup_log.md", file=sys.stderr)
            print(f"Available headings:", file=sys.stderr)
            for h, _ in blocks:
                print(f"  {h}", file=sys.stderr)
            return 2

    header, body = target
    # Parse "From | To" rows from the body
    moves = []
    in_table = False
    for line in body:
        s = line.strip()
        if s.startswith("|") and "From" in s and "To" in s:
            in_table = True
            continue
        if s.startswith("|---"):
            continue
        if in_table and s.startswith("|"):
            cells = [c.strip().strip("`") for c in s.split("|")[1:-1]]
            if len(cells) >= 2 and cells[0] and cells[1]:
                moves.append((cells[0], cells[1]))
        elif in_table and not s.startswith("|"):
            in_table = False

    out_path = P.cowork / f"_revert_proposal_{today_iso()}.md"
    lines = [
        "---",
        f"name: Revert Proposal — {today_iso()}",
        f"description: Reverse the moves of cleanup batch '{header}'. NOT EXECUTED until approved.",
        "type: proposal",
        "cadence: event-driven",
        f"last_updated: {today_iso()}",
        "---",
        "",
        f"# Revert Proposal — {today_iso()}",
        "",
        f"Reversing batch: `{header}`",
        "",
        f"Found {len(moves)} moves to reverse.",
        "",
        "## Reverse moves",
        "",
    ]
    if moves:
        lines.append("| Currently at | Restore to |")
        lines.append("|--------------|------------|")
        for src, dst in moves:
            lines.append(f"| `{dst}` | `{src}` |")
    else:
        lines.append("_No move rows parseable from this batch._")
    lines.append("")
    lines.append("## Approval")
    lines.append("")
    lines.append("Trigger: \"approve revert proposal\" → execute reverse moves and append a counter-entry to `_cleanup_log.md`.")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(tz=timezone.utc).isoformat()} by kb-curator_")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path.relative_to(P.root)}  moves_to_reverse={len(moves)}")
    return 0


# ---- Mode: migrate-vocab --------------------------------------------------

def mode_migrate_vocab(P: Project) -> int:
    """Compare project's `_lint_frontmatter.py` KNOWN_TYPES with curator's PROMOTION_MAP keys.

    Surfaces:
      - Types curator routes for that lint warns on (drift, requires lint update).
      - Types lint accepts that curator doesn't route (potential PROMOTION_MAP additions).
      - Cowork contract `vocab_version` mismatch (if `_cowork_contract.json` exists).

    Read-only; writes a markdown report.
    """
    out_path = P.cowork / f"_migrate_vocab_{today_iso()}.md"

    # Parse project's lint script for KNOWN_TYPES + KNOWN_CADENCES
    lint_types: set[str] = set()
    lint_cadences: set[str] = set()
    if P.lint_fm.exists():
        lint_text = P.lint_fm.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"KNOWN_TYPES\s*=\s*\{([^}]*)\}", lint_text, re.DOTALL)
        if m:
            lint_types = set(re.findall(r'"([^"]+)"', m.group(1)))
        m = re.search(r"KNOWN_CADENCES\s*=\s*\{([^}]*)\}", lint_text, re.DOTALL)
        if m:
            lint_cadences = set(re.findall(r'"([^"]+)"', m.group(1)))

    # Read cowork contract if present
    contract_path = P.cowork.parent / "_cowork_contract.json"
    contract_version = "(no contract file)"
    if contract_path.exists():
        try:
            import json as _json
            data = _json.loads(contract_path.read_text(encoding="utf-8"))
            contract_version = data.get("vocab_version", "(unset)")
        except (OSError, ValueError):
            contract_version = "(unparseable)"

    curator_types = set(PROMOTION_MAP.keys()) | NON_PROMOTABLE_TYPES
    curator_cadences = PROMOTABLE_CADENCES | OPERATIONAL_CADENCES

    drift_curator_only = curator_types - lint_types  # curator routes, lint warns
    drift_lint_only = lint_types - curator_types     # lint accepts, curator never sees
    cadence_drift_curator = curator_cadences - lint_cadences
    cadence_drift_lint = lint_cadences - curator_cadences

    lines = [
        "---",
        f"name: Vocabulary Migration Report — {today_iso()}",
        "description: Diff between project lint vocabulary and kb-curator's expected vocabulary.",
        "type: audit",
        "cadence: one-off",
        f"last_updated: {today_iso()}",
        "---",
        "",
        f"# Vocabulary Migration Report — {today_iso()}",
        "",
        f"Project root: `{P.root}`",
        f"Project contract `vocab_version`: `{contract_version}`",
        f"Curator expects (built-in): see `PROMOTION_MAP` + `NON_PROMOTABLE_TYPES` in curator.py",
        "",
        "## Type vocabulary drift",
        "",
        f"- Lint accepts (`KNOWN_TYPES`): **{len(lint_types)}** types — `{sorted(lint_types)}`",
        f"- Curator routes or pins: **{len(curator_types)}** types — `{sorted(curator_types)}`",
        "",
        "### Curator routes types lint will warn on",
        "",
    ]
    if drift_curator_only:
        for t in sorted(drift_curator_only):
            lines.append(f"- `{t}` — curator has a route, project lint will WARN. **Action:** add to `_lint_frontmatter.py` `KNOWN_TYPES`.")
    else:
        lines.append("- None.")
    lines.append("")

    lines.append("### Lint accepts types curator doesn't route")
    lines.append("")
    if drift_lint_only:
        for t in sorted(drift_lint_only):
            lines.append(f"- `{t}` — lint accepts, curator falls through to 'Needs review'. **Action:** decide if it needs a `PROMOTION_MAP` entry, or leave for human routing.")
    else:
        lines.append("- None.")
    lines.append("")

    lines.append("## Cadence vocabulary drift")
    lines.append("")
    lines.append(f"- Lint `KNOWN_CADENCES`: `{sorted(lint_cadences)}`")
    lines.append(f"- Curator promotable + operational: `{sorted(curator_cadences)}`")
    lines.append("")
    if cadence_drift_curator:
        lines.append(f"- Curator references cadences lint warns on: `{sorted(cadence_drift_curator)}`")
    if cadence_drift_lint:
        lines.append(f"- Lint accepts cadences curator doesn't classify: `{sorted(cadence_drift_lint)}`")
    if not cadence_drift_curator and not cadence_drift_lint:
        lines.append("- No cadence drift.")
    lines.append("")
    lines.append("## Recommended action")
    lines.append("")
    if drift_curator_only or drift_lint_only or cadence_drift_curator or cadence_drift_lint:
        lines.append("Update either `_lint_frontmatter.py` (project) or kb-curator's `PROMOTION_MAP` (skill, requires re-install) to converge. The lint script is the canonical project vocabulary; align curator to it for project-specific extensions.")
    else:
        lines.append("Vocabularies are aligned. No migration needed.")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(tz=timezone.utc).isoformat()} by kb-curator_")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path.relative_to(P.root)}  curator_only={len(drift_curator_only)}  lint_only={len(drift_lint_only)}")
    return 0



# ---- Upgrade-project: canonical templates ---------------------------------
# Embedded so kb-curator can upgrade a project without depending on
# cowork-preparation being installed at the right path. Kept short — these
# are project-instantiated assets, not the templates with {{PLACEHOLDERS}}.

UPGRADE_TEMPLATES: dict[str, str] = {
    "_cowork_contract.json": """{
  "schema_version": "1.0.0",
  "vocab_version": "2026-04",
  "scaffolded_by": "kb-curator upgrade-apply",
  "scaffolded_on": "{TODAY}",
  "skill_versions": {
    "cowork-preparation": "2.2",
    "kb-curator": "2.2"
  },
  "thresholds": {
    "promote_age_days": 14,
    "handoff_kb": 15,
    "claudemd_kb": 12,
    "state_kb": 120,
    "cleanup_log_kb": 200,
    "auto_writes_kb": 80,
    "cowork_item_count": 250,
    "index_age_days": 7
  },
  "strict_mode": false,
  "pii_patterns": [],
  "_comment": "Edit thresholds here per-project. kb-curator reads this on every invocation."
}
""",
    "cowork_outputs/_reflection_log.md": """---
name: Reflection log
description: Append-only learning log. Records mistakes, corrections, and patterns. Reviewed weekly to extract durable lessons.
type: log
cadence: append-only
last_updated: {TODAY}
---

# Reflection Log

Append-only. Per OpenClaw's Reflexion pattern, with the explicit safeguard: reflections are hypotheses, not facts.

Entry format:

```
## YYYY-MM-DD - {{trigger: error | correction | pattern}}

Context: What was being worked on.
What happened: The mistake or insight.
Root cause (hypothesis): Why it happened (clearly marked as hypothesis).
Proposed lesson: WHEN-THEN-BECAUSE if applicable.
Status: untested | applied-once | applied-twice | discarded | promoted
```

Trigger conditions: tool errors, user corrections, tasks taking >2 min with multiple iterations, surprising audit findings.

---

## Log

_No entries yet._
""",
    ".claude/rules/auto-write-discipline.md": """---
name: Auto-write discipline
description: Discipline for files written under cowork_outputs/. Read when writing inside the working zone.
type: guide
cadence: stable
last_updated: {TODAY}
---

# Auto-write discipline

Per cowork-preparation P-7. Inside `cowork_outputs/` Claude writes without per-file approval, **provided** every write is logged to `_auto_writes.md`. Outside requires explicit user trigger.

Format: `YYYY-MM-DD | verb | path | one-line reason`. Verbs: write, edit, rename, note. Append-only.

Before writing: confirm path is under `cowork_outputs/`, confirm frontmatter, populate `provenance:` if it's a debrief/analysis/audit/battleplan.

After writing: append the line. If >5 files this session, propose `kb-curator refresh-index`.

Reconciliation safety net: weekly `kb-curator audit-writes` catches dropped log entries.

Never auto-write: state file, CLAUDE.md, handoff (only on explicit triggers), or anything outside `cowork_outputs/`.
""",
    ".claude/rules/promotion-quality.md": """---
name: Promotion quality gate
description: Three-question filter before approving any cleanup proposal.
type: guide
cadence: stable
last_updated: {TODAY}
---

# Promotion quality gate

`kb-curator propose-cleanup` is mechanical. Apply this filter to each row before approval:

1. Is this still true? (vs. state file + recent debriefs)
2. Will this affect tomorrow's decisions?
3. Is this encoded elsewhere?

If any answer is "no, archive instead" or "duplicate" — edit the proposal file before approval.

Optional `quality:` block in promoted file frontmatter:

```yaml
quality:
  signal: stable      # stable | needs_review | superseded
  reviewed_by: <user>
  reviewed_on: YYYY-MM-DD
```

For high-stakes content (audits, strategic analyses), spawn a verification subagent before approval.
""",
    ".claude/rules/freshness-discipline.md": """---
name: Freshness discipline
description: Reading-time freshness check. Read when consulting any file older than its cadence threshold.
type: guide
cadence: stable
last_updated: {TODAY}
---

# Freshness discipline

Cadence triggers (when to verify before quoting):

- weekly | event-driven: stale if >7d. Cross-check handoff and recent debriefs.
- monthly | monthly-or-on-structural-change: stale if >30d. Verify if recent decisions matter.
- stable: no auto-check. Only verify if recency is explicitly relevant.
- per-session | continuous | append-only: operational - if these look stale, the file is misconfigured.

Per-section freshness for state file: each anchored section carries `Last touched:` line. If >14d, flag potential staleness before acting on content.
""",
    ".claude/hooks/session-start.sh": """#!/usr/bin/env bash
# Cowork session bootstrap. Fires on Claude Code CLI SessionStart.
# In Cowork this is currently NOT fired (issue #45514). Safe to leave installed.
set -e
PROJECT_DIR="${{CLAUDE_PROJECT_DIR:-$(pwd)}}"
HANDOFF="$PROJECT_DIR/cowork_outputs/_session_handoff.md"
RECENT=""
if command -v git >/dev/null 2>&1 && [ -d "$PROJECT_DIR/.git" ]; then
  RECENT=$(cd "$PROJECT_DIR" && git log --oneline -10 2>/dev/null || true)
fi
CONTEXT=""
if [ -f "$HANDOFF" ]; then CONTEXT="HANDOFF:\n$(head -200 "$HANDOFF")"; fi
if [ -n "$RECENT" ]; then CONTEXT="$CONTEXT\n\nRECENT COMMITS:\n$RECENT"; fi
if [ -n "$CONTEXT" ] && command -v jq >/dev/null 2>&1; then
  jq -n --arg ctx "$CONTEXT" '{{hookSpecificOutput: {{hookEventName: "SessionStart", additionalContext: $ctx}}}}'
fi
exit 0
""",
    ".claude/hooks/pre-compact.sh": """#!/usr/bin/env bash
# PreCompact snapshot. Fires on Claude Code CLI; not Cowork yet (issue #45514).
set -e
PROJECT_DIR="${{CLAUDE_PROJECT_DIR:-$(pwd)}}"
HANDOFF="$PROJECT_DIR/cowork_outputs/_session_handoff.md"
TS="$(date -u +%Y-%m-%dT%H:%MZ)"
if [ -f "$HANDOFF" ]; then
  echo "" >> "$HANDOFF"
  echo "<!-- pre-compact checkpoint $TS - context was compacting; in-flight state may be partial -->" >> "$HANDOFF"
fi
exit 0
""",
    ".claude/hooks/post-write.sh": """#!/usr/bin/env bash
# Auto-log Write/Edit under cowork_outputs/ to _auto_writes.md.
# Fires on Claude Code CLI; not Cowork yet (issue #45514).
set -e
PROJECT_DIR="${{CLAUDE_PROJECT_DIR:-$(pwd)}}"
LOG="$PROJECT_DIR/cowork_outputs/_auto_writes.md"
INPUT=$(cat)
if command -v jq >/dev/null 2>&1; then
  TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
  FILEPATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')
else
  TOOL=""; FILEPATH=""
fi
case "$FILEPATH" in
  */cowork_outputs/*)
    REL="${{FILEPATH#$PROJECT_DIR/}}"
    DATE=$(date -u +%Y-%m-%d)
    VERB="write"
    case "$TOOL" in Edit|MultiEdit) VERB="edit" ;; esac
    echo "$DATE | $VERB | $REL | tool=$TOOL (auto via post-write hook)" >> "$LOG"
    ;;
esac
exit 0
""",
    "cowork_outputs/_lessons.md": """---
name: Lessons (durable)
description: Promoted durable lessons from _reflection_log.md. Each entry was tested at least twice. Append-only.
type: log
cadence: append-only
last_updated: {TODAY}
---

# Lessons

Promoted from `_reflection_log.md` entries with `status: applied-twice`. Each lesson is in WHEN-THEN-BECAUSE form. Append-only.

---

_No lessons yet — first promotion will land here._
""",
    ".claude/settings.json": """{
  "_comment": "Hook registrations for Claude Code CLI. Not yet fired in Cowork (issue #45514).",
  "hooks": {
    "SessionStart": [{"matcher": "startup|resume|compact|clear", "hooks": [{"type": "command", "command": "${{CLAUDE_PROJECT_DIR}}/.claude/hooks/session-start.sh"}]}],
    "PreCompact": [{"matcher": "manual|auto", "hooks": [{"type": "command", "command": "${{CLAUDE_PROJECT_DIR}}/.claude/hooks/pre-compact.sh"}]}],
    "PostToolUse": [{"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": "${{CLAUDE_PROJECT_DIR}}/.claude/hooks/post-write.sh"}]}]
  }
}
""",
}

# Files marked executable on apply
UPGRADE_EXECUTABLE = {".claude/hooks/session-start.sh", ".claude/hooks/pre-compact.sh", ".claude/hooks/post-write.sh"}

# Schema version this kb-curator expects from the contract
EXPECTED_VOCAB_VERSION = "2026-04"
EXPECTED_SKILL_VERSIONS = {"cowork-preparation": "2.2", "kb-curator": "2.2"}

# ---- Upgrade-project: probes ----------------------------------------------

def probe_upgrade_gaps(P: Project) -> dict:
    """Walk a project against the canonical scaffold; surface what's missing or stale.

    Returns a dict with keys:
      missing_additive: list of (relpath, content) — files we can drop in safely
      content_merge: list of (relpath, reason) — files that exist but may need merging
      vocab_drift: dict from migrate-vocab logic
      contract_status: 'ok' | 'missing' | 'old_vocab' | 'old_skill'
      handoff_format: 'yaml' | 'prose' | 'unknown'
      claude_md_size_kb: int
    """
    contract = load_contract(P.root)
    today = today_iso()

    missing_additive = []
    for rel, template in UPGRADE_TEMPLATES.items():
        target = P.root / rel
        if not target.exists():
            content = template.replace("{TODAY}", today)
            missing_additive.append((rel, content))

    content_merge = []
    # CLAUDE.md — check size; canonical is <200 lines and structured per template
    claude_md_size_kb = kb(P.claude_md) if P.claude_md.exists() else 0
    if P.claude_md.exists():
        cmd_text = P.claude_md.read_text(encoding="utf-8", errors="replace")
        if cmd_text.count("\n") > 250:
            content_merge.append(("CLAUDE.md", f">250 lines — exceeds best-practice ceiling (200). Manual trim recommended."))
        if ".claude/rules/" not in cmd_text:
            content_merge.append(("CLAUDE.md", "no reference to `.claude/rules/` — old template predates layered-rules pattern. Manual edit needed to add pointers."))

    # Handoff format detection
    handoff_format = "unknown"
    if P.handoff.exists():
        ho_text = P.handoff.read_text(encoding="utf-8", errors="replace")
        if "session_start_checks:" in ho_text and "threads:" in ho_text:
            handoff_format = "yaml"
        else:
            handoff_format = "prose"
            content_merge.append(("cowork_outputs/_session_handoff.md", "prose handoff — old format. New format is YAML body with `threads:`, `session_start_checks:`, `next_session_suggested:`. Manual conversion recommended (next \"wrap up session\" can use new format)."))

    # State file — check for per-section Last touched markers
    if P.state and P.state.exists():
        st_text = P.state.read_text(encoding="utf-8", errors="replace")
        sections = re.findall(r"^## (Workstream|Counterparty|Concept):", st_text, re.MULTILINE)
        last_touched_count = st_text.count("**Last touched:**")
        if sections and last_touched_count < len(sections):
            content_merge.append((str(P.state.relative_to(P.root)),
                                  f"{len(sections)} anchored sections but only {last_touched_count} `**Last touched:**` markers. Add markers per-section."))

    # Lint vocabulary — compare project lint vs curator
    lint_types: set[str] = set()
    if P.lint_fm.exists():
        lt = P.lint_fm.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"KNOWN_TYPES\s*=\s*\{([^}]*)\}", lt, re.DOTALL)
        if m:
            lint_types = set(re.findall(r'"([^"]+)"', m.group(1)))
    expected_lint_types = set(PROMOTION_MAP.keys()) | NON_PROMOTABLE_TYPES | {"strategic", "concept_note", "data_companion", "proposal", "review", "extraction", "other"}
    missing_lint_types = expected_lint_types - lint_types
    extra_lint_types = lint_types - expected_lint_types
    vocab_drift = {
        "missing_in_lint": sorted(missing_lint_types),
        "extra_in_lint": sorted(extra_lint_types),
    }

    # Contract status
    contract_status = "ok"
    if contract is None:
        contract_status = "missing"
    elif contract.get("vocab_version") != EXPECTED_VOCAB_VERSION:
        contract_status = "old_vocab"
    else:
        sk = contract.get("skill_versions", {}) or {}
        for skill, expected in EXPECTED_SKILL_VERSIONS.items():
            if sk.get(skill) != expected:
                contract_status = "old_skill"
                break

    return {
        "missing_additive": missing_additive,
        "content_merge": content_merge,
        "vocab_drift": vocab_drift,
        "contract_status": contract_status,
        "handoff_format": handoff_format,
        "claude_md_size_kb": claude_md_size_kb,
    }

# ---- Mode: upgrade-audit ---------------------------------------------------

def mode_upgrade_audit(P: Project) -> int:
    """Read-only audit of which canonical scaffold elements are missing/stale."""
    out_path = P.cowork / f"_upgrade_audit_{today_iso()}.md"
    gaps = probe_upgrade_gaps(P)

    lines = [
        "---",
        f"name: Upgrade Audit - {today_iso()}",
        "description: Read-only diff between this project and the current canonical cowork-preparation + kb-curator scaffold. No changes applied.",
        "type: audit",
        "cadence: one-off",
        f"last_updated: {today_iso()}",
        "---",
        "",
        f"# Upgrade Audit - {today_iso()}",
        "",
        f"Project root: `{P.root}`",
        f"Expected vocab_version: `{EXPECTED_VOCAB_VERSION}`",
        f"Expected skill versions: `{EXPECTED_SKILL_VERSIONS}`",
        "",
        "## 1. Contract status",
        "",
        f"- `_cowork_contract.json`: **{gaps['contract_status']}**",
        "",
        "## 2. Missing additive files (safe to add)",
        "",
    ]
    if gaps["missing_additive"]:
        lines.append("These files don't exist in this project. `kb-curator upgrade-apply` will create them.")
        lines.append("")
        for rel, _ in gaps["missing_additive"]:
            lines.append(f"- `{rel}`")
    else:
        lines.append("- All canonical additive files present.")
    lines.append("")

    lines.append("## 3. Content-merge needed (manual attention)")
    lines.append("")
    if gaps["content_merge"]:
        lines.append("These files exist but predate the current scaffold conventions. **`upgrade-apply` will NOT touch them** to avoid destroying user content. Address manually:")
        lines.append("")
        for rel, reason in gaps["content_merge"]:
            lines.append(f"- `{rel}` - {reason}")
    else:
        lines.append("- No content-merge gaps detected.")
    lines.append("")

    lines.append("## 4. Vocabulary drift")
    lines.append("")
    if gaps["vocab_drift"]["missing_in_lint"]:
        lines.append(f"- Curator references types lint warns on (add to `_lint_frontmatter.py` `KNOWN_TYPES`): `{gaps['vocab_drift']['missing_in_lint']}`")
    if gaps["vocab_drift"]["extra_in_lint"]:
        lines.append(f"- Lint accepts types curator doesn't route: `{gaps['vocab_drift']['extra_in_lint']}` (informational)")
    if not gaps["vocab_drift"]["missing_in_lint"] and not gaps["vocab_drift"]["extra_in_lint"]:
        lines.append("- Vocabularies aligned.")
    lines.append("")

    lines.append("## 5. Handoff format")
    lines.append("")
    lines.append(f"- Detected: **{gaps['handoff_format']}**")
    if gaps['handoff_format'] == "prose":
        lines.append("- Old prose format predates the YAML-body convention. Next `wrap up session` should produce the new format. No automated migration (would risk losing user content).")
    lines.append("")

    lines.append("## 6. CLAUDE.md size")
    lines.append("")
    lines.append(f"- Size: {gaps['claude_md_size_kb']} KB. Best-practice ceiling: 12 KB / ~200 lines.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Next step")
    lines.append("")
    lines.append("- For additive additions only: run `kb-curator upgrade-propose` to generate a proposal, then `kb-curator upgrade-apply` after review.")
    lines.append("- For content-merge items: edit manually or use the next \"wrap up session\" / \"update CLAUDE.md\" trigger to evolve naturally.")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(tz=timezone.utc).isoformat()} by kb-curator_")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"Wrote {out_path.relative_to(P.root)}  "
        f"contract={gaps['contract_status']}  "
        f"missing={len(gaps['missing_additive'])}  "
        f"content_merge={len(gaps['content_merge'])}  "
        f"vocab_drift={len(gaps['vocab_drift']['missing_in_lint'])}  "
        f"handoff={gaps['handoff_format']}"
    )
    return 0

# ---- Mode: upgrade-propose -------------------------------------------------

def mode_upgrade_propose(P: Project) -> int:
    """Generate an upgrade proposal listing files to add. NOT EXECUTED until approved."""
    out_path = P.cowork / f"_upgrade_proposal_{today_iso()}.md"
    gaps = probe_upgrade_gaps(P)

    lines = [
        "---",
        f"name: Upgrade Proposal - {today_iso()}",
        "description: Proposed additive upgrades from kb-curator. NOT EXECUTED until approved with the phrase \"approve upgrade proposal\".",
        "type: proposal",
        "cadence: event-driven",
        f"last_updated: {today_iso()}",
        "---",
        "",
        f"# Upgrade Proposal - {today_iso()}",
        "",
        f"Project root: `{P.root}`",
        f"Contract status: **{gaps['contract_status']}**",
        "",
        "## What `upgrade-apply` will do",
        "",
        "- Create the missing additive files listed below using the embedded canonical content.",
        "- Make hook scripts executable.",
        "- Append a single line to `_auto_writes.md` recording the upgrade event.",
        "",
        "## What `upgrade-apply` will NOT do",
        "",
        "- Touch any file that already exists (CLAUDE.md, state file, handoff, lint script). These are listed under 'Manual attention needed' and require human merge.",
        "- Create scheduled tasks (Cowork's MCP can't be called from a script). Do that yourself via `mcp__scheduled-tasks__create_scheduled_task` after applying.",
        "- Modify `_lint_frontmatter.py` (its KNOWN_TYPES set may need vocabulary additions; surfaced separately).",
        "",
        "## Files to add",
        "",
    ]
    if gaps["missing_additive"]:
        lines.append("| File | Action |")
        lines.append("|------|--------|")
        for rel, _ in gaps["missing_additive"]:
            exec_note = " (will chmod +x)" if rel in UPGRADE_EXECUTABLE else ""
            lines.append(f"| `{rel}` | create{exec_note} |")
    else:
        lines.append("_No additive files missing._")
    lines.append("")

    lines.append("## Manual attention needed (NOT applied)")
    lines.append("")
    if gaps["content_merge"]:
        for rel, reason in gaps["content_merge"]:
            lines.append(f"- `{rel}` - {reason}")
    else:
        lines.append("_None._")
    lines.append("")

    if gaps["vocab_drift"]["missing_in_lint"]:
        lines.append("## Lint vocabulary additions (manual)")
        lines.append("")
        lines.append(f"Add these to `cowork_outputs/_lint_frontmatter.py` `KNOWN_TYPES`: `{gaps['vocab_drift']['missing_in_lint']}`")
        lines.append("")

    lines.append("## Approval")
    lines.append("")
    lines.append("Trigger: \"**approve upgrade proposal**\" - kb-curator will create the listed files.")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(tz=timezone.utc).isoformat()} by kb-curator_")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path.relative_to(P.root)}  add={len(gaps['missing_additive'])}  manual={len(gaps['content_merge'])}")
    return 0

# ---- Mode: upgrade-apply ---------------------------------------------------

def mode_upgrade_apply(P: Project) -> int:
    """Execute the upgrade: create missing additive files. Idempotent (won't overwrite)."""
    gaps = probe_upgrade_gaps(P)
    created = []
    skipped_existing = []

    for rel, content in gaps["missing_additive"]:
        target = P.root / rel
        if target.exists():
            skipped_existing.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        if rel in UPGRADE_EXECUTABLE:
            try:
                target.chmod(0o755)
            except OSError:
                pass
        created.append(rel)

    # Log the event to _auto_writes.md
    if P.auto_writes.exists() and created:
        stamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        with P.auto_writes.open("a", encoding="utf-8") as fh:
            fh.write(f"\n{stamp} | upgrade | (multiple) | kb-curator upgrade-apply added {len(created)} file(s)\n")

    print(f"Upgrade applied. Created: {len(created)}  Skipped (already existed): {len(skipped_existing)}")
    for rel in created:
        print(f"  + {rel}")
    if skipped_existing:
        print("  Already existed (no action):")
        for rel in skipped_existing:
            print(f"    - {rel}")
    if gaps["content_merge"]:
        print(f"\nNOTE: {len(gaps['content_merge'])} files require manual merge. Re-run `kb-curator upgrade-audit` for the full list.")
    return 0



# ---- Mode: promote-lesson -------------------------------------------------

# Reflection log entry status that signals "ready to promote into durable lessons"
LESSON_READY_STATUS = "applied-twice"

def parse_reflection_log(path: Path) -> list[dict]:
    """Parse reflection log entries. Returns list of dicts with keys:
    header, date_iso, trigger, body_lines, status."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    entries: list[dict] = []
    cur: dict | None = None
    for line in text.splitlines():
        if line.startswith("## ") and re.match(r"## \d{4}-\d{2}-\d{2}", line):
            if cur is not None:
                entries.append(cur)
            m = re.match(r"## (\d{4}-\d{2}-\d{2})\s*[\-\u2014\u2013]\s*(?:\{?\{?trigger:?\s*)?([a-zA-Z]+)?", line)
            cur = {
                "header": line,
                "date_iso": m.group(1) if m else "",
                "trigger": (m.group(2) or "").strip() if m else "",
                "body_lines": [],
                "status": "",
            }
        elif cur is not None:
            cur["body_lines"].append(line)
            sm = re.match(r"\*?\*?Status:\*?\*?\s*(\S+)", line.strip())
            if sm:
                cur["status"] = sm.group(1).strip().rstrip(".,;:")
    if cur is not None:
        entries.append(cur)
    return entries

def probe_pending_lessons(P: Project) -> list[dict]:
    """Reflection log entries with status: applied-twice — ready to promote."""
    log_path = P.cowork / "_reflection_log.md"
    return [e for e in parse_reflection_log(log_path) if e["status"] == LESSON_READY_STATUS]

def mode_promote_lesson(P: Project) -> int:
    """Generate a promotion proposal: reflection-log entries -> _lessons.md.

    Reads `_reflection_log.md`, finds entries with `status: applied-twice`,
    writes `_lesson_promotion_proposal_YYYY-MM-DD.md`. Approval phrase:
    `approve lesson promotion`.
    """
    log_path = P.cowork / "_reflection_log.md"
    out_path = P.cowork / f"_lesson_promotion_proposal_{today_iso()}.md"

    candidates = probe_pending_lessons(P)

    lines = [
        "---",
        f"name: Lesson Promotion Proposal {today_iso()}",
        "description: Reflection-log entries ready to promote to _lessons.md. NOT EXECUTED until approved.",
        "type: proposal",
        "cadence: event-driven",
        f"last_updated: {today_iso()}",
        "---",
        "",
        f"# Lesson Promotion Proposal - {today_iso()}",
        "",
        f"Source: `{log_path.relative_to(P.root)}`",
        f"Candidates (status: {LESSON_READY_STATUS}): **{len(candidates)}**",
        "",
        "## Proposed promotions",
        "",
    ]
    if candidates:
        for e in candidates:
            # Strip the leading "## " from the source header before re-emitting at "### " level
            clean = e["header"][3:] if e["header"].startswith("## ") else e["header"]
            lines.append(f"### {clean}")
            lines.append("")
            for ln in e["body_lines"]:
                lines.append(ln)
            lines.append("")
            lines.append(f"_Will be appended to `cowork_outputs/_lessons.md` and the source entry's status changed to `promoted`._")
            lines.append("")
    else:
        lines.append("_No applied-twice entries found. Add `Status: applied-twice` to a reflection log entry once you've successfully applied a hypothesised lesson twice without further correction._")
        lines.append("")

    lines.append("## Approval")
    lines.append("")
    lines.append('Trigger: "approve lesson promotion" - Claude appends each entry to `cowork_outputs/_lessons.md` (creating it if absent) and rewrites the source entries\' status from `applied-twice` to `promoted`.')
    lines.append("")
    lines.append(f"_Generated: {datetime.now(tz=timezone.utc).isoformat()} by kb-curator_")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path.relative_to(P.root)}  candidates={len(candidates)}")
    return 0

# ---- Mode: cleanup-dryrun -------------------------------------------------

def mode_cleanup_dryrun(P: Project) -> int:
    """Read the most recent _cleanup_proposal_*.md and simulate all moves +
    cross-reference rewrites without applying anything. Writes a dryrun report
    showing exact before/after lines for every reference rewrite."""

    proposals = sorted(P.cowork.glob("_cleanup_proposal_*.md"))
    if not proposals:
        print("ERROR: no _cleanup_proposal_*.md found", file=sys.stderr)
        return 2
    latest = proposals[-1]
    text = latest.read_text(encoding="utf-8", errors="replace")

    # Parse table rows of form: | `path/source.md` | ... | `path/dest.md` | ...
    # Match: | `source.ext` | ... | `dest/path.ext` | ... — destination MUST contain / to avoid
    # capturing single-token columns like Type.
    move_pattern = re.compile(
        r"\|\s*`([^`]+\.(?:md|docx|pptx|xlsx|pdf|html))`\s*\|"
        r"(?:[^|]*\|){0,4}\s*"
        r"`([^`/]*/[^`]+\.(?:md|docx|pptx|xlsx|pdf|html))`"
    )
    moves: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        if "From" in line and "To" in line:
            continue
        if line.strip().startswith("|---"):
            continue
        m = move_pattern.search(line)
        if m:
            src, dst = m.group(1), m.group(2)
            if src and dst and "/" in src:
                moves.append((src, dst))

    state_name = P.state.name if P.state else None
    pinned_set = set(PINNED_NAMES)
    if state_name:
        pinned_set.add(state_name)

    out_path = P.cowork / f"_cleanup_dryrun_{today_iso()}.md"
    lines = [
        "---",
        f"name: Cleanup Dry-Run - {today_iso()}",
        f"description: Simulated execution of {latest.name}. No files were moved or modified.",
        "type: audit",
        "cadence: one-off",
        f"last_updated: {today_iso()}",
        "---",
        "",
        f"# Cleanup Dry-Run - {today_iso()}",
        "",
        f"Source proposal: `{latest.relative_to(P.root)}`",
        f"Moves parsed: **{len(moves)}**",
        "",
        "Each section below shows: the move that would happen, plus every cross-reference rewrite (before / after) that would be bundled with it.",
        "",
    ]

    total_rewrites = 0
    for i, (src, dst) in enumerate(moves, 1):
        src_name = Path(src).name
        lines.append(f"## Move {i} of {len(moves)}")
        lines.append("")
        lines.append(f"- **From:** `{src}`")
        lines.append(f"- **To:**   `{dst}`")
        lines.append("")

        # Find references in non-pinned .md files. Try two rewrites per matching line:
        # 1. Full path `src` -> `dst`. 2. Bare filename `src_name` -> `dst` (basename only).
        rewrites: list[tuple[str, list[tuple[str, str]]]] = []
        # Pattern A: full source path
        pat_full = re.compile(rf"(?<![A-Za-z0-9_/\-]){re.escape(src)}(?![A-Za-z0-9_\-])")
        # Pattern B: bare basename (when reference doesn't use the path)
        pat_name = re.compile(rf"(?<![A-Za-z0-9_/\-]){re.escape(src_name)}(?![A-Za-z0-9_\-])")
        dst_name = Path(dst).name
        try:
            for dirpath, dirnames, filenames in os.walk(P.root):
                dirnames[:] = [d for d in dirnames if d not in GREP_SKIP_DIRS and not d.startswith(".")]
                for fname in filenames:
                    if not fname.endswith(".md"):
                        continue
                    if fname == src_name or fname in pinned_set:
                        continue
                    if any(fname.startswith(pre) for pre in PINNED_PREFIXES):
                        continue
                    md = Path(dirpath) / fname
                    try:
                        ftext = md.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue
                    file_rewrites = []
                    for ln in ftext.splitlines():
                        after = ln
                        if pat_full.search(after):
                            after = pat_full.sub(dst, after)
                        if pat_name.search(after) and src_name != dst_name:
                            after = pat_name.sub(dst_name, after)
                        if after != ln:
                            file_rewrites.append((ln, after))
                    if file_rewrites:
                        rewrites.append((str(md.relative_to(P.root)), file_rewrites))
        except OSError:
            pass

        if rewrites:
            for relpath, line_pairs in rewrites:
                lines.append(f"### Reference rewrite in `{relpath}`")
                lines.append("")
                lines.append("```diff")
                for before, after in line_pairs:
                    lines.append(f"- {before}")
                    lines.append(f"+ {after}")
                    total_rewrites += 1
                lines.append("```")
                lines.append("")
        else:
            lines.append("_No cross-references to update._")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"**Summary:** {len(moves)} moves, {total_rewrites} reference rewrites across {sum(1 for _ in moves)} candidates.")
    lines.append("")
    lines.append("If this looks right, approve the original proposal: `approve cleanup proposal`.")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(tz=timezone.utc).isoformat()} by kb-curator_")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path.relative_to(P.root)}  moves={len(moves)}  rewrites={total_rewrites}")
    return 0


# ---- Entry point ----------------------------------------------------------

def mode_setup_automation(P: Project) -> int:
    """Generate the canonical 5 scheduled-task creation prompts.

    Writes _automation_setup_<date>.md with exact mcp__scheduled-tasks__create_scheduled_task
    payloads (taskId, cron, prompt) parameterised by project slug. Claude reads the file and
    issues the MCP calls — the script itself cannot call MCPs.

    Mirrors cowork-preparation Phase 3b. Use this on retrofitted projects (those upgraded via
    upgrade-apply) so they reach parity with newly-bootstrapped projects.
    """
    out_path = P.cowork / f"_automation_setup_{today_iso()}.md"

    # Derive project slug — try contract, fall back to root folder name
    contract = load_contract(P.root)
    slug = None
    if contract:
        slug = contract.get("project_slug")
    if not slug:
        slug = P.root.name.lower().replace(" ", "-").replace("_", "-")

    # Best-effort first-name extraction from CLAUDE.md (fallback: "the user")
    user_first = "the user"
    claudemd = P.root / "CLAUDE.md"
    if claudemd.exists():
        try:
            txt = claudemd.read_text()
            after_who = txt.split("## Who", 1)[-1] if "## Who" in txt else ""
            m = re.search(r"\b([A-Z][a-z]+)\b", after_who)
            if m:
                user_first = m.group(1)
        except Exception:
            pass

    project_root_str = str(P.root)

    tasks = [
        {
            "id": f"{slug}-handoff-freshness",
            "cron": "30 7 * * *",
            "schedule": "Daily 07:30 local",
            "description": "Daily handoff staleness check — flags open threads >24h old.",
            "prompt": (
                f"For the project at `{project_root_str}`: read `cowork_outputs/_session_handoff.md`. "
                f"If `last_updated` is more than 24h ago AND there are threads with `status: open`, "
                f"surface a notification asking {user_first} to update or close them. "
                f"Otherwise reply: \"Handoff fresh.\""
            ),
        },
        {
            "id": f"{slug}-audit-writes",
            "cron": "35 7 * * *",
            "schedule": "Daily 07:35 local",
            "description": "Daily auto-writes reconciliation — catches dropped log entries.",
            "prompt": (
                f"For the project at `{project_root_str}`: invoke the kb-curator skill and run mode `audit-writes`. "
                f"If `unlogged > 0`, surface a notification with the report contents. "
                f"Otherwise reply: \"Auto-writes log clean.\""
            ),
        },
        {
            "id": f"{slug}-kb-audit",
            "cron": "0 9 * * 1",
            "schedule": "Weekly Monday 09:00 local",
            "description": "Weekly KB health audit + cleanup proposal.",
            "prompt": (
                f"For the project at `{project_root_str}`: invoke the kb-curator skill. "
                f"Run mode `audit`, then mode `propose-cleanup`. "
                f"Reply with a brief summary (under 200 words): drift signals that flipped from 0, "
                f"number of promotion candidates ready to move, threshold breaches, pending lessons. "
                f"If everything is clean, reply: \"Clean. No action needed this week.\" "
                f"DO NOT execute moves, edit state file, edit CLAUDE.md, or write outside the audit/proposal files."
            ),
        },
        {
            "id": f"{slug}-eval-recency",
            "cron": "0 9 1-7 * 1",
            "schedule": "First Monday of month 09:00 local",
            "description": "Monthly retrieval-eval recency check.",
            "prompt": (
                f"For the project at `{project_root_str}`: check `cowork_outputs/_eval_context_retrieval.md` `last_updated`. "
                f"If > 30 days ago, propose re-running the retrieval eval per its top-of-file ritual. "
                f"Otherwise reply: \"Eval current.\""
            ),
        },
        {
            "id": f"{slug}-log-rotation",
            "cron": "0 9 1 1,4,7,10 *",
            "schedule": "Quarterly (1st of Jan/Apr/Jul/Oct) 09:00 local",
            "description": "Quarterly log rotation check.",
            "prompt": (
                f"For the project at `{project_root_str}`: invoke the kb-curator skill and run mode `audit`. "
                f"If `_cleanup_log.md` > 200KB or `_auto_writes.md` > 80KB, run mode `rotate-logs` to generate a proposal. "
                f"Otherwise reply: \"Logs within thresholds.\""
            ),
        },
    ]

    lines = [
        "---",
        f"name: Automation Setup — {today_iso()}",
        "description: Scheduled-task creation prompts for this project. Claude reads this file and calls mcp__scheduled-tasks__create_scheduled_task for each entry.",
        "type: proposal",
        "cadence: event-driven",
        f"last_updated: {today_iso()}",
        "---",
        "",
        f"# Automation Setup — {today_iso()}",
        "",
        f"Project root: `{project_root_str}`",
        f"Project slug: `{slug}`",
        f"User first name (best-effort from CLAUDE.md): `{user_first}`",
        "",
        "## What to do",
        "",
        "Claude: for each task below, call `mcp__scheduled-tasks__create_scheduled_task` with the exact parameters shown. ",
        "After all five complete, call `mcp__scheduled-tasks__list_scheduled_tasks` to verify and report any missing.",
        "",
        "These five tasks mirror cowork-preparation Phase 3b and bring this retrofitted project to parity with newly-bootstrapped ones.",
        "",
        "## Tasks to create",
        "",
    ]
    for t_ in tasks:
        lines += [
            f"### `{t_['id']}`",
            "",
            f"- **Schedule:** {t_['schedule']}",
            f"- **Cron:** `{t_['cron']}`",
            f"- **Description:** {t_['description']}",
            "",
            "MCP call:",
            "```json",
            json.dumps({
                "taskId": t_["id"],
                "cronExpression": t_["cron"],
                "description": t_["description"],
                "prompt": t_["prompt"],
                "notifyOnCompletion": True,
            }, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    lines += [
        "## After creation",
        "",
        "1. List scheduled tasks to verify all five landed.",
        "2. If any are missing, retry the MCP call for that one.",
        "3. Once all five are confirmed, append a line to `_auto_writes.md`:",
        f"   `{today_iso()} | note | scheduled-tasks | created 5 canonical maintenance tasks for {slug}`",
        "4. Mark this proposal applied by renaming to `_automation_setup_<date>_applied.md` (so future setup-automation runs detect automation is in place).",
        "",
        "## Why these five and not more?",
        "",
        "- **Daily handoff-freshness:** catches stale threads before they decay.",
        "- **Daily audit-writes:** reconciles auto-writes log against filesystem; daily cadence keeps drift small.",
        "- **Weekly kb-audit:** the main health check + cleanup proposal generation.",
        "- **Monthly eval-recency:** keeps the retrieval eval from going stale.",
        "- **Quarterly log-rotation:** logs grow slowly; quarterly is enough.",
        "",
        "Bundling daily checks into weekly loses fidelity; splitting weekly into per-probe tasks creates noise. This split has been validated by cowork-preparation Phase 3b across multiple projects.",
        "",
        f"_Generated: {datetime.now(tz=timezone.utc).isoformat()} by kb-curator setup-automation_",
    ]
    out_path.write_text("\n".join(lines))
    print(f"Wrote {out_path.relative_to(P.root)}  tasks_proposed={len(tasks)}  slug={slug}")
    return 0


def _dispatch_obsidian(root: Path, args) -> int:
    """Dispatch modes to OBSIDIAN-substrate scripts.

    audit        → chains audit_obsidian, audit_bitemporal, audit_rules,
                   audit_plans_index in sequence (all four always run so all
                   findings are surfaced; exit 0 = all scripts ran without crash).
    propose-cleanup → directs the caller to references/propose-cleanup-obsidian.md
                      (no standalone Python script; Claude follows the reference).
    all others   → friendly error (FLAT-only mode).
    """
    scripts_dir = Path(os.path.abspath(__file__)).parent
    ref_dir = scripts_dir.parent / "references"

    if args.mode == "audit":
        obsidian_scripts = [
            "audit_obsidian.py",
            "audit_bitemporal.py",
            "audit_rules.py",
            "audit_plans_index.py",
        ]
        crashed = False
        for script_name in obsidian_scripts:
            script_path = scripts_dir / script_name
            result = subprocess.run(
                [sys.executable, str(script_path), "--root", str(root)],
                check=False,
            )
            # Exit code 1 = findings present (expected); 2 = script error.
            if result.returncode == 2:
                crashed = True
        return 2 if crashed else 0

    if args.mode == "propose-cleanup":
        ref_path = ref_dir / "propose-cleanup-obsidian.md"
        print(
            "OBSIDIAN substrate detected.\n"
            "propose-cleanup routing for Johnny-Decimal vaults is defined in:\n"
            f"  {ref_path}\n\n"
            "Read that reference and follow its routing table, doneness gate, and\n"
            "pinned-files list to generate:\n"
            "  99 Workspace/_cleanup_proposal_YYYY-MM-DD.md"
        )
        return 0

    # All other modes are FLAT-only.
    print(
        f"ERROR: mode '{args.mode}' requires a FLAT (cowork-preparation) project "
        f"with cowork_outputs/.\n"
        "OBSIDIAN substrate supports: audit, propose-cleanup.\n"
        "To scaffold a FLAT project, run cowork-preparation.",
        file=sys.stderr,
    )
    return 2


def main() -> int:
    ap = argparse.ArgumentParser(description="kb-curator orchestrator")
    ap.add_argument("mode", choices=["audit", "refresh-index", "propose-cleanup", "rotate-logs", "audit-writes", "revert", "migrate-vocab", "upgrade-audit", "upgrade-propose", "upgrade-apply", "promote-lesson", "cleanup-dryrun", "setup-automation"])
    ap.add_argument("--root", default=None, help="Project root (overrides COWORK_ROOT env and auto-detect)")
    ap.add_argument("--revert-id", default=None, help="For revert mode: the cleanup batch id to undo (date or batch number)")
    args = ap.parse_args()

    root = resolve_root(args.root)

    # ---- Substrate dispatch ------------------------------------------------
    substrate, _checked = _detect_substrate(root)

    if substrate == "OBSIDIAN":
        # If a legacy cowork_outputs/ is also present (FLAT→OBSIDIAN mid-migration
        # or vault preserving cowork_outputs/_archive/), emit a one-line warning
        # so the operator knows the FLAT artefacts are not being audited.
        if (root / "cowork_outputs").is_dir():
            print(
                "WARN: both OBSIDIAN markers and cowork_outputs/ detected — "
                "routing to OBSIDIAN dispatch; cowork_outputs/ ignored "
                "(treat as legacy archive zone).",
                file=sys.stderr,
            )
        return _dispatch_obsidian(root, args)

    # ---- UNKNOWN substrate -------------------------------------------------
    # Reject only when neither FLAT (cowork_outputs/) nor OBSIDIAN (90 System/
    # + 99 Workspace/) markers are present. Substrate-agnostic error message.
    if substrate == "UNKNOWN":
        print(f"ERROR: substrate UNKNOWN under {root}", file=sys.stderr)
        print(
            "  FLAT     requires: CLAUDE.md + cowork_outputs/\n"
            "  OBSIDIAN requires: CLAUDE.md + 90 System/ + 99 Workspace/\n"
            "Run cowork-preparation (FLAT) or project-setup (OBSIDIAN) to scaffold.",
            file=sys.stderr,
        )
        sys.exit(2)

    # ---- FLAT substrate ----------------------------------------------------
    # Re-apply cowork_outputs/ requirement defensively (already guaranteed by
    # FLAT detection — kept for explicitness in case substrate values change).
    if not (root / "cowork_outputs").is_dir():
        print(f"ERROR: cowork_outputs/ not found under {root}", file=sys.stderr)
        print("FLAT substrate requires cowork_outputs/. Run cowork-preparation to scaffold.", file=sys.stderr)
        sys.exit(2)

    contract = load_contract(root)
    apply_contract_thresholds(contract)
    P = Project(root)

    if args.mode == "revert":
        return mode_revert(P, args.revert_id)
    return {
        "audit": mode_audit,
        "refresh-index": mode_refresh_index,
        "propose-cleanup": mode_propose_cleanup,
        "rotate-logs": mode_rotate_logs,
        "audit-writes": mode_audit_writes,
        "migrate-vocab": mode_migrate_vocab,
        "upgrade-audit": mode_upgrade_audit,
        "upgrade-propose": mode_upgrade_propose,
        "upgrade-apply": mode_upgrade_apply,
        "promote-lesson": mode_promote_lesson,
        "cleanup-dryrun": mode_cleanup_dryrun,
        "setup-automation": mode_setup_automation,
    }[args.mode](P)

if __name__ == "__main__":
    sys.exit(main())
