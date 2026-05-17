# kb-curator propose-cleanup mode

Generate a full P-10 cleanup proposal — promotions to curated zones AND archive moves. **PROPOSAL ONLY** — no files move until the user explicitly approves with the phrase `approve cleanup proposal`.

The `propose-cleanup` mode is also the canonical implementation of the **"run cleanup"** P-9 manual trigger from `cowork_outputs/_guide_context_engineering.md`.

## Invocation

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/kb-curator/scripts/curator.py propose-cleanup
```

Override the doneness threshold (default 14 days) per project:

```bash
COWORK_PROMOTE_AGE_DAYS=7 python3 ${CLAUDE_PLUGIN_ROOT}/skills/kb-curator/scripts/curator.py propose-cleanup
```

## Vocabulary alignment with cowork-preparation

This mode reads frontmatter `type:` and `cadence:` using the canonical vocabulary enforced by `cowork_outputs/_lint_frontmatter.py`. Routing decisions only fire on values from that vocabulary. Files with non-canonical types are surfaced under "Needs review" rather than guessed at.

**Canonical types** (lint's `KNOWN_TYPES`): `guide, state, handoff, eval, strategic, battleplan, meeting_debrief, debrief, audit, concept_note, analysis, data_companion, proposal, review, extraction, log, cleanup-log, archive, other`.

**Canonical cadences** (lint's `KNOWN_CADENCES`): `stable, weekly, monthly, event-driven, per-session, continuous, append-only, monthly-or-on-structural-change`.

## What it identifies (seven categories, in order)

1. **Promotions to curated zones** — markdown whose frontmatter `type:` is in `PROMOTION_MAP` and that passes the doneness gate.

   | `type:` value                                  | Destination                          |
   |------------------------------------------------|--------------------------------------|
   | `meeting_debrief`, `debrief`                   | `05_Knowledge_Base/debriefs/`        |
   | `battleplan`                                   | `05_Knowledge_Base/battleplans/`     |
   | `audit`                                        | `05_Knowledge_Base/audits/`          |
   | `analysis`, `strategic`                        | `05_Knowledge_Base/analysis/`        |
   | `extraction`, `concept_note`, `data_companion` | `05_Knowledge_Base/extractions/`     |

   When frontmatter is absent or has no `type:`, filename patterns are a fallback: `meeting_debrief_*`, `battleplan_*`, `audit_*`, and the P-10 audit-extraction pattern `^\d{4}_\d{3}_.*\.md$`.

2. **Polished binary deliverables** — `.docx`, `.pptx`, `.xlsx`, `.pdf`, `.html` in `cowork_outputs/` older than the threshold → `02_Final_Deliverables/`. Excludes anything matching a template prefix (see 2a).

2a. **Templates / brand assets** — any extension whose filename starts with `template_`, `master_`, or `brand_` → `06_Templates/`. Per cowork-preparation P-10 ("Template / brand asset"). Note: `template` is intentionally NOT a recognised `type:` value (it isn't in lint vocabulary); templates are identified by filename and zone.

3. **Quarterly state archives** — files matching `_*_archive_*.md` directly under `cowork_outputs/` → `_archive/state_archives/`.

4. **Superseded version pairs** — `*_v\d+\.md` where a higher version exists with the same stem → `_archive/superseded/`. Superseded files are excluded from the promotion section even if they'd otherwise pass the gate.

5. **In-flight (recognised type, not yet ready)** — files with a recognised `type:` or done-prefix that fail the doneness gate. Listed but not proposed for move.

6. **Needs review (no `type:`, unrecognised type)** — files that can't be routed mechanically. Listed under their own section so the user can add frontmatter or run `_retrofit_frontmatter.py --apply`.

## The doneness gate

The signal that a file is "done" is **age**, not cadence label. cowork-preparation's retrofit assigns `cadence: event-driven` to meeting debriefs by default; a debrief with no follow-up events for 14+ days is exactly what a finished debrief looks like. So `event-driven` files are promotable when old enough — same as `stable` or `monthly`.

A file is promoted when **all** of:

- Frontmatter `cadence:` is in **PROMOTABLE_CADENCES** (`stable, weekly, monthly, event-driven, monthly-or-on-structural-change`), OR cadence is unset/empty and the filename matches a done-pattern.
- `last_updated` (frontmatter) or filesystem mtime is at least `THRESH_PROMOTE_AGE_DAYS` days old (default 14, override via `COWORK_PROMOTE_AGE_DAYS`).
- Not pinned, not `archived_reference: true`, not in `NON_PROMOTABLE_TYPES` (`guide, state, handoff, eval, log, cleanup-log, archive`).

Vetoes:
- `archived_reference: true` blocks always.
- Cadence in **OPERATIONAL_CADENCES** (`per-session, continuous, append-only`) blocks always — these belong on pinned files; on a non-pinned file they signal misconfiguration, surfaced in section 5.
- Age below threshold blocks (surfaced in section 5).

## Cross-reference column

Every promotion row in the proposal table includes a `Cross-refs` column listing non-pinned `.md` files that mention the candidate by name (substring match, project-wide). When the user approves, the move is bundled with a reference rewrite for each listed file in the same batch — per the P-10 cross-reference safeguard.

The grep skips the same directories as cowork-preparation's `_build_index.py` and `_lint_frontmatter.py`: `01_Personal_HR/`, `04_Meeting_Recordings/`, `.git/`, `node_modules/`, `__pycache__/`. HR is explicitly out of scope per the cowork-preparation contract.

Refs in pinned files (handoff, state, index, guides, eval, audit reports, prior cleanup proposals) are not listed; they get rewritten by their own update flow.

## Output

`cowork_outputs/_cleanup_proposal_YYYY-MM-DD.md` — seven sections:

1. Promotions to curated zones (table with cross-refs)
2. Polished deliverables → `02_Final_Deliverables/`
2a. Templates / brand assets → `06_Templates/`
3. State archives → `_archive/state_archives/`
4. Superseded versions → `_archive/superseded/`
5. In-flight — recognised type, not yet ready
6. Needs review — no `type:` or unrecognised type

Plus a "files staying put (pinned)" section and the approval phrase.

## Post-approval execution (not done by this script)

When the user approves with `approve cleanup proposal`, the executor (Claude in conversation) MUST:

1. Execute moves in the order listed.
2. Before each move, grep the project for the old filename and update any references in non-pinned files in the same batch.
3. Append one entry to `cowork_outputs/_cleanup_log.md` per the format in cowork-preparation's `_cleanup_log.md.template`:

   ```
   ## YYYY-MM-DD — Cleanup batch N
   **Proposal file:** _cleanup_proposal_YYYY-MM-DD.md
   **Approved by:** <user_first_name> on YYYY-MM-DD
   **Files moved:** N
   **Cross-references updated:** N
   ### Moves
   | From | To | Rationale |
   ...
   ```

4. Re-run `cowork_outputs/_build_index.py` so the global index reflects the new zones.
5. Re-run the retrieval eval if monthly cadence is due.

## What to report

After the run, report to the user:

- **Total moves proposed**, broken down: `N knowledge, M deliverables, K templates, X archives, Y superseded`.
- **In-flight count** — informational, not a problem.
- **Needs-review count** — surface as the only actual blocker.
- The exact phrase to trigger execution: **`approve cleanup proposal`**.
- That line-level edits to the proposal file before approval are honoured (delete the rows you don't want moved).

The script's stdout is the source of truth for counts. Do not re-count by reading the proposal file.

## Hard guardrails

- DOES NOT execute any move. Only writes the proposal file.
- Pinned files are never proposed for move: state file (discovered by `type: state`), handoff, all `_guide_*.md`, all `_eval_*.md`, `_auto_writes.md`, `_cleanup_log.md`, `_retrofit_log.md`, `_index.md`, `_index_*.md` shards, `_build_index.py`, `_lint_frontmatter.py`, `_retrofit_frontmatter.py`, `_run_retrieval_eval.py`. Plus runtime artefacts: `_audit_*.md`, `_cleanup_proposal_*.md`, `_log_rotation_proposal_*.md`.
- `archived_reference: true` files stay where they are.
- Cadence in `OPERATIONAL_CADENCES` blocks promotion.
- No deletes ever — destinations are always inside the project (`05_Knowledge_Base/`, `02_Final_Deliverables/`, `06_Templates/`, `_archive/`).
- Approval is line-level — the user can edit the proposal file before approving.
