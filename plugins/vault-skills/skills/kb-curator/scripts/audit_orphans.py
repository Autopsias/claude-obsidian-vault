#!/usr/bin/env python3
"""
audit_orphans.py — kb-curator Karpathy Lint Mode 2.

Surfaces notes that are unreachable from the vault's MOC seed set AND
not surfaced by any primary .base file AND not in the expected-empty
type allow-list. Proposal-only output; never edits or moves source
notes.

Full design in:
  .claude/skills/kb-curator/references/lint-orphans.md

Reachability model:
  A note is REACHABLE iff any of:
    1. BFS over the wikilink graph from the entry-point set reaches it.
    2. Its `type:` binds to a PRIMARY .base file (not view-only).
    3. Its `type:` is in the BASES_UNBOUND_TYPES allow-list (lifted from
       _bases_verifier.py).
  Anything else, after exclusion-path filtering, is an orphan candidate.

Usage
-----
  python3 audit_orphans.py --root /path/to/vault
  python3 audit_orphans.py --root /path/to/vault --dry-run   # no proposal file
  python3 audit_orphans.py --root /path/to/vault --out /tmp/proposal.md

Exit
----
  0  success
  1  pipeline error (vault walk failure, etc.)
  2  configuration error (vault not found, Bases dir missing)
"""

import argparse
import os
import re
import sys
import time
from collections import deque, defaultdict
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration (single-source-of-truth pointer back to _bases_verifier.py)
# ---------------------------------------------------------------------------

# Closed P-4 vocabulary (mirrors _bases_verifier.py KNOWN_TYPES).
KNOWN_TYPES = frozenset({
    "person", "company", "project", "meeting", "source", "concept",
    "decision", "guide", "contract", "log", "handoff", "handoff_archive",
    "eval", "inbox", "daily", "template", "base", "system",
})

# Types valid but NOT bound to any .base — orphan-exempt by design.
# Mirrors _bases_verifier.py BASES_UNBOUND_TYPES.
BASES_UNBOUND_TYPES = frozenset({
    "inbox", "daily", "log", "handoff", "handoff_archive", "system",
    "contract", "guide", "eval", "template", "base", "concept",
})

# Skip dirs (subset of _bases_verifier.py SKIP_DIRS + orphan-specific extras).
SKIP_DIRS = frozenset({
    ".git", ".obsidian", ".smart-env", ".claude", "__pycache__",
    "node_modules", "_archive", "_archives", "archive", "archives",
    "Templates", "_skill_packages", "_skill_resources",
    "_log_archive", "_session_handoff_archive", "_auto_writes_archive",
    "_galp_vault_scheduled_tasks_staging",
    "_ingestion_pipeline",  # python source tree, not vault content
    "_drop",  # ingestion pipeline drop zone (mid-transit binaries)
})

# Zones we treat as temporal/non-graph — exclude from the candidate set.
EXCLUDE_ZONES = ("80 Daily",)

# Entry-point seeds for the wikilink BFS.
SEED_FILES = (
    "CLAUDE.md",
    "_plans_index.md",
    "30 Projects/Peninsula.md",
    "99 Workspace/_session_handoff.md",
)
# Whole-zone seed sets: every .md inside these zones is a BFS seed.
SEED_ZONES = (
    "30 Projects",
    "60 Concepts",
    "20 Companies",
)

# Wikilink regex — matches [[Target]], [[Target|Alias]], [[Path/Target]],
# [[Target#Section]], and ![[Embed]]. Non-greedy.
WIKILINK_RE = re.compile(r"\[\[([^\[\]\|]+?)(?:\|[^\[\]]*?)?\]\]")

