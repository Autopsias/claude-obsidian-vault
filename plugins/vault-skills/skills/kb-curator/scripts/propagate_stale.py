#!/usr/bin/env python3
"""
propagate_stale.py - kb-curator Karpathy Lint Mode 3 (stale propagation).

Surfaces citing notes whose upstream truth has moved:

- Rule A (hash drift on self):   the note is itself an ingested .md, and
                                  its `pipeline.sha256` (or stem-derived
                                  identity) is now superseded in the
                                  manifest.
- Rule B (bitemporal supersession on cited sources): the note cites a
                                  `type:source` / `type:decision` whose
                                  `is_latest_version` is false OR whose
                                  `superseded_date` is set.
- Rule C (transitive supersession via manifest): the note wikilinks to a
                                  basename whose `ingested_md_path` is
                                  attached to a sha that is superseded
                                  in the manifest.

Proposal-only - never edits or moves citing notes.

Full design in:
  .claude/skills/kb-curator/references/lint-stale.md

Usage
-----
  python3 propagate_stale.py --root /path/to/vault
  python3 propagate_stale.py --root /path/to/vault --dry-run
  python3 propagate_stale.py --root /path/to/vault --out /tmp/proposal.md

Exit
----
  0  success (even when manifest empty - graceful no-op)
  1  pipeline error
  2  configuration error (vault not found)
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration - lifted-pattern from audit_orphans.py
# ---------------------------------------------------------------------------

KNOWN_TYPES = frozenset({
    "person", "company", "project", "meeting", "source", "concept",
    "decision", "guide", "contract", "log", "handoff", "handoff_archive",
    "eval", "inbox", "daily", "template", "base", "system", "audit",
})

SOURCE_TYPES = frozenset({"source", "decision"})

SKIP_DIRS = frozenset({
    ".git", ".obsidian", ".smart-env", ".claude", "__pycache__",
    "node_modules", "_archive", "_archives", "archive", "archives",
    "Templates", "_skill_packages", "_skill_resources",
    "_log_archive", "_session_handoff_archive", "_auto_writes_archive",
    "_galp_vault_scheduled_tasks_staging",
    "_ingestion_pipeline",
    "_drop",
    "_originals",        # explicit skip - binaries only, not vault content
})

EXCLUDE_ZONES = ("80 Daily",)

WIKILINK_RE = re.compile(r"\[\[([^\[\]\|]+?)(?:\|[^\[\]]*?)?\]\]")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
SIMPLE_FIELD_RE = re.compile(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*?)\s*$")

# Supersession stem-strip regex, per _ingestion_contract.md §7.1.
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

DATE_FMT = "%Y-%m-%d"
ISO_FMT  = "%Y-%m-%dT%H:%M:%SZ"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_date(s):
    if not s:
        return None
    s = s.strip().strip('"').strip("'")
    if not s:
        return None
    try:
        return datetime.strptime(s, DATE_FMT).date()
    except Exception:
        # Try ISO with time component
        try:
            return datetime.strptime(s, ISO_FMT).date()
        except Exception:
            return None


def supersession_stem(filename):
    """Strip version/preread/variant suffixes from filename stem.

    Per `_ingestion_contract.md` §7.1.
    """
    stem = Path(filename).stem
    prev = None
    while prev != stem:
        prev = stem
        stem = SUPERSESSION_STRIP.sub("", stem).strip(" _-")
    return stem.lower()


def parse_frontmatter(text):
    """Return dict of top-level scalar fields, or None if no frontmatter.

    Captures top-level scalars AND a nested `pipeline:` mapping (sub-keys).
    Block-list fields (sources, tags, supersedes) are parsed separately by
    `parse_listfield()`.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    body = m.group(1)
    out = {}
    in_pipeline = False
    pipeline = {}
    for line in body.splitlines():
        # Empty / comment lines: terminate pipeline block if we were in one.
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # Indented under pipeline: a sub-key.
        if in_pipeline and (line.startswith("  ") or line.startswith("\t")):
            stripped = line.lstrip()
            # skip list items under pipeline (e.g. supersedes: [...])
            if stripped.startswith("-"):
                continue
            fm = SIMPLE_FIELD_RE.match(stripped)
            if fm:
                pipeline[fm.group(1)] = fm.group(2)
            continue
        # Out-of-block scalar - exit pipeline section.
        in_pipeline = False
        # Top-level pipeline header?
        if re.match(r"^pipeline\s*:\s*$", line):
            in_pipeline = True
            continue
        # Top-level list start: skip (handled separately).
        if line.startswith((" ", "\t", "-")):
            continue
        fm = SIMPLE_FIELD_RE.match(line)
        if not fm:
            continue
        key, val = fm.group(1), fm.group(2)
        if val.startswith(('"', "'")) and val.endswith(('"', "'")) and len(val) >= 2:
            val = val[1:-1]
        out[key] = val
    if pipeline:
        out["__pipeline__"] = pipeline
    return out


