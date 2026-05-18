---
paths:
  - "**/*.md"
  - "**/*.py"
  - "**/*.sh"
  - "**/*.json"
  - "**/*.html"
---

# Git commit discipline

Every file write by Claude that is tracked in the vault git repo MUST result in
a git commit with a structured message. This rule documents the convention so
the format is consistent and greppable across `git log`.

## Commit message format

```
[<zone>] <verb> <path> — <reason>
```

**Examples:**
```
[99 Workspace] write _audit_2026-05-17_session_review.md — S02 auto-commit acceptance test
[.claude/rules] write git-commit-discipline.md — convention enforcement
[90 System] edit audit_chain.py — fix chain verify edge case
[00 Inbox] write 2026-05-17-meeting-notes.md — meeting-notes
[70 Decisions] write 2026-05-17_decision.md — record architecture decision
```

## Zone — first path component

Derived from the path relative to the vault root. Always the first directory segment:

| Path prefix           | Zone                  |
|-----------------------|-----------------------|
| `00 Inbox/`           | `00 Inbox`            |
| `80 Daily/`           | `80 Daily`            |
| `99 Workspace/`       | `99 Workspace`        |
| `.claude/rules/`      | `.claude/rules`       |
| `.claude/hooks/`      | `.claude/hooks`       |
| `90 System/`          | `90 System`           |
| `10 People/`          | `10 People`           |
| `20 Companies/`       | `20 Companies`        |
| `30 Projects/`        | `30 Projects`         |
| `40 Meetings/`        | `40 Meetings`         |
| `50 Sources/`         | `50 Sources`          |
| `60 Concepts/`        | `60 Concepts`         |
| `70 Decisions/`       | `70 Decisions`        |

If the file is at vault root, zone = `[vault]`.

## Verbs

Match the auto-write log verbs exactly:

| Verb     | When to use                                      |
|----------|--------------------------------------------------|
| `write`  | New file created, or file fully replaced         |
| `edit`   | Existing file modified (partial change)          |
| `rename` | File moved or renamed (old path → new path)      |
| `note`   | Annotation added (no structural change)          |
| `delete` | File removed (log only; physical delete uses OS) |

For Bash tool calls that touch multiple files: use `write (bash)` and commit
all staged changes in one commit.

## Reason

- **≤80 characters** (enforced by the hook's `cut -c1-80`)
- Sourced from the last hash-chain entry in `_auto_writes.md` when the chain
  log is the file being committed — this gives the reason Claude logged for the
  preceding file write
- For all other file writes: defaults to `$(basename <path>)` at commit time;
  the hash-chain entry (written shortly after) carries the full reason

## What the hook does

`hooks/post-write.sh` fires on every `Write|Edit|MultiEdit|Bash` tool call
in Claude Code CLI (⚠ NOT in Cowork — see hooks/README.md):

1. Extracts `file_path` from the tool-input JSON (via stdin).
2. Skips `.smart-env/` (gitignored).
3. Runs `git add -- <REL>`.
4. If the file written is `_auto_writes.md` (the chain log): parses the last
   chain entry → uses its `verb | path | reason` for the commit message, then
   stages the referenced file and commits everything together.
5. Otherwise: commits immediately with `[zone] verb path — basename`.

This means each file + its chain entry are typically committed in the same
git commit, with the full reason the chain captured.

## Two parallel records — hash chain vs git

These two surfaces protect different things and neither replaces the other:

| Surface        | Proves          | Enables              | Threat addressed            |
|----------------|-----------------|----------------------|-----------------------------|
| Hash chain     | Authorship, why | Integrity audit      | Fabrication, back-dating     |
| Git commit     | Content, what   | Surgical revert      | Corruption, bad write        |

Cross-verify snippet (run during weekly health checks):

```bash
# Count hash-chain entries for writes in 99 Workspace/
CHAIN=$(grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}' \
  "99 Workspace/_auto_writes.md" | wc -l)

# Count git commits touching 99 Workspace/
GIT=$(git log --oneline -- "99 Workspace/" | wc -l)

echo "Chain entries: $CHAIN | Git commits (99 Workspace): $GIT"
# Expect: CHAIN ≈ GIT (±5 to allow for bulk reconciliation commits)
```

## Greppable patterns

```bash
# All 99 Workspace commits this week
git log --oneline --since=7.days.ago | grep '\[99 Workspace\]'

# All write commits (not edits)
git log --oneline | grep '] write '

# Commits touching .claude/rules
git log --oneline | grep '\[\.claude/rules\]'

# Full audit trail for a specific file
git log --follow --oneline -- "99 Workspace/_session_handoff.md"
```

## Cross-references

- `hooks/post-write.sh` — the hook implementation
- `hooks/README.md` — install instructions + Cowork caveat
- `.claude/settings.json` — hook registration (PostToolUse matcher)
- `rules/auto-write-discipline.md` — hash-chain discipline (parallel surface)
- `scripts/audit_chain.py` — chain append/verify CLI
