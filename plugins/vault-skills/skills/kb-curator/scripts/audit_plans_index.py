#!/usr/bin/env python3
"""
audit_plans_index.py — kb-curator _plans_index.md conformance audit.

Validates that the vault-root `_plans_index.md` (canonical list of active
plan dashboards) is internally consistent and matches reality on disk.

Checks
------
  P1. Every referenced `_plan_*.html` file exists at the path listed.
  P2. Each line's session-count claim ("· N sessions ·") matches the actual
      number of session articles inside the plan HTML.
  P3. Each line's item-count claim ("· N items ·") matches the actual number
      of item articles inside the plan HTML.
  P4. Each line's "created YYYY-MM-DD" date is parseable.
  P5. At most ONE plan in the index is marked "CANONICAL".

  P-MOD: each plan referenced is listed exactly once (no duplicate rows).

Refresh
-------
Mode `refresh-plans-index` is wired into curator.py — this script computes
the recomputed line for every plan and prints it under `--proposal`. The
operator approves before curator.py writes the new index.

Usage
-----
  python3 audit_plans_index.py [--root /path/to/vault]
  python3 audit_plans_index.py --proposal     # print recomputed lines
  python3 audit_plans_index.py --json

Exit
----
  0  index is internally consistent and matches disk
  1  at least one violation
  2  configuration error (vault not found, _plans_index.md missing)
"""

import argparse
import json
import os
import re
import sys
from datetime import date

INDEX_FILENAME = "_plans_index.md"

# Markdown link to a plan HTML: [Title](path/to/_plan_*.html)
PLAN_LINK_RE = re.compile(
    r"\[(?P<title>[^\]]+)\]\((?P<path>[^)]*_plan_[^)]*\.html)\)"
)

# Optional session-count fragment after the link: · N sessions ·
SESSION_COUNT_RE = re.compile(r"·\s*(\d+)\s*sessions?\b")

# Optional item-count fragment: · N items ·
ITEM_COUNT_RE = re.compile(r"·\s*(\d+)\s*items?\b")

# created YYYY-MM-DD anywhere on the line.
CREATED_DATE_RE = re.compile(r"created\s+(\d{4}-\d{2}-\d{2})")

# CANONICAL marker (case-insensitive).
CANONICAL_RE = re.compile(r"\bCANONICAL\b", re.IGNORECASE)

# Inside the plan HTML, session articles look like:
#   <article class="session" id="s07" data-status="...">
SESSION_ARTICLE_RE = re.compile(
    r'<article[^>]*\bclass\s*=\s*"[^"]*\bsession\b[^"]*"', re.IGNORECASE
)

# Inside the plan HTML, item articles look like:
#   <article class="item" id="kc-04" ...>
ITEM_ARTICLE_RE = re.compile(
    r'<article[^>]*\bclass\s*=\s*"[^"]*\bitem\b[^"]*"', re.IGNORECASE
)


def parse_index(text):
    """Return a list of parsed-plan-line dicts in source order."""
    parsed = []
    for raw_line in text.splitlines():
        m = PLAN_LINK_RE.search(raw_line)
        if not m:
            continue
        entry = {
            "raw":            raw_line,
            "title":          m.group("title").strip(),
            "path":           m.group("path").strip(),
            "claimed_sessions": None,
            "claimed_items":    None,
            "claimed_created":  None,
            "is_canonical":     bool(CANONICAL_RE.search(raw_line)),
        }
        sm = SESSION_COUNT_RE.search(raw_line)
        if sm:
            entry["claimed_sessions"] = int(sm.group(1))
        im = ITEM_COUNT_RE.search(raw_line)
        if im:
            entry["claimed_items"] = int(im.group(1))
        dm = CREATED_DATE_RE.search(raw_line)
        if dm:
            entry["claimed_created"] = dm.group(1)
        parsed.append(entry)
    return parsed


