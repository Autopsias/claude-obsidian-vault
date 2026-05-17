---
description: P-10 promotion ritual — move a file from 99 Workspace/ into a typed zone (10 People / 20 Companies / 30 Projects / 40 Meetings / 50 Sources / 60 Concepts / 70 Decisions) with quality-filter check + cross-reference rewrite + audit log.
argument-hint: "<workspace-file-path>"
---

# /promote

You are running the `promote` slash command from the `vault-framework`
plugin. The goal is to apply the **P-10 promotion ritual**: take a file
from `99 Workspace/` and move it into the correct typed zone with the
right frontmatter, after passing a quality filter.

## The three-question quality filter

Before proposing any move, the file must pass all three:

1. **Will the future-me search for this?** If no, leave it in workspace or
   delete. If yes (likely lookup, citation, decision reference, person
   bio), continue.
2. **Is the content typed?** Does it belong to a single category — a
   person, a company, a meeting, a source, a concept, a decision? If it's
   a hybrid (e.g. a sources-and-analysis mix), split it before promotion.
3. **Does the content stand on its own?** If the file makes sense only as
   part of the workspace conversation that produced it, it's not promotion-
   ready — extract the durable claim into a new file first.

A "no" on any of the three = surface the gap to the user and stop. Do not
silently promote a borderline file.

## Process

### Step 1 — Read + classify

Read the target file. Decide the destination zone:

| Content | → Zone |
|---|---|
| Bio + role + responsibilities for one person | `10 People/` |
| Org overview + market position for one company | `20 Companies/` |
| State of one ongoing project / workstream | `30 Projects/` |
| One meeting's notes / transcript / agreed actions | `40 Meetings/` |
| External reference content (a memo, an article, a PDF extract) | `50 Sources/` |
| Reusable explanation of a concept (3-tier definition, terminology) | `60 Concepts/` |
| One discrete decision with criteria + rationale + counter-args | `70 Decisions/` |

If you can't fit it cleanly into a zone, surface the gap and stop.

### Step 2 — Propose frontmatter

For the destination zone, propose the canonical frontmatter contract.
Reference the entity-anchors canonical spec in
`90 System/_entity_anchors_canonical.md` (if present) for required H2
sections.

Minimum frontmatter, by zone:

- **10 People/**: `type: person, name: ..., role: ..., aliases: [...]`
- **20 Companies/**: `type: company, name: ..., industry: ..., aliases: [...]`
- **30 Projects/**: `type: project, name: ..., status: active|paused|closed`
- **40 Meetings/**: `type: meeting, date: YYYY-MM-DD, attendees: [...]`
- **50 Sources/**: `type: source, source_kind: ..., document_date: YYYY-MM-DD, is_latest_version: true, document_version: v1`
- **60 Concepts/**: `type: concept, aliases: [...]`
- **70 Decisions/**: `type: decision, decision_date: YYYY-MM-DD, workstream: ..., outcome: ...`

### Step 3 — Propose H2 section structure

Each zone has required anchored sections. For example:

- **People**: `## Profile / ## Recent mentions / ## Related materials / ## Cross-references`
- **Sources**: `## Summary / ## Key claims / ## Related materials / ## Cross-references`
- **Decisions**: `## Decision / ## Rationale / ## Counter-arguments / ## Cross-references`
- **Concepts**: `## Definition / ## Counter-arguments / ## Cross-references / ## Recent mentions`

If the source file doesn't have the required sections, propose how to
restructure. Do NOT silently re-organise — surface the structure and ask
for the user's sign-off.

### Step 4 — Cross-reference rewrite

`grep` for the workspace file's existing path across the vault. Any
existing wikilink pointing at the old path must be rewritten to the new
path. Surface the list before moving — the user should see the blast
radius.

### Step 5 — Move + log

Use `os.rename()` (atomic). After move:

1. Append the move to `99 Workspace/_cleanup_log.md` with reason.
2. Append the hash-chain entry to `_auto_writes.md` via
   `90 System/_audit_chain.py append --verb move --path <new-path>`.
3. If the source file produced a "this got too big to leave in workspace"
   tag in the session handoff, mark the original handoff thread as
   resolved.

### Step 6 — Confirm

Single short message:

> "Promoted `<old-path>` → `<new-path>` (zone: <zone>). N cross-references
> rewritten. Logged at `_cleanup_log.md` and `_auto_writes.md`. Frontmatter
> applied. H2 sections: <list>."

## Guardrails

- **Never bypass the three-question filter.** Even if the user types
  `/promote <file>` directly — surface the filter check first.
- **Never silently restructure content.** Headings, frontmatter, body
  changes all surface for sign-off before move.
- **Never promote without cross-reference scan.** Broken wikilinks are
  the failure mode this command exists to prevent.
- **One file per invocation.** Bulk-promote is a different operation; ask
  the user to call `/promote` once per file or invoke `kb-curator
  propose-cleanup` instead.

## When NOT to promote

- File is a daily note → stays in `80 Daily/`.
- File is a session handoff or auto-write log → stays in `99 Workspace/`.
- File is a draft that hasn't passed quality-filter Q3 → keep in
  workspace; surface what's missing.
- File is system / infrastructure (operating guide, contract, eval) →
  goes to `90 System/`, NOT to a typed zone.
