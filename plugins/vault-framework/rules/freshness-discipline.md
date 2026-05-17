# Freshness discipline

Cadence triggers (when to verify before quoting):

- weekly | event-driven: stale if >7d. Cross-check handoff and recent debriefs.
- monthly | monthly-or-on-structural-change: stale if >30d. Verify if recent
  decisions matter.
- stable: no auto-check. Only verify if recency is explicitly relevant.
- per-session | continuous | append-only: operational — if these look stale,
  the file is misconfigured.

Per-section freshness for the state MOC: each anchored section carries
`Last touched: YYYY-MM-DD`. If >14d, flag potential staleness before
acting on content.

## Handoff size — 3-strike compression rule

`99 Workspace/_session_handoff.md` target size: ≤15 KB. Soft flag at >15 KB;
**hard trigger at 3 consecutive sessions over the threshold**.

When the third consecutive session would write a >15 KB handoff:

1. **Before writing the new handoff**, run handoff compression: archive the
   oldest "what we worked on" arc(s) into
   `99 Workspace/_session_handoff_archive/YYYY-MM-DDTHHMM_<descriptor>.md`.
2. Replace the archived arcs in the live handoff with one-line pointers.
3. Then write the new session's content into the slimmed live handoff.

Counting strikes: read the prior 2 handoff archive entries; if both >15 KB and
today would be the third, compression is mandatory. Reset strike count after
each compression.
