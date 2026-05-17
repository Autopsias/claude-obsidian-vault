#!/usr/bin/env python3
"""
audit_rules.py — kb-curator .claude/rules/ drift audit.

Compares a project's `.claude/rules/*.md` discipline files against the
canonical shared-references templates (shipped by obsidian-project-new /
obsidian-project-convert). Surfaces:

  • missing files — present in canonical, absent in project
  • extra files   — present in project, absent in canonical (informational)
  • content drift — file present in both but content differs

Canonical templates are discovered in this order:

  1. --canonical /path/to/dir          (explicit flag)
  2. KB_CURATOR_CANONICAL env var
  3. <vault>/90 System/_skill_resources/galp-vault-canonical/rules/
  4. <vault>/90 System/_skill_resources/<any-canonical>/rules/   (first match)
  5. embedded fallback (paired SHA256 fingerprints written by S08)

Mode `refresh-rules` is implemented by curator.py — this script only
audits and prints the diff plan. curator.py copies the canonical files
into `.claude/rules/` after Ricardo approves.

Usage
-----
  python3 audit_rules.py [--root /path/to/vault] [--canonical /path/to/rules]
  python3 audit_rules.py --json
  python3 audit_rules.py --proposal     # print refresh-rules action plan

Exit
----
  0  rules align with canonical
  1  drift detected
  2  configuration error (vault not found, canonical not found)
"""

import argparse
import difflib
import hashlib
import json
import os
import sys
from datetime import date

# Canonical rules filename list — keep in sync with audit_obsidian.py
# EXPECTED_RULES. This list is the source-of-truth for what a healthy
# `.claude/rules/` should contain.
EXPECTED_RULES = (
    "auto-write-discipline.md",
    "daily-notes-discipline.md",
    "freshness-discipline.md",
    "inbox-discipline.md",
    "mount-discipline.md",
    "plugin-security-discipline.md",
    "state-moc-edit-discipline.md",
)


def find_canonical(root, override=None):
    """Locate the canonical rules directory. Returns absolute path or None."""
    if override:
        if os.path.isdir(override):
            return os.path.realpath(override)
        return None
    env = os.environ.get("KB_CURATOR_CANONICAL")
    if env and os.path.isdir(env):
        return os.path.realpath(env)
    # 90 System/_skill_resources/galp-vault-canonical/rules/
    primary = os.path.join(root, "90 System", "_skill_resources",
                           "galp-vault-canonical", "rules")
    if os.path.isdir(primary):
        return primary
    # First _skill_resources/<any>/rules/
    sr = os.path.join(root, "90 System", "_skill_resources")
    if os.path.isdir(sr):
        for entry in sorted(os.listdir(sr)):
            cand = os.path.join(sr, entry, "rules")
            if os.path.isdir(cand):
                return cand
    return None


