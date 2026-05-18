<!-- KERNEL: Enforces P-5 (session lifecycle / bootstrap) from the operating
     guide as an always-on session-start reminder. Auto-loads every session.
     The 7-step sequence is universal; specific path names and rollback
     windows in PROJECT-SPECIFIC sections adapt per project. -->

# Session bootstrap discipline

P-5 (`90 System/_operating_guide.md`) defines the 7-step session
bootstrap. The lifecycle is enforced — skipping steps silently corrupts
state.

## At session start — before substantive work

Claude MUST have, in order:

1. **Mount check.** `{{VAULT_FOLDER_NAME}}/` only at mount root. Per
   `mount-discipline.md`.
2. **Read `99 Workspace/_hot.md` FIRST** — always-fresh, ≤2 KB
   orientation surface: canonical plan + progress counter, Up Next session
   items, one in-flight risk, one open question. Takes ~5 seconds; gives
   the whole session context before anything else loads. Then read
   **`99 Workspace/_session_handoff.md`** — forensic detail, open threads,
   next actions. Run the 3 sanity checks on the handoff (date / file-list /
   maintenance-flag). Flag mismatches to {{USER_FIRST_NAME}} immediately;
   do not begin substantive work until the mismatch is explained.
3. **Read `90 System/_operating_guide.md`** when the task is
   non-trivial. "Non-trivial" = anything beyond a quick factual lookup
   (see `retrieval-cascade-discipline.md` for the "substantive query"
   criteria — same threshold applies).
4. **Open `80 Daily/YYYY-MM-DD.md`** — create stub if missing per
   `daily-notes-discipline.md`.
5. **Read `_plans_index.md`** at vault root → identify the canonical
   (un-archived) plan → read its Operating Manual + Up Next session
   card. Skip silently if the index is empty or all plans are
   archived / completed. *(This is step 4.5 in `_operating_guide.md`;
   numbered 5 here for sequential clarity.)*
6. **Glance at `90 System/Bases/Open Items.base`** for at-a-glance
   state across People / Companies / Projects / Decisions. The "Stale
   (oldest touched first)" view surfaces freshness concerns proactively.
7. **Check Smart Connections health** — `mcp__smart-connections__stats`.
   If the index is >7 days stale or source-count drift exceeds 2%, flag
   and pause writes.
8. **Check prior handoff for next-session triggers** — consolidation
   backlog, eval re-run due, log rotation pending, compression flagged.
   Surface to {{USER_FIRST_NAME}} before starting new work.

After bootstrap, give {{USER_FIRST_NAME}} a **30-second orientation**:
last session date, what was worked on, open threads, what was wanted
next. If Claude can't summarise where things stand, bootstrap was
incomplete.

## ⚠ Eval banner

If the eval-recency scheduled task signals the last retrieval eval is
more than 30 days old (no dated `99 Workspace/_eval_baseline_*.md` in
the last 35 days), surface this as the **first line** of the
orientation — before any other content:

> **EVAL DUE — last baseline is [N] days old (≥30). Run
> `90 System/_eval_retrieval.md` before substantive new work this
> session.**

Do not bury this in Maintenance Flags. The monthly eval is the sole
falsifiability check on vault behaviour; a late eval means every
P-rule's performance claim is unverified.

## When bootstrap is skippable

Bootstrap is skippable ONLY for:

- Pure conversational replies (no tool use, no file reads)
- Trivial factual lookups answered from CLAUDE.md alone
- Continuation work where the prior session-end orientation is fresh
  (same calendar day, ≤2 hours elapsed)

When skipping, state it. **Default is to bootstrap.**

<!-- PROJECT-SPECIFIC: If your project has a rollback window after a
     vault migration, add a second permitted mount-root folder for that
     window (e.g. Galp Vault permits "Galp/" alongside "Galp-Vault/"
     until 2026-06-08). Otherwise omit. -->

## Why

Every dropped step corrupts state in a way that surfaces hours or days
later as a missed trigger, a stale fact, a conflict between handoff and
reality. A consistent lifecycle is what makes a sequence of stateless
sessions feel like a continuous collaboration. The 30-second
orientation is the cheapest test of whether bootstrap actually worked.

## How to apply

Treat the lifecycle as load-bearing, not ceremonial. If a step seems
redundant for today's task, do it anyway — the cost is small; the cost
of silent drift is large. When the lifecycle disagrees with apparent
task urgency, surface the conflict; do not skip to "real work".
Document any deviation in the handoff.

## Cross-references

- `90 System/_operating_guide.md` — P-5 full definition with all 3
  sanity-check details and end-of-session handoff lifecycle
- `CLAUDE.md` — Session Bootstrap stable-prefix pointer
- `99 Workspace/_hot.md` — always-fresh ≤2 KB orientation surface; read before _session_handoff.md
- `99 Workspace/_session_handoff.md` — live handoff (target ≤15 KB)
- `99 Workspace/_session_handoff_archive/` — forensic archive
- `_plans_index.md` — plans registry
- `80 Daily/` — daily notes (per `daily-notes-discipline.md`)
- `90 System/Bases/Open Items.base` — at-a-glance state Base
- `.claude/rules/freshness-discipline.md` — handoff ≤15 KB threshold,
  3-strike compression rule
