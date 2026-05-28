# [PROJECT_NAME] override: This file is a PROJECT-SPECIFIC IMPLEMENTATION of the
# canonical ingestion-pipeline-discipline template.
# When filling in a new project, replace all [PROJECT_*] placeholders and remove
# these comment lines.
# Reference implementation: Galp Vault (.claude/rules/ingestion-pipeline-discipline.md)
# Do NOT align a filled project file back to this template — keep project-specific values.

---
paths:
  - "[PROJECT_DROP_ZONE]/**/*"
  - "[PROJECT_ORIGINALS_DIR]/**/*"
  - "[PROJECT_QUARANTINE_DIR]/**/*"
  - "[PROJECT_PIPELINE_DIR]/**/*"
  - "[PROJECT_INGESTION_LOG]"
  - "[PROJECT_INGESTION_CONTRACT]"
  - "[PROJECT_PIPELINE_CODE_DIR]/**/*"
---

# Ingestion pipeline discipline

Source of truth: `[PROJECT_INGESTION_CONTRACT]` (P-[N] designation in
`[PROJECT_OPERATING_GUIDE]`).

The pipeline lifts files dropped in `[PROJECT_DROP_ZONE]` into vault-shaped
markdown under `[PROJECT_INBOX]` while preserving the binary original at
`[PROJECT_ORIGINALS_DIR]`. This rule is the operational kernel of P-[N] —
when this file and the contract conflict, the contract wins (facts) but this
file wins for behaviour (the rules file is what Claude loads first).

## Five load-bearing rules

### 1. Drop-zone semantics

`[PROJECT_DROP_ZONE]` is the **binary drop zone**. The operator drops files
there — PDFs, DOCX, PPTX, XLSX, HTML, MD, TXT, images. The pipeline picks
them up, extracts content, writes the ingested .md to `[PROJECT_INBOX]`, and
moves the binary to `[PROJECT_ORIGINALS_DIR]/[ORIG_NAMING_CONVENTION]`.

**Do NOT** treat `[PROJECT_DROP_ZONE]` as a quick-capture zone for
hand-edited markdown notes — that goes to `[PROJECT_INBOX]` directly per the
inbox-discipline rules. Drop-zone arrivals are processed by the pipeline, not
Claude directly.

**Do NOT** read from `[PROJECT_DROP_ZONE]` to answer a query — the file may be
mid-extraction. Read from the ingested .md in `[PROJECT_INBOX]` (or query the
manifest) instead.

### 2. Originals are read-only after write

Files in `[PROJECT_ORIGINALS_DIR]` are pipeline-managed. Once written, they
are **immutable** — never edit, never rename, never overwrite, never delete
except via explicit [PROJECT_OPERATOR]-approved cleanup.

If the original was wrong (corrupted, mis-dropped) or has a new version, the
correct path is:

1. Drop the new version into `[PROJECT_DROP_ZONE]`.
2. Let the pipeline run; supersession (contract §[SUPERSESSION_SECTION])
   handles the version chain.
3. Old version stays in `[PROJECT_ORIGINALS_DIR]` with
   `is_latest_version: false` on its companion .md — supersession does not
   delete originals.

Editing an original in place corrupts the SHA-256 integrity check (contract
§[INTEGRITY_SECTION]) and renders the manifest a lie. If you suspect
corruption, run the §[INTEGRITY_SECTION] verification — do NOT "fix" by
overwriting.

### 3. Manifest is the truth for dedup — three tiers

`[PROJECT_MANIFEST]` is the **authoritative dedup record**. One line per
ingested file with full SHA-256, text_sha256, supersession_stem (contract
§[SUPERSESSION_SECTION]), run_id, supersedes list, extracted_at timestamp.

The [ORIG_PREFIX_LENGTH]-character SHA prefix on the `[PROJECT_ORIGINALS_DIR]`
filename is **cosmetic** — disambiguates two files with identical original
names in the file picker. Do NOT use the prefix for dedup logic anywhere in
the code; collision risk above ~1500 files is too high. Query the manifest.

The dedup check runs in **three sequential tiers**. Each tier has a distinct
outcome — do not conflate them:

**Tier 1 — Binary identity (exact_duplicate).**
`manifest.has_sha(new_sha256)` — hit means the file is byte-for-byte identical
to a previously ingested binary. Action: quarantine to
`[PROJECT_QUARANTINE_DIR]` with reason `exact_duplicate`. No further tiers run.