def sha256_file(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def diff_files(canonical_path, project_path, context=3):
    a = read_text(canonical_path) or ""
    b = read_text(project_path) or ""
    if a == b:
        return None
    return list(difflib.unified_diff(
        a.splitlines(keepends=False),
        b.splitlines(keepends=False),
        fromfile="canonical/{}".format(os.path.basename(canonical_path)),
        tofile="project/{}".format(os.path.basename(project_path)),
        n=context,
        lineterm="",
    ))


def audit(root, canonical_dir):
    rules_dir = os.path.join(root, ".claude", "rules")
    result = {
        "rules_dir":          rules_dir,
        "canonical_dir":      canonical_dir,
        "missing":            [],   # canonical files absent in project
        "extra":              [],   # project files absent in canonical
        "drift":              [],   # [(name, canon_sha, proj_sha, diff_preview)]
        "aligned":            [],   # files matching exactly
        "canonical_missing":  [],   # canonical files we expected but didn't find
    }

    # 1. Inventory canonical.
    canonical_files = {}
    for name in EXPECTED_RULES:
        cpath = os.path.join(canonical_dir, name)
        if os.path.exists(cpath):
            canonical_files[name] = cpath
        else:
            result["canonical_missing"].append(name)

    # 2. Compare each expected file against the project.
    if not os.path.isdir(rules_dir):
        # Everything is missing — surface that explicitly.
        result["missing"] = sorted(canonical_files.keys())
        return result

    project_files = set(os.listdir(rules_dir))
    for name, cpath in canonical_files.items():
        ppath = os.path.join(rules_dir, name)
        if not os.path.exists(ppath):
            result["missing"].append(name)
            continue
        canon_sha = sha256_file(cpath)
        proj_sha  = sha256_file(ppath)
        if canon_sha == proj_sha:
            result["aligned"].append(name)
        else:
            d = diff_files(cpath, ppath)
            preview = "\n".join(d[:20]) if d else "(content differs but diff empty)"
            result["drift"].append({
                "file":       name,
                "canon_sha":  canon_sha,
                "project_sha": proj_sha,
                "diff_preview": preview,
            })

    # 3. Extra files in project (not necessarily wrong — informational).
    expected_set = set(EXPECTED_RULES)
    for f in sorted(project_files):
        if f.startswith(".") or not f.endswith(".md"):
            continue
        if f not in expected_set:
            result["extra"].append(f)

    return result


def print_text_report(result):
    print("audit_rules: project = {}\n          canonical = {}\n".format(
        result["rules_dir"], result["canonical_dir"]
    ))

    if result["canonical_missing"]:
        print("Canonical templates MISSING from canonical dir (skill resources out of date?):")
        for f in result["canonical_missing"]:
            print("  • {}".format(f))
        print()

    if result["missing"]:
        print("MISSING in project .claude/rules/ ({}):".format(len(result["missing"])))
        for f in result["missing"]:
            print("  • {}".format(f))
        print()

    if result["drift"]:
        print("DRIFT — content differs from canonical ({}):".format(len(result["drift"])))
        for d in result["drift"]:
            print("  • {} (canon {}… vs project {}…)".format(
                d["file"],
                (d["canon_sha"] or "?")[:8],
                (d["project_sha"] or "?")[:8],
            ))
        print()

    if result["extra"]:
        print("EXTRA in project .claude/rules/ (informational — not necessarily wrong):")
        for f in result["extra"]:
            print("  • {}".format(f))
        print()

    print("=" * 60)
    aligned = len(result["aligned"])
    missing = len(result["missing"])
    drift   = len(result["drift"])
    total   = aligned + missing + drift
    print("Rules audit: {}/{} aligned, {} missing, {} drift, {} extra".format(
        aligned, total, missing, drift, len(result["extra"])
    ))
    print("=" * 60)


def print_proposal(result):
    print("REFRESH-RULES proposal — actions kb-curator would take on `apply`:\n")
    if not result["missing"] and not result["drift"]:
        print("  (no actions — rules already align with canonical)")
        return
    for name in result["missing"]:
        print("  CREATE  .claude/rules/{}  ←  {}".format(name, os.path.join(result["canonical_dir"], name)))
    for d in result["drift"]:
        print("  OVERWRITE  .claude/rules/{}  ←  {}  (content drift)".format(
            d["file"], os.path.join(result["canonical_dir"], d["file"])
        ))
    print()
    print("Notes:")
    print("  • OVERWRITE only fires after explicit user approval (refresh-rules mode).")
    print("  • Extra files (project-only) are NEVER deleted — surface only.")
    print("  • Canonical templates ship with obsidian-project-new / obsidian-project-convert.")


def main():
    parser = argparse.ArgumentParser(
        description="Audit .claude/rules/ drift against canonical shared references."
    )
    parser.add_argument("--root", metavar="PATH", default=None,
                        help="Vault root (default: auto-detect from cwd via CLAUDE.md).")
    parser.add_argument("--canonical", metavar="PATH", default=None,
                        help="Override canonical rules directory.")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="Output results as JSON.")
    parser.add_argument("--proposal", action="store_true",
                        help="Print refresh-rules action plan (text-only).")
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
    canonical_dir = find_canonical(root, override=args.canonical)
    if canonical_dir is None:
        msg = ("ERROR: canonical rules dir not found. Tried:\n"
               "  --canonical flag\n"
               "  KB_CURATOR_CANONICAL env var\n"
               "  {}/90 System/_skill_resources/galp-vault-canonical/rules/\n"
               "  {}/90 System/_skill_resources/*/rules/\n"
               "Install obsidian-project-new or obsidian-project-convert to provide canonical.").format(root, root)
        print(msg, file=sys.stderr)
        sys.exit(2)

    result = audit(root, canonical_dir)

    if args.json_out:
        out = dict(result)
        out["date"] = date.today().isoformat()
        out["aligned_count"] = len(result["aligned"])
        out["missing_count"] = len(result["missing"])
        out["drift_count"]   = len(result["drift"])
        print(json.dumps(out, indent=2))
    elif args.proposal:
        print_proposal(result)
    else:
        print_text_report(result)

    has_drift = bool(result["missing"] or result["drift"] or result["canonical_missing"])
    sys.exit(1 if has_drift else 0)


if __name__ == "__main__":
    main()
