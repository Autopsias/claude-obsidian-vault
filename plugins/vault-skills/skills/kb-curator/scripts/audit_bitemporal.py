#!/usr/bin/env python3
"""
audit_bitemporal.py — kb-curator P-4 bitemporal-frontmatter conformance.
VAULT-SIDE OVERRIDE (Galp Vault, S05/FM-03, 2026-05-14).

Extends the canonical plugin script with two new optional-field validators
(FM-01 + FM-02):
  confidence:  if present on CONFIDENCE_TYPES, must be float 0.0–1.0
  stale:       if present on any type, must be pending|confirmed|cleared

Both fields are optional — absent = pass. Fully backwards-compatible.

For every typed note in an OBSIDIAN vault that should carry bitemporal
metadata, verifies the frontmatter contract from `_operating_guide.md` P-4:

  type: source   → require `document_date` AND `is_latest_version`
  type: decision → require `document_date` AND `is_latest_version`
  type: meeting  → if `document_date` is present, must match filename YYYY-MM-DD
  type: source | decision | meeting | concept
                 → if `confidence:` is present, must be float 0.0–1.0
  any type       → if `stale:` is present, must be pending|confirmed|cleared

Usage
-----
  python3 audit_bitemporal.py [--root /path/to/vault]
  python3 audit_bitemporal.py --json    # machine-readable output
  python3 audit_bitemporal.py --quiet   # print failures only

Exit
----
  0  no violations
  1  at least one violation
  2  configuration error (vault not found, etc.)
"""

import argparse
import json
import os
import re
import sys
from datetime import date

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TYPES_REQUIRING_BITEMPORAL = frozenset({"source", "decision"})
TYPES_FILENAME_DATE_CHECK = frozenset({"meeting"})
REQUIRED_BITEMPORAL_FIELDS = ("document_date", "is_latest_version")

# Optional field types (P-4, S05/FM-01 + FM-02)
CONFIDENCE_TYPES = frozenset({"source", "decision", "meeting", "concept"})
STALE_VALID_VALUES = frozenset({"pending", "confirmed", "cleared"})

TYPED_ZONE_ROOTS = (
    "10 People", "20 Companies", "30 Projects",
    "40 Meetings", "50 Sources", "60 Concepts", "70 Decisions",
)

SKIP_DIRS = frozenset({
    ".git", ".obsidian", ".smart-env", ".claude",
    "_archive", "_archives", "_skill_packages", "_skill_resources",
    "_log_archive", "_session_handoff_archive",
    "node_modules", "__pycache__",
})


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
SIMPLE_FIELD_RE = re.compile(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*?)\s*$")


def parse_frontmatter(text):
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


def _norm_bool(val):
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in ("true", "yes", "on"):
        return True
    if s in ("false", "no", "off"):
        return False
    return None


def _norm_date(val):
    if val is None:
        return None
    s = str(val).strip().strip('"').strip("'")
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Vault walk
# ---------------------------------------------------------------------------

