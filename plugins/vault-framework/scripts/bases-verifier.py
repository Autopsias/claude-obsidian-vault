#!/usr/bin/env python3
"""
_bases_verifier.py — Vault Bases coverage / schema-conformance verifier (M7).

Walks the live Bases under ``90 System/Bases/``, parses each ``.base`` YAML,
extracts the per-Base schema (type filter + fields referenced in views),
then verifies that every typed-zone ``.md`` file in the vault conforms.

For each .base view the verifier extracts:
  * the bound ``type`` value (from ``filters.and: [..., 'type == "X"', ...]``)
  * field names referenced by ``order``, ``groupBy``, view-level ``filters``
    (these are the de-facto schema keys — Obsidian Bases will silently
    misrender if any are missing)

For every .md file in the vault (skipping plumbing dirs, archives, folder
notes) the verifier checks:
  1. YAML frontmatter parses cleanly.
  2. ``type:`` value (if present) is in the closed P-4 vocabulary.
  3. If the type binds to a live Base, every required key from that Base's
     extracted schema is present (and non-empty).
  4. Wikilinks anywhere in frontmatter resolve to an existing note (basename
     or alias match, vault-wide; Obsidian's default behaviour).

Type vocabulary (P-4 closed) — see ``90 System/_operating_guide.md`` P-4:
  person | company | project | meeting | source | concept | decision |
  guide | contract | log | handoff | handoff_archive | eval | inbox |
  daily | template | base | system

Allow-list — types that are valid but Bases-unbound (no per-Base schema check):
  inbox | daily | log | handoff | handoff_archive | system | contract |
  guide | eval | template | base
  (``concept`` is also Bases-unbound today — present in the vocabulary but
  no .base file yet; treated identically.)

CLI
---
    python3 90\ System/_bases_verifier.py [--strict] [--report PATH]
                                          [--vault PATH]

  --strict     exit 1 if any violation
  --report     custom report path
               (default: 99 Workspace/_bases_verification_YYYY-MM-DD.md)
  --vault      vault root override (default: parent-of-parent of script)

Exit codes
----------
  0  no violations, OR violations exist but --strict is not set
  1  --strict set and at least one violation
  2  unexpected error (Bases dir missing, malformed .base, IO failure)

Read by
-------
  galp-vault-health (weekly Mon 09:00) — invokes this script per
  ``90 System/_maintenance_automation.md`` step 3 of the health pass.
  The skill greps the stdout summary; the full report is the audit
  artefact.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError:
    print(
        "_bases_verifier.py: PyYAML required (apt install python3-yaml or "
        "pip install pyyaml --break-system-packages).",
        file=sys.stderr,
    )
    sys.exit(2)


# --- Constants --------------------------------------------------------------

# P-4 closed type vocabulary (operating guide, 2026-05-10).
KNOWN_TYPES: frozenset[str] = frozenset({
    "person", "company", "project", "meeting", "source", "concept",
    "decision", "guide", "contract", "log", "handoff", "handoff_archive",
    "eval", "inbox", "daily", "template", "base", "system",
})

# Types that may carry a `confidence:` field (P-4 optional, added 2026-05-14
# / FM-01 of Framework Remediation & Karpathy Adoption plan S05).
CONFIDENCE_TYPES: frozenset[str] = frozenset({"source", "decision", "meeting", "concept"})

# Valid values for the `stale:` tri-state field (P-4 optional, added 2026-05-14
# / FM-02 of Framework Remediation & Karpathy Adoption plan S05).
STALE_VALID_VALUES: frozenset[str] = frozenset({"pending", "confirmed", "cleared"})

# Types that are valid but not bound to any .base — Bases checks skipped.
BASES_UNBOUND_TYPES: frozenset[str] = frozenset({
    "inbox", "daily", "log", "handoff", "handoff_archive", "system",
    "contract", "guide", "eval", "template", "base", "concept",
})

# Built-in Bases properties prefixed with file. — not frontmatter keys.
BUILTIN_PROPERTY_PREFIXES: tuple[str, ...] = ("file.",)

# Directories never walked.
SKIP_DIRS: frozenset[str] = frozenset({
    ".obsidian", ".smart-env", ".git", ".claude", "__pycache__",
    "node_modules", "_archive",
    # Templates carry the typed schema with empty placeholder values by
    # design — they should never trip the schema-conformance check. Lives
    # at 90 System/Templates/ but matched here as a directory name.
    "Templates",
    # Staging folder for scheduled-task SKILL.md files; SKILL.md frontmatter
    # uses a different schema (Anthropic agent skill spec, not P-4).
    "_galp_vault_scheduled_tasks_staging",
})

# Filenames never checked.
SKIP_FILES: frozenset[str] = frozenset({
    "folder.md",  # Obsidian folder note placeholders
})

# Frontmatter fields that may legitimately contain `[[X]]` wikilinks.
# Restricting scanning to these avoids false positives where free-form
# fields like `description:` discuss link syntax academically (e.g.
# `_wikilink_audit.md`'s description mentions `[[Note#Heading]]` as an
# example, not as a real outbound link).
WIKILINK_FIELDS: frozenset[str] = frozenset({
    # Person / company / project relations
    "organization", "people", "companies", "projects", "project",
    "owner", "lead", "stakeholders", "attendees", "counterparty",
    "competitors", "related",
    # Decision lineage
    "replaces", "supersedes", "superseded_by", "supersedes_pointer",
    # Workstream / source linkage
    "workstream", "workstreams", "source_of", "linked_to",
})

# Frontmatter fields that are NEVER scanned for wikilinks even if they
# contain bracket-like text. `aliases` are this file's *own* alias names,
# not outbound links; `description` / `provenance` are free-form prose.
WIKILINK_EXCLUDE_FIELDS: frozenset[str] = frozenset({
    "aliases", "description", "provenance", "name", "title", "tags",
    "topics", "context", "role", "source", "status", "cadence",
    "companion_docs", "ricardo_verdicts", "quality",
})

# Wikilink pattern. Matches [[Target]] and [[Target|Alias]]. Non-greedy.
WIKILINK_RE = re.compile(r"\[\[([^\[\]\|]+?)(?:\|[^\[\]]*?)?\]\]")

# Filter expression: e.g. status == "active". Captures the LHS field name.
# We only use this to extract the field name, not to evaluate truth.
FILTER_FIELD_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*[!=<>]")


# --- Data classes -----------------------------------------------------------


@dataclass
class BaseSchema:
    """Schema extracted from a single .base file."""

    name: str  # filename stem, e.g. "People"
    path: Path
    type_value: str | None  # e.g. "person"; None if no type filter found
    is_view_only: bool = False  # True if Base filters a subset / spans
                                # multiple types — does NOT contribute to
                                # per-type schema enforcement (e.g.
                                # "Tier-2 Sources", "Open Items").
    all_types: list[str] = field(default_factory=list)  # all type literals
                                # referenced anywhere in the filter tree
                                # (for human-readable labelling).
    required_keys: set[str] = field(default_factory=set)
    raw: dict = field(default_factory=dict)

    def type_label(self) -> str:
        """Human-readable label used in stdout summary and report."""
        if not self.is_view_only:
            return f"`{self.type_value or '—'}`"
        unique = sorted(set(self.all_types))
        if len(unique) > 1:
            return "view-only (cross-type: " + ", ".join(unique) + ")"
        if len(unique) == 1:
            return f"view-only ({unique[0]})"
        return "view-only (cross-type)"


@dataclass
class FileReport:
    """Per-file verification result."""

    path: Path
    rel: str
    type_value: str | None
    base: str | None  # which Base this file is checked against (or None)
    violations: list[str] = field(default_factory=list)
    wikilink_orphans: list[str] = field(default_factory=list)


# --- Base parsing -----------------------------------------------------------


def _walk_filter_clause(clause, fields_out: set[str]) -> None:
    """Recursively pull field names out of a Bases filter clause."""
    if isinstance(clause, dict):
        for op_key in ("and", "or", "not"):
            if op_key in clause:
                children = clause[op_key]
                if isinstance(children, list):
                    for child in children:
                        _walk_filter_clause(child, fields_out)
                elif isinstance(children, dict):
                    _walk_filter_clause(children, fields_out)
    elif isinstance(clause, str):
        m = FILTER_FIELD_RE.match(clause)
        if m:
            field_name = m.group(1)
            if not field_name.startswith(BUILTIN_PROPERTY_PREFIXES):
                fields_out.add(field_name)


def _extract_type_binding(filters: dict | list | None) -> str | None:
    """Return the literal value X from `type == "X"` if present.
    Returns the FIRST binding found (depth-first, top-down). Used for
    primary-Base detection paired with _is_view_only_filter.
    """
    if not filters:
        return None
    if isinstance(filters, dict):
        for child in filters.values():
            if isinstance(child, list):
                for clause in child:
                    found = _extract_type_binding_from_string(clause)
                    if found:
                        return found
                    nested = _extract_type_binding(clause if isinstance(clause, dict) else None)
                    if nested:
                        return nested
    return None


def _extract_all_type_bindings(filters) -> list[str]:
    """Return EVERY ``type == "X"`` value found anywhere in the filter
    tree. Used for human-readable labelling of view-only Bases that span
    multiple types (e.g. Open Items spans person/company/project/decision).
    """
    out: list[str] = []
    if not filters:
        return out
    if isinstance(filters, dict):
        for child in filters.values():
            if isinstance(child, list):
                for clause in child:
                    s = _extract_type_binding_from_string(clause)
                    if s:
                        out.append(s)
                    elif isinstance(clause, dict):
                        out.extend(_extract_all_type_bindings(clause))
            elif isinstance(child, dict):
                out.extend(_extract_all_type_bindings(child))
    return out


def _extract_type_binding_from_string(s) -> str | None:
    if not isinstance(s, str):
        return None
    m = re.match(r"""^\s*type\s*==\s*['"](.+?)['"]\s*$""", s)
    return m.group(1) if m else None


