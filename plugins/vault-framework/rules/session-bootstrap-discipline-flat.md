<!-- KERNEL: Flat-markdown variant of session-bootstrap-discipline.md.
     Adapted for cowork-preparation projects (no Obsidian, no Smart Connections, no Bases).
     Differences from the Obsidian variant:
       - `cowork_outputs/` replaces `99 Workspace/` throughout
       - Step 6 (Bases glance) removed — no Bases in flat-markdown
       - Step 7 (Smart Connections stats) removed — no SC in flat-markdown
     Universally applicable pieces kept:
       - _plans_index.md step
       - 30-second orientation rule
       - Eval banner (PD-01)
       - Bootstrap-skippable criteria
     Source: galp-vault-canonical/rules/session-bootstrap-discipline.md (Obsidian variant)
     Added: 2026-05-13 (Substrate Hygiene S02 — HF-03) -->

# Session bootstrap discipline (flat-markdown)

This rule enforces the session bootstrap lifecycle for **flat-markdown cowork-preparation projects** — projects scaffolded by the `cowork-preparation` skill that do not use Obsidian, Smart Connections, or Bases. The operating guide's P-5 section (if present in your project) is the canonical definition; this rule enforces it as an always-on session-start checklist.

The lifecycle is enforced — skipping steps silently corrupts state.

## At session start — before substantive work

Claude MUST have, in order:

1. **Mount check.** Confirm the correct project folder is mounted. If a parallel or duplicate folder is mounted at the same level, **STOP and surface to {{USER_FIRST_NAME}} immediately.** Do not write to either folder until the conflict is resolved.

2. **Read `cowork_outputs/_session_handoff.md`** — last session, open threads, next actions. Run 3 sanity checks:
   - Date sanity: `last_updated` is consistent with when the last session ran.
   - File-list sanity: key files referenced in the handoff still exist at their paths.
   - Maintenance-flag sanity: any flagged actions from prior session are either actioned or carried forward.
   Flag mismatches to {{USER_FIRST_NAME}} immediately; do not begin substantive work until the mismatch is explained.

3. **Read the project's context-engineering guide** (`cowork_outputs/_guide_context_engineering.md`) when the task is non-trivial. "Non-trivial" = anything beyond a quick factual lookup. See "Substantive vs lookup" criteria below.

4. **Read `_plans_index.md`** at project root → identify the canonical (un-archived) plan → read its Operating Manual + Up Next session card. Skip silently if the index is empty or all plans are archived / completed.

5. **Check prior handoff for next-session triggers** — consolidation backlog, eval re-run due, log rotation pending, compression flagged. Surface to {{USER_FIRST_NAME}} before starting new work.

After bootstrap, give {{USER_FIRST_NAME}} a **30-second orientation**: last session date, what was worked on, open threads, what was wanted next. If Claude can't summarise where things stand, bootstrap was incomplete.

## ⚠ Eval banner (PD-01)

If the last retrieval eval is more than 30 days old (no dated `cowork_outputs/_eval_baseline_*.md` in the last 35 days), surface this as the **first line** of the orientation — before any other content:

> **EVAL DUE — last baseline is [N] days old (≥30). Run `cowork_outputs/_eval_context_retrieval.md` before substantive new work this session.**

Do not bury this in Maintenance Flags. The monthly eval is the sole falsifiability check on project retrieval behaviour; a late eval means every P-rule's performance claim is unverified.

## Substantive vs lookup

A **substantive query** = anything that informs a decision, meeting, document, stakeholder communication, or output {{USER_FIRST_NAME}} will act on. These trigger the full bootstrap and (if retrieval-cascade-discipline.md is present) the full cascade.

A **quick lookup** = a factual question answerable directly from `CLAUDE.md` alone (file path, name, date, status). Bootstrap may be abbreviated; cascade step 0 only.

## When bootstrap is skippable

Bootstrap is skippable ONLY for:

- Pure conversational replies (no tool use, no file reads)
- Trivial factual lookups answered from CLAUDE.md alone
- Continuation work where the prior session-end orientation is fresh (same calendar day, ≤2 hours elapsed)

When skipping, state it. **Default is to bootstrap.**

## Why

Every dropped step corrupts state in a way that surfaces hours or days later as a missed trigger, a stale fact, a conflict between handoff and reality. A consistent lifecycle is what makes a sequence of stateless sessions feel like a continuous collaboration. The 30-second orientation is the cheapest test of whether bootstrap actually worked.

## How to apply

Treat the lifecycle as load-bearing, not ceremonial. If a step seems redundant for today's task, do it anyway — the cost is small; the cost of silent drift is large. When the lifecycle disagrees with apparent task urgency, surface the conflict; do not skip to "real work". Document any deviation in the handoff.

## Cross-references

- `cowork_outputs/_guide_context_engineering.md` — project P-rules (operating guide equivalent)
- `CLAUDE.md` — Session Bootstrap stable-prefix pointer (if present)
- `cowork_outputs/_session_handoff.md` — live handoff
- `cowork_outputs/_session_handoff_archive/` — forensic archive
- `_plans_index.md` — plans registry
- `.claude/rules/freshness-discipline.md` — handoff size threshold + 3-strike compression rule
- `.claude/rules/auto-write-discipline.md` — write zone discipline (cowork_outputs/ is the auto-write zone)