# Supersession stem-strip regex (F-01 Option C, S07 follow-up, 2026-05-14):
# lifted from propagate_stale.py to enable version-suffix allow-list. A
# note whose stripped stem matches a seed-reachable note's stripped stem
# is treated as reachable — this rescues version-suffix predecessors that
# are cited by their successors but whose successors are themselves not
# BFS-reachable from the MOC seed set.
SUPERSESSION_STRIP = re.compile(
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


def supersession_stem(basename):
    """Strip version/preread/variant suffixes from basename. Return the
    stripped form. If nothing strips, return the basename unchanged.
    Caller decides whether to treat unchanged-after-strip as a non-match
    (i.e. only stems that actually got stripped contribute to the
    version-suffix allow-list — see classify_reach_4).
    """
    prev = None
    stem = basename
    while prev != stem:
        prev = stem
        stem = SUPERSESSION_STRIP.sub("", stem).strip(" _-")
    return stem.lower()

# Frontmatter regex + lightweight scalar field parse.
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
SIMPLE_FIELD_RE = re.compile(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*?)\s*$")

# Action heuristics — age in days.
AGE_MEETING_ARCHIVE = 60
AGE_SOURCE_ARCHIVE  = 120
AGE_PERSON_ARCHIVE  = 180


# ---------------------------------------------------------------------------
# Frontmatter parsing (lifted-pattern from audit_bitemporal.py)
# ---------------------------------------------------------------------------

def parse_frontmatter(text):
    """Return dict of top-level scalar fields, or None if no frontmatter."""
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


def parse_aliases(text):
    """Extract aliases list (block-list or inline-list) from frontmatter."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return []
    body = m.group(1)
    aliases = []
    in_aliases = False
    for line in body.splitlines():
        if not in_aliases:
            ls = line.lstrip()
            # Inline: aliases: ["A", "B"]
            mb = re.match(r"^aliases\s*:\s*\[(.*)\]\s*$", line)
            if mb:
                inner = mb.group(1)
                for part in re.findall(r'"([^"]+)"|\'([^\']+)\'|([^,\s][^,]*)', inner):
                    val = next((p.strip() for p in part if p.strip()), None)
                    if val:
                        aliases.append(val.strip())
                return aliases
            # Block-list start
            if re.match(r"^aliases\s*:\s*$", line):
                in_aliases = True
                continue
            # Single-line scalar: aliases: SomeName
            ms = re.match(r"^aliases\s*:\s*(\S.*?)\s*$", line)
            if ms:
                aliases.append(ms.group(1).strip().strip('"').strip("'"))
                return aliases
        else:
            # Block-list continuation: indented list-item or terminate.
            if line.startswith(("- ", "  - ", "    -")):
                item = line.lstrip().lstrip("-").strip().strip('"').strip("'")
                if item:
                    aliases.append(item)
            elif line == "" or line.startswith(" "):
                continue
            else:
                in_aliases = False
    return aliases


# ---------------------------------------------------------------------------
# Vault walk
# ---------------------------------------------------------------------------

def is_excluded_path(rel_parts):
    """Return True if any part of the relative path is in SKIP_DIRS or
    starts with an excluded zone."""
    for p in rel_parts:
        if p in SKIP_DIRS:
            return True
    # Exclude top-level zones (80 Daily/, etc.)
    if rel_parts and rel_parts[0] in EXCLUDE_ZONES:
        return True
    return False


def walk_vault(vault_root):
    """Yield (Path, rel_str, rel_parts) for every .md outside excluded paths."""
    for dirpath, dirnames, filenames in os.walk(vault_root):
        # Prune in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            if fname in ("folder.md",):
                continue
            p = Path(dirpath) / fname
            rel = p.relative_to(vault_root)
            rel_parts = rel.parts
            if is_excluded_path(rel_parts):
                continue
            yield p, str(rel), rel_parts


# ---------------------------------------------------------------------------
# Base parsing — primary vs view-only (mirrors _bases_verifier.py heuristic)
# ---------------------------------------------------------------------------

def _extract_type_from_string(s):
    if not isinstance(s, str):
        return None
    m = re.match(r"""^\s*type\s*==\s*['"](.+?)['"]\s*$""", s)
    return m.group(1) if m else None


def parse_primary_bases(bases_dir):
    """Return set of types bound by PRIMARY .base files (single conjunct
    `type == "X"` at top level). View-only Bases ignored.

    Minimal YAML parse — only enough to detect the top-level filter
    structure. Failure to parse a Base is non-fatal.
    """
    try:
        import yaml
    except ImportError:
        # Fallback: regex-based scan for top-level `- type == "X"` lines.
        types = set()
        for fp in sorted(bases_dir.glob("*.base")):
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            # Heuristic: count top-level filter conjuncts. We accept the Base
            # as primary if it has exactly one `- type == "X"` clause directly
            # under `filters:` `and:` and no other top-level filter clauses.
            m = re.search(
                r"^filters\s*:\s*\n\s*and\s*:\s*\n((?:\s*-\s*[^\n]+\n)+)",
                text, re.MULTILINE,
            )
            if not m:
                continue
            clauses = re.findall(r"^\s*-\s*(.+)$", m.group(1), re.MULTILINE)
            type_clauses = [_extract_type_from_string(c) for c in clauses]
            non_null = [t for t in type_clauses if t]
            if len(clauses) == 1 and len(non_null) == 1:
                types.add(non_null[0])
        return types

    primary_types = set()
    for fp in sorted(bases_dir.glob("*.base")):
        try:
            data = yaml.safe_load(fp.read_text(encoding="utf-8", errors="replace")) or {}
        except Exception as e:
            print(f"WARN: failed to parse {fp.name}: {e}", file=sys.stderr)
            continue
        filters = data.get("filters")
        if not isinstance(filters, dict):
            continue
        if list(filters.keys()) != ["and"]:
            continue
        children = filters.get("and")
        if not isinstance(children, list) or len(children) != 1:
            continue
        sole = children[0]
        t = _extract_type_from_string(sole) if isinstance(sole, str) else None
        if t:
            primary_types.add(t)
    return primary_types


# ---------------------------------------------------------------------------
# Wikilink graph
# ---------------------------------------------------------------------------

def collect_wikilinks(text):
    """Pull every [[Target]] from full text (frontmatter + body)."""
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(text)]