def _is_view_only_filter(filters) -> bool:
    """A Base "primarily defines a type" only if its top-level filter is
    exactly ``and: [type == "X"]`` with a single conjunct. Anything else
    (multi-conjunct AND like ``type == "source" AND tier == "tier-2"``,
    OR clauses spanning multiple types like Open Items, NOT clauses, or
    a missing filter) means the Base is **view-only**: it filters a
    subset or spans types, and its required_keys must NOT be merged into
    the type→base mapping (that would shadow the primary Base for that
    type, leading to a wrong schema check).

    This heuristic preserves the existing six primary Bases (each is a
    single-conjunct ``type == "X"``) while correctly classifying
    derivative Bases like ``Open Items.base`` and ``Tier-2 Sources.base``.
    """
    if not isinstance(filters, dict):
        return True
    if list(filters.keys()) != ["and"]:
        return True  # OR or NOT at the top level → view-only
    children = filters.get("and")
    if not isinstance(children, list) or len(children) != 1:
        return True  # zero or >1 conjuncts → view-only
    sole = children[0]
    if not isinstance(sole, str):
        return True  # nested clause → view-only
    return _extract_type_binding_from_string(sole) is None


def parse_base_file(path: Path) -> BaseSchema:
    """Parse a .base file and extract its schema-relevant fields."""
    raw_text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f"ERROR: malformed .base YAML at {path}: {exc}")

    schema = BaseSchema(name=path.stem, path=path, type_value=None, raw=data)

    # Top-level type filter (informational; preserves the underlying type
    # for view-only Bases so the run summary stays human-readable).
    schema.type_value = _extract_type_binding(data.get("filters"))
    schema.is_view_only = _is_view_only_filter(data.get("filters"))
    schema.all_types = _extract_all_type_bindings(data.get("filters"))

    # Pull field references from top-level filters (excluding `type`)
    top_fields: set[str] = set()
    _walk_filter_clause(data.get("filters"), top_fields)
    top_fields.discard("type")
    schema.required_keys.update(top_fields)

    # Pull from each view
    for view in data.get("views", []) or []:
        if not isinstance(view, dict):
            continue
        # View-level filters
        view_fields: set[str] = set()
        _walk_filter_clause(view.get("filters"), view_fields)
        view_fields.discard("type")
        schema.required_keys.update(view_fields)

        # order: [{property: X, direction: ...}]
        order = view.get("order")
        if isinstance(order, list):
            for entry in order:
                if isinstance(entry, dict):
                    prop = entry.get("property")
                    if prop and isinstance(prop, str) and not prop.startswith(BUILTIN_PROPERTY_PREFIXES):
                        schema.required_keys.add(prop)

        # groupBy: {property: X}
        group_by = view.get("groupBy")
        if isinstance(group_by, dict):
            prop = group_by.get("property")
            if prop and isinstance(prop, str) and not prop.startswith(BUILTIN_PROPERTY_PREFIXES):
                schema.required_keys.add(prop)

    # `title` is implicit (every Obsidian note has it via filename) but Bases
    # views often `order: title` — keep it as a required key only if a view
    # references it explicitly. We do; the loop above already added it.

    return schema


