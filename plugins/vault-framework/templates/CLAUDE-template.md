---
name: {{PROJECT_NAME}} Vault — Stable Prefix
description: Facts, canonical paths, and load-bearing pointers for the {{PROJECT_NAME}} Vault. Volatile state lives in {{KEY_PROJECT_PAGE}} and 99 Workspace/_session_handoff.md. Behaviour in 90 System/_operating_guide.md (thirteen P-rules).
cadence: stable
last_updated: {{LAST_UPDATED}}
---

# {{PROJECT_NAME}} Vault — Stable Prefix

This file is the **stable prefix** — six-month test for any addition. Volatile content lives in `{{KEY_PROJECT_PAGE}}` (state MOC) and `99 Workspace/_session_handoff.md`. Behaviour lives in `90 System/_operating_guide.md`. If this file and `_operating_guide.md` conflict: `_operating_guide.md` wins for **behaviour**; this file wins for **facts**.

## Canonical Workspace

Canonical path: **`{{VAULT_PATH}}`**. Bash mount: `/sessions/<session>/mnt/{{VAULT_FOLDER_NAME}}/`. Any other {{VAULT_KEYWORD_LIST}}-named mount at root level is a misconfiguration — hard stop per `mount-discipline.md`. Legacy canonical `{{LEGACY_VAULT_PATH}}` is the T+30 rollback target (read-only after {{LEGACY_FREEZE_DATE}}).

## Who

{{USER_NAME}}, **{{USER_ROLE}}** (effective {{ROLE_EFFECTIVE_DATE}}). Reports to {{REPORTING_LINE}}. Background: {{BACKGROUND_SUMMARY}}. {{COMMUNICATION_STYLE}}. Philosophy: {{OPERATING_PHILOSOPHY}}.

## What — {{PROJECT_CODENAME}}

{{PURPOSE_STATEMENT}}. Live workstream status and strategy framework: `{{KEY_PROJECT_PAGE}}` (state MOC).

## Vault Topology — Johnny-Decimal

Eleven zones. **Auto-write OK** (log per `auto-write-discipline.md`): `00 Inbox/`, `80 Daily/`, `99 Workspace/`. **Trigger-only** (explicit {{USER_FIRST_NAME}} authorisation): `10 People/`, `20 Companies/`, `30 Projects/`, `40 Meetings/`, `50 Sources/`, `60 Concepts/`, `70 Decisions/`, `90 System/`. Special trigger-only: `CLAUDE.md`, `{{KEY_PROJECT_PAGE}}`, `99 Workspace/_session_handoff.md`. `.obsidian/` and `.smart-env/` — infrastructure, never touched manually. Full autonomy boundary: P-7 in `90 System/_operating_guide.md`.

**Versioning.** Source and decision files carry `document_date` + `is_latest_version` frontmatter. Use `Latest Only.base` for current state, `As Of.base` for point-in-time, `Version Chain.base` for history. Full contract: P-4.

## Retrieval Cascade (M1)

Five steps in order — stop at first clear hit: **Step 0 Lexical** (grep/ripgrep — exact names, identifiers, frontmatter) → **Step 1 Semantic** (`mcp__smart-connections__lookup`) → **Step 2 Bases** (`90 System/Bases/`) → **Step 3 Link-expand** (wikilink BFS) → **Step 4 Deep-read** (anchored sections `## Concept:` / `## Workstream:` / `## Counterparty:`). **Before step 0, detect temporal intent in the query — see P-3 routing matrix.** **M9 caveat:** skip step 1 for {{M9_LANGUAGE}} content — go directly to step 2. Full discipline and acceptance template: P-3 in `90 System/_operating_guide.md`. Enforced via `.claude/rules/retrieval-cascade-discipline.md` (pre-answer checklist for substantive queries — added 2026-05-13 retrospective).

## Session Bootstrap

Seven steps — full sequence: P-5 in `90 System/_operating_guide.md`. Enforced via `.claude/rules/session-bootstrap-discipline.md` (always-on session-start checklist — added 2026-05-13 retrospective). Load-bearing reminders:
- Step 1: mount check — `{{VAULT_FOLDER_NAME}}/` only at mount root (+ `{{LEGACY_VAULT_FOLDER}}` during rollback window).
- Step 2: read `_session_handoff.md` + run 3 sanity checks (date / file-list / maintenance-flag).
- Step 4.5 (added 2026-05-25): read `_plans_index.md` and load the canonical active plan's Operating Manual + Up Next card. See P-5.
- ⚠ **If eval >30 days old:** banner as first line of orientation — before any other content.

{{DECOMMISSION_SECTION}}

## Write Rule

All session outputs go to `99 Workspace/`. Typed-zone promotion (`10 People/`, `40 Meetings/`, `50 Sources/`, `70 Decisions/`, etc.) via P-10 ritual only — proposed by Claude, approved by {{USER_FIRST_NAME}}, logged in `_cleanup_log.md`.

{{VOICE_RULE_SECTION}}

{{TITLE_RULE_SECTION}}

{{ANONYMISATION_SECTION}}

## Key People

Always-on: {{KEY_PEOPLE}}. Full roster: `10 People/`. Decoder ring (all people / acronyms / systems / codenames): `99 Workspace/memory/glossary.md`.

## External Resources

{{EXTERNAL_RESOURCES_LINE}} Skill packaging: **`.skill` file only** (never `.plugin`).

## Pointers — Where Things Live

- Operating guide (thirteen P-rules): `90 System/_operating_guide.md`
- Retrieval contract / eval / smoke-test: `90 System/_retrieval_contract.md` / `_eval_retrieval.md` / `_smoke_test_retrieval.py`
- State MOC: `{{KEY_PROJECT_PAGE}}` (anchored sections)
- Session handoff (live): `99 Workspace/_session_handoff.md` | Archive: `99 Workspace/_session_handoff_archive/`
- Auto-writes log / cleanup log / lessons / reflections: `99 Workspace/` (`_auto_writes.md`, `_cleanup_log.md`, `_lessons.md`, `_reflection_log.md`)
- Bases ({{BASES_COUNT}}): `90 System/Bases/` | Verifier: `90 System/_bases_verifier.py`
- Plugin security: `90 System/_plugin_security.md` | Memory landscape: `90 System/_memory_landscape.md`
- Comms policy (anonymisation): `90 System/_comms_policy.md`
{{ADDITIONAL_POINTERS}}

## Maintenance Automation

Five tasks (`{{VAULT_SLUG}}-handoff-freshness`, `{{VAULT_SLUG}}-write-audit`, `{{VAULT_SLUG}}-health`, `{{VAULT_SLUG}}-eval-recency`, `{{VAULT_SLUG}}-log-rotation`) surface drift; never execute moves. {{USER_FIRST_NAME}} approves. Cadences: `90 System/_maintenance_automation.md`.