def iter_typed_files(root):
    for zone in TYPED_ZONE_ROOTS:
        zone_root = os.path.join(root, zone)
        if not os.path.isdir(zone_root):
            continue
        for dirpath, dirnames, filenames in os.walk(zone_root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for f in filenames:
                if not f.endswith(".md"):
                    continue
                if f.startswith("_"):
                    continue
                yield os.path.join(dirpath, f)


# ---------------------------------------------------------------------------
# Per-file check
# ---------------------------------------------------------------------------

def check_file(path, root):
    rel = os.path.relpath(path, root)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(4096)
    except OSError as e:
        return ["{}: cannot read file ({})".format(rel, e)]

    fm = parse_frontmatter(head)
    if fm is None:
        return ["{}: no YAML frontmatter found".format(rel)]

    ftype = (fm.get("type") or "").strip().strip('"').strip("'").lower()
    if not ftype:
        return ["{}: frontmatter missing `type:` (cannot audit P-4 conformance)".format(rel)]

    violations = []

    # --- Bitemporal required fields (type: source, decision) ---------------
    if ftype in TYPES_REQUIRING_BITEMPORAL:
        for field_name in REQUIRED_BITEMPORAL_FIELDS:
            if field_name not in fm or fm[field_name] in ("", None):
                violations.append(
                    "{}: type:{} missing required field `{}` (P-4)".format(
                        rel, ftype, field_name
                    )
                )
        if "document_date" in fm and fm["document_date"]:
            if _norm_date(fm["document_date"]) is None:
                violations.append(
                    "{}: type:{} has unparseable document_date `{}` (expect YYYY-MM-DD)".format(
                        rel, ftype, fm["document_date"]
                    )
                )
        if "is_latest_version" in fm and fm["is_latest_version"]:
            if _norm_bool(fm["is_latest_version"]) is None:
                violations.append(
                    "{}: type:{} has non-boolean is_latest_version `{}` (expect true/false)".format(
                        rel, ftype, fm["is_latest_version"]
                    )
                )

    # --- Meeting date-consistency check ------------------------------------
    if ftype in TYPES_FILENAME_DATE_CHECK:
        if "document_date" in fm and fm["document_date"]:
            fm_date = _norm_date(fm["document_date"])
            if fm_date is None:
                violations.append(
                    "{}: type:meeting has unparseable document_date `{}` (expect YYYY-MM-DD)".format(
                        rel, fm["document_date"]
                    )
                )
            else:
                filename = os.path.basename(path)
                fname_m = re.match(r"(\d{4})-(\d{2})-(\d{2})", filename)
                if not fname_m:
                    violations.append(
                        "{}: type:meeting filename does not start with YYYY-MM-DD; "
                        "filename is the source of truth for meeting date".format(rel)
                    )
                else:
                    fname_date_str = "{}-{}-{}".format(
                        fname_m.group(1), fname_m.group(2), fname_m.group(3)
                    )
                    try:
                        fname_date = date(
                            int(fname_m.group(1)),
                            int(fname_m.group(2)),
                            int(fname_m.group(3)),
                        )
                    except ValueError:
                        violations.append(
                            "{}: type:meeting filename prefix `{}` is not a valid date".format(
                                rel, fname_date_str
                            )
                        )
                    else:
                        if fname_date != fm_date:
                            violations.append(
                                "{}: type:meeting document_date `{}` != filename prefix `{}` "
                                "(filename wins per P-4)".format(
                                    rel, fm["document_date"], fname_date_str,
                                )
                            )

    # --- confidence: optional range check (S05/FM-01, P-4) ----------------
    # Applicable to CONFIDENCE_TYPES. Absent = pass.
    conf_raw = fm.get("confidence")
    if conf_raw is not None and conf_raw != "":
        if ftype not in CONFIDENCE_TYPES:
            violations.append(
                "{}: type:{} has `confidence:` but this field is only valid for "
                "{} (P-4 S05/FM-01)".format(rel, ftype, sorted(CONFIDENCE_TYPES))
            )
        else:
            try:
                conf_val = float(conf_raw)
                if not (0.0 <= conf_val <= 1.0):
                    violations.append(
                        "{}: type:{} confidence={} out of range [0.0, 1.0] (P-4)".format(
                            rel, ftype, conf_raw
                        )
                    )
            except (ValueError, TypeError):
                violations.append(
                    "{}: type:{} confidence='{}' is not a valid float (P-4)".format(
                        rel, ftype, conf_raw
                    )
                )

    # --- stale: optional enum check (S05/FM-02, P-4) ----------------------
    # Applicable to any typed note. Absent = pass.
    stale_raw = fm.get("stale")
    if stale_raw is not None and stale_raw != "":
        stale_str = str(stale_raw).strip().strip("'\"").lower()
        if stale_str not in STALE_VALID_VALUES:
            violations.append(
                "{}: type:{} stale='{}' not in valid enum {} (P-4 S05/FM-02)".format(
                    rel, ftype, stale_raw, sorted(STALE_VALID_VALUES)
                )
            )

    return violations


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_audit(root, verbose=True):
    by_type = {}
    all_violations = []
    files_checked = 0
    for path in iter_typed_files(root):
        files_checked += 1
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                head = f.read(4096)
        except OSError:
            continue
        fm = parse_frontmatter(head) or {}
        ftype = (fm.get("type") or "").strip().lower()
        by_type[ftype] = by_type.get(ftype, 0) + 1

        violations = check_file(path, root)
        for v in violations:
            all_violations.append(v)
            if verbose:
                print("  FAIL  {}".format(v))

    return {
        "files_checked": files_checked,
        "by_type": by_type,
        "violations": all_violations,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Audit P-4 bitemporal-frontmatter conformance across an OBSIDIAN vault."
    )
    parser.add_argument("--root", metavar="PATH", default=None,
                        help="Vault root (default: auto-detect from cwd via CLAUDE.md).")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="Output results as JSON.")
    parser.add_argument("--quiet", action="store_true",
                        help="Only print summary (no per-violation lines).")
    args = parser.parse_args()

    root = args.root or os.environ.get("COWORK_ROOT")
    if root is None:
        current = os.path.abspath(os.getcwd())
        while True:
            if os.path.exists(os.path.join(current, "CLAUDE.md")):
                root = current
                break
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
    if root is None:
        print("ERROR: no vault root found. Pass --root or set COWORK_ROOT.", file=sys.stderr)
        sys.exit(2)

    root = os.path.realpath(root)
    if not args.json_out:
        print("audit_bitemporal: checking root = {}\n".format(root))
        print("P-4 violations:")
        print("  bitemporal : document_date + is_latest_version (source/decision)")
        print("  date match : document_date vs filename prefix (meeting)")
        print("  confidence : float 0.0-1.0 if present (source/decision/meeting/concept)")
        print("  stale      : pending|confirmed|cleared if present (any type)")

    verbose = not args.quiet and not args.json_out
    result = run_audit(root, verbose=verbose)

    if args.json_out:
        print(json.dumps({
            "root":            root,
            "date":            date.today().isoformat(),
            "files_checked":   result["files_checked"],
            "by_type":         result["by_type"],
            "violations":      result["violations"],
            "violation_count": len(result["violations"]),
        }, indent=2))
    else:
        print()
        print("=" * 60)
        print("P-4 bitemporal audit: {} file(s) checked across typed zones".format(
            result["files_checked"]
        ))
        if result["by_type"]:
            tally = ", ".join(
                "{}:{}".format(t or "(no type)", n)
                for t, n in sorted(result["by_type"].items())
            )
            print("By type: {}".format(tally))
        if result["violations"]:
            print("VIOLATIONS: {}".format(len(result["violations"])))
        else:
            print("All typed notes conform to P-4.")
        print("=" * 60)

    sys.exit(0 if not result["violations"] else 1)


if __name__ == "__main__":
    main()