def load_all_bases(bases_dir: Path) -> list[BaseSchema]:
    if not bases_dir.is_dir():
        raise SystemExit(f"ERROR: Bases directory not found: {bases_dir}")
    bases = sorted(bases_dir.glob("*.base"))
    if not bases:
        raise SystemExit(f"ERROR: no .base files in {bases_dir}")
    return [parse_base_file(p) for p in bases]


# --- Frontmatter parsing ----------------------------------------------------


def parse_frontmatter(text: str) -> tuple[dict | None, str | None]:
    """Return (dict, error_or_none). dict is None if no frontmatter at all."""
    if not text.startswith("---"):
        return None, None  # No frontmatter — caller decides
    body = text[3:]
    end = body.find("\n---")
    if end == -1:
        return None, "unterminated_frontmatter"
    block = body[:end]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        # Squash multi-line YAML errors to one line
        first = str(exc).splitlines()[0]
        return None, f"yaml_error: {first}"
    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return None, f"frontmatter_not_mapping: top-level is {type(data).__name__}"
    return data, None


# --- Wikilink scanning ------------------------------------------------------


def _collect_wikilinks_recursive(value) -> list[str]:
    """Recurse into a value (already known to be link-bearing) and pull all `[[X]]`."""
    out: list[str] = []
    if isinstance(value, str):
        for m in WIKILINK_RE.finditer(value):
            out.append(m.group(1).strip())
    elif isinstance(value, list):
        for item in value:
            out.extend(_collect_wikilinks_recursive(item))
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_collect_wikilinks_recursive(v))
    return out


