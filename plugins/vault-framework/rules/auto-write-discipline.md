# Auto-write discipline

Per operating guide P-7. Inside `99 Workspace/` Claude writes without
per-file approval, **provided** every write is logged to
`99 Workspace/_auto_writes.md`. Outside requires explicit user trigger.

Same applies to `00 Inbox/` and `80 Daily/` — auto-write OK; logging required.

Format: `YYYY-MM-DD | verb | path | one-line reason`.
Verbs: write, edit, rename, note, delete. Append-only.

Before writing: confirm path is under `99 Workspace/` (or `00 Inbox/`,
`80 Daily/`); confirm frontmatter; populate `provenance:` if it's a debrief /
analysis / audit / battleplan.

After writing: append the line. If >5 files this session, propose
`kb-curator refresh-index`.

Reconciliation safety net: weekly vault-health check catches dropped
log entries.

Never auto-write: state MOC, CLAUDE.md, handoff
(only on explicit triggers), or anything outside the three auto-write zones.

## Audit-time size-breach surfacing

When any audit (write-audit, kb-audit, vault-health) runs against
`99 Workspace/_auto_writes.md`, the audit must check size at completion:

- `_auto_writes.md` >80 KB → recommend `kb-curator rotate-logs --root <vault>`
  in the same report. Do not wait for the quarterly log-rotation.
- `_cleanup_log.md` >200 KB → same recommendation.

## Bulk reconciliation pattern

When a write-audit reports **>20 unlogged files**, do NOT back-date
one entry per file (bloats the log). Instead append ONE summary line:

```
YYYY-MM-DD | note | 99 Workspace/_audit_writes_YYYY-MM-DD.md | bulk reconciliation: N unlogged files reconciled; see audit report for the full list
```

The audit report is the durable, complete record.

## OS-junk delete carve-out

OS junk files (`.~lock.*`, `~$*`, `.DS_Store`, `Thumbs.db`, `*.tmp`, `lu*.tmp`)
MAY be deleted without per-file authorisation when they block a clean audit
state, **provided** the deletion is logged with verb `delete`.

Real artefacts (`.md`, `.docx`, `.pptx`, `.xlsx`, `.pdf`, `.html`, `.skill`,
`.zip`, `.png`, `.jpg`) remain under "no deletes ever — moves only, after
approval". If ambiguous, ask.

If bash returns "Operation not permitted" on `rm`, call
`mcp__cowork__allow_cowork_file_delete` with the target path before retrying.
