---
name: project-setup
description: Single entry point for all project knowledge-base scaffolding. Interviews the user with three questions (starting point / target substrate / working language), then routes to the correct sub-skill — cowork-preparation (flat markdown, new or port-existing), obsidian-project-new (Obsidian vault, new, with Obsidian installed OR with bootstrap.sh first), or obsidian-project-convert (flat → Obsidian upgrade, or existing-Obsidian retrofit). Guarantees every project ends with the same baseline regardless of path. Use when the user says "set up a new project", "scaffold a project", "bootstrap a knowledge base", "/project-setup", "/vault-setup", "I want to start a project", "convert this project to Obsidian", or asks which scaffolding skill to invoke. Do NOT use for adding files to an existing already-scaffolded project, or for running maintenance on an existing setup.
---

# Project Setup — Orchestrator (consolidated v0.2.0)

A thin router that owns three things:

1. **The unified interview** — three questions max, regardless of path.
2. **The routing decision** — picks the right sub-skill from
   `cowork-preparation`, `obsidian-project-new`, or `obsidian-project-convert`.
3. **The baseline guarantee** — every project, regardless of path, ends with
   the same five elements (cascade, M9 caveat if non-English, session
   bootstrap, auto-write log, operating-guide pointer). Verified post-scaffold
   by `scripts/verify_baseline.py`.

Everything else (substrate-specific scaffolding, template substitution,
scheduled tasks, retrofitting, migration logic) is owned by the sub-skill we
route to.

## When to use this skill

Trigger phrases — `/project-setup`, `/vault-setup`, `/project-setup new`,
`/project-setup convert`, "set up a new project", "scaffold a project",
"bootstrap a knowledge base", "I want to start a project", "convert this
folder to Obsidian", "which scaffolding skill should I use".

Do **NOT** use this skill for:
- Adding a file to an existing already-scaffolded project — just write the
  file.
- Maintenance on an existing scaffold — use `kb-curator` (flat or Obsidian).
- A folder that already has a project structure installed (use the rules,
  do not re-scaffold).

## Workflow

### Phase 0 — Prerequisite check

Verify which sub-skills are installed:

| Sub-skill | Required for path |
|-----------|-------------------|
| `cowork-preparation` | New + Flat; Existing flat + Flat (port-existing) |
| `obsidian-project-new` | New + Obsidian (any state) |
| `obsidian-project-convert` | Existing flat + Obsidian; Existing Obsidian (retrofit) |

If a sub-skill is missing, do not offer its path. If none of the three are
installed, surface this and stop.

### Phase 1 — Three-question interview

Use `AskUserQuestion` if available. Branch on each answer before asking the
next.

**Q1 — Starting point.** "Is this a new project or existing content?"
- New project (greenfield, empty or near-empty folder)
- Existing flat-markdown knowledge base (Cowork project, Downloads folder,
  scratch notes you've been accumulating)
- Existing Obsidian vault

**Q2 — Target substrate.** "What knowledge-base substrate do you want?"
- Flat markdown (simple — no Obsidian install needed; cleanup via
  `kb-curator`)
- Obsidian vault (structured Bases queries + semantic via Smart Connections;
  richer retrieval but more setup)

**Q3 — Primary working language.** "What language(s) will the project's
content be in?"
- English only
- Portuguese / Spanish / other non-English primary
- Mixed (English + at least one non-English)

If Q3 is non-English-primary or mixed, the **M9 caveat** must appear
verbatim in the resulting CLAUDE.md (semantic retrieval is unreliable for
PT/ES/non-English content — skip step 1, go directly to step 2).

### Phase 2 — Route (5 scenarios)

The full substrate × scenario matrix:

| Q1 — Starting point | Q2 — Substrate | → Route | Sub-action |
|---|---|---|---|
| **New** | Flat | `cowork-preparation` | greenfield mode |
| **New** | Obsidian (Obsidian installed) | `obsidian-project-new` | scaffold-new |
| **New** | Obsidian (Obsidian NOT installed) | bootstrap.sh prompt → `obsidian-project-new` | bootstrap-then-new |
| **Existing flat** | Flat | `cowork-preparation` | port-existing mode |
| **Existing flat** | Obsidian | `obsidian-project-convert` | convert |
| **Existing Obsidian** | Obsidian | `obsidian-project-convert` | retrofit-on-existing-obsidian |
| **Existing Obsidian** | Flat | **Refuse** — substrate downgrade unsupported | exit |

Detection logic for Obsidian-installed vs not:

```bash
if [ -d ".obsidian" ] || command -v obsidian >/dev/null 2>&1; then
  OBSIDIAN_INSTALLED=true
fi
```

If `Obsidian NOT installed`, emit the bootstrap prompt (see below) and wait
for the user to confirm install before proceeding.

Echo the routing decision to the user before invoking, e.g.:

> "Based on your answers (new project, Obsidian, English primary, Obsidian
> installed) I'll route to `obsidian-project-new`. M9 caveat: skipped —
> English primary. Proceeding."