def resolve_link(target, basenames, aliases):
    """Return the canonical basename if resolvable, else None."""
    t = target.strip()
    if not t:
        return None
    if "#" in t:
        t = t.split("#", 1)[0].strip()
    if "|" in t:
        t = t.split("|", 1)[0].strip()
    if "/" in t:
        t = t.rsplit("/", 1)[1]
    if not t:
        return None
    if t in basenames:
        return t
    if t in aliases:
        return aliases[t]
    return None


def build_indexes(notes):
    """Return (basenames_set, alias_map_basename, path_by_basename).

    alias_map maps alias-string -> canonical basename.
    path_by_basename maps basename -> rel_str (first wins on collision).
    """
    basenames = set()
    aliases = {}
    path_by_basename = {}
    for n in notes:
        stem = n["path"].rsplit("/", 1)[-1]
        if stem.endswith(".md"):
            stem = stem[:-3]
        basenames.add(stem)
        path_by_basename.setdefault(stem, n["path"])
        n["basename"] = stem
        for a in n.get("aliases", []):
            aliases.setdefault(a, stem)
    return basenames, aliases, path_by_basename


def bfs_reachable(notes, basenames, aliases, seeds_set):
    """BFS the wikilink graph; return set of basenames reachable."""
    note_by_basename = {n["basename"]: n for n in notes}
    visited = set()
    queue = deque()
    for s in seeds_set:
        if s in note_by_basename:
            visited.add(s)
            queue.append(s)
    while queue:
        cur = queue.popleft()
        n = note_by_basename.get(cur)
        if not n:
            continue
        for target in collect_wikilinks(n["text"]):
            canonical = resolve_link(target, basenames, aliases)
            if canonical and canonical not in visited:
                visited.add(canonical)
                queue.append(canonical)
    return visited


# ---------------------------------------------------------------------------
# Action heuristics
# ---------------------------------------------------------------------------

DATE_FMT = "%Y-%m-%d"


def parse_date(s):
    if not s:
        return None
    s = s.strip().strip('"').strip("'")
    try:
        return datetime.strptime(s, DATE_FMT).date()
    except Exception:
        return None