def parse_listfield(text, field_name):
    """Extract a list-typed frontmatter field (block-list or inline).

    Pattern lifted from audit_orphans.parse_aliases. Returns list of
    cleaned string values.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return []
    body = m.group(1)
    items = []
    in_block = False
    for line in body.splitlines():
        if not in_block:
            # Inline form: field: [A, "B", ...]
            mb = re.match(rf"^{re.escape(field_name)}\s*:\s*\[(.*)\]\s*$", line)
            if mb:
                inner = mb.group(1)
                for part in re.findall(r'"([^"]+)"|\'([^\']+)\'|([^,\s][^,]*)', inner):
                    val = next((p.strip() for p in part if p.strip()), None)
                    if val:
                        items.append(val.strip())
                return items
            # Block-list start
            if re.match(rf"^{re.escape(field_name)}\s*:\s*$", line):
                in_block = True
                continue
            # Scalar single-value: field: name
            ms = re.match(rf"^{re.escape(field_name)}\s*:\s*(\S.*?)\s*$", line)
            if ms:
                items.append(ms.group(1).strip().strip('"').strip("'"))
                return items
        else:
            if line.startswith(("- ", "  - ", "    -")):
                item = line.lstrip().lstrip("-").strip().strip('"').strip("'")
                if item:
                    items.append(item)
            elif line == "" or line.startswith(" "):
                continue
            else:
                in_block = False
    return items


def strip_wikilink(s):
    """Turn `[[Target|Alias]]` or `[[Path/Target#Section]]` into bare basename."""
    s = s.strip().strip('"').strip("'")
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2]
    if "#" in s:
        s = s.split("#", 1)[0]
    if "|" in s:
        s = s.split("|", 1)[0]
    if "/" in s:
        s = s.rsplit("/", 1)[1]
    if s.endswith(".md"):
        s = s[:-3]
    return s.strip()


def is_excluded_path(rel_parts):
    for p in rel_parts:
        if p in SKIP_DIRS:
            return True
    if rel_parts and rel_parts[0] in EXCLUDE_ZONES:
        return True
    return False


def walk_vault(vault_root):
    for dirpath, dirnames, filenames in os.walk(vault_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            if fname == "folder.md":
                continue
            p = Path(dirpath) / fname
            rel = p.relative_to(vault_root)
            rel_parts = rel.parts
            if is_excluded_path(rel_parts):
                continue
            yield p, str(rel), rel_parts


# ---------------------------------------------------------------------------
# Manifest reader
# ---------------------------------------------------------------------------

def load_manifest(manifest_path, telemetry):
    """Return (hash_state, latest_by_stem, path_by_sha, manifest_lines).

    See lint-stale.md Step 1.
    """
    hash_state    = {}
    latest_by_stem = {}     # stem -> (sha, extracted_at)
    path_by_sha   = {}      # sha -> ingested_md_path basename (for Rule C)
    lines_read    = 0
    superseded    = set()

    if not manifest_path.exists():
        telemetry["manifest_present"] = False
        return hash_state, latest_by_stem, path_by_sha, 0, 0

    telemetry["manifest_present"] = True

    with open(manifest_path) as f:
        for line_no, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            lines_read += 1
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"WARN: manifest line {line_no} malformed: {e}", file=sys.stderr)
                telemetry["manifest_malformed"] += 1
                continue
            sha = entry.get("sha256")
            if not sha:
                telemetry["manifest_no_sha"] += 1
                continue
            hash_state[sha] = {
                "run_id":          entry.get("run_id"),
                "source_file":     entry.get("source_file"),
                "original_path":   entry.get("original_path"),
                "supersession_stem": entry.get("supersession_stem"),
                "supersedes":      entry.get("supersedes", []) or [],
                "extracted_at":    entry.get("extracted_at"),
                "ingested_md_path": entry.get("ingested_md_path"),
                "is_superseded":   False,
                "superseded_by_sha": None,
            }
            if entry.get("ingested_md_path"):
                p = Path(entry["ingested_md_path"]).stem
                path_by_sha[sha] = p

    # Step 1b: mark superseded shas
    for sha, st in hash_state.items():
        for prior_sha in st["supersedes"]:
            if prior_sha in hash_state:
                hash_state[prior_sha]["is_superseded"]    = True
                hash_state[prior_sha]["superseded_by_sha"] = sha
                superseded.add(prior_sha)

    # Step 1c: latest_by_stem
    by_stem = defaultdict(list)
    for sha, st in hash_state.items():
        stem = st.get("supersession_stem") or supersession_stem(st.get("source_file") or "")
        if stem:
            by_stem[stem].append((sha, st.get("extracted_at") or ""))
    for stem, items in by_stem.items():
        items.sort(key=lambda x: x[1], reverse=True)  # newest first by ISO string
        latest_by_stem[stem] = items[0][0]

    return hash_state, latest_by_stem, path_by_sha, lines_read, len(superseded)


# ---------------------------------------------------------------------------
# Vault scan - build citing-note index + source-note registry
# ---------------------------------------------------------------------------

def build_indexes(notes):
    """basenames set + alias map + path_by_basename (first-wins)."""
    basenames = set()
    aliases = {}
    path_by_basename = {}
    for n in notes:
        stem = Path(n["path"]).stem
        n["basename"] = stem
        basenames.add(stem)
        path_by_basename.setdefault(stem, n["path"])
        for a in n.get("aliases", []):
            aliases.setdefault(a, stem)
    return basenames, aliases, path_by_basename


def resolve_link(target, basenames, aliases):
    t = strip_wikilink(target)
    if not t:
        return None
    if t in basenames:
        return t
    if t in aliases:
        return aliases[t]
    return None


# ---------------------------------------------------------------------------
# Rule application
# ---------------------------------------------------------------------------

def confidence_rank(c):
    return {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(c, 0)


def evaluate_note(
    n,
    today,
    hash_state,
    latest_by_stem,
    path_by_sha,
    source_notes_by_basename,
    basenames,
    aliases,
    telemetry,
    manifest_empty,
):
    """Apply rules A/B/C to one citing note. Return list of finding dicts."""
    findings = []
    fm = n["fm"] or {}
    pipeline_ns = fm.get("__pipeline__") or {}
    last_updated = parse_date(fm.get("last_updated"))

    # Self-citation fields
    self_sha = pipeline_ns.get("sha256")
    if self_sha:
        self_sha = self_sha.strip().strip('"').strip("'").lower()
    self_source_file  = fm.get("source_file")
    self_original_path = fm.get("original_path")

    # Derive self stem
    self_stem = None
    if self_source_file:
        self_stem = supersession_stem(self_source_file)
    elif self_original_path:
        self_stem = supersession_stem(Path(self_original_path).name)

    # ----- Rule A.1 / A.2 / A.3 -----
    if self_sha and self_sha in hash_state:
        if hash_state[self_sha]["is_superseded"]:
            findings.append({
                "rule":       "A.1",
                "confidence": "HIGH",
                "reason":     (f"upstream binary superseded by sha={hash_state[self_sha]['superseded_by_sha'][:8]}"
                               if hash_state[self_sha]["superseded_by_sha"] else "upstream binary superseded"),
                "action":     "update-citation",
            })
    elif self_sha and self_sha not in hash_state and not manifest_empty:
        findings.append({
            "rule":       "A.2",
            "confidence": "MEDIUM",
            "reason":     f"self pipeline.sha256={self_sha[:8]} not in manifest",
            "action":     "review",
        })
    elif (not self_sha) and self_stem and self_stem in latest_by_stem and (self_source_file or self_original_path):
        # We have no self sha but a stem we can compare. Without a self sha
        # we cannot know whether *we* are already the latest, so only fire
        # when the latest entry's `extracted_at` is newer than the note's
        # own `extracted_at` frontmatter (if available).
        note_extracted_at = fm.get("extracted_at") or ""
        latest_sha = latest_by_stem[self_stem]
        latest_entry = hash_state.get(latest_sha) or {}
        latest_extracted = latest_entry.get("extracted_at") or ""
        if latest_extracted and note_extracted_at and latest_extracted > note_extracted_at:
            findings.append({
                "rule":       "A.3",
                "confidence": "MEDIUM",
                "reason":     f"newer version of stem '{self_stem}' ingested at {latest_extracted}",
                "action":     "review",
            })

    # ----- Rule B (bitemporal supersession on cited sources) -----
    cited = []
    for s in n["frontmatter_sources"]:
        cited.append(("fm.sources", s))
    for s in n["body_wikilinks"]:
        cited.append(("body", s))

    seen_cited_basenames = set()
    self_basename = n.get("basename")
    for kind, target in cited:
        bn = resolve_link(target, basenames, aliases)
        if bn is None:
            telemetry["unresolved_citations"] += 1
            continue
        # F-04 (S07 follow-up, 2026-05-14): skip self-citation. A note whose
        # body or frontmatter wikilinks to its own basename should not be
        # flagged Rule B/C against itself - the "citation" is self-reference,
        # not a real cite that would propagate staleness.
        if bn == self_basename:
            telemetry["self_citations_skipped"] = telemetry.get("self_citations_skipped", 0) + 1
            continue
        if bn in seen_cited_basenames:
            continue
        seen_cited_basenames.add(bn)
        src = source_notes_by_basename.get(bn)
        if src is None:
            continue  # cited but the target is not a source/decision - skip
        src_fm = src.get("fm") or {}
        is_latest_raw = (src_fm.get("is_latest_version") or "").strip().strip('"').strip("'").lower()
        superseded_date_raw = src_fm.get("superseded_date")
        if is_latest_raw == "false":
            # F-05 (S07 follow-through, 2026-05-15; extended 2026-05-15):
            # within-version-chain suppressor with v-in-middle + sibling-suffix
            # handling. Two notes are "in the same chain" if any of:
            #   (a) supersession_stem matches (trailing version markers)
            #   (b) both have an internal _v\d+_ pattern and share the prefix
            #       before that pattern
            #   (c) one is a sibling variant of the other (suffixes like
            #       _galp, _co_ceo, _readonly, _FULL, _amazon, _draft)
            # Mirror of Q25 F-01 Option C extended reachability — same intent
            # for the propagation script.
            import re as _re
            SIBLING_SUFFIXES = (r"_galp", r"_co_ceo", r"_readonly", r"_full",
                                 r"_amazon", r"_draft", r"_clean", r"_comentada\d*")
            def _chain_key(stem):
                s = stem.lower()
                # strip trailing version + sibling suffixes
                for suf in SIBLING_SUFFIXES + (r"_v\d+(?:\.\d+)*", r"_ver\d+",
                                                r"_vcomentada\d+", r"_v\d+_full",
                                                r"_v\d+_co_ceo", r"_v\d+_galp",
                                                r"_v\d+_readonly"):
                    s = _re.sub(suf + r"$", "", s)
                # also strip an internal _v\d+_ if present, keeping prefix
                m_v = _re.search(r"^(.*?)_v\d+_", s)
                if m_v:
                    s = m_v.group(1)
                # F-05 extension (2026-05-15, 2nd round): collapse non-alphanumerics
                # so e.g. "6_pager" and "6pager" treated as same chain. Handles
                # the underscore-variant duplicate-ingestion case in this corpus.
                s = _re.sub(r"[_\-\s]+", "", s)
                return s
            # F-05 (2nd extension): version-chain meta-doc allow-list.
            # Files whose basename signals "this is a version-evolution doc by
            # design" cite multiple versions intentionally — never fire B.1
            # from them. Also includes state MOCs (30 Projects/) and audit
            # logs (99 Workspace/_audit_*) which document version history.
            META_DOC_TOKENS = ("_evolution", "_delta", "change_framework",
                                "_version_chain", "_history", "_archive_index")
            META_DOC_PATHS = ("30 Projects/",)         # state MOCs
            META_DOC_BASENAME_PREFIXES = ("_audit_",)  # workspace audit logs
            basename_lower = n["basename"].lower()
            path_lower = n["path"].lower()
            is_meta = (
                any(tok in basename_lower for tok in META_DOC_TOKENS)
                or any(path_lower.startswith(p.lower()) for p in META_DOC_PATHS)
                or any(basename_lower.startswith(p.lower()) for p in META_DOC_BASENAME_PREFIXES)
            )
            if is_meta:
                telemetry["version_meta_doc_skipped"] = telemetry.get("version_meta_doc_skipped", 0) + 1
                continue
            citer_key = _chain_key(n["basename"])
            cited_key = _chain_key(bn)
            if (citer_key and cited_key and citer_key == cited_key
                and citer_key != n["basename"].lower()
                and cited_key != bn.lower()):
                telemetry["version_chain_skipped"] = telemetry.get("version_chain_skipped", 0) + 1
                continue
            findings.append({
                "rule":       "B.1",
                "confidence": "HIGH",
                "reason":     f"cited source [[{bn}]] is no longer latest",
                "action":     "update-citation",
            })
            continue
        if superseded_date_raw and superseded_date_raw.strip().strip('"').strip("'"):
            findings.append({
                "rule":       "B.2",
                "confidence": "HIGH",
                "reason":     f"cited source [[{bn}]] has superseded_date={superseded_date_raw}",
                "action":     "update-citation",
            })
            continue
        # B.3 - cited source updated after citing note
        src_lu = parse_date(src_fm.get("last_updated"))
        if last_updated and src_lu and src_lu > last_updated:
            findings.append({
                "rule":       "B.3",
                "confidence": "LOW",
                "reason":     f"cited source [[{bn}]] last_updated={src_lu} > note last_updated={last_updated}",
                "action":     "monitor",
            })

    # ----- Rule C (transitive supersession via manifest) -----
    if hash_state:
        for s in n["body_wikilinks"]:
            bn = resolve_link(s, basenames, aliases)
            if not bn:
                continue
            # Does this basename match an ingested_md_path stem in the manifest?
            for sha, mstem in path_by_sha.items():
                if mstem == bn and hash_state[sha]["is_superseded"]:
                    by_sha = hash_state[sha]["superseded_by_sha"]
                    by_prefix = (by_sha[:8] if by_sha else "?")
                    findings.append({
                        "rule":       "C.1",
                        "confidence": "MEDIUM",
                        "reason":     f"body cites [[{bn}]]; upstream binary superseded by sha={by_prefix}",
                        "action":     "review",
                    })
                    break  # only one finding per cited basename

    # Dedup: keep highest-confidence finding per rule family
    if not findings:
        return []
    # Keep all unique (rule, basename-ish) combos but cap one finding per
    # confidence-rank per note - we want diversity of evidence without
    # spam.
    seen = set()
    dedup = []
    findings.sort(key=lambda f: -confidence_rank(f["confidence"]))
    for f in findings:
        key = (f["rule"], f["reason"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(f)
    return dedup


# ---------------------------------------------------------------------------
# Proposal render
# ---------------------------------------------------------------------------

def render_proposal(stats, by_conf, rule_counts, telemetry, out_path):
    today = date.today().isoformat()
    lines = []
    lines.append("---")
    lines.append("type: audit")
    lines.append("provenance: kb-curator lint-stale (KP-06 - Karpathy Lint Mode 3)")
    lines.append(f"generated: {today}")
    lines.append(f"candidates_total: {stats['candidates_total']}")
    lines.append(f"flagged_high: {len(by_conf['HIGH'])}")
    lines.append(f"flagged_medium: {len(by_conf['MEDIUM'])}")
    lines.append(f"flagged_low: {len(by_conf['LOW'])}")
    lines.append(f"flagged_total: {sum(len(v) for v in by_conf.values())}")
    lines.append(f"manifest_entries: {stats['manifest_entries']}")
    lines.append(f"manifest_superseded: {stats['manifest_superseded']}")
    lines.append(f"runtime_seconds: {stats['runtime_s']:.2f}")
    lines.append("---")
    lines.append("")
    lines.append("# kb-curator - Stale Propagation Proposal")
    lines.append("")
    lines.append(f"**Generated:** {today}  ")
    lines.append(f"**Vault:** `{stats['vault']}`  ")
    lines.append(f"**Citing notes scanned:** {stats['candidates_total']}  ")
    lines.append(f"**Flagged HIGH:** {len(by_conf['HIGH'])}  ")
    lines.append(f"**Flagged MEDIUM:** {len(by_conf['MEDIUM'])}  ")
    lines.append(f"**Flagged LOW:** {len(by_conf['LOW'])}  ")
    lines.append(f"**Flagged total:** {sum(len(v) for v in by_conf.values())}  ")
    lines.append(f"**Runtime:** {stats['runtime_s']:.2f}s  ")
    lines.append("")
    lines.append("Runtime breakdown:  ")
    lines.append(f"- Manifest load: {stats['manifest_s']:.2f}s  ")
    lines.append(f"- Vault walk + frontmatter parse: {stats['walk_s']:.2f}s  ")
    lines.append(f"- Rule evaluation: {stats['eval_s']:.2f}s  ")
    lines.append(f"- Proposal render: {stats['render_s']:.2f}s  ")
    lines.append("")

    # Manifest snapshot
    lines.append("## Manifest snapshot")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Manifest present | {telemetry['manifest_present']} |")
    lines.append(f"| Entries read | {stats['manifest_entries']} |")
    lines.append(f"| Superseded entries | {stats['manifest_superseded']} |")
    lines.append(f"| Distinct stems | {stats['manifest_stems']} |")
    lines.append(f"| Malformed lines skipped | {telemetry['manifest_malformed']} |")
    lines.append(f"| Entries without sha256 | {telemetry['manifest_no_sha']} |")
    lines.append("")
    if stats["manifest_entries"] == 0:
        lines.append(
            "_Manifest is empty - the v2 ingestion pipeline has not yet "
            "produced any production entries. Only Rule B (bitemporal "
            "supersession on cited sources) can fire in this state. Real "
            "hash-drift propagation activates once `00 Inbox/_drop/` "
            "ingests start writing to the manifest (post-S06 go-live)._"
        )
        lines.append("")

    # Stale by confidence
    lines.append("## Stale by confidence")
    lines.append("")
    if not any(by_conf.values()):
        lines.append("_No stale citations found._")
        lines.append("")
    else:
        for conf in ("HIGH", "MEDIUM", "LOW"):
            group = by_conf[conf]
            if not group:
                continue
            lines.append(f"### Confidence {conf} - {len(group)} note(s)")
            lines.append("")
            lines.append("| Path | Rule | Reason | Suggested action |")
            lines.append("|---|---|---|---|")
            # Sort by last_updated ascending (oldest first); None last.
            group.sort(key=lambda r: (r["last_updated"] is None, r["last_updated"] or date.today()))
            for r in group:
                # Each note may have multiple findings; show one line per finding.
                for f in r["findings"]:
                    lines.append(
                        f"| `{r['path']}` | {f['rule']} | {f['reason']} | {f['action']} |"
                    )
            lines.append("")

    # Stale by rule
    lines.append("## Stale by rule (diagnostic)")
    lines.append("")
    lines.append("| Rule | Count | Confidence |")
    lines.append("|---|---:|---|")
    rule_meta = {
        "A.1": ("HIGH",   "self pipeline.sha256 marked superseded in manifest"),
        "A.2": ("MEDIUM", "self pipeline.sha256 not in manifest"),
        "A.3": ("MEDIUM", "newer version of self stem ingested"),
        "B.1": ("HIGH",   "cited source is_latest_version: false"),
        "B.2": ("HIGH",   "cited source superseded_date set"),
        "B.3": ("LOW",    "cited source updated since citing note"),
        "C.1": ("MEDIUM", "body wikilinks an ingested note whose upstream is superseded"),
    }
    for rule in ("A.1", "A.2", "A.3", "B.1", "B.2", "B.3", "C.1"):
        c, _ = rule_meta[rule]
        lines.append(f"| {rule} | {rule_counts.get(rule, 0)} | {c} |")
    lines.append("")

    # Telemetry
    lines.append("## Telemetry")
    lines.append("")
    lines.append("| Bucket | Count |")
    lines.append("|---|---:|")
    lines.append(f"| Notes walked (post-exclusion) | {stats['notes_walked']} |")
    lines.append(f"| Citing-note candidates (has cite or self-ref) | {stats['candidates_total']} |")
    lines.append(f"| Source/decision pool | {stats['source_pool']} |")
    lines.append(f"| Notes without frontmatter | {telemetry['no_fm']} |")
    lines.append(f"| Notes with unparseable frontmatter | {telemetry['fm_error']} |")
    lines.append(f"| Unresolved citations (wikilink integrity, not stale) | {telemetry['unresolved_citations']} |")
    lines.append(f"| Manifest present | {telemetry['manifest_present']} |")
    lines.append(f"| Manifest malformed lines | {telemetry['manifest_malformed']} |")
    lines.append(f"| Manifest entries without sha256 | {telemetry['manifest_no_sha']} |")
    lines.append("")

    # Auto-suggest gate
    high = len(by_conf["HIGH"])
    medium = len(by_conf["MEDIUM"])
    lines.append("## Auto-suggest gate (KP-07 thresholds)")
    lines.append("")
    lines.append("| Threshold | Current | Triggered |")
    lines.append("|---|---:|---|")
    lines.append(f"| HIGH >= 5 | {high} | {'YES' if high >= 5 else 'no'} |")
    lines.append(f"| MEDIUM >= 20 | {medium} | {'YES' if medium >= 20 else 'no'} |")
    lines.append("")
    if high >= 5 or medium >= 20:
        lines.append(
            "_One or more auto-suggest thresholds tripped. Surface in next "
            "session start orientation._"
        )
        lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="kb-curator Karpathy Lint Mode 3 - stale propagation."
    )
    ap.add_argument("--root", default=None,
                    help="Vault root (auto-detect from cwd via CLAUDE.md).")
    ap.add_argument("--out", default=None,
                    help="Override proposal output path.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print summary only; do not write proposal.")
    args = ap.parse_args()

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

    telemetry = {
        "manifest_present":     False,
        "manifest_malformed":   0,
        "manifest_no_sha":      0,
        "no_fm":                0,
        "fm_error":             0,
        "unresolved_citations": 0,
    }

    t0 = time.time()

    # 1) Manifest
    manifest_path = vault_root / "99 Workspace" / "_ingestion_pipeline" / "_manifest.jsonl"
    print(f"[1/4] loading manifest at {manifest_path}...")
    hash_state, latest_by_stem, path_by_sha, manifest_entries, manifest_superseded = \
        load_manifest(manifest_path, telemetry)
    manifest_empty = manifest_entries == 0
    t1 = time.time()
    print(f"      {manifest_entries} entries, {manifest_superseded} superseded, "
          f"{len(latest_by_stem)} distinct stems")
    if manifest_empty:
        print(f"      INFO: manifest is empty - pipeline pre-go-live; "
              f"only Rule B can fire.")

    # 2) Vault walk - notes
    print(f"[2/4] walking vault at {vault_root}...")
    notes = []
    for path, rel, rel_parts in walk_vault(vault_root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        try:
            fm = parse_frontmatter(text)
        except Exception:
            fm = None
            telemetry["fm_error"] += 1
        if fm is None:
            telemetry["no_fm"] += 1
            note = {
                "path": rel, "abs_path": path, "text": text, "fm": None,
                "type": None, "aliases": [],
                "frontmatter_sources": [],
                "body_wikilinks": [],
            }
        else:
            type_value = fm.get("type")
            if type_value:
                type_value = type_value.strip().strip('"').strip("'")
            srcs   = parse_listfield(text, "sources")
            tagrs  = parse_listfield(text, "aliases")
            # body wikilinks (entire text, not just body - duplicates from FM are OK)
            wikis = [WIKILINK_RE.findall(text)]
            note = {
                "path": rel, "abs_path": path, "text": text, "fm": fm,
                "type": type_value, "aliases": tagrs,
                "frontmatter_sources": srcs,
                "body_wikilinks": [strip_wikilink(w) for w in WIKILINK_RE.findall(text)],
            }
        notes.append(note)
    t2 = time.time()
    print(f"      {len(notes)} notes scanned ({telemetry['no_fm']} without frontmatter)")

    # 3) Build indexes
    basenames, aliases, path_by_basename = build_indexes(notes)
    source_notes_by_basename = {
        n["basename"]: n
        for n in notes
        if n["type"] in SOURCE_TYPES
    }
    print(f"      {len(basenames)} basenames, "
          f"{len(source_notes_by_basename)} source/decision notes")

    # 4) Rule evaluation
    print(f"[3/4] evaluating rules A/B/C across {len(notes)} notes...")
    today = date.today()
    by_conf = {"HIGH": [], "MEDIUM": [], "LOW": []}
    rule_counts = defaultdict(int)
    candidates_total = 0

    for n in notes:
        fm = n["fm"] or {}
        pipeline_ns = fm.get("__pipeline__") or {}
        # Does this note carry self-citation fields OR cite-others fields?
        has_self = bool(
            pipeline_ns.get("sha256")
            or fm.get("source_file")
            or fm.get("original_path")
        )
        has_cites = bool(n["frontmatter_sources"]) or bool(n["body_wikilinks"])
        if not (has_self or has_cites):
            continue
        candidates_total += 1
        last_updated = parse_date(fm.get("last_updated"))
        findings = evaluate_note(
            n, today, hash_state, latest_by_stem, path_by_sha,
            source_notes_by_basename, basenames, aliases, telemetry,
            manifest_empty,
        )
        if not findings:
            continue
        # Top confidence determines bucket; all findings carry along.
        top_conf = max(findings, key=lambda f: confidence_rank(f["confidence"]))["confidence"]
        for f in findings:
            rule_counts[f["rule"]] += 1
        by_conf[top_conf].append({
            "path":         n["path"],
            "last_updated": last_updated,
            "findings":     findings,
        })
    t3 = time.time()
    print(f"      {sum(len(v) for v in by_conf.values())} notes flagged "
          f"(HIGH={len(by_conf['HIGH'])}, MEDIUM={len(by_conf['MEDIUM'])}, "
          f"LOW={len(by_conf['LOW'])})")

    # 5) Render proposal
    print(f"[4/4] rendering proposal...")
    stats = {
        "vault":               str(vault_root),
        "candidates_total":    candidates_total,
        "notes_walked":        len(notes),
        "source_pool":         len(source_notes_by_basename),
        "manifest_entries":    manifest_entries,
        "manifest_superseded": manifest_superseded,
        "manifest_stems":      len(latest_by_stem),
        "manifest_s":          t1 - t0,
        "walk_s":              t2 - t1,
        "eval_s":              t3 - t2,
        "render_s":            0.0,
        "runtime_s":           t3 - t0,
    }

    if args.dry_run:
        print(f"DRY RUN - no proposal written.")
        _print_summary(stats, by_conf, rule_counts, telemetry)
        return 0

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = vault_root / "99 Workspace" / f"_lint_stale_{date.today().isoformat()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    t_render_start = time.time()
    render_proposal(stats, by_conf, rule_counts, telemetry, out_path)
    stats["render_s"] = time.time() - t_render_start
    stats["runtime_s"] = time.time() - t0

    # Rewrite render-time-aware stats by patching the line we already wrote
    # (cheap: re-render)
    render_proposal(stats, by_conf, rule_counts, telemetry, out_path)

    _print_summary(stats, by_conf, rule_counts, telemetry)
    print(f"proposal written: {out_path}")
    return 0


def _print_summary(stats, by_conf, rule_counts, telemetry):
    print()
    print("=" * 60)
    print("lint-stale summary")
    print(f"  vault:               {stats['vault']}")
    print(f"  notes walked:        {stats['notes_walked']}")
    print(f"  citing candidates:   {stats['candidates_total']}")
    print(f"  source pool:         {stats['source_pool']}")
    print(f"  manifest entries:    {stats['manifest_entries']}")
    print(f"  manifest superseded: {stats['manifest_superseded']}")
    print(f"  flagged HIGH:        {len(by_conf['HIGH'])}")
    print(f"  flagged MEDIUM:      {len(by_conf['MEDIUM'])}")
    print(f"  flagged LOW:         {len(by_conf['LOW'])}")
    print(f"  runtime:             {stats['runtime_s']:.2f}s")
    if rule_counts:
        print("  rule counts:")
        for rule in ("A.1", "A.2", "A.3", "B.1", "B.2", "B.3", "C.1"):
            if rule_counts.get(rule):
                print(f"    {rule}: {rule_counts[rule]}")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
