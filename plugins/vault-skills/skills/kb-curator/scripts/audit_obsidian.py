#!/usr/bin/env python3
"""
audit_obsidian.py — kb-curator OBSIDIAN substrate audit checks

Runs six structural integrity checks against a Johnny-Decimal Obsidian vault:

  1. 11 canonical Bases exist in 90 System/Bases/
  2. _bases_verifier.py runs clean (exit 0, no errors on stdout)
  3. _operating_guide.md contains anchors P-1 through P-13
  4. .claude/rules/ has all 7 canonical rules files
  5. _plans_index.md exists + all referenced plan HTML files are present
  6. _retrieval_contract.md exists and is dated within the last 30 days

Usage:
  python3 audit_obsidian.py [--root /path/to/vault]
  python3 audit_obsidian.py --json    # machine-readable output

Exit:
  0  all checks passed
  1  one or more checks failed (details on stdout/stderr)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Canonical expected files
# ---------------------------------------------------------------------------

EXPECTED_BASES = [
    "People.base",
    "Companies.base",
    "Projects.base",
    "Meetings.base",
    "Sources.base",
    "Decisions.base",
    "Open Items.base",
    "Tier-2 Sources.base",
    "Latest Only.base",
    "As Of.base",
    "Version Chain.base",
]

EXPECTED_RULES = [
    "auto-write-discipline.md",
    "daily-notes-discipline.md",
    "freshness-discipline.md",
    "inbox-discipline.md",
    "mount-discipline.md",
    "plugin-security-discipline.md",
    "state-moc-edit-discipline.md",
]

RETRIEVAL_CONTRACT_MAX_AGE_DAYS = 30


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------

def check_bases(root):
    """Check 1: 11 canonical Bases exist in 90 System/Bases/."""
    bases_dir = os.path.join(root, "90 System", "Bases")
    missing = []
    for b in EXPECTED_BASES:
        if not os.path.exists(os.path.join(bases_dir, b)):
            missing.append(b)
    if missing:
        return False, "Missing {} of {} Bases in 90 System/Bases/: {}".format(
            len(missing), len(EXPECTED_BASES), ", ".join(missing)
        )
    return True, "All {} Bases present in 90 System/Bases/".format(len(EXPECTED_BASES))


def check_bases_verifier(root):
    """Check 2: _bases_verifier.py runs clean (exit 0) AND has no schema violations.

    Wired per KC-08: parses the verifier's stdout for BC-XX schema checks and
    surfaces individual violations as audit signal. Any FAIL line in the
    structural output blocks 'all green' regardless of the exit code (defensive —
    in case the verifier loosens its strict mode in the future).
    """
    verifier = os.path.join(root, "90 System", "_bases_verifier.py")
    if not os.path.exists(verifier):
        return False, "_bases_verifier.py not found at 90 System/_bases_verifier.py"
    try:
        result = subprocess.run(
            [sys.executable, verifier, "--vault", root, "--bases", "--strict"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, "_bases_verifier.py timed out after 30s"
    except Exception as e:
        return False, "_bases_verifier.py failed to run: {}".format(e)

    stdout = result.stdout or ""
    stderr = result.stderr or ""

    # Parse BC-XX structural-check lines. Each line is shaped:
    #   "    BC-NN  <BaseName>   ✓ <detail>"     (pass)
    #   "    BC-NN  <BaseName>   ✗ <detail>"     (fail)
    bc_pass = []
    bc_fail = []
    for line in stdout.splitlines():
        # Tolerate any whitespace, alphanumerics in the check id
        m = re.search(r"\b(BC-\S+)\s+(\S(?:.*?\S)?)\s+([✓✗])\s+(.+)$", line)
        if not m:
            continue
        check_id, base_name, mark, detail = m.groups()
        entry = (check_id.strip(), base_name.strip(), detail.strip())
        if mark == "✓":
            bc_pass.append(entry)
        else:
            bc_fail.append(entry)

    # Any FAIL → block all-green, even if return-code happens to be 0.
    if bc_fail:
        violations = "; ".join("{}/{}: {}".format(c, b, d) for c, b, d in bc_fail)
        return False, ("_bases_verifier.py surfaced {} schema violation(s) "
                       "across {} BC-check(s): {}".format(
                           len(bc_fail), len(bc_pass) + len(bc_fail), violations
                       ))

    if result.returncode != 0:
        detail = (stdout + "\n" + stderr).strip()
        return False, "_bases_verifier.py exited {} (no BC-FAIL lines parsed; check stderr) — {}".format(
            result.returncode, detail[:300] if detail else "(no output)"
        )

    # All BC-XX checks passed; return code clean.
    bases_count = None
    bcount_m = re.search(r"Bases found:\s*(\d+)", stdout)
    if bcount_m:
        bases_count = int(bcount_m.group(1))
    summary = "_bases_verifier.py clean — {}/{} BC-checks passed".format(
        len(bc_pass), len(bc_pass)
    )
    if bases_count is not None:
        summary += "; {} Bases parsed".format(bases_count)
    return True, summary


def check_operating_guide(root):
    """Check 3: _operating_guide.md contains P-1 through P-13."""
    guide_path = os.path.join(root, "90 System", "_operating_guide.md")
    if not os.path.exists(guide_path):
        return False, "_operating_guide.md not found at 90 System/_operating_guide.md"

    with open(guide_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    missing = []
    for i in range(1, 14):
        # Match P-N as a heading anchor or standalone label (P-1 through P-13)
        pattern = r"\bP-{}\b".format(i)
        if not re.search(pattern, content):
            missing.append("P-{}".format(i))

    if missing:
        return False, "_operating_guide.md missing rules: {}".format(", ".join(missing))
    return True, "_operating_guide.md contains all P-1 through P-13 anchors"


def check_rules_files(root):
    """Check 4: .claude/rules/ has all 7 canonical rules files."""
    rules_dir = os.path.join(root, ".claude", "rules")
    if not os.path.isdir(rules_dir):
        return False, ".claude/rules/ directory not found"

    missing = []
    for f in EXPECTED_RULES:
        if not os.path.exists(os.path.join(rules_dir, f)):
            missing.append(f)

    if missing:
        return False, "Missing {} of {} rules files in .claude/rules/: {}".format(
            len(missing), len(EXPECTED_RULES), ", ".join(missing)
        )
    return True, "All {} canonical rules files present in .claude/rules/".format(len(EXPECTED_RULES))


def check_plans_index(root):
    """Check 5: _plans_index.md exists + all referenced plan HTMLs are present."""
    index_path = os.path.join(root, "_plans_index.md")
    if not os.path.exists(index_path):
        return False, "_plans_index.md not found at vault root"

    with open(index_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Find relative paths to plan HTML files — pattern: ](path/to/_plan_*.html)
    html_refs = re.findall(r'\]\(([^)]+\.html)\)', content)
    if not html_refs:
        # Also try bare filenames without markdown link syntax
        html_refs = re.findall(r'`?(_plan_[^`\s]+\.html)`?', content)

    missing = []
    for ref in html_refs:
        # Paths in _plans_index.md are relative to vault root
        # Strip leading spaces or quotes
        ref = ref.strip().strip('"').strip("'")
        full_path = os.path.join(root, ref)
        if not os.path.exists(full_path):
            missing.append(ref)

    if missing:
        return False, "_plans_index.md references {} plan(s) that don't exist: {}".format(
            len(missing), "; ".join(missing)
        )

    plan_count = len(html_refs)
    return True, "_plans_index.md present; all {} referenced plan HTML(s) exist".format(plan_count)


def check_retrieval_contract(root):
    """Check 6: _retrieval_contract.md present and dated within the last 30 days."""
    contract_path = os.path.join(root, "90 System", "_retrieval_contract.md")
    if not os.path.exists(contract_path):
        return False, "_retrieval_contract.md not found at 90 System/_retrieval_contract.md"

    with open(contract_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Look for last_updated in YAML frontmatter
    date_str = None
    fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        lu_match = re.search(r'^last_updated\s*:\s*(\S+)', fm, re.MULTILINE)
        if lu_match:
            date_str = lu_match.group(1).strip('"').strip("'")

    # Fallback: look for a bare date in the first 500 chars of the file
    if not date_str:
        date_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', content[:500])
        if date_match:
            date_str = date_match.group(1)

    if not date_str:
        return False, "_retrieval_contract.md found but no date detected (checked frontmatter last_updated + first 500 chars)"

    try:
        contract_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False, "_retrieval_contract.md: unparseable date '{}'".format(date_str)

    today = date.today()
    age_days = (today - contract_date).days

    if age_days > RETRIEVAL_CONTRACT_MAX_AGE_DAYS:
        return False, "_retrieval_contract.md is {} days old (last_updated: {}; limit: {} days) — re-run retrieval eval to refresh".format(
            age_days, date_str, RETRIEVAL_CONTRACT_MAX_AGE_DAYS
        )

    return True, "_retrieval_contract.md dated {} ({} days ago — within {} day limit)".format(
        date_str, age_days, RETRIEVAL_CONTRACT_MAX_AGE_DAYS
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CHECKS = [
    ("bases",             "11 canonical Bases in 90 System/Bases/",     check_bases),
    ("bases_verifier",    "_bases_verifier.py runs clean",              check_bases_verifier),
    ("operating_guide",   "_operating_guide.md has P-1 to P-13",        check_operating_guide),
    ("rules_files",       ".claude/rules/ has all 7 canonical files",   check_rules_files),
    ("plans_index",       "_plans_index.md + all plan HTMLs present",   check_plans_index),
    ("retrieval_contract","_retrieval_contract.md dated ≤30 days ago",  check_retrieval_contract),
]


def run_checks(root, verbose=True):
    results = []
    for check_id, label, fn in CHECKS:
        passed, detail = fn(root)
        results.append({
            "id":     check_id,
            "label":  label,
            "passed": passed,
            "detail": detail,
        })
        if verbose:
            icon = "PASS" if passed else "FAIL"
            print("[{}]  {}".format(icon, label))
            if not passed or verbose:
                print("       {}".format(detail))
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run OBSIDIAN structural integrity checks for kb-curator."
    )
    parser.add_argument("--root", metavar="PATH", default=None,
                        help="Vault root (default: auto-detect from cwd via CLAUDE.md).")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="Output results as JSON.")
    parser.add_argument("--quiet", action="store_true",
                        help="Only print failures (no PASS lines).")
    args = parser.parse_args()

    # Resolve root
    root = args.root or os.environ.get("COWORK_ROOT")
    if root is None:
        # Walk up from cwd
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
    print("audit_obsidian: checking root = {}\n".format(root))

    verbose = not args.quiet
    results = run_checks(root, verbose=verbose)

    failures = [r for r in results if not r["passed"]]
    passed   = [r for r in results if r["passed"]]

    if args.json_out:
        print(json.dumps({
            "root":     root,
            "date":     date.today().isoformat(),
            "passed":   len(passed),
            "failed":   len(failures),
            "results":  results,
        }, indent=2))
    else:
        print()
        print("=" * 60)
        print("OBSIDIAN audit: {}/{} checks passed".format(len(passed), len(CHECKS)))
        if failures:
            print("\nFailed checks:")
            for r in failures:
                print("  • {} — {}".format(r["label"], r["detail"]))
        else:
            print("All checks passed.")
        print("=" * 60)

    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