### Phase 2.5 — Bootstrap prompt (only for "new + Obsidian + Obsidian-not-installed")

Emit this exact set of steps (do NOT execute the install — bootstrap is the
user's call):

```
To proceed you need Obsidian + the Smart Connections plugin + a configured
.obsidian directory. Run this once on your machine:

  # macOS (Homebrew Cask):
  brew install --cask obsidian

  # Then open Obsidian once, point it at this folder, and accept the
  # vault-creation prompt. Quit Obsidian.

  # Install Smart Connections (within Obsidian):
  # Settings → Community plugins → Browse → "Smart Connections" → Install → Enable

When that's done, re-run /vault-setup or /project-setup. I'll detect the
.obsidian/ directory and proceed with scaffold-new.
```

Then stop. Re-running detects the new state and routes to `obsidian-project-new`.

### Phase 3 — Invoke the sub-skill

Use the Skill tool to invoke the routed sub-skill, passing through whatever
answers were already collected so the sub-skill doesn't re-ask:

- Working language → goes into the sub-skill's CLAUDE.md template (M9
  caveat trigger).
- Project mode (greenfield vs port-existing) for `cowork-preparation` —
  pre-answered by Q1.
- Vault state (empty vs has-content) for `obsidian-project-convert` —
  derived from Q1.

Let the sub-skill run its own clarification interview (project name, vault
path, key entities), scaffold, retrofit/migration, and verification phases.
Do NOT intervene mid-execution.

### Phase 4 — Baseline verification

After the sub-skill returns, run `scripts/verify_baseline.py --root
<project_root>`. The script asserts five elements exist:

1. **CLAUDE.md** containing canonical phrases for the five required
   sections — identity, cascade (5 steps), M9 caveat (if non-English
   declared), session bootstrap, write rule.
2. **Auto-write zone** — `99 Workspace/` (Obsidian) or `cowork_outputs/`
   (flat).
3. **`_auto_writes.md`** — present and frontmattered as `type: log` or
   equivalent.
4. **`_session_handoff.md`** — present with `last_updated:` frontmatter.
5. **Operating-guide pointer** — `_operating_guide.md` (Obsidian, kernel-
   generated) or `_guide_context_engineering.md` (flat).

If verification fails, report each missing element with the exact path and
remediation hint. Do NOT silently paper over a gap.

### Phase 5 — Companion offers

After verification passes:

- **Flat projects:** "I recommend installing `kb-curator` for session-to-
  session maintenance."
- **Obsidian projects:** "Smart Connections MCP indexing is part of
  `obsidian-project-new`'s Phase 6. If the sub-skill didn't get there, run
  that phase now. Also consider installing the other four plugins in the
  `claude-obsidian-vault` marketplace: vault-skills, vault-eval, vault-
  ingestion, vault-voice."

### Phase 6 — Handoff

Single short message:

> "Project scaffolded as **[Project Name]** at `<path>`. Substrate:
> **[Flat | Obsidian]**. Routing path: **[FLAT-new | FLAT-existing |
> OBSIDIAN-new-with-obsidian | OBSIDIAN-new-no-obsidian (bootstrap then
> new) | OBSIDIAN-existing]**. M9 caveat: **[applied | not applied]**.
> Baseline verifier: **PASSED**.
>
> First-session steps are in CLAUDE.md's bootstrap section. To run another
> setup, invoke `/project-setup` or `/vault-setup` again."

## Guardrails

- **Never inline sub-skill logic.** If a sub-skill is missing, stop.
- **Never override the sub-skill's interview answers.** Q1/Q2/Q3 here are
  pre-fills, not replacements.
- **Never skip baseline verification.** Even if the sub-skill says "done".
- **Never run a path whose sub-skill is uninstalled.**
- **Never proceed past Phase 2.5 without Obsidian installed for an
  Obsidian path.**

## Baseline guarantee — what every project gets

This table is the contract this orchestrator enforces.

| Element | Flat (`cowork-preparation`) | Obsidian (`obsidian-project-new` / `-convert`) |
|---|---|---|
| Identity block in CLAUDE.md | Yes | Yes |
| 5-step retrieval cascade | Yes (Step 0 lex → 1 sem → 2 grep/struct → 3 link-expand → 4 deep-read) | Yes (Step 0 lex → 1 sem → 2 Bases → 3 link-expand → 4 deep-read) |
| M9 caveat (if non-English) | In CLAUDE.md | In CLAUDE.md and `_operating_guide.md` |
| Session bootstrap (≥6 steps) | Yes | Yes (8 steps for Obsidian) |
| Auto-write zone | `cowork_outputs/` | `99 Workspace/` |
| `_auto_writes.md` | Yes | Yes (hash-chained) |
| `_session_handoff.md` | Yes | Yes |
| Operating-guide pointer | `_guide_context_engineering.md` | `_operating_guide.md` (kernel + 4 stubs) |
| `_hot.md` orientation surface | No (optional) | Yes (≤2 KB) |

## Smoke-test paths

Seven branches to walk when testing this skill end-to-end:

1. **New + Flat + English** → `cowork-preparation` greenfield. No M9.
2. **New + Obsidian + Obsidian-installed + English** → `obsidian-project-new`.
3. **New + Obsidian + Obsidian-NOT-installed + English** → emit
   bootstrap.sh prompt; on re-run, `obsidian-project-new`.
4. **New + Obsidian + PT/ES** → `obsidian-project-new`. M9 caveat fires.
5. **Existing flat + Obsidian** → `obsidian-project-convert`. Analysis +
   migration phase.
6. **Existing flat + Flat** → `cowork-preparation` port-existing.
7. **Existing Obsidian + Obsidian** → `obsidian-project-convert` retrofit.

Edge:
- Existing Obsidian + Flat → refuse (substrate downgrade unsupported).

## Reference files

- `cowork-preparation/SKILL.md` — flat-markdown scaffold workflow.
- `obsidian-project-new/SKILL.md` — Obsidian vault scaffold workflow.
- `obsidian-project-convert/SKILL.md` — flat → Obsidian migration + existing-
  Obsidian retrofit workflow.
- `scripts/verify_baseline.py` — post-scaffold 5-element check.

## Versioning

- **v0.2.0 (2026-05-17)** — Consolidated entry point for vault-framework
  marketplace plugin. Adds the 5-scenario routing matrix (FLAT-new / FLAT-
  existing / OBSIDIAN-new-with-obsidian / OBSIDIAN-new-no-obsidian / OBSIDIAN-
  existing). Adds bootstrap.sh prompt for "Obsidian wanted but not installed".
  Adds existing-Obsidian retrofit path (was previously refused). Compatible
  with the consolidated `/vault-setup` slash command. Phase 0 unchanged. Phase
  2 routing matrix expanded.
- **v0.1.0 (2026-05-10)** — Initial release; 4-path routing matrix; existing-
  Obsidian was out of scope.

## Precedence

If the user's answers conflict with the routing matrix, the user wins — but
the orchestrator must explain which path it would have routed to and let the
user confirm or override. Silent re-routing is forbidden.
