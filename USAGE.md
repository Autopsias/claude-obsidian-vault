# Usage Guide

Daily-driver reference for working with Claude in a vault-framework vault.

---

## Session start

Run `/hot` — Claude reads `99 Workspace/_hot.md`, a ≤2 KB always-fresh orientation surface, and gives you a 30-second summary: what was worked on last session, open threads, and what's next. It then reads the full session handoff for forensic detail.

Alternatively: "What's on the handoff?" prompts the same bootstrap sequence without the slash command.

If the bootstrap surfaces an eval banner (retrieval eval >30 days old), deal with that before starting new work — it means every P-rule's performance claim is currently unverified.

---

## Query the vault

Ask Claude naturally — it walks the retrieval cascade automatically:

> "What did we decide about the API authentication approach?"

For substantive queries (anything that informs a decision or document), Claude walks all 5 steps: lexical scan of `_index.md`, semantic lookup via Smart Connections, Bases structured query, wikilink expansion, and deep-read of anchored sections in long files. It stops at the first clean hit and tells you which step resolved it.

For complex multi-hop queries, add "walk the cascade" to make the multi-step retrieval explicit:

> "Walk the cascade: how does Susana's role connect to the Day 1 IT workstream?"

Claude will state the route at the top of its response (e.g., "Route D — no temporal signal. Walking Step 0 → 1 → 1.5 → 2 → 3.") and show its reasoning at each step.

If Claude says `Confidence: low — [reason]`, retrieval was thin — only one step fired or a single file without cross-zone corroboration. The answer may be right, but treat it as a lead to verify, not a confirmed fact.

---

## Ingest a source document

Drop a file into `00 Inbox/_drop/`:

```
00 Inbox/_drop/report.pdf
00 Inbox/_drop/presentation.pptx
00 Inbox/_drop/data-extract.xlsx
```

The ingestion pipeline (`ingest.py`) picks it up, extracts content into `00 Inbox/YYYY-MM-DD-<slug>.md` with structured frontmatter, moves the original to `99 Workspace/_originals/`, and appends a line to `_ingestion_log.md`. Supported formats: PDF, DOCX, PPTX, XLSX, HTML, plain text, images, markdown.

For immediate ingestion without the drop zone: "Ingest this document and add it to 50 Sources/" — Claude runs the pipeline inline and proposes the target note.

The scheduled task `vault-ingestion` processes the drop zone nightly. If you need it now: `/kb-curator audit` will notice unprocessed files and offer to run the pipeline.

---

## Run KB health audit

```
/kb-curator audit
```

Surfaces: orphan notes (no inbound wikilinks), stale citations (linked notes with `is_latest_version: false`), contradictions (two notes with conflicting claims about the same entity), and oversized log files. Each finding comes with a proposed action — Claude asks for approval before acting on any of them.

For targeted audits:
- `/kb-curator lint-orphans` — orphans only
- `/kb-curator lint-stale` — staleness only
- `/kb-curator lint-contradictions` — contradiction detection only

---

## Promote a draft to a typed zone

Once a note in `00 Inbox/` or `99 Workspace/` has decision-relevant content:

```
/promote
```

Claude runs the P-10 quality filter (3 questions: Is this note complete enough to be useful 6 months from now? Does it have the right frontmatter? Is there already a canonical home for this content?), proposes a target zone (`10 People/`, `30 Projects/`, `50 Sources/`, `70 Decisions/`, etc.), and asks for your approval before moving anything. The write is logged to `_auto_writes.md` via the audit chain.

You can also trigger promotion inline: "Promote this note to 70 Decisions/" and Claude will run the filter and ask for confirmation.

---

## Run the retrieval eval

```
/vault-eval
```

Runs the 33-question retrieval eval against your vault. Questions span 6 dimensions:

- **S** — semantic retrieval (does Smart Connections surface the right note?)
- **X** — cross-zone retrieval (does the cascade cross folder boundaries correctly?)
- **T** — temporal routing (does the cascade pick the right route for time-anchored queries?)
- **MH** — multi-hop (does PPR + link-expand resolve two-entity questions?)
- **CAL** — calibrated refusal (does Claude say "Confidence: low" or REFUSE when it should?)
- **F** — faithfulness (are answers grounded in the retrieved text, not hallucinated?)

Expect ~30 minutes for a full run. Results go to `99 Workspace/_eval_baseline_YYYY-MM-DD.md`. Run monthly or after any structural change to the cascade. The eval banner at session start fires if the last baseline is >30 days old.

---

## Supersede an outdated source

When a new document replaces an old one: "This Q2 report supersedes the Q1 analysis in 50 Sources/."

Claude runs a semantic sweep to find claims in other notes that cite or depend on the superseded document, proposes edits, and asks for approval on each. It updates `is_latest_version: false` on the old note and adds a `superseded_by:` pointer. Both sides of the version chain are preserved — no deletes.

---

## Session close

"Close the session, update handoff" — Claude writes the session handoff to `99 Workspace/_session_handoff.md` (and archives the previous one to `_session_handoff_archive/`), updates `_hot.md` with the orientation summary for next session, logs any pending writes, and updates the daily note. If the handoff exceeds 15 KB on the third consecutive session, Claude compresses it before writing.

You can also run `/hot` at session end to just refresh the hot-cache without writing a full handoff.

---

## Build a session plan

```
/plan-builder
```

Claude interviews you (goals, constraints, session count, infographic style) and generates an HTML session plan with a visual progress tracker. Plans live in `99 Workspace/_plan_*.html`. The plans index at `_plans_index.md` lists all plans with title, path, and session count. The active plan's Up Next card is loaded at session bootstrap (P-5 step 4.5).

---

## Autoresearch loop (advanced)

The autoresearch loop runs overnight and self-improves the retrieval cascade. It hill-climbs on the eval score by iterating over the cascade's editable surface — P-rule thresholds, rerank parameters, step-ordering heuristics — and surfaces a diff for your approval.

First run: after 90 days of production use (you need a meaningful question history for the hill-climb to have signal). Trigger manually: "Run the autoresearch loop against last month's eval baseline." Claude will flag if the vault isn't mature enough to run it usefully yet.

Full details and the stopping criterion (20 non-improving iterations or perfect score): see ARCHITECTURE.md.

---

## Tips

- **Ask "why did you retrieve that?"** after any cascade response — Claude will explain which step fired and why, which helps you tune the P-rules.
- **`_index.md` is Claude's map.** If it's stale (>1 day old), regenerate it: `python3 "90 System/_build_index.py" --root <vault>`. The cascade's Step 0 reads this file first.
- **Bases are the structured layer.** If semantic search is degraded or rebuilding, Bases queries (Step 2) still work — filtered by frontmatter, sorted by last-touched. A partially working cascade is still useful.
- **The audit chain is forensic.** `python3 _audit_chain.py verify --json` validates every write since the key was generated. Run it if you suspect a write was corrupted or back-dated.
