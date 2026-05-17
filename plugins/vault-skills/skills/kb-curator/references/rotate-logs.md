# kb-curator rotate-logs mode

Generate a log rotation proposal — snapshot operational logs to `_archive/logs/` when they exceed size thresholds. **PROPOSAL ONLY** — no rotation happens until the user approves with the phrase `approve log rotation`.

## Invocation

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/kb-curator/scripts/curator.py rotate-logs
```

## Triggers

- Size: `_cleanup_log.md` >200 KB OR `_auto_writes.md` >80 KB.
- Time: quarterly (paired with state-file compression).

## Output

`cowork_outputs/_log_rotation_proposal_YYYY-MM-DD.md`. If no logs are over threshold, the proposal is empty — say so explicitly to the user.

## CRITICAL — trust the script, do not eyeball file sizes

The `curator.py rotate-logs` output is authoritative. Read its stdout (which says "N snapshots proposed" — N is exact) AND the proposal file content. Do NOT open `_cleanup_log.md` or `_auto_writes.md` and judge their sizes by eye — the script's threshold check is ground truth. A 130 KB log is NOT over a 200 KB threshold even though it "looks big". If the script says `0 snapshots proposed`, report exactly that — say "all logs within rotation thresholds, no action needed". Reading the raw log files in this mode is wasted work and a source of false positives.

## Post-approval procedure

After the user approves, the rotation steps are:
1. Move current log to `_archive/logs/_<logname>_YYYY_QN_through_YYYY-MM-DD.md`.
2. Create fresh `_<logname>.md` in `cowork_outputs/` with frontmatter and a `previous_snapshot:` pointer to the archived file.
3. Append the rotation event to the new (fresh) log so the audit trail stays continuous.

This skill writes only the proposal — execution is a separate, explicit step.

## Hard guardrails

- DOES NOT execute snapshots. Only writes the proposal file.
- Snapshot destination is always `_archive/logs/`.
- Outside the P-7 autonomy boundary because moves into `_archive/` touch a curated zone — same rule as cleanup proposal.