**Tier 2 — Content identity (content_duplicate).**
`manifest.has_text_sha(new_text_sha256)` — hit means the extracted text is
identical after normalisation (whitespace-collapsed, line-ending-normalised,
lowercased), even if the binary differs (e.g. a re-exported PDF with updated
metadata, or different compression). Action: quarantine to
`[PROJECT_QUARANTINE_DIR]` with reason `content_duplicate`. The original binary
is still written to `[PROJECT_ORIGINALS_DIR]` (it is not identical at binary
level) but the ingested .md is not written — the content is already captured.
The log entry includes both the new sha256 and the matching existing md_path
for traceability. No further tiers run.

**Tier 3 — Semantic proximity (soft warning only).**
`mcp__smart-connections__lookup` top-3 nearest by cosine similarity — a hit at
≥ [SEMANTIC_DEDUP_THRESHOLD] means the document is *similar* but not identical.
Action: **NEVER quarantine.** Ingest proceeds to commit. The semantic_neighbors
are written to `pipeline.semantic_neighbors` and high-similarity matches
(≥ [SEMANTIC_DEDUP_THRESHOLD]) surface as soft duplicate candidates in
`[PROJECT_SUPERSESSION_QUEUE]`. See contract §[SEMANTIC_DEDUP_SECTION] for the
locked posture — this tier must not be silently escalated to blocking.

**Summary table:**

| Tier | Match type | Manifest query | Action |
|------|-----------|----------------|--------|
| 1 | Binary SHA-256 match | `has_sha()` | Quarantine (exact_duplicate) |
| 2 | Text SHA-256 match | `has_text_sha()` | Quarantine (content_duplicate) |
| 3 | Semantic score ≥ [SEMANTIC_DEDUP_THRESHOLD] | Smart Connections lookup | Soft warning only; ingest proceeds |

If `[PROJECT_MANIFEST]` is corrupted, the pipeline runs in
`--rebuild-manifest` mode: walks `[PROJECT_ORIGINALS_DIR]`, recomputes SHA-256s
and text_sha256s, queries each `.md` in `[PROJECT_INBOX]` + typed zones for
matching `pipeline.sha256:` and `pipeline.text_sha256:`, and reconstructs the
manifest. Slow, idempotent, non-destructive. Never auto-runs.

### 4. Frontmatter namespacing — user fields always win

Per contract §[NS_SECTION], pipeline-only fields live under `pipeline:`; user
fields (title, source_file, original_path, file_type, extracted_at,
page_count, type, bitemporal fields, plus any project-specific auxiliary
fields) stay top-level.

**On collision** (a `.md` file in `[PROJECT_DROP_ZONE]` arrives with existing
user frontmatter): user values at top-level are **never overwritten** by the
pipeline. Pipeline-computed equivalents are suppressed or moved under
`pipeline:`. Pipeline namespace is regenerated fresh every run — any user edit
inside `pipeline:` is overwritten with a `pipeline.warnings:
["user_edit_in_pipeline_ns"]` flag and a HARD ALERT.

**Re-ingest of an already-ingested file** (detected by
`pipeline.provenance: ingestion-pipeline` already present) is refused: file
moved to `[PROJECT_QUARANTINE_DIR]` with a log entry. This is the early-exit
dedup gate.

### 5. Supersession is auto-detected but never auto-applied

Per contract §[SUPERSESSION_SECTION], when the pipeline detects a stem-strip
match within the last [PROJECT_SUPERSESSION_WINDOW] days, it:

- Writes the NEW .md with `is_latest_version: true` and
  `pipeline.supersedes: [<prior_shas>]`.
- Queues the PRIOR .md(s) for `is_latest_version: false` +
  `pipeline.superseded_by:` update in `[PROJECT_SUPERSESSION_QUEUE]`.
- Surfaces a HARD ALERT on next session bootstrap.

**The demotion of prior versions never runs automatically.** The operator sees
the queue, approves (or amends — e.g. demotes the supersession to
"side-by-side variant"), and runs `--apply-queue` to batch the edits. This is
the trigger-only boundary on what would otherwise be a silent structural edit
to typed zones / `[PROJECT_INBOX]`.

Long-window matches (>[PROJECT_SUPERSESSION_WINDOW] days) are reported but
never auto-queued — the operator decides manually.

## What lives where (recap)

| Path | Auto-write? | Purpose |
|------|-------------|---------|
| `[PROJECT_DROP_ZONE]` | Yes (pipeline + operator) | Binary drop zone |
| `[PROJECT_INBOX]/<date>-<slug>.md` | Yes (pipeline) | Ingested .md output |
| `[PROJECT_ORIGINALS_DIR]/[ORIG_NAMING_CONVENTION]` | Yes (pipeline, write-once) | Binary original, read-only after write |
| `[PROJECT_QUARANTINE_DIR]` | Yes (pipeline) | Dedup-hits, re-ingest attempts, extractor failures |
| `[PROJECT_PIPELINE_STAGING]` | Yes (pipeline) | In-flight extraction; cleaned on commit |
| `[PROJECT_MANIFEST]` | Append-only (pipeline) | Truth-for-dedup |
| `[PROJECT_INGESTION_LOG]` | Append-only (pipeline) | Human-readable run log |
| `[PROJECT_SUPERSESSION_QUEUE]` | Yes (pipeline) | Awaits operator approval before --apply-queue |
| `[PROJECT_INGESTION_CONTRACT]` | Trigger-only | The spec |
| `[PROJECT_PIPELINE_CODE_DIR]` | Trigger-only | Code |

