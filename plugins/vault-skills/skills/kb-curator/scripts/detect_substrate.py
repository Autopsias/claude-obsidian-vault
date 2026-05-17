#!/usr/bin/env python3
"""
detect_substrate.py — kb-curator Phase 0

Determines whether a project root is a FLAT (cowork-preparation) or OBSIDIAN
(Johnny-Decimal Obsidian vault) substrate, or neither.

Exit codes:
  0  → prints "FLAT"
  1  → prints "OBSIDIAN"
  2  → prints "UNKNOWN" + error detail to stderr

Usage (called by curator.py at Phase 0 of every mode):
  python3 detect_substrate.py [--root /path/to/project]
  python3 detect_substrate.py --check-only   # exits 0 always, even on UNKNOWN
"""

import argparse
import os
import sys


# ---------------------------------------------------------------------------
# Substrate fingerprints
# ---------------------------------------------------------------------------

FLAT_MARKERS = [
    "CLAUDE.md",       # universal anchor (both substrates)
    "cowork_outputs",  # flat working zone — absent in Obsidian vaults
]

OBSIDIAN_MARKERS = [
    "CLAUDE.md",       # universal anchor (both substrates)
    "90 System",       # Johnny-Decimal system zone
    "99 Workspace",    # Johnny-Decimal workspace / auto-write zone
]

FLAT_CONFIRMATORY = [
    "cowork_outputs/_build_index.py",
    "cowork_outputs/_lint_frontmatter.py",
]
OBSIDIAN_CONFIRMATORY = [
    "90 System/_operating_guide.md",
    "90 System/Bases",
    "_plans_index.md",
    ".obsidian",       # Obsidian app directory — informational signal (kb-curator requires JD layout, not just an Obsidian vault)
    ".smart-env",      # Smart Connections substrate — informational signal
]


def _exists(root, rel):
    return os.path.exists(os.path.join(root, rel))


def _marker_role(m):
    roles = {
        "CLAUDE.md":                           "required by both substrates",
        "cowork_outputs":                      "FLAT fingerprint — working zone",
        "90 System":                           "OBSIDIAN fingerprint — system zone",
        "99 Workspace":                        "OBSIDIAN fingerprint — workspace zone",
        "cowork_outputs/_build_index.py":      "FLAT confirmatory",
        "cowork_outputs/_lint_frontmatter.py": "FLAT confirmatory",
        "90 System/_operating_guide.md":       "OBSIDIAN confirmatory",
        "90 System/Bases":                     "OBSIDIAN confirmatory",
        "_plans_index.md":                     "OBSIDIAN confirmatory",
        ".obsidian":                           "OBSIDIAN confirmatory — Obsidian app directory (informational)",
        ".smart-env":                          "OBSIDIAN confirmatory — Smart Connections substrate (informational)",
    }
    return roles.get(m, "marker")


def detect(root):
    """Returns (substrate, checked_lines).
    substrate is 'FLAT', 'OBSIDIAN', or 'UNKNOWN'.
    OBSIDIAN takes precedence when both fingerprints match (a vault may
    preserve a legacy cowork_outputs/ as _archive/legacy-cowork_outputs/).
    """
    all_markers = sorted(set(
        FLAT_MARKERS + OBSIDIAN_MARKERS + FLAT_CONFIRMATORY + OBSIDIAN_CONFIRMATORY
    ))
    checked = []
    for m in all_markers:
        found = _exists(root, m)
        checked.append(
            "  {}  {:<45}  ({})".format("OK" if found else "--", m, _marker_role(m))
        )

    obsidian_ok = all(_exists(root, m) for m in OBSIDIAN_MARKERS)
    flat_ok     = all(_exists(root, m) for m in FLAT_MARKERS)

    if obsidian_ok:
        return "OBSIDIAN", checked
    if flat_ok:
        return "FLAT", checked
    return "UNKNOWN", checked


def find_project_root(start=None):
    """Walk up from start (default cwd) until CLAUDE.md is found."""
    current = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.exists(os.path.join(current, "CLAUDE.md")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def main():
    parser = argparse.ArgumentParser(
        description="Detect kb-curator substrate: FLAT (cowork-preparation) or OBSIDIAN (Johnny-Decimal)."
    )
    parser.add_argument("--root", metavar="PATH", default=None,
                        help="Project root (default: auto-detect by walking up from cwd).")
    parser.add_argument("--check-only", action="store_true",
                        help="Print result and always exit 0 (useful for scripting).")
    args = parser.parse_args()

    # Resolve root: flag > env var > auto-detect
    root = args.root or os.environ.get("COWORK_ROOT") or find_project_root()
    if root is None:
        print(
            "ERROR: no project root found (no CLAUDE.md walking up from cwd).\n"
            "  Pass --root /path/to/project or set COWORK_ROOT.",
            file=sys.stderr,
        )
        sys.exit(2)

    root = os.path.realpath(root)
    substrate, checked = detect(root)

    if substrate == "UNKNOWN":
        if args.check_only:
            print("UNKNOWN")
            sys.exit(0)
        lines = [
            "ERROR: substrate unrecognised for project root:",
            "  {}".format(root),
            "",
            "Files / directories checked:",
        ] + checked + [
            "",
            "Criteria:",
            "  FLAT     requires: CLAUDE.md + cowork_outputs/",
            "  OBSIDIAN requires: CLAUDE.md + 90 System/ + 99 Workspace/",
            "",
            "If neither matches, run cowork-preparation or project-setup to scaffold the project first.",
        ]
        print("\n".join(lines), file=sys.stderr)
        print("UNKNOWN")
        sys.exit(2)

    print(substrate)
    sys.exit(0 if substrate == "FLAT" else 1)


if __name__ == "__main__":
    main()