def collect_wikilinks(fm: dict) -> list[str]:
    """Return all [[Target]] wiki-ids inside *link-bearing* frontmatter fields.

    Only scans top-level keys present in WIKILINK_FIELDS. Free-form fields
    like `description` or `provenance` may contain illustrative bracket
    syntax that is not a real outbound link — those are excluded explicitly
    via WIKILINK_EXCLUDE_FIELDS to keep the policy auditable.
    """
    out: list[str] = []
    if not isinstance(fm, dict):
        return out
    for key, value in fm.items():
        if key in WIKILINK_EXCLUDE_FIELDS:
            continue
        if key not in WIKILINK_FIELDS:
            # Conservative default: only scan known link-bearing fields.
            # Add new fields to WIKILINK_FIELDS as the schema grows.
            continue
        out.extend(_collect_wikilinks_recursive(value))
    return out


def build_link_index(vault: Path) -> tuple[set[str], set[str]]:
    """Return (basenames, aliases) for vault-wide wikilink resolution."""
    basenames: set[str] = set()
    aliases: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(vault):
        # Prune skip dirs
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            stem = fname[:-3]
            basenames.add(stem)
            # Read frontmatter for aliases (lightweight — we already do this
            # for verification; but build_link_index is called once before
            # the verification loop, so just touch each file once here too).
            path = Path(dirpath) / fname
            try:
                head = path.read_text(encoding="utf-8", errors="replace")[:4096]
            except OSError:
                continue
            fm, _err = parse_frontmatter(head)
            if not fm:
                continue
            al = fm.get("aliases")
            if isinstance(al, list):
                for a in al:
                    if isinstance(a, str) and a.strip():
                        aliases.add(a.strip())
            elif isinstance(al, str) and al.strip():
                aliases.add(al.strip())
    return basenames, aliases


def resolve_wikilink(target: str, basenames: set[str], aliases: set[str]) -> bool:
    """Return True if target resolves to an existing note."""
    target = target.strip()
    if not target:
        return False
    # Path-style links like [[10 People/Ricardo Carvalho]] — match on basename.
    if "/" in target:
        target = target.rsplit("/", 1)[1]
    # Section anchors: [[Note#Section]]
    if "#" in target:
        target = target.split("#", 1)[0].strip()
    if not target:
        return False
    return target in basenames or target in aliases


# --- Verification core ------------------------------------------------------


@dataclass
class Verification:
    bases: list[BaseSchema]
    file_reports: list[FileReport] = field(default_factory=list)
    type_violations: list[FileReport] = field(default_factory=list)
    yaml_violations: list[tuple[str, str]] = field(default_factory=list)  # (rel, error)
    orphan_wikilinks: list[tuple[str, str]] = field(default_factory=list)  # (rel, target)

    def per_base_counts(self) -> dict[str, tuple[int, int]]:
        """{base_name: (pass_count, fail_count)}."""
        counts: dict[str, tuple[int, int]] = {}
        for b in self.bases:
            passes = 0
            fails = 0
            for r in self.file_reports:
                if r.base != b.name:
                    continue
                if r.violations:
                    fails += 1
                else:
                    passes += 1
            counts[b.name] = (passes, fails)
        return counts


def assert_unbound_types_have_no_base(bases: list[BaseSchema]) -> None:
    """IH-05: Assert BASES_UNBOUND_TYPES ∩ {type_value for b in bases} == ∅.

    Fail loud if any type in BASES_UNBOUND_TYPES is also declared by a .base
    file.  This catches the case where someone adds e.g. ``Concepts.base``
    without removing ``concept`` from BASES_UNBOUND_TYPES — the schema check
    would silently skip that type, leaving files mischecked.
    """
    drift = [b for b in bases if b.type_value and b.type_value in BASES_UNBOUND_TYPES]
    if drift:
        details = ", ".join(f"'{b.type_value}' ({b.name}.base)" for b in drift)
        raise SystemExit(
            f"ERROR (IH-05): BASES_UNBOUND_TYPES drift — type(s) {details} are "
            f"declared by a .base file but also listed in BASES_UNBOUND_TYPES. "
            f"Fix: remove the type from BASES_UNBOUND_TYPES, or delete/rename the "
            f".base file."
        )


