# Acme-BetaCo Integration Vault — Stable Prefix

This file is the **stable prefix** — a six-month test for any addition. Volatile content lives in `30 Projects/Acme-BetaCo Integration.md` (state MOC) and `99 Workspace/_session_handoff.md`. Behaviour lives in `90 System/_operating_guide.md`. If this file and `_operating_guide.md` conflict: `_operating_guide.md` wins for **behaviour**; this file wins for **facts**.

## Canonical Workspace

Canonical path: **`/Users/yourname/Documents/Vaults/Acme-BetaCo`**. Replace `yourname` with your actual macOS username. Any other Acme/BetaCo/Atlas-named mount at root level is a misconfiguration — hard stop.

## Who

Morgan Chen, **CIO of Acme Corp** (role held since 2024-03-01). Reports to CEO Linda Park and CFO David Kim. Background: former CDO at a Fortune 100 US retailer, 20+ years enterprise technology. Direct, technically deep, business-value focused. Philosophy: open/event-driven architecture, no monoliths, technology integrated into business lines, people drive transformation. English-only vault.

## What — Project Atlas

Codename for the acquisition and integration of BetaCo (UK SaaS, ~150 employees, customer lifecycle analytics) by Acme Corp (US enterprise SaaS, ~3,000 employees, B2B CRM/analytics). Deal closed 2026-01-15. Currently in the 100-day integration phase (Day 45 as of 2026-03-01). Four active workstreams: SSO Migration, Data Residency, Customer Comms, Contract Novation.

Live workstream status and strategy framework: `30 Projects/Acme-BetaCo Integration.md` (state MOC).

## Vault Topology — Johnny-Decimal

Eight zones. **Auto-write OK** (log per auto-write discipline): `00 Inbox/`, `80 Daily/`, `99 Workspace/`. **Trigger-only** (explicit Morgan authorisation): `10 People/`, `20 Companies/`, `30 Projects/`, `40 Meetings/`, `50 Sources/`, `60 Concepts/`, `70 Decisions/`, `90 System/`. Special trigger-only: `CLAUDE.md`, `30 Projects/Acme-BetaCo Integration.md`, `99 Workspace/_session_handoff.md`.

**Versioning.** Source and decision files carry `document_date` + `is_latest_version` frontmatter. Full contract: P-4 in `90 System/_operating_guide.md`.

## Retrieval Cascade (M1)

Five steps in order — stop at first clear hit: **Step 0 Lexical** (scan `_index.md` first, then grep/ripgrep — exact names, identifiers, frontmatter) → **Step 1 Semantic** (smart connections lookup if available) → **Step 2 Bases** (`90 System/Bases/`) → **Step 3 Link-expand** (wikilink BFS) → **Step 4 Deep-read** (anchored sections `## Workstream:` / `## Counterparty:`). Full discipline: P-3 in `90 System/_operating_guide.md`.

## Session Bootstrap

Seven steps — full sequence: P-5 in `90 System/_operating_guide.md`. Load-bearing reminders:
- Step 1: mount check — `Acme-BetaCo/` only at mount root.
- Step 2: read `_hot.md` FIRST, then `_session_handoff.md` + run 3 sanity checks (date / file-list / maintenance-flag).
- Step 4.5: read `_plans_index.md` and load the canonical active plan's Operating Manual + Up Next card.
- Step 4.6: read first 100 lines of `_index.md` (vault content catalog).
- ⚠ **If eval >30 days old:** banner as first line of orientation.

## Write Rule

All session outputs go to `99 Workspace/`. Typed-zone promotion (`10 People/`, `40 Meetings/`, `50 Sources/`, `70 Decisions/`, etc.) requires explicit Morgan authorisation, logged in `99 Workspace/_cleanup_log.md`.

## Voice Rule

Any audience-facing prose drafted under Morgan's name (emails, board updates, stakeholder comms, presentations) follows the voice profile at `90 System/_voice_profile.md` (placeholder — populate with your own writing corpus and voice notes). Target: the real Morgan Chen voice, not AI-polished register. Sign-off repertoire: Best regards / Thanks / Cheers — never "Warm regards."

## Title Rule

**"CIO"** is the correct title (since 2024-03-01). **NEVER "CTIO"** or **"CDO"** in current-context documents. Documents before 2024-03-01 may reference prior CDO role — do not retro-edit.

## Document Anonymisation

External-facing documents: role titles not names (Morgan → "Acme Technology"; Raj Patel → "BetaCo Technology"). Internal documents: real names OK. Full policy: `90 System/_comms_policy.md` (placeholder).

## Key People

Always-on: **CEO Linda Park** + **CFO David Kim**; **BetaCo counterparts** Raj Patel (CTO) + Emma Walsh (SVP Product, ex-CEO). Full roster: `10 People/`. Decoder ring: `99 Workspace/glossary.md`.

## External Resources

Calendar: Outlook via web. Consultants: Alpha Advisory (integration management, Sarah Torres) + Sigma Partners (data architecture, James Whitfield). Integration target: Day 90 = 2026-04-14 (SSO cutover); Day 100 = 2026-04-25.

## Pointers — Where Things Live

- Operating guide (P-rules): `90 System/_operating_guide.md`
- State MOC: `30 Projects/Acme-BetaCo Integration.md` (anchored sections)
- Session handoff (live): `99 Workspace/_session_handoff.md`
- Auto-writes log: `99 Workspace/_auto_writes.md`
- Bases (7): `90 System/Bases/`
- Voice profile: `90 System/_voice_profile.md` (populate with your corpus)
