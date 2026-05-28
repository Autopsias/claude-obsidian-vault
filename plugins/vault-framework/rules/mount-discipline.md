# Mount discipline

**[PROJECT-SPECIFIC: Substitute your vault's canonical path below and adapt
the path-gating logic for your project's mount convention.]**

The canonical vault path must be defined in CLAUDE.md as:
```
Canonical path: {{VAULT_PATH}}
Bash mount: /sessions/<session>/mnt/{{VAULT_FOLDER_NAME}}/
```

## Session-bootstrap check

At session start, before any Write/Edit operation under `99 Workspace/`:

1. List Cowork mounts (e.g. `ls /sessions/*/mnt/`).
2. If a folder whose name matches your project's vault naming pattern (the
   vault name, or a known legacy/migration alias) is mounted at the
   mount-root level and is NOT exactly the canonical mount, **STOP and
   surface to the user immediately.** Do not write to either folder until
   they resolve the conflict.
3. If only the canonical vault is mounted: proceed.

<!-- PROJECT-SPECIFIC: If your project has a rollback window after a vault
     migration, a second legacy-canonical folder may be expected at the
     mount root during that window (e.g. Galp Vault permits "Galp/"
     alongside "Galp-Vault/" until T+30 from the migration date). During the
     window, both mounts are expected; after it closes, expect exactly one.
     Otherwise omit. -->

This is a hard-stop rule. The cost of one false-stop conversation is much
lower than the cost of silently routing writes to the wrong folder.

Plumbing dirs (`mnt/.claude/`, `mnt/.projects/`, `mnt/.local-plugins/`,
`mnt/.remote-plugins/`, `mnt/.auto-memory/`) and session-scoped mounts
(`mnt/outputs/`, `mnt/uploads/`) do NOT trigger this rule.

## Why this rule exists

Between mid-April and 2026-05-02, Cowork silently routed session writes to a
parallel auto-created folder while routing edits on existing canonical files to
the canonical. ~22 load-bearing artefacts accumulated in the wrong folder over
~2 weeks before detection. This rule prevents recurrence.

## Recovery if this rule fires

1. Don't write anything new until the user approves a recovery plan.
2. Inventory the non-canonical folder by sha256.
3. Bucket as: identical (skip), unique (rescue), divergent (manual diff).
4. Migrate via `cp -a` + `cmp` verify; bulk-log per `auto-write-discipline.md`.
5. Delete the non-canonical folder via `mcp__cowork__allow_cowork_file_delete`.
6. Document the consolidation in an audit file at
   `99 Workspace/_audit_YYYY-MM-DD_folder_consolidation.md` (lifted into the
   vault as part of the migration) and reference it as the recovery precedent.