def verify_vault(vault: Path) -> Verification:
    bases_dir = vault / "90 System" / "Bases"
    bases = load_all_bases(bases_dir)
    assert_unbound_types_have_no_base(bases)  # IH-05 invariant check
    # Only PRIMARY Bases (single ``type == "X"`` top-level filter) define
    # a type's schema. View-only Bases — those spanning types or applying
    # extra conjuncts — are recorded in the run summary but do NOT bind
    # to the type, so they cannot shadow the primary Base.
    type_to_base: dict[str, BaseSchema] = {
        b.type_value: b for b in bases if b.type_value and not b.is_view_only
    }

    basenames, aliases = build_link_index(vault)
    v = Verification(bases=bases)

    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            if not fname.endswith(".md") or fname in SKIP_FILES:
                continue
            path = Path(dirpath) / fname
            try:
                rel = str(path.relative_to(vault))
            except ValueError:
                rel = str(path)

            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                v.yaml_violations.append((rel, f"read_error: {exc}"))
                continue

            fm, err = parse_frontmatter(text)
            if err:
                v.yaml_violations.append((rel, err))
                continue
            if fm is None:
                # No frontmatter — out of scope for the Bases verifier.
                # _lint_frontmatter.py is the right tool for that check.
                continue

            type_value = fm.get("type") if isinstance(fm.get("type"), str) else None

            report = FileReport(path=path, rel=rel, type_value=type_value, base=None)

            # Type-vocabulary check
            if type_value is None:
                # No type set — skip Base check; allowed if file is in
                # Inbox/Daily/Workspace (P-4 carve-outs), otherwise the
                # frontmatter linter handles it.
                pass
            elif type_value not in KNOWN_TYPES:
                report.violations.append(f"type '{type_value}' outside closed P-4 vocabulary")
                v.type_violations.append(report)
                # Continue to wikilink check; do not skip the file entirely.
            else:
                # Type is in the closed vocabulary. Check Bases binding.
                if type_value in BASES_UNBOUND_TYPES:
                    pass  # No per-Base schema check
                elif type_value in type_to_base:
                    base = type_to_base[type_value]
                    report.base = base.name
                    for key in sorted(base.required_keys):
                        if key not in fm:
                            report.violations.append(
                                f"missing required key '{key}' (per {base.name}.base)"
                            )
                            continue
                        val = fm[key]
                        # Empty string / None / empty list — counts as missing.
                        if val is None or (isinstance(val, str) and not val.strip()) \
                                or (isinstance(val, list) and len(val) == 0):
                            report.violations.append(
                                f"empty required key '{key}' (per {base.name}.base)"
                            )
                else:
                    # Type is in vocabulary but no .base maps to it. This is
                    # a structural inconsistency — flag it.
                    report.violations.append(
                        f"type '{type_value}' has no matching .base file"
                    )

            # --- Optional-field validation (P-4, S05/FM-03) ---------------------
            # `confidence:` — if present, must be float 0.0–1.0.
            # Applicable only to CONFIDENCE_TYPES; absent = pass.
            if "confidence" in fm:
                conf_raw = fm["confidence"]
                if conf_raw is None or (isinstance(conf_raw, str) and not conf_raw.strip()):
                    pass  # absent / null → pass (not assessed)
                else:
                    try:
                        conf_val = float(conf_raw)
                        if not (0.0 <= conf_val <= 1.0):
                            report.violations.append(
                                f"confidence={conf_raw!r} out of range [0.0, 1.0] (P-4)"
                            )
                        elif type_value and type_value not in CONFIDENCE_TYPES:
                            report.violations.append(
                                f"confidence field on type='{type_value}' — "
                                f"only {sorted(CONFIDENCE_TYPES)} support it (P-4)"
                            )
                    except (ValueError, TypeError):
                        report.violations.append(
                            f"confidence={conf_raw!r} is not a valid float (P-4)"
                        )

            # `stale:` — if present, must be one of STALE_VALID_VALUES.
            # Applicable to any typed note; absent = pass.
            if "stale" in fm:
                stale_raw = fm.get("stale")
                if stale_raw is None or (isinstance(stale_raw, str) and not str(stale_raw).strip()):
                    pass  # absent / null → pass
                else:
                    stale_str = str(stale_raw).strip().strip("'\"").lower()
                    if stale_str not in STALE_VALID_VALUES:
                        report.violations.append(
                            f"stale='{stale_raw}' not in valid enum "
                            f"{sorted(STALE_VALID_VALUES)} (P-4)"
                        )
            # --------------------------------------------------------------------

            # Wikilink resolution — anywhere in frontmatter.
            for target in collect_wikilinks(fm):
                if not resolve_wikilink(target, basenames, aliases):
                    report.wikilink_orphans.append(target)
                    v.orphan_wikilinks.append((rel, target))

            v.file_reports.append(report)

    return v


# --- Reporting --------------------------------------------------------------