def last_touched(note, path):
    """Return (date, source_label)."""
    fm = note.get("fm") or {}
    d = parse_date(fm.get("last_updated"))
    if d:
        return d, "last_updated"
    d = parse_date(fm.get("document_date"))
    if d:
        return d, "document_date"
    try:
        mt = datetime.fromtimestamp(os.path.getmtime(path)).date()
        return mt, "mtime"
    except Exception:
        return None, "unknown"


def suggest_action(type_value, age_days):
    if type_value is None:
        return "triage"
    t = type_value
    if t == "meeting":
        return "archive" if age_days is not None and age_days > AGE_MEETING_ARCHIVE else "link-from-moc"
    if t == "source":
        return "archive" if age_days is not None and age_days > AGE_SOURCE_ARCHIVE else "link-from-moc"
    if t == "decision":
        return "link-from-moc"
    if t == "person":
        return "archive" if age_days is not None and age_days > AGE_PERSON_ARCHIVE else "link-from-moc"
    if t == "company":
        return "link-from-moc"
    if t == "project":
        return "review"
    return "triage"


# ---------------------------------------------------------------------------
# Proposal output
# ---------------------------------------------------------------------------

def render_proposal(stats, orphans_typed, orphans_typeless, telemetry, out_path):
    today = date.today().isoformat()
    lines = []
    lines.append("---")
    lines.append("type: audit")
    lines.append("provenance: kb-curator lint-orphans (KP-04 — Karpathy Lint Mode 2)")
    lines.append(f"generated: {today}")
    lines.append(f"candidates_total: {stats['candidates_total']}")
    lines.append(f"reached_wikilink: {stats['reached_wikilink']}")
    lines.append(f"reached_base: {stats['reached_base']}")
    lines.append(f"reached_allowlist: {stats['reached_allowlist']}")
    lines.append(f"orphans_total: {stats['orphans_total']}")
    lines.append(f"runtime_seconds: {stats['runtime_s']:.2f}")
    lines.append("entry_points:")
    for s in stats["entry_points"]:
        lines.append(f"  - {s}")
    lines.append("allowlist_types:")
    for t in sorted(BASES_UNBOUND_TYPES):
        lines.append(f"  - {t}")
    lines.append("---")
    lines.append("")
    lines.append("# kb-curator — Orphan Lint Proposal")
    lines.append("")
    lines.append(f"**Generated:** {today}  ")
    lines.append(f"**Vault:** `{stats['vault']}`  ")
    lines.append(f"**Candidate notes (post-exclusion):** {stats['candidates_total']}  ")
    lines.append(f"**Reached via wikilink BFS:** {stats['reached_wikilink']}  ")
    lines.append(f"**Reached via primary Base:** {stats['reached_base']}  ")
    lines.append(f"**Allow-listed types (concept/log/system/etc.):** {stats['reached_allowlist']}  ")
    lines.append(f"**Orphans flagged:** {stats['orphans_total']}  ")
    lines.append(f"**Runtime:** {stats['runtime_s']:.2f}s  ")
    lines.append("")
    lines.append("Runtime breakdown:  ")
    lines.append(f"- Vault walk + frontmatter parse: {stats['walk_s']:.2f}s  ")
    lines.append(f"- Index build: {stats['index_s']:.2f}s  ")
    lines.append(f"- BFS: {stats['bfs_s']:.2f}s  ")
    lines.append(f"- Proposal render: {stats['render_s']:.2f}s  ")
    lines.append("")

    # Orphans by type
    lines.append("## Orphans by type")
    lines.append("")
    if not orphans_typed and not orphans_typeless:
        lines.append("_No orphans found. Graph fully reachable._")
        lines.append("")
    else:
        for tv in sorted(orphans_typed.keys()):
            group = orphans_typed[tv]
            lines.append(f"### `type: {tv}` — {len(group)} orphan(s)")
            lines.append("")
            lines.append("| Path | Last-touched | Source | Age (days) | Suggested action |")
            lines.append("|---|---|---|---:|---|")
            for o in group:
                age = o["age_days"]
                age_str = "—" if age is None else f"{age}"
                lt = o["last_touched"].isoformat() if o["last_touched"] else "—"
                lines.append(
                    f"| `{o['path']}` | {lt} | {o['date_source']} | {age_str} | {o['action']} |"
                )
            lines.append("")

    # Typeless orphans
    if orphans_typeless:
        lines.append("## Typeless orphans")
        lines.append("")
        lines.append(
            "_These notes have no `type:` frontmatter or unparseable "
            "frontmatter. Suggested action: `triage` — fix the frontmatter "
            "and re-run the lint. They are listed here separately because "
            "they cannot be Base-reached on type and were not BFS-reached "
            "via wikilink either._"
        )
        lines.append("")
        lines.append("| Path | Last-touched | Source | Age (days) |")
        lines.append("|---|---|---|---:|")
        for o in orphans_typeless:
            age = o["age_days"]
            age_str = "—" if age is None else f"{age}"
            lt = o["last_touched"].isoformat() if o["last_touched"] else "—"
            lines.append(
                f"| `{o['path']}` | {lt} | {o['date_source']} | {age_str} |"
            )
        lines.append("")

    # Telemetry
    lines.append("## Telemetry")
    lines.append("")
    lines.append("| Bucket | Count |")
    lines.append("|---|---:|")
    lines.append(f"| Candidate notes scanned | {stats['candidates_total']} |")
    lines.append(f"| Reached via wikilink BFS | {stats['reached_wikilink']} |")
    lines.append(f"| Reached via primary Base | {stats['reached_base']} |")
    lines.append(f"| Allow-listed types | {stats['reached_allowlist']} |")
    lines.append(f"| Orphans flagged | {stats['orphans_total']} |")
    lines.append("")
    lines.append("| Telemetry detail | Count |")
    lines.append("|---|---:|")
    lines.append(f"| Seed files resolved | {telemetry['seeds_resolved']} |")
    lines.append(f"| Seed files unresolved | {telemetry['seeds_unresolved']} |")
    lines.append(f"| Primary Bases detected | {telemetry['primary_bases']} |")
    lines.append(f"| Notes with no frontmatter | {telemetry['no_fm']} |")
    lines.append(f"| Notes with unknown-type frontmatter | {telemetry['unknown_type']} |")
    lines.append("")

    # Action breakdown
    action_counts = defaultdict(int)
    for o in orphans_typeless:
        action_counts["triage"] += 1
    for tv, group in orphans_typed.items():
        for o in group:
            action_counts[o["action"]] += 1
    if action_counts:
        lines.append("## Suggested-action breakdown")
        lines.append("")
        lines.append("| Action | Count |")
        lines.append("|---|---:|")
        for a in sorted(action_counts):
            lines.append(f"| {a} | {action_counts[a]} |")
        lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def resolve_seeds(vault_root, notes_by_path):
    """Return (basenames_seed_set, resolved_count, unresolved_count)."""
    seeds = set()
    resolved = 0
    unresolved = 0
    for s in SEED_FILES:
        fp = vault_root / s
        if fp.exists():
            stem = fp.name
            if stem.endswith(".md"):
                stem = stem[:-3]
            seeds.add(stem)
            resolved += 1
        else:
            unresolved += 1
            print(f"  WARN: seed not found: {s}", file=sys.stderr)
    for z in SEED_ZONES:
        zd = vault_root / z
        if not zd.exists():
            unresolved += 1
            continue
        for fp in zd.glob("*.md"):
            stem = fp.name[:-3]
            seeds.add(stem)
            resolved += 1
    return seeds, resolved, unresolved