Anything not in this table is **outside the pipeline's scope**. A run that
writes to typed zones (people, companies, projects, decisions, etc.) violates
the autonomy boundary and must fail-fast.

## Cross-references

- `[PROJECT_INGESTION_CONTRACT]` — the spec (namespacing, supersession,
  retrieval, discipline sections)
- `[PROJECT_OPERATING_GUIDE]` — P-[N] designation
- `[PROJECT_INBOX_RULE]` — the parent rule covering `[PROJECT_INBOX]`; this
  file extends it for binaries
- `[PROJECT_AUTO_WRITE_RULE]` — the auto-write logging contract; pipeline runs
  log per the standard format

## Why this rule exists

The ingestion pipeline is typically the first vault subsystem that
auto-writes binaries (not just markdown) and that auto-recomputes frontmatter
on existing .md files. Both are higher blast-radius than the prior auto-write
zones. The autonomy boundary rule (P-7 or equivalent) alone is too coarse —
it says "the workspace output zone is auto-write OK" but doesn't speak to
"originals are read-only after write" or "user fields win on collision". This
rule is the operational kernel that fills those gaps.

---

## [PROJECT_*] Placeholder reference

| Placeholder | Galp Vault value | What to fill |
|-------------|-----------------|--------------|
| `[PROJECT_NAME]` | Galp Vault | Your project/vault name |
| `[PROJECT_DROP_ZONE]` | `00 Inbox/_drop/` | Drop zone path |
| `[PROJECT_ORIGINALS_DIR]` | `99 Workspace/_originals/` | Originals storage path |
| `[PROJECT_QUARANTINE_DIR]` | `99 Workspace/_inbox_quarantine/` | Quarantine path |
| `[PROJECT_PIPELINE_DIR]` | `99 Workspace/_ingestion_pipeline/` | Pipeline state dir |
| `[PROJECT_PIPELINE_CODE_DIR]` | `90 System/_ingestion_pipeline/` | Pipeline code dir |
| `[PROJECT_INGESTION_LOG]` | `99 Workspace/_ingestion_log.md` | Run log file |
| `[PROJECT_INGESTION_CONTRACT]` | `90 System/_ingestion_contract.md` | The spec file |
| `[PROJECT_OPERATING_GUIDE]` | `90 System/_operating_guide.md` | Operating guide file |
| `[PROJECT_INBOX]` | `00 Inbox/` | Inbox directory |
| `[PROJECT_INBOX_RULE]` | `.claude/rules/inbox-discipline.md` | Inbox rule file |
| `[PROJECT_AUTO_WRITE_RULE]` | `.claude/rules/auto-write-discipline.md` | Auto-write rule file |
| `[PROJECT_MANIFEST]` | `99 Workspace/_ingestion_pipeline/_manifest.jsonl` | Manifest file |
| `[PROJECT_PIPELINE_STAGING]` | `99 Workspace/_ingestion_pipeline/_staging/<run_id>/` | Staging dir |
| `[PROJECT_SUPERSESSION_QUEUE]` | `99 Workspace/_ingestion_supersession_queue.md` | Supersession queue |
| `[PROJECT_OPERATOR]` | Ricardo | Project operator name/role |
| `[PROJECT_SUPERSESSION_WINDOW]` | 90 | Supersession detection window in days |
| `[ORIG_NAMING_CONVENTION]` | `<sha[:8]>_<original_name>` | Originals filename scheme |
| `[ORIG_PREFIX_LENGTH]` | 8 | SHA prefix length in originals filename |
| `[SUPERSESSION_SECTION]` | §7 | Contract section number for supersession |
| `[SEMANTIC_DEDUP_SECTION]` | §7.5 | Contract section for the locked semantic-dedup (soft-warning) posture |
| `[SEMANTIC_DEDUP_THRESHOLD]` | 0.80 | Cosine-similarity threshold for Tier 3 soft duplicate candidates |
| `[INTEGRITY_SECTION]` | §8.3 | Contract section number for SHA verification |
| `[NS_SECTION]` | §5 | Contract section for frontmatter namespacing |
| `[N]` (in P-[N]) | 14 | P-rule number for the ingestion pipeline |
