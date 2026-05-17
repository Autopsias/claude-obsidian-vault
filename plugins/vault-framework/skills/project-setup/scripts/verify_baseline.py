#!/usr/bin/env python3
"""
verify_baseline.py — Post-scaffold baseline verifier.

Asserts the five elements every scaffolded project must contain:

1. CLAUDE.md with five canonical-phrase markers (identity / cascade / M9
   caveat (if non-English) / session bootstrap / write rule)
2. Auto-write zone (99 Workspace/ or cowork_outputs/)
3. _auto_writes.md with frontmatter type: log
4. _session_handoff.md with last_updated frontmatter
5. Operating-guide pointer (_operating_guide.md or _guide_context_engineering.md)

Exit 0 on PASS, exit 1 on FAIL (with details printed to stderr).

Usage:
    python3 verify_baseline.py --root /path/to/scaffolded/project
    python3 verify_baseline.py --root . --language pt
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def has_marker(text: str, *markers: str) -> bool:
    """True if any of the markers (case-insensitive) appears in text."""
    return any(m.lower() in text.lower() for m in markers)


def check_claude_md(root: Path, language: str) -> list[str]:
    """Return list of failure messages; empty list = PASS."""
    fails: list[str] = []
    p = root / "CLAUDE.md"
    if not p.exists():
        return [f"CLAUDE.md not found at {p}"]
    text = p.read_text(encoding="utf-8")

    # 1. Identity block (project name, working folder, who)
    if not has_marker(text, "## Who", "## Identity", "**Project:**"):
        fails.append("CLAUDE.md missing identity block (## Who / ## Identity / **Project:**)")

    # 2. Cascade — must mention all 5 steps OR reference the cascade rule
    cascade_markers = ["Step 0", "Step 1", "Step 2", "Step 3", "Step 4"]
    cascade_hits = sum(1 for m in cascade_markers if m in text)
    if cascade_hits < 4:
        fails.append(
            f"CLAUDE.md cascade reference weak ({cascade_hits}/5 step markers); "
            "expect Step 0/1/2/3/4 or a cascade pointer"
        )

    # 3. M9 caveat (if non-English declared)
    if language and language.lower() not in ("en", "english"):
        if not has_marker(text, "M9", "multilingual", "PT/ES", "non-English"):
            fails.append(
                f"CLAUDE.md missing M9 caveat for non-English language '{language}'"
            )

    # 4. Session bootstrap
    if not has_marker(text, "Session Bootstrap", "session-bootstrap", "session start"):
        fails.append("CLAUDE.md missing Session Bootstrap pointer")

    # 5. Write rule
    if not has_marker(text, "Write Rule", "99 Workspace/", "cowork_outputs/", "auto-write"):
        fails.append("CLAUDE.md missing Write Rule (zone pointer)")

    return fails


def check_auto_write_zone(root: Path) -> list[str]:
    """Either 99 Workspace/ or cowork_outputs/ must exist."""
    obs = root / "99 Workspace"
    flat = root / "cowork_outputs"
    if not (obs.is_dir() or flat.is_dir()):
        return [
            "auto-write zone missing — expected '99 Workspace/' (Obsidian) or "
            "'cowork_outputs/' (flat) at project root"
        ]
    return []


def check_auto_writes_log(root: Path) -> list[str]:
    """Find _auto_writes.md in auto-write zone with type: log frontmatter."""
    for candidate in (root / "99 Workspace" / "_auto_writes.md",
                      root / "cowork_outputs" / "_auto_writes.md"):
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8")
            if re.search(r"type:\s*(log|audit)", text):
                return []
            return [
                f"{candidate} exists but missing 'type: log' frontmatter"
            ]
    return ["_auto_writes.md not found in 99 Workspace/ or cowork_outputs/"]


def check_session_handoff(root: Path) -> list[str]:
    """Find _session_handoff.md with last_updated frontmatter."""
    for candidate in (root / "99 Workspace" / "_session_handoff.md",
                      root / "cowork_outputs" / "_session_handoff.md"):
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8")
            if re.search(r"last_updated:\s*\S", text):
                return []
            return [
                f"{candidate} exists but missing 'last_updated:' frontmatter"
            ]
    return [
        "_session_handoff.md not found in 99 Workspace/ or cowork_outputs/"
    ]


def check_operating_guide_pointer(root: Path) -> list[str]:
    """Operating-guide file must exist."""
    obs = root / "90 System" / "_operating_guide.md"
    flat = root / "cowork_outputs" / "_guide_context_engineering.md"
    if obs.exists() or flat.exists():
        return []
    return [
        "operating-guide file missing — expected '90 System/_operating_guide.md' "
        "(Obsidian) or 'cowork_outputs/_guide_context_engineering.md' (flat)"
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, help="path to project root")
    ap.add_argument(
        "--language",
        default="en",
        help="primary working language (en/pt/es/mixed); enables M9 caveat check if non-English",
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"[FAIL] {root} is not a directory", file=sys.stderr)
        return 1

    all_fails: list[str] = []
    all_fails += check_claude_md(root, args.language)
    all_fails += check_auto_write_zone(root)
    all_fails += check_auto_writes_log(root)
    all_fails += check_session_handoff(root)
    all_fails += check_operating_guide_pointer(root)

    if all_fails:
        print(f"[FAIL] baseline verifier — {len(all_fails)} issue(s):", file=sys.stderr)
        for f in all_fails:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("[PASS] baseline verifier — all 5 elements present at " + str(root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
