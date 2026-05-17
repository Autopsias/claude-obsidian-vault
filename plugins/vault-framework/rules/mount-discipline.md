# Mount discipline

**[PROJECT-SPECIFIC: Substitute your vault's canonical path below and adapt
the path-gating logic for your project's mount convention.]**

The canonical vault path must be defined in CLAUDE.md as:
```
Canonical path: /path/to/YourVault
Bash mount: /sessions/<session>/mnt/YourVaultFolderName/
```

## Session-bootstrap check

At session start, before any Write/Edit operation under `99 Workspace/`:

1. List Cowork mounts (e.g. `ls /sessions/*/mnt/`).
2. If a non-canonical vault-named folder is mounted at the mount-root level
   (any Galp/GALP/Peninsula-named folder that is NOT exactly the canonical
   mount), **STOP and surface to the user immediately.** Do not write to
   either folder until they resolve the conflict.
3. If only the canonical vault is mounted: proceed.

This is a hard-stop rule. The cost of one false-stop conversation is much
lower than the cost of silently routing writes to the wrong folder.

## Why this rule exists

Between mid-April and 2026-05-02, Cowork silently routed session writes to a
parallel auto-created folder while routing edits on existing canonical files to
the canonical. ~22 load-bearing artefacts accumulated in the wrong folder over
~2 weeks before detection. This rule prevents recurrence.

## Recovery if this rule fires

1. Don't write anything new until the user approves a recovery plan.
2. Inventory the non-canonical folder by sha256.
3. Bucket as: identical (skip), unique (rescue), divergent (manual diff).
4. Migrate via `cp -a` + `cmp` verify; bulk-log per auto-write discipline.
5. Delete the non-canonical folder via `mcp__cowork__allow_cowork_file_delete`.
