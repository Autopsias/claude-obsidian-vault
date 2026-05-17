---
description: Path-detecting Obsidian-vault scaffolder. Inspects current folder + Obsidian install state, then routes to scaffold-on-existing, bootstrap-then-new, or scaffold-new.
argument-hint: "[--path=/abs/path] [--language=en|pt|es|mixed]"
---

# /vault-setup

You are running the `vault-setup` slash command from the `vault-framework`
plugin. The goal is to scaffold a disciplined Obsidian vault on the user's
current working folder — or, if Obsidian isn't installed, to set them up to
do so cleanly, then scaffold.

## Phase 0 — Detect the path

Before anything else, run **path detection** to decide which of the three
paths applies. The user does NOT type which path; you infer it.

Run these probes in order and stop at the first match:

```bash
# Probe 1 — is the current folder an Obsidian vault?
if [ -d ".obsidian" ]; then
  OBSIDIAN_PRESENT=true
fi

# Probe 2 — does the folder have content?
# Count non-hidden markdown files (excluding the standard scaffolded ones)
CONTENT_FILES=$(find . -name '*.md' -not -path './.obsidian/*' \
                     -not -path './.smart-env/*' \
                     -not -path './CLAUDE.md' \
                     | head -5 | wc -l)
if [ "$CONTENT_FILES" -gt 0 ]; then
  HAS_CONTENT=true
fi

# Probe 3 — is the framework installed at user scope?
# (Look for vault-framework plugin presence in ~/.claude/plugins/ or similar)
if [ -d "$HOME/.claude/plugins/vault-framework" ] || \
   [ -d "$HOME/.local/share/claude/plugins/vault-framework" ]; then
  FRAMEWORK_AT_USER_SCOPE=true
fi
```

Then apply the routing table:

| OBSIDIAN_PRESENT | HAS_CONTENT | FRAMEWORK_AT_USER_SCOPE | → Path |
|---|---|---|---|
| true  | true  | * | **Path A** — scaffold-on-existing |
| false | *     | * | **Path B** — bootstrap.sh then scaffold-new |
| true  | false | true  | **Path C** — scaffold-new (substrate-aware) |
| true  | false | false | Path C, but warn the user the framework isn't user-scope-installed |

Tell the user clearly which path you detected and why, before proceeding.

## Path A — Scaffold-on-existing (Obsidian present + content)

The vault already exists with content. Do NOT over-write existing files;
retrofit instead.

1. **Snapshot.** Use `git status` or a checksum of the top-level files so the
   user can revert. If the folder is not a git repo, propose initialising
   one before scaffolding.
2. **Interview** — three questions:
   - What name should this vault carry (becomes `{{PROJECT_NAME}}`)?
   - What is the primary working language (en / pt / es / mixed)?
   - What is the canonical state-MOC file (the live-state Markdown — e.g.
     `30 Projects/MyProject.md`)? If unsure, name a candidate.
3. **Run the `project-setup` skill** with `--mode=existing-obsidian` — it
   will invoke `obsidian-project-convert`. That sub-skill handles
   frontmatter retrofit, Bases install (without over-writing existing
   queries), rule install (.claude/rules/), CLAUDE.md generation (with
   stable-prefix discipline applied; reference existing zones not blank
   ones).
4. **Verify** the baseline via `scripts/verify_baseline.py` from the
   `project-setup` skill (5-element check: cascade / M9 caveat / bootstrap /
   write zone / operating-guide pointer).
5. **Report.** Echo what was written, what was preserved, and the diff
   summary against the snapshot.

## Path B — Bootstrap.sh then scaffold-new (Obsidian absent)

Obsidian isn't installed. Don't try to scaffold a vault into a
non-Obsidian folder — that produces a half-formed mess.

1. **Emit the bootstrap prompt.** Surface this exact set of steps to the
   user (do NOT execute the install — bootstrap is the user's call):

   ```
   To proceed you need Obsidian + the Smart Connections plugin + a configured
   .obsidian directory. Run this once on your machine:

     # macOS (Homebrew Cask):
     brew install --cask obsidian

     # Then open Obsidian once, point it at this folder, and accept the
     # vault-creation prompt. Quit Obsidian.

     # Install Smart Connections (within Obsidian):
     # Settings → Community plugins → Browse → "Smart Connections" → Install → Enable

   When that's done, re-run /vault-setup. I'll detect the .obsidian/
   directory and proceed with scaffold-new.
   ```

2. **Wait for the user** to confirm install completion. Re-run path
   detection. If `.obsidian/` is now present, route to **Path C**.

## Path C — Scaffold-new (Obsidian present + no content)

A clean slate. Run the full new-vault scaffold.

1. **Run the consolidated `project-setup` skill** — it owns the three-
   question interview (starting point / target substrate / working
   language) and routes to `obsidian-project-new`. For Path C, pre-answer
   "starting point = new" + "target substrate = Obsidian"; only ask the
   working-language question.
2. **`obsidian-project-new`** then runs its own clarification interview
   (project name, vault path, key entities, M9 caveat decision) and
   scaffolds:
   - `CLAUDE.md` from `templates/CLAUDE-template.md` via `scripts/populate-claude-md.py`
   - `90 System/_operating_guide.md` from `templates/operating-guide-template.md`
   - `90 System/Bases/` — 11 .base files
   - `.claude/rules/` — 11 path-gated discipline rules
   - 11 zone folders (00 Inbox … 99 Workspace)
   - `99 Workspace/_session_handoff.md` + `_hot.md` + `_auto_writes.md`
3. **Verify** via `scripts/verify_baseline.py`.
4. **Companion offer.** "I recommend also installing `vault-skills`,
   `vault-eval`, `vault-ingestion`, and `vault-voice` — they share the
   marketplace and assume this framework is the base."

## After-action

Whatever path ran, finish with a single short message:

> "Vault scaffolded as **[Project Name]** at `<path>`. Path **[A | B → C |
> C]** applied. M9 caveat: **[applied | not applied]**. Baseline verifier:
> **PASSED**. First-session steps are in CLAUDE.md's Session Bootstrap
> section."

## Guardrails

- Path detection is the contract. Don't ask the user "which path is this?" —
  they don't know. You inspect and tell them.
- Never overwrite existing files on Path A. Retrofit only.
- Never proceed on Path B if Obsidian isn't installed; emit the prompt and
  stop.
- Never skip the verifier. A scaffolder that says "done" without a passing
  baseline check is broken.
