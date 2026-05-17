---
name: Operating Guide
type: system
last_updated: 2026-03-01
---

# Acme-BetaCo Integration Vault — Operating Guide

This file defines how Claude interacts with this vault. It is the authoritative source for behaviour rules. When this file and `CLAUDE.md` conflict: this file wins for **behaviour**; `CLAUDE.md` wins for **facts**.

---

## P-1: Stable Prefix Discipline

`CLAUDE.md` is the stable prefix — populated once, updated rarely. It contains facts that are unlikely to change month-to-month: who Morgan is, what Project Atlas is, where the vault lives, key people. Do not add content to `CLAUDE.md` that belongs in the state MOC (`30 Projects/Acme-BetaCo Integration.md`) or the session handoff (`99 Workspace/_session_handoff.md`).

**Test for CLAUDE.md inclusion:** "Will this still be true in six months?" If yes, it may belong in `CLAUDE.md`. If it changes weekly, it belongs in the state MOC or handoff.

*Example:* The fact that Morgan is CIO belongs in `CLAUDE.md`. The current SSO migration phase (Phase 2, 60% complete) belongs in the state MOC, not `CLAUDE.md`.

---

## P-3: Retrieval Cascade

Five steps in order. Stop at first clear hit. **Before Step 0, detect temporal intent:** if the query is about "what was decided in January" or "the state as of Day 30," route to the archive/handoff, not the live state MOC.

**Step 0 — Lexical.** Scan `_index.md` at vault root first (if it exists). On a clean stem match, jump to the matching notes. On a miss, fall through to `grep`/`Glob` over the vault. For frontmatter queries, use `yq`; for JSON, use `jq`.

*Example:* Query "who owns the SSO migration?" → scan `_index.md` for "SSO" → jump to `30 Projects/Acme-BetaCo Integration.md` § Workstream: SSO Migration → answer: Mike Okafor.

**Step 1 — Semantic.** Smart connections lookup (if available). Use Sources granularity for short notes; switch to Blocks for long mixed-topic notes (>20 KB, like the state MOC or operating guide) when the query targets a specific anchored section.

**Step 2 — Bases.** Open `90 System/Bases/Open Items.base` for unresolved action items. Open `90 System/Bases/Decisions.base` for the decision log. Use the Base for orientation, then drill to the linked note for detail.

**Step 3 — Wikilink BFS.** From the top Step 1/2 hit, expand one hop. Example: a query about Brightway Financial's contract risk → `BetaCo Customer Segmentation Report` links to → `Customer Comms Timing — Post-Close Announcement` and → `Contract Novation Workshop` meeting note.

**Step 4 — Deep-read.** Anchored sections in `30 Projects/Acme-BetaCo Integration.md`. Each workstream section, counterparty section, and open questions section has distinct content. Do not treat the state MOC as a single blob — read the relevant anchor.

**Routing matrix:**

| Signal | Route | Steps |
|--------|-------|-------|
| "as of [past date]" / "what did we decide in January" | A — archive | handoff archive + meeting notes by date |
| "latest" / "current status" | B — live state | Steps 0 → state MOC |
| "what does [person] think" | C — people | Steps 0 → 1 → People note + meeting notes |
| No temporal signal, substantive | D — full cascade | Steps 0 → 1 → 2 → 3 → 4 |

---

## P-4: Versioning Discipline

Source files (`50 Sources/`) and decision files (`70 Decisions/`) carry `document_date` and `is_latest_version: true` frontmatter. When a source is superseded, set `is_latest_version: false` on the old version and create a new file with the updated content and a new `document_date`. Do not overwrite the old version — the history matters for audit purposes.

*Example:* When the SSO Architecture Assessment is updated at Day 60, the new file is `SSO Architecture Assessment v2.md` with `is_latest_version: true`. The v1 file gets `is_latest_version: false`.

---

## P-5: Session Bootstrap

Seven steps — always run in order before substantive work.