def render_report(v: Verification, vault: Path) -> str:
    today = date.today().isoformat()
    lines: list[str] = []
    lines.append("---")
    lines.append("name: Bases Verification Report")
    lines.append(
        "description: Per-Base schema-conformance and wikilink-integrity audit "
        "for the live Galp Vault Bases. Produced by 90 System/_bases_verifier.py."
    )
    lines.append("type: log")
    lines.append("cadence: weekly")
    lines.append(f"last_updated: {today}")
    lines.append("provenance: 90 System/_bases_verifier.py — auto-generated")
    lines.append("---")
    lines.append("")
    lines.append(f"# Bases Verification — {today}")
    lines.append("")
    lines.append(f"Vault: `{vault}`")
    lines.append(f"Bases scanned: {len(v.bases)}")
    lines.append(f"Files inspected: {len(v.file_reports) + len(v.yaml_violations)}")
    lines.append("")
    lines.append("## How to read this report")
    lines.append("")
    lines.append(
        "Four classes of finding. Each is independent — fixing one does not "
        "alter the others."
    )
    lines.append("")
    lines.append(
        "1. **Schema fails** — files whose `type:` binds to a Base but are "
        "missing or have empty values for keys the Base's views require. "
        "The Base will silently misrender these rows."
    )
    lines.append(
        "2. **Type-vocabulary violations** — files with a `type:` value "
        "outside the closed P-4 list (operating guide P-4). Bases ignore "
        "them; cascade step 2 (structural) cannot find them."
    )
    lines.append(
        "3. **Malformed YAML** — frontmatter that PyYAML refuses to parse. "
        "Obsidian's lenient parser may still render these, but Bases and the "
        "verifier cannot index them."
    )
    lines.append(
        "4. **Orphan wikilinks** — `[[Target]]` references in link-bearing "
        "frontmatter fields that resolve to no existing note (no basename "
        "match, no alias match) anywhere in the vault."
    )
    lines.append("")

    # --- Summary table ---
    lines.append("## Summary")
    lines.append("")
    lines.append("| Base | Type | Pass | Fail | Required keys |")
    lines.append("|---|---|---:|---:|---|")
    counts = v.per_base_counts()
    for b in v.bases:
        p, f = counts[b.name]
        keys = ", ".join(sorted(b.required_keys)) or "—"
        lines.append(f"| {b.name} | {b.type_label()} | {p} | {f} | {keys} |")
    lines.append("")

    total_yaml = len(v.yaml_violations)
    total_type = len(v.type_violations)
    total_orphan = len(v.orphan_wikilinks)
    total_schema_fails = sum(f for _, f in counts.values())
    lines.append(
        f"**Totals:** schema-fails={total_schema_fails} · type-vocab-violations="
        f"{total_type} · malformed-yaml={total_yaml} · orphan-wikilinks={total_orphan}"
    )
    lines.append("")

    # --- Per-Base detail ---
    for b in v.bases:
        lines.append(f"## {b.name}")
        lines.append("")
        if b.is_view_only:
            lines.append(
                "- **View-only Base.** Filters a subset or spans multiple "
                "types; does not contribute to per-type schema enforcement."
            )
            lines.append(f"- **Type label:** {b.type_label()}")
        else:
            lines.append(f"- **Type filter:** `type == \"{b.type_value}\"`")
        lines.append(f"- **Required keys (extracted from views):** "
                     f"{', '.join(sorted(b.required_keys)) or '—'}")
        p, f = counts[b.name]
        lines.append(f"- **Pass / Fail:** {p} / {f}")
        lines.append("")
        if f == 0:
            lines.append("Clean.")
            lines.append("")
            continue
        lines.append("### Failures")
        lines.append("")
        for r in v.file_reports:
            if r.base != b.name or not r.violations:
                continue
            lines.append(f"- `{r.rel}`")
            for vio in r.violations:
                lines.append(f"  - {vio}")
        lines.append("")

    # --- Type-vocabulary violations ---
    lines.append("## Type-vocabulary violations")
    lines.append("")
    if not v.type_violations:
        lines.append("Clean.")
        lines.append("")
    else:
        for r in v.type_violations:
            lines.append(f"- `{r.rel}` — type=`{r.type_value}`")
        lines.append("")

    # --- Malformed YAML ---
    lines.append("## Malformed YAML")
    lines.append("")
    if not v.yaml_violations:
        lines.append("Clean.")
        lines.append("")
    else:
        for rel, err in v.yaml_violations:
            lines.append(f"- `{rel}` — {err}")
        lines.append("")

    # --- Orphan wikilinks ---
    lines.append("## Orphan wikilinks (frontmatter only)")
    lines.append("")
    if not v.orphan_wikilinks:
        lines.append("Clean.")
        lines.append("")
    else:
        # Group by file
        by_file: dict[str, list[str]] = {}
        for rel, target in v.orphan_wikilinks:
            by_file.setdefault(rel, []).append(target)
        for rel in sorted(by_file):
            tgts = sorted(set(by_file[rel]))
            lines.append(f"- `{rel}` — unresolved: {', '.join(f'`{t}`' for t in tgts)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_stdout_summary(v: Verification, report_path: Path) -> str:
    today = date.today().isoformat()
    out: list[str] = []
    out.append(f"Bases verifier — {today}")
    counts = v.per_base_counts()
    width = max((len(b.name) for b in v.bases), default=8)
    for b in v.bases:
        p, f = counts[b.name]
        total = p + f
        out.append(f"  {b.name.ljust(width)} : {p:3d} pass / {f:3d} fail "
                   f"({total} files; type={b.type_label()})")
    out.append(f"Type-vocabulary violations: {len(v.type_violations)}")
    out.append(f"Malformed YAML: {len(v.yaml_violations)}")
    out.append(f"Orphan wikilinks: {len(v.orphan_wikilinks)}")
    out.append(f"Report: {report_path}")
    return "\n".join(out)


# --- CLI --------------------------------------------------------------------


def default_vault_root(script: Path) -> Path:
    # script lives at <vault>/90 System/_bases_verifier.py
    return script.resolve().parent.parent


def default_report_path(vault: Path) -> Path:
    return vault / "99 Workspace" / f"_bases_verification_{date.today().isoformat()}.md"


# --- --bases mode: fast structural check on .base files only ---------------
#
# Added Session S03 (2026-05-11), BT-05 extension. Checks all .base files
# for structural validity WITHOUT walking the vault's .md files. Three
# specific checks are added for the three new BT-04/05/06 bases:
#   BC-01  Latest Only   — is_latest_version in filters; document_date in order
#   BC-02  As Of         — document_date AND superseded_date in filters
#   BC-03  Version Chain — document_version in filters or order; file.name in order
#
# Exit codes (--bases mode):
#   0  all bases parse and pass their structural checks
#   1  --strict and at least one failure
#   2  unexpected error
#
# The full vault walk (default mode) is still the authoritative check; --bases
# is a fast daily/CI gate for catching .base regressions without the ~N-file walk.


def _collect_filter_fields(filters) -> set[str]:
    """Return all field names referenced in a filter tree (flat set)."""
    out: set[str] = set()
    _walk_filter_clause(filters, out)
    return out


def _collect_order_properties(views: list) -> set[str]:
    """Return all property names used in any view's order clause."""
    out: set[str] = set()
    for view in views or []:
        if not isinstance(view, dict):
            continue
        order = view.get("order")
        if isinstance(order, list):
            for entry in order:
                if isinstance(entry, dict):
                    prop = entry.get("property")
                    if isinstance(prop, str):
                        out.add(prop)
    return out


@dataclass
class BaseCheck:
    """Result of one --bases structural check."""
    base_name: str
    check_id: str
    passed: bool
    detail: str


def check_latest_only(schema: BaseSchema) -> list[BaseCheck]:
    """BC-01: Latest Only — is_latest_version in filters; document_date in order."""
    checks: list[BaseCheck] = []
    filter_fields = _collect_filter_fields(schema.raw.get("filters"))
    order_props = _collect_order_properties(schema.raw.get("views", []))

    checks.append(BaseCheck(
        base_name=schema.name,
        check_id="BC-01a",
        passed="is_latest_version" in filter_fields,
        detail=(
            "filter references 'is_latest_version'" if "is_latest_version" in filter_fields
            else "FAIL: 'is_latest_version' not found in filters"
        ),
    ))
    checks.append(BaseCheck(
        base_name=schema.name,
        check_id="BC-01b",
        passed="document_date" in order_props,
        detail=(
            "at least one view orders by 'document_date'" if "document_date" in order_props
            else "FAIL: no view orders by 'document_date'"
        ),
    ))
    return checks


def check_as_of(schema: BaseSchema) -> list[BaseCheck]:
    """BC-02: As Of — document_date AND superseded_date in filters."""
    checks: list[BaseCheck] = []
    filter_fields = _collect_filter_fields(schema.raw.get("filters"))

    for field in ("document_date", "superseded_date"):
        checks.append(BaseCheck(
            base_name=schema.name,
            check_id=f"BC-02({'a' if field == 'document_date' else 'b'})",
            passed=field in filter_fields,
            detail=(
                f"filter references '{field}'" if field in filter_fields
                else f"FAIL: '{field}' not found in filters"
            ),
        ))
    return checks


def check_version_chain(schema: BaseSchema) -> list[BaseCheck]:
    """BC-03: Version Chain — document_version in filters or order; file.name in order."""
    checks: list[BaseCheck] = []
    filter_fields = _collect_filter_fields(schema.raw.get("filters"))
    order_props = _collect_order_properties(schema.raw.get("views", []))

    # document_version must appear in filters OR order
    dv_ok = "document_version" in filter_fields or "document_version" in order_props
    checks.append(BaseCheck(
        base_name=schema.name,
        check_id="BC-03a",
        passed=dv_ok,
        detail=(
            "'document_version' found in filters/order" if dv_ok
            else "FAIL: 'document_version' not in filters or order"
        ),
    ))
    checks.append(BaseCheck(
        base_name=schema.name,
        check_id="BC-03b",
        passed="file.name" in order_props,
        detail=(
            "at least one view orders by 'file.name'" if "file.name" in order_props
            else "FAIL: no view orders by 'file.name' (needed for family grouping)"
        ),
    ))
    return checks


# Map of base name → specific check function (for the 3 new BT bases)
BASE_SPECIFIC_CHECKS: dict[str, object] = {
    "Latest Only": check_latest_only,
    "As Of": check_as_of,
    "Version Chain": check_version_chain,
}


def run_bases_mode(vault: Path) -> tuple[list[BaseSchema], list[BaseCheck]]:
    """Load all bases, run structural checks, return (bases, check_results)."""
    bases_dir = vault / "90 System" / "Bases"
    bases = load_all_bases(bases_dir)
    checks: list[BaseCheck] = []
    for schema in bases:
        fn = BASE_SPECIFIC_CHECKS.get(schema.name)
        if fn is not None:
            checks.extend(fn(schema))  # type: ignore[call-arg]
    return bases, checks


def render_bases_report(bases: list[BaseSchema], checks: list[BaseCheck], vault: Path) -> str:
    today = date.today().isoformat()
    lines: list[str] = []
    lines.append("---")
    lines.append("name: Bases Structural Check Report")
    lines.append(
        "description: Fast structural check on all .base files — validates YAML, "
        "required views, and the three BT-specific invariants (BC-01/02/03). "
        "Produced by 90 System/_bases_verifier.py --bases."
    )
    lines.append("type: log")
    lines.append(f"last_updated: {today}")
    lines.append("provenance: 90 System/_bases_verifier.py --bases — auto-generated")
    lines.append("---")
    lines.append("")
    lines.append(f"# Bases Structural Check — {today}")
    lines.append("")
    lines.append(f"Vault: `{vault}`")
    lines.append(f"Bases found: {len(bases)}")
    lines.append(f"Structural checks run: {len(checks)}")
    lines.append("")

    all_pass = all(c.passed for c in checks)
    lines.append(f"**Result: {'✓ ALL PASS' if all_pass else '✗ FAILURES DETECTED'}**")
    lines.append("")

    # Per-base table
    lines.append("## All Bases")
    lines.append("")
    lines.append("| Base | Type label | Views | Required keys | Parse |")
    lines.append("|---|---|---:|---|---|")
    for b in bases:
        views = b.raw.get("views") or []
        keys = ", ".join(sorted(b.required_keys)) or "—"
        lines.append(
            f"| {b.name} | {b.type_label()} | {len(views)} | {keys} | ✓ |"
        )
    lines.append("")

    # BC checks
    lines.append("## BT Structural Checks (BC-01 / BC-02 / BC-03)")
    lines.append("")
    lines.append("| Check | Base | Passed | Detail |")
    lines.append("|---|---|:---:|---|")
    for c in checks:
        icon = "✓" if c.passed else "✗"
        lines.append(f"| {c.check_id} | {c.base_name} | {icon} | {c.detail} |")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify Galp Vault Bases conformance.")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any violation")
    ap.add_argument("--bases", action="store_true",
                    help="fast structural check on .base files only (no vault walk); "
                         "also runs BC-01/02/03 checks on the three BT-new bases")
    ap.add_argument("--report", type=Path, default=None,
                    help="report path (default: 99 Workspace/_bases_verification_<date>.md "
                         "or _bases_structural_<date>.md in --bases mode)")
    ap.add_argument("--vault", type=Path, default=None,
                    help="vault root (default: parent-of-parent of script)")
    args = ap.parse_args(argv)

    script = Path(__file__)
    vault = (args.vault or default_vault_root(script)).resolve()
    if not vault.is_dir():
        print(f"ERROR: vault root not a directory: {vault}", file=sys.stderr)
        return 2

    today = date.today().isoformat()

    # --- --bases mode: fast structural check only ---
    if args.bases:
        default_rp = vault / "99 Workspace" / f"_bases_structural_{today}.md"
        report_path = (args.report or default_rp).resolve()
        try:
            bases, checks = run_bases_mode(vault)
        except SystemExit as exc:
            if exc.code is not None:
                return int(exc.code) if isinstance(exc.code, int) else 2
            return 2

        report_text = render_bases_report(bases, checks, vault)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")

        # Stdout summary
        print(f"Bases structural check — {today}")
        print(f"  Bases found: {len(bases)}")
        for b in bases:
            label = b.type_label()
            views_n = len(b.raw.get("views") or [])
            print(f"    {b.name.ljust(20)} : {views_n} view(s); type={label}")
        if checks:
            print(f"  BT structural checks ({len(checks)}):")
            for c in checks:
                icon = "✓" if c.passed else "✗"
                print(f"    {c.check_id}  {c.base_name.ljust(16)} {icon}  {c.detail}")
        else:
            print("  No BT structural checks registered for these bases.")
        all_pass = all(c.passed for c in checks)
        print(f"  Report: {report_path}")
        if args.strict and not all_pass:
            return 1
        return 0

    # --- Default mode: full vault walk ---
    report_path = (args.report or default_report_path(vault)).resolve()

    try:
        v = verify_vault(vault)
    except SystemExit as exc:
        # SystemExit raised by load_all_bases / parse_base_file
        if exc.code is not None:
            return int(exc.code) if isinstance(exc.code, int) else 2
        return 2

    report_text = render_report(v, vault)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")

    print(render_stdout_summary(v, report_path))

    counts = v.per_base_counts()
    has_violation = (
        any(f > 0 for _, f in counts.values())
        or v.type_violations
        or v.yaml_violations
        or v.orphan_wikilinks
    )
    if args.strict and has_violation:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