def main():
    ap = argparse.ArgumentParser(
        description="kb-curator Karpathy Lint Mode 2 — orphan detection."
    )
    ap.add_argument("--root", default=None,
                    help="Vault root (auto-detect from cwd via CLAUDE.md).")
    ap.add_argument("--out", default=None,
                    help="Override proposal output path.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print summary only; do not write proposal.")
    args = ap.parse_args()

    # Resolve root
    root = args.root or os.environ.get("COWORK_ROOT")
    if root is None:
        cur = Path.cwd().resolve()
        while True:
            if (cur / "CLAUDE.md").exists():
                root = str(cur); break
            if cur.parent == cur: break
            cur = cur.parent
    if root is None:
        print("ERROR: vault root not found. Pass --root.", file=sys.stderr)
        sys.exit(2)
    vault_root = Path(root).resolve()
    if not vault_root.exists():
        print(f"ERROR: vault root does not exist: {vault_root}", file=sys.stderr)
        sys.exit(2)

    bases_dir = vault_root / "90 System" / "Bases"
    if not bases_dir.exists():
        print(f"WARN: Bases directory not found at {bases_dir} — "
              f"orphan check will run without base-reach.", file=sys.stderr)
        primary_base_types = set()
    else:
        primary_base_types = parse_primary_bases(bases_dir)
        print(f"  primary Bases bind types: {sorted(primary_base_types)}")

    t0 = time.time()

    # Step 1 — walk vault, parse frontmatter, build notes list.
    print(f"[1/4] walking vault at {vault_root}...")
    notes = []
    no_fm = 0
    unknown_type = 0
    for path, rel, rel_parts in walk_vault(vault_root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        fm = parse_frontmatter(text)
        if fm is None:
            no_fm += 1
            note = {
                "path": rel, "abs_path": path, "text": text, "fm": None,
                "type": None, "aliases": [],
            }
        else:
            type_value = fm.get("type")
            if type_value:
                type_value = type_value.strip().strip('"').strip("'")
            if type_value and type_value not in KNOWN_TYPES:
                unknown_type += 1
            note = {
                "path": rel, "abs_path": path, "text": text, "fm": fm,
                "type": type_value, "aliases": parse_aliases(text),
            }
        notes.append(note)
    t1 = time.time()
    print(f"      {len(notes)} notes scanned ({no_fm} without frontmatter, "
          f"{unknown_type} with unknown type)")

    # Step 2 — build indexes.
    print(f"[2/4] building basename + alias indexes...")
    basenames, aliases, path_by_basename = build_indexes(notes)
    t2 = time.time()
    print(f"      {len(basenames)} basenames, {len(aliases)} aliases")

    # Step 3 — resolve seeds, run BFS.
    print(f"[3/4] resolving seeds + running wikilink BFS...")
    seeds_set, seeds_resolved, seeds_unresolved = resolve_seeds(vault_root, basenames)
    reachable = bfs_reachable(notes, basenames, aliases, seeds_set)
    # F-01 Option C (extended, S07 follow-up, 2026-05-14): build the
    # reachable_stems set from ANY vault basename whose supersession_stem
    # is non-trivially-stripped — not just BFS-reachable ones. The narrow
    # form (seed-reachable only) catches almost nothing in this corpus
    # because most version chains are intra-50-Sources/ and the chain has
    # no MOC anchor. Extending to "any sibling version anywhere" rescues
    # the predecessors as long as ANY note in the vault shares a stripped
    # stem with them — which is exactly the user-relevant orphan
    # definition for version-suffix predecessors.
    reachable_stems = set()
    for r_bn in basenames:  # ALL vault basenames, not just reachable
        r_stem = supersession_stem(r_bn)
        if r_stem and r_stem != r_bn.lower():
            reachable_stems.add(r_stem)
    t3 = time.time()
    print(f"      {seeds_resolved} seeds resolved ({seeds_unresolved} unresolved); "
          f"{len(reachable)} basenames reachable via BFS")

    # Step 4 — classify each note; render proposal.
    print(f"[4/4] classifying + rendering...")
    notes_by_path = {n["path"]: n for n in notes}

    today = date.today()
    orphans_typed = defaultdict(list)
    orphans_typeless = []
    reached_wikilink_count = 0
    reached_base_count = 0
    reached_allowlist_count = 0
    reached_version_count = 0  # F-01 Option C (S07 follow-up, 2026-05-14)

    for n in notes:
        bn = n["basename"]
        tv = n["type"]
        wl_reach = bn in reachable
        base_reach = (tv in primary_base_types) if tv else False
        allowlist = (tv in BASES_UNBOUND_TYPES) if tv else False
        # F-01 Option C (S07 follow-up, 2026-05-14): version-suffix
        # allow-list. A note whose supersession_stem matches a
        # seed-reachable note's supersession_stem is treated as reachable
        # via the version-chain — the predecessor inherits reachability
        # from its successor.
        my_stem = supersession_stem(bn)
        version_reach = (my_stem in reachable_stems and my_stem != bn.lower())
        if wl_reach:
            reached_wikilink_count += 1
            continue
        if base_reach:
            reached_base_count += 1
            continue
        if allowlist:
            reached_allowlist_count += 1
            continue
        if version_reach:
            reached_version_count += 1
            continue
        # Orphan!
        lt, source = last_touched(n, n["abs_path"])
        age_days = (today - lt).days if lt else None
        action = suggest_action(tv, age_days)
        record = {
            "path": n["path"],
            "type": tv,
            "last_touched": lt,
            "date_source": source,
            "age_days": age_days,
            "action": action,
        }
        if tv is None or tv not in KNOWN_TYPES:
            orphans_typeless.append(record)
        else:
            orphans_typed[tv].append(record)

    # Sort each type group: oldest first (None last).
    for tv in orphans_typed:
        orphans_typed[tv].sort(
            key=lambda o: (o["last_touched"] is None, o["last_touched"] or date.today())
        )
    orphans_typeless.sort(
        key=lambda o: (o["last_touched"] is None, o["last_touched"] or date.today())
    )

    orphans_total = sum(len(v) for v in orphans_typed.values()) + len(orphans_typeless)
    t4 = time.time()

    stats = {
        "vault":              str(vault_root),
        "candidates_total":   len(notes),
        "reached_wikilink":   reached_wikilink_count,
        "reached_version":    reached_version_count,
        "reached_base":       reached_base_count,
        "reached_allowlist":  reached_allowlist_count,
        "orphans_total":      orphans_total,
        "entry_points":       list(SEED_FILES) + [f"{z}/*.md" for z in SEED_ZONES],
        "walk_s":             t1 - t0,
        "index_s":            t2 - t1,
        "bfs_s":              t3 - t2,
        "render_s":           t4 - t3,
        "runtime_s":          t4 - t0,
    }
    telemetry = {
        "seeds_resolved":   seeds_resolved,
        "seeds_unresolved": seeds_unresolved,
        "primary_bases":    len(primary_base_types),
        "no_fm":            no_fm,
        "unknown_type":     unknown_type,
    }

    # Stdout summary
    print()
    print("=" * 60)
    print("lint-orphans summary")
    print(f"  vault:               {vault_root}")
    print(f"  notes scanned:       {len(notes)}")
    print(f"  reached (wikilink):  {reached_wikilink_count}")
    print(f"  reached (Base):      {reached_base_count}")
    print(f"  reached (allowlist): {reached_allowlist_count}")
    print(f"  orphans flagged:     {orphans_total}")
    print(f"    typed orphans:     {sum(len(v) for v in orphans_typed.values())}")
    print(f"    typeless orphans:  {len(orphans_typeless)}")
    print(f"  runtime total:       {stats['runtime_s']:.2f}s")
    print(f"    walk:                {stats['walk_s']:.2f}s")
    print(f"    index:               {stats['index_s']:.2f}s")
    print(f"    bfs:                 {stats['bfs_s']:.2f}s")
    print(f"    render:              {stats['render_s']:.2f}s")
    if orphans_typed:
        print("  orphans by type:")
        for tv, group in sorted(orphans_typed.items()):
            print(f"    {tv}: {len(group)}")
    print("=" * 60)

    if args.dry_run:
        print(f"DRY RUN — no proposal written.")
        return 0

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = vault_root / "99 Workspace" / f"_lint_orphans_{date.today().isoformat()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    render_proposal(stats, orphans_typed, orphans_typeless, telemetry, out_path)
    print(f"proposal written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