1. **Mount check.** `Acme-BetaCo/` only at mount root.
2. **Read `99 Workspace/_hot.md` FIRST** (≤2 KB orientation surface). Then read `99 Workspace/_session_handoff.md`. Run 3 sanity checks: date / file-list / maintenance-flag. Flag mismatches immediately.
3. **Read this operating guide** for non-trivial tasks.
4. **Open `80 Daily/YYYY-MM-DD.md`** — create stub if missing.
5. **Read `_plans_index.md`** at vault root. Load canonical active plan's Operating Manual + Up Next card.
6. **Read first 100 lines of `_index.md`** at vault root (content catalog). Regenerate if >1 day old.
7. **Check `90 System/Bases/Open Items.base`** for at-a-glance integration state.

After bootstrap: give Morgan a 30-second orientation — last session date, what was worked on, open threads, what to do next.

---

## P-6: Source Ingestion

When a new document enters the vault (meeting notes, consultant deliverables, assessments), it goes to `00 Inbox/YYYY-MM-DD-<slug>.md` first. Frontmatter required: `type: source`, `document_date`, `provenance` (author/firm), `workstream`. Promotion to `50 Sources/` via P-10 quality filter and explicit Morgan authorisation.

*Example:* The Sigma Partners GDPR compliance validation report, when delivered, goes to `00 Inbox/2026-03-25-sigma-gdpr-compliance.md` first. Morgan reviews. If decision-relevant and complete, promotes to `50 Sources/`.

---

## P-7: Autonomy Boundary

**Auto-write OK (log in `99 Workspace/_auto_writes.md`):** `99 Workspace/`, `00 Inbox/`, `80 Daily/`.

**Trigger-only (explicit Morgan authorisation):** `10 People/`, `20 Companies/`, `30 Projects/`, `40 Meetings/`, `50 Sources/`, `60 Concepts/`, `70 Decisions/`, `90 System/`.

**Special trigger-only (named individually, regardless of zone):** `CLAUDE.md`, `30 Projects/Acme-BetaCo Integration.md` (state MOC), `99 Workspace/_session_handoff.md`.

State MOC edits always require an explicit trigger ("update the SSO workstream status," "yes please do") and never auto-log to `_auto_writes.md`. They surface in the next session handoff instead.

*Example:* Morgan says "note that Tom Bradley's retention conversation is scheduled for March 12." → Claude adds a `99 Workspace/` note (auto-write OK) + offers to update the state MOC Open Questions section (trigger-only, requires Morgan's explicit yes).

---

## P-8: Freshness Discipline

| Content | Freshness cadence | Stale threshold |
|---------|-------------------|-----------------|
| State MOC anchored sections | Weekly / event-driven | >7 days → flag |
| Session handoff | Per-session | >3 days → flag |
| People pages | Monthly or on change | >30 days → note |
| Decisions | Stable | Only if status changes |
| Sources | Per document version | `is_latest_version` flag |

**Handoff size:** Target ≤15 KB. Flag at >15 KB; compress if 3 consecutive sessions exceed threshold.

---

## P-10: Promotion Quality Filter

Before promoting an inbox note to a typed zone (`10 People/` through `70 Decisions/`), Claude must confirm:
1. The content is complete enough to be self-contained — a future reader without context can understand it.
2. It has correct frontmatter for its target zone.
3. It does not duplicate an existing note (check Step 0 first).
4. Morgan has explicitly approved the promotion (trigger-only).

Log the promotion in `99 Workspace/_cleanup_log.md`.

---

## P-11: Language

This vault is English-only. No multilingual routing required. All notes, frontmatter, and cross-references in English.

---

## P-12: Decommission Timeline

Post-integration (target: 2026-07-01, ~Day 165): review vault for archival. Active integration notes move to `_archive/` within each zone. The state MOC status changes to `status: complete`. Scheduled maintenance tasks retired. Full decommission protocol to be defined at Day 100.

---

## Vault quick reference

| Zone | Type | Auto-write? |
|------|------|-------------|
| `00 Inbox/` | Quick capture | Yes |
| `10 People/` | Person profiles | Trigger-only |
| `20 Companies/` | Company profiles | Trigger-only |
| `30 Projects/` | Project state MOC | Trigger-only |
| `40 Meetings/` | Meeting notes | Trigger-only |
| `50 Sources/` | Documents + reports | Trigger-only |
| `60 Concepts/` | Concept definitions | Trigger-only |
| `70 Decisions/` | Decision records | Trigger-only |
| `80 Daily/` | Daily notes | Yes |
| `90 System/` | System + config | Trigger-only |
| `99 Workspace/` | Working files | Yes |
