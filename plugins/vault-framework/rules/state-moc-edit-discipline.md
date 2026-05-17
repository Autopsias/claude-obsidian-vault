---
paths:
  - "30 Projects/**/*.md"
---

# State MOC edit discipline

**[PROJECT-SPECIFIC: Adapt the file path, vocabulary, and maintenance guide
reference for your state MOC. The gating rules below are universal kernel.]**

Before any **structural** edit to the state MOC (header bump, version change,
new anchored section, archived block move), Claude **must**:

1. **Read the state MOC maintenance guide first** if one exists for this project
   (e.g. `90 System/_state_moc_maintenance.md`). Check the guide's `last_updated`.
   If older than 90 days, flag staleness in the next handoff and edit anyway,
   but note which rules may be drifting from current practice.

2. **Always update the affected anchored section's `Last touched: YYYY-MM-DD`
   marker** when the section's content actually changes. Do not bulk-update
   markers that didn't change — per-section freshness is the signal.

Non-structural edits (a single-line correction, a new bullet inside an existing
section without changing the section header) do not require the guide read,
but **must** still update the affected `Last touched` marker.

State-MOC edits are outside the P-7 autonomy boundary regardless of size — they
require explicit user trigger and never auto-log to `99 Workspace/_auto_writes.md`.
They surface in the next session handoff instead.

## Anchored section vocabulary (project must define in EXT-2)

The state MOC uses **anchored sections** with recognised heading vocabulary.
Canonical vocabulary from the Galp reference implementation:

```markdown
## Concept: <name>        — durable strategy concepts
## Workstream: <name>     — active workstreams / streams of work
## Counterparty: <name>   — external partners, clients, counterparties
## Decision: <id>         — pointer rows into 70 Decisions/
## Archive: <date> <desc> — superseded blocks kept for context
```

Each section carries a `Last touched: YYYY-MM-DD` marker on its own line,
immediately under the header. This is the unit of per-section freshness used
by the 14-day threshold in freshness-discipline.md.

**[FILL IN: project-specific vocabulary additions or overrides for EXT-2.]**

## Why

The state MOC is the single source of truth for live project context. Drift
between the maintenance guide and actual practice silently corrupts the file's
auditability. Per-section freshness markers are what make the 14-day staleness
threshold work at section granularity rather than file level.
