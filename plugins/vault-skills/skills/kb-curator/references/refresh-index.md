# kb-curator refresh-index mode

Rebuild the project's global knowledge base index by running the project's own `_build_index.py`. Autonomous per P-7 of the context engineering guide.

## Invocation

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/kb-curator/scripts/curator.py refresh-index
```

## Side effects

- `cowork_outputs/_index.md` regenerated.
- If rendered output exceeds 800 lines, per-zone `_index_<zone>.md` shards are written and `_index.md` becomes a slim navigator (handled by the project's `_build_index.py`, not this script).
- One line appended to `cowork_outputs/_auto_writes.md` for the audit trail.
- No other files touched.

## What to report

After the run, report to the user:

- Total counts: good / legacy / broken / binary files.
- Mode used: monolithic vs sharded.
- Delta from the previous build if known.
- If `broken > 0`, suggest reading `cowork_outputs/_index_errors.log` to diagnose.

## Hard guardrails

- The only files written are `_index.md`, possibly per-zone shards, and one append to `_auto_writes.md`.
- Never edit content files. Never edit `CLAUDE.md` or the state file.
