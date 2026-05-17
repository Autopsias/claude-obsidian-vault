# kb-curator propose-cleanup — OBSIDIAN substrate

Generate a full P-10 promotion proposal for a Johnny-Decimal Obsidian vault.
**PROPOSAL ONLY** — no files move until the user explicitly approves with
`approve cleanup proposal`.

This file is loaded by kb-curator when `detect_substrate.py` returns `OBSIDIAN`.
For FLAT (cowork-preparation) routing, see `propose-cleanup-flat.md`.

## Invocation

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/kb-curator/scripts/curator.py propose-cleanup
```

The orchestrator calls `detect_substrate.py` after resolving the root. When
OBSIDIAN substrate is detected it prints the path to this file and exits 0 —
signalling Claude to read this reference and follow its routing table,
doneness gate, and pinned-files list to generate
`99 Workspace/_cleanup_proposal_YYYY-MM-DD.md`.

There is no standalone `propose_cleanup_obsidian.py` script; the routing
logic is entirely implemented by Claude following this document.

## Vault write zones (auto-write OK)

Per the vault's `auto-write-discipline.md` (`.claude/rules/`), three zones
accept writes without per-file approval:

| Zone | Path | Purpose |
|------|------|---------|
| Inbox | `00 Inbox/` | Triage holding area |
| Daily | `80 Daily/` | Daily notes (session summaries, ad-hoc) |
| Workspace | `99 Workspace/` | Working zone — all session outputs land here |

`propose-cleanup` reads only from `99 Workspace/` (the source of candidates).
All other typed zones require explicit user authorisation (trigger-only).

## Routing — type → Johnny-Decimal zone

Routing is driven by frontmatter `type:` (canonical) with filename pattern as
fallback. The vocabulary mirrors the vault's Bases structure.

**Markdown — by frontmatter `type:`:**

| `type:` value | Destination zone | Zone number |
|---------------|-----------------|-------------|
| `person`, `contact` | `10 People/` | 10 |
| `company`, `organisation`, `counterparty` | `20 Companies/` | 20 |
| `project`, `battleplan`, `briefing` | `30 Projects/` | 30 |
| `meeting_debrief`, `debrief`, `meeting` | `40 Meetings/` | 40 |
| `source`, `strategic`, `analysis`, `sixpager`, `deepdive`, `extraction`, `concept_note`, `data_companion`, `prd`, `review` | `50 Sources/` | 50 |
| `concept`, `framework`, `definition` | `60 Concepts/` | 60 |
| `decision`, `audit`, `adversarial_review`, `feedback_pack` | `70 Decisions/` | 70 |
| `deliverable` | `50 Sources/` (default) or `30 Projects/` if project-scoped | 50 or 30 |

**Markdown — filename pattern fallback (when `type:` is absent or unrouted):**

| Filename pattern | Destination |
|-----------------|-------------|
| `meeting_debrief_*.md`, `debrief_*.md` | `40 Meetings/` |
| `battleplan_*.md`, `briefing_*.md` | `30 Projects/` |
| `decision_*.md`, `audit_*.md` | `70 Decisions/` |
| `^\d{4}_\d{3}_.*\.md$` (P-10 audit-extraction pattern) | `70 Decisions/` |

**Binary and non-markdown files:**

| File | Destination |
|------|-------------|
| `.docx`, `.pptx`, `.xlsx`, `.pdf`, `.html` (deliverable) | `50 Sources/` or zone matching content |
| `template_*`, `master_*`, `brand_*` (any extension) | `99 Workspace/` (keep — vault has no 06_Templates equivalent) |

## Archive routing (OBSIDIAN)

Per vault policy `70 Decisions/archive_policy_2026-06-08.md` (PO-01), all
archive targets use a **single root archive** mirroring the typed-zone structure.
There is NO per-zone `<zone>/_archive/` subfolder.

| Source pattern | Archive destination |
|---------------|-------------------|
| `_*_archive_*.md` (state archive marker in workspace) | `_archive/99 Workspace/` |
| Superseded versions (`*_v\d+\.md`, lower version exists) | `_archive/<zone>/superseded/` |
| Quality-filter rejects (three-question filter → archive) | `_archive/<original-zone>/` |

Add archival frontmatter to every archived file:
```yaml
archived_date: YYYY-MM-DD
archived_from: 99 Workspace/<filename>
archived_reason: <one line>
```

Preserve any existing bitemporal frontmatter (`document_date`, `is_latest_version`).

## The doneness gate (OBSIDIAN)

Same logic as FLAT, adapted for vault file patterns:

A file in `99 Workspace/` is a promotion candidate when **all** of:

- Frontmatter `cadence:` is in PROMOTABLE_CADENCES (`stable, weekly, monthly,
  event-driven, monthly-or-on-structural-change`), OR cadence is unset/empty
  AND filename matches a done pattern.
- `last_updated` or filesystem mtime is ≥ `THRESH_PROMOTE_AGE_DAYS` days old
  (default 14; override via `COWORK_PROMOTE_AGE_DAYS`).
- Not pinned (see pinned list below).
- `type:` not in NON_PROMOTABLE_TYPES (`guide, state, handoff, eval, log,
  cleanup-log, archive`).

**Vetoes:**
- `archived_reference: true` — blocks always.
- Cadence in OPERATIONAL_CADENCES (`per-session, continuous, append-only`) — blocks always.
- Age below threshold — surfaced as in-flight.

## Promotion quality filter (P-10 — OBSIDIAN)

Apply the three-question filter from `90 System/_promotion_quality_guide.md`
to each proposed row before presenting to the user:

1. **Is this still true?** (vs. `30 Projects/Peninsula.md` + recent debriefs in `40 Meetings/`)
2. **Will this affect tomorrow's decisions?**
3. **Is this encoded elsewhere?** (duplicate-check across all typed zones)

Default outcome: "archive instead" or "skip — duplicate". Promotion is the
exception. A proposal of 20 rows collapsing to 4 actual promotions is healthy.

For high-stakes content (audits, strategic analyses), spawn a verification
sub-agent before presenting the proposal — independent read against current
vault state, returns pass/fail with citations.

## Pinned files — never proposed for move

These files live permanently in `99 Workspace/` or vault root and are excluded
from every proposal:

- `_session_handoff.md` and all `_session_handoff_archive/` contents
- `_auto_writes.md`, `_cleanup_log.md`, `_reflection_log.md`, `_lessons.md`
- `_plans_index.md` and all `_plan_*.html` plan dashboards
- `memory/` directory (auto-memory files)
- `_skill_packages/` directory
- All `_audit_*.md` and `_cleanup_proposal_*.md` runtime artefacts
- `CLAUDE.md` (vault root — trigger-only per `auto-write-discipline.md`)

## Cross-reference column

Every promotion row includes a `Cross-refs` column: non-pinned `.md` files
in `99 Workspace/` and typed zones that mention the candidate by filename.
When approved, moves are bundled with reference rewrites in the same batch.

The grep skips: `.obsidian/`, `.smart-env/`, `.git/`, `.claude/`, `node_modules/`.

## Output

`99 Workspace/_cleanup_proposal_YYYY-MM-DD.md` — sections:

1. Promotions to typed zones (table with zone and cross-refs)
2. Archive moves (state archives + superseded)
3. Quality-filter rejects (with reason: "archive instead" / "duplicate")
4. In-flight — recognised type, not yet ready (below age threshold)
5. Needs review — no `type:` or unrouted type

Plus pinned-files summary and approval phrase.

## Post-approval execution

When the user approves with `approve cleanup proposal`:

1. Execute moves in the listed order.
2. Before each move, grep `99 Workspace/` and typed zones for the old filename
   and update references in non-pinned files (same batch).
3. Append to `99 Workspace/_cleanup_log.md`:
   ```
   ## YYYY-MM-DD — Cleanup batch N
   **Proposal file:** _cleanup_proposal_YYYY-MM-DD.md
   **Approved by:** Ricardo on YYYY-MM-DD
   **Files moved:** N
   **Cross-references updated:** N
   ### Moves
   | From | To | Rationale |
   ...
   ```
4. Append each move to `99 Workspace/_auto_writes.md` per auto-write discipline:
   `YYYY-MM-DD | rename | <from> → <to> | P-10 promote — <reason>`
5. Do NOT re-run `_build_index.py` (that's a FLAT tool). In OBSIDIAN mode,
   Smart Connections re-indexes on next vault open automatically.

## What to report

After generating the proposal:

- **Total promotions proposed**, broken down by zone: `N to 40 Meetings/, M to 70 Decisions/, …`
- **Archive moves** — informational
- **In-flight count** — informational
- **Needs-review count** — the only actual blocker
- Exact approval phrase: **`approve cleanup proposal`**
- Reminder that line-level edits to the proposal file before approval are honoured

## Hard guardrails

- DOES NOT execute any move. Only writes the proposal to `99 Workspace/`.
- Pinned files are never proposed (see list above).
- No deletes — destinations are always typed zones or `_archive/`.
- No edits to `CLAUDE.md`, `30 Projects/Peninsula.md`, typed-zone files, or
  any file outside `99 Workspace/` without explicit user trigger.
- Archive routes to single root `_archive/<zone>/` — never `<zone>/_archive/`.
- Approval is line-level: the user can edit the proposal before approving.
