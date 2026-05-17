# setup-automation mode

## When to invoke

After `kb-curator upgrade-apply` completes on a retrofitted project. The upgrade creates the additive files (contract, rules, hooks, reflection log, lessons) but does NOT create scheduled tasks — the script can't call MCPs. This mode produces the prompts so Claude can.

For newly-bootstrapped projects, the cowork-preparation skill's Phase 3b already creates these tasks. Don't run setup-automation on a freshly-bootstrapped project — you'd duplicate the tasks.

## What it does

Writes `cowork_outputs/_automation_setup_<date>.md` containing five MCP tool-call payloads, parameterised by project slug:

1. `<slug>-handoff-freshness` — daily 07:30 — flags open threads >24h old.
2. `<slug>-audit-writes` — daily 07:35 — reconciles auto-writes log against filesystem.
3. `<slug>-kb-audit` — weekly Monday 09:00 — main audit + propose-cleanup.
4. `<slug>-eval-recency` — first Monday of month 09:00 — retrieval eval recency check.
5. `<slug>-log-rotation` — quarterly (1st of Jan/Apr/Jul/Oct) 09:00 — log rotation check.

## How Claude uses the output

After running `setup-automation`, Claude:

1. Reads the proposal file.
2. For each of the 5 tasks, calls `mcp__scheduled-tasks__create_scheduled_task` with the JSON-encoded payload.
3. Calls `mcp__scheduled-tasks__list_scheduled_tasks` to verify all five landed.
4. Appends a single line to `_auto_writes.md` recording the setup event.
5. Renames the proposal file to `_automation_setup_<date>_applied.md` to signal completion.

## Project slug derivation

In order:
1. `_cowork_contract.json` `project_slug` field, if set.
2. Fallback: lowercased project root folder name with spaces and underscores → hyphens.

## Hard constraints

- Doesn't create the tasks itself. Claude does, via MCP.
- Doesn't edit state file, CLAUDE.md, handoff, or anything outside the proposal file.
- Doesn't re-run if `_automation_setup_*_applied.md` exists for current month — surface "already applied" instead.

## Bash invocation

```
python3 scripts/curator.py setup-automation [--root /path/to/project]
```