def count_in_html(path):
    """Return (session_count, item_count) by counting <article> tags."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
    except OSError as e:
        return None, None, "cannot read ({})".format(e)
    sessions = len(SESSION_ARTICLE_RE.findall(html))
    items    = len(ITEM_ARTICLE_RE.findall(html))
    return sessions, items, None


def audit(root):
    index_path = os.path.join(root, INDEX_FILENAME)
    if not os.path.exists(index_path):
        return None, "{} not found at vault root".format(INDEX_FILENAME)

    with open(index_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    plans = parse_index(text)

    results = {
        "index_path":  index_path,
        "plan_count":  len(plans),
        "plans":       [],
        "violations":  [],
    }

    canonical_count = 0
    path_seen = {}

    for p in plans:
        path = p["path"]

        # Duplicate row?
        if path in path_seen:
            results["violations"].append(
                "duplicate row for plan `{}` (also seen above)".format(path)
            )
        path_seen[path] = True

        if p["is_canonical"]:
            canonical_count += 1

        full = os.path.join(root, path) if not os.path.isabs(path) else path
        rec = {
            "title":           p["title"],
            "path":            path,
            "is_canonical":    p["is_canonical"],
            "exists":          os.path.exists(full),
            "claimed_sessions": p["claimed_sessions"],
            "claimed_items":    p["claimed_items"],
            "claimed_created":  p["claimed_created"],
            "actual_sessions":  None,
            "actual_items":     None,
            "computed_created": None,
        }

        # P1 — existence.
        if not rec["exists"]:
            results["violations"].append(
                "plan file missing on disk: {}".format(path)
            )
            results["plans"].append(rec)
            continue

        # P2/P3 — session/item counts.
        s_count, i_count, err = count_in_html(full)
        if err:
            results["violations"].append("{}: {}".format(path, err))
            results["plans"].append(rec)
            continue
        rec["actual_sessions"] = s_count
        rec["actual_items"]    = i_count

        if rec["claimed_sessions"] is not None and rec["claimed_sessions"] != s_count:
            results["violations"].append(
                "{}: claims {} sessions but contains {}".format(
                    path, rec["claimed_sessions"], s_count
                )
            )
        if rec["claimed_items"] is not None and rec["claimed_items"] != i_count:
            results["violations"].append(
                "{}: claims {} items but contains {}".format(
                    path, rec["claimed_items"], i_count
                )
            )

        # P4 — created date is parseable.
        if rec["claimed_created"]:
            try:
                date.fromisoformat(rec["claimed_created"])
            except ValueError:
                results["violations"].append(
                    "{}: created `{}` is not a valid YYYY-MM-DD date".format(
                        path, rec["claimed_created"]
                    )
                )

        # Derive a recommended `created` from the plan filename if it has
        # a date suffix (e.g. _plan_<slug>_YYYY-MM-DD.html). Used by
        # --proposal output.
        filename = os.path.basename(path)
        d_m = re.search(r"(\d{4}-\d{2}-\d{2})\.html$", filename)
        if d_m:
            rec["computed_created"] = d_m.group(1)

        results["plans"].append(rec)

    # P5 — ≤1 CANONICAL.
    if canonical_count > 1:
        results["violations"].append(
            "more than one plan marked CANONICAL ({} found; max 1)".format(canonical_count)
        )

    return results, None


def print_text_report(result):
    print("audit_plans_index: {}".format(result["index_path"]))
    print("Plans referenced: {}\n".format(result["plan_count"]))

    for rec in result["plans"]:
        marker = " [CANONICAL]" if rec["is_canonical"] else ""
        exists = "✓" if rec["exists"] else "✗"
        print("  {} {}{}".format(exists, rec["title"], marker))
        print("       {}".format(rec["path"]))
        if rec["exists"]:
            ses = "?" if rec["actual_sessions"] is None else rec["actual_sessions"]
            it  = "?" if rec["actual_items"] is None else rec["actual_items"]
            c_ses = rec["claimed_sessions"]
            c_it  = rec["claimed_items"]
            s_flag = " (CLAIMED: {})".format(c_ses) if c_ses is not None and c_ses != ses else ""
            i_flag = " (CLAIMED: {})".format(c_it)  if c_it  is not None and c_it  != it  else ""
            print("       sessions: {}{}, items: {}{}".format(ses, s_flag, it, i_flag))
        print()

    print("=" * 60)
    if result["violations"]:
        print("VIOLATIONS ({}):".format(len(result["violations"])))
        for v in result["violations"]:
            print("  • {}".format(v))
    else:
        print("Plans index is consistent: all paths resolve, counts match, ≤1 CANONICAL.")
    print("=" * 60)


def print_proposal(result):
    print("REFRESH-PLANS-INDEX proposal — recomputed lines:\n")
    print("# Active Plans\n")
    print("This file lists all plan dashboards in this project. Each plan is a self-contained")
    print("HTML file built by the `plan-builder` skill. To execute a session: open the plan,")
    print("find the session card, copy its prompt, paste into a fresh Cowork session. To")
    print("update progress: read the plan's Operating Manual at the top of the file.\n")
    print("## Plans")
    for rec in result["plans"]:
        if not rec["exists"]:
            print("# MISSING — kept from index but file not on disk: {}".format(rec["path"]))
            continue
        sessions = rec["actual_sessions"] if rec["actual_sessions"] is not None else "?"
        items    = rec["actual_items"]    if rec["actual_items"]    is not None else "?"
        created  = rec["claimed_created"] or rec["computed_created"] or "????-??-??"
        canon = " · **CANONICAL — update this file**" if rec["is_canonical"] else ""
        print("- **[{}]({})** · {} sessions · {} items · created {}{}".format(
            rec["title"], rec["path"], sessions, items, created, canon,
        ))


def main():
    parser = argparse.ArgumentParser(
        description="Audit _plans_index.md for consistency with plan HTML files."
    )
    parser.add_argument("--root", metavar="PATH", default=None,
                        help="Vault root (default: auto-detect from cwd via CLAUDE.md).")
    parser.add_argument("--proposal", action="store_true",
                        help="Print refresh-plans-index recomputed body.")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="Output results as JSON.")
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
    result, err = audit(root)
    if err:
        print("ERROR: {}".format(err), file=sys.stderr)
        sys.exit(2)

    if args.json_out:
        out = dict(result)
        out["date"] = date.today().isoformat()
        out["violation_count"] = len(result["violations"])
        print(json.dumps(out, indent=2))
    elif args.proposal:
        print_proposal(result)
    else:
        print_text_report(result)

    sys.exit(0 if not result["violations"] else 1)


if __name__ == "__main__":
    main()
