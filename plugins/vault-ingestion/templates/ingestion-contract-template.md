---
name: Ingestion Frontmatter Contract
description: Canonical contract for the v2 ingestion pipeline. Defines the namespaced frontmatter shape pipeline runs write to ingested .md files, the user / pipeline collision policy (user wins), and the supersession-detection algorithm including the stem-strip regex. Code in `90 System/_ingestion_pipeline/` reads this file as the spec.
type: contract
provenance: "S01 (Foundations) of `_plan_ingestion_pipeline_v2_2026-05-13.html`. Finalises the STUB locked in S00. STUB is preserved verbatim under §1–§4 (the ADOPTed inheritance boundary); the namespacing rule, supersession algorithm, retrieval pattern, and v2 fields are added in §5–§9. STUB cross-reference: `99 Workspace/_audit_2026-05-13_prior_ingestion.md` for the full reconciliation of prior plans."
document_date: 2026-05-13
is_latest_version: true
status: FINAL — supersedes the S00 STUB; code-loadable from S02 onwards
cadence: monthly-or-on-structural-change
last_updated: 2026-05-17  # AL-04 (Frontier Adoption S08): added §12 link_candidates contract + pipeline.namespace extension (language + link_candidates) + pipeline writes _ingestion_log.md candidate counts
---

# Ingestion Frontmatter Contract

**Status.** FINAL. This file is the single source of truth for the
namespaced frontmatter shape, the user/pipeline collision policy, and
the supersession-detection algorithm. Code under
`90 System/_ingestion_pipeline/` (from S02 onwards) reads this file as
the spec — changes here are structural and must update `last_updated:`
and surface in the next handoff.

**Two-layer organisation.** §1–§4 are the **inheritance boundary** —
the field set the S00 audit decided to ADOPT from prior plans
(`_plan_galp_content_ingestion_2026-05-10.html` +
`_plan_galp_delta_ingestion_2026-05-11.html`), locked verbatim from
the STUB so the inheritance trail stays auditable. §5–§9 are the
**v2 invention layer** — the namespacing rule, supersession
algorithm, retrieval pattern, MIGRATE deltas, and v2-only fields.

**Cross-references.**
- `99 Workspace/_audit_2026-05-13_prior_ingestion.md` — S00 audit; Section 5 shows the field set as actually written to disk by prior runs; Section 6 lists ADOPT / MIGRATE / RETIRE per artefact.
- `99 Workspace/_plan_ingestion_pipeline_v2_2026-05-13.html` — v2 plan; this contract is the F-02 deliverable.
- `99 Workspace/_plan_galp_content_ingestion_2026-05-10.html` — completed prior plan; §1–§4 reverse-engineered from its outputs.
- `.claude/rules/ingestion-pipeline-discipline.md` — operational rule that gates writes against this contract (P-14).
- `90 System/_operating_guide.md` — P-14 designation; this contract is the load-bearing reference.
- `99 Workspace/_archive/prior_ingestion/ingestion_configs/*.yaml` — original `metadata_fields` declarations; six-field baseline lifted from here.

---

## 1. Baseline Field Set (ADOPT — locked in S00)

These six fields are written by every successful prior ingestion run.
Confirmed by sampling three ingested files in `50 Sources/pdfs/strategic/`
and cross-referencing the `metadata_fields` declarations across all
seven retired YAML configs. v2 inherits the field NAMES; the FORMAT for
two of them (`original_path`, `tags`) changes — see §6.

| Field | Type | Required | Source | Example |
|-------|------|----------|--------|---------|
| `title` | string | yes | derived from filename or first-heading | `"Peninsula Shareholders Presentation 17 Apr 2026"` |
| `source_file` | string | yes | original filename, unchanged | `"260417_PNSL_Shareholders_Pres_vPreread01.pdf"` |
| `original_path` | string | yes | path to the binary original — **vault-relative in v2** (was absolute-legacy in v1) | `"99 Workspace/_originals/a1b2c3d4_260417_PNSL_Shareholders_Pres_vPreread01.pdf"` |
| `file_type` | string | yes | extension without dot — `pdf` / `docx` / `pptx` / `xlsx` / `html` / `md` / `txt` / `image` | `"pdf"` |
| `extracted_at` | ISO-8601 UTC | yes | timestamp of pipeline run | `"2026-05-11T01:07:08Z"` |
| `page_count` | int | yes (where applicable) | extractor output; 0 / null for non-paginated | `25` |

Pipeline RUNS write all six. Code MUST NOT skip a field by leaving it
absent — null is permitted where genuinely not applicable
(`page_count: null` for an image; `page_count: 0` for an empty PDF is
a different signal — the extractor produced zero pages, which is a
data-quality issue, not a missing-field issue).

## 2. Per-Type `type` Field (ADOPT — locked in S00)

Prior plans wrote a `type:` field distinguishing the document role
(not just the file extension). This is inherited as-is. Catalogue
observed across 277 ingested files:

| `type:` value | Used for |
|---------------|----------|
| `meeting-transcript` | DOCX from `04_Meeting_Recordings/transcripts/` |
| `pdf-source` | Strategic PDFs |
| `pdf-reference` | Reference / governance / cyber PDFs |
| `presentation` | PPTX |
| `spreadsheet` | XLSX |
| `deep-dive-report` | DOCX deep-dive reports |
| `working-document` | DOCX from cowork_outputs |
| `final-deliverable` | DOCX from `02_Final_Deliverables` |
| `html-deliverable` | HTML cowork outputs (delta plan) |
| `image-ocr` | NEW in v2 — image ingestion with Tesseract OCR output |
| `text-note` | NEW in v2 — raw `.txt` drop |

`type:` is a closed enum. v2 extends it (e.g. `image-ocr`, `text-note`)
but only by adding to this catalogue — never by silent free-form
assignment by the extractor. Any handler that needs a new `type:`
value must update this contract first.

## 3. Optional / Auxiliary Fields (ADOPT — locked in S00)

These fields are observed in prior outputs but not always present.
Pipeline writes them when the extractor produces them; absent otherwise.

| Field | Type | When | Example |
|-------|------|------|---------|
| `document_type` | string | when classifiable from filename or first page | `shareholder-presentation`, `red-flag-report`, `guidelines`, `strategy-deck` |
| `date` | YYYY-MM-DD | when extractable from filename or first page | `2026-04-17` |
| `slide_count` | int | PPTX only | `21` |
| `participants` | list[string] | meeting transcripts only | `["MJ", "JDMS", "Ricardo"]` |
| `meeting_date` | YYYY-MM-DD | meeting transcripts only | `2026-03-04` |
| `domain` | string | deep-dive reports only | `erp`, `m2c`, `hcm`, `ulysses`, `infrastructure`, `integration` |
| `key_data` | string | when the doc is the authoritative reference for a data table | `app-tier-assignments` |

## 4. Body Conventions (ADOPT — locked in S00)

Inherited from prior plans without modification:

```markdown
---
<frontmatter as above>
---
**Open original:** [[<source_file>]]

<extractor output begins here>
```

The `**Open original:** [[file]]` body link is mandatory. Together
with `original_path:` in frontmatter, it gives both human (clickable
in Obsidian / Cowork) and machine (queryable via Bases) access to the
source binary. Sample verified in
`50 Sources/pdfs/strategic/peninsula_shareholders_presentation_17_apr_2026.md`
and 9 spot-checks in ORIG-03 of the content-ingestion plan.

**Optional body blocks added by the pipeline.** From the LD series of
S03 (Next-Wave plan v2.1, 2026-05-16) the pipeline may append the
following body blocks AFTER the extractor output:

- **`## See also` block** — wikilinks to semantic neighbours with
  score ≥ 0.85, wrapped in idempotent re-render markers. Full contract
  at §7.5.1.
- **Wikilink enrichment** — first-mention catalogue links are
  woven into the body in place. Contract at §5 (`pipeline.tags`,
  `pipeline.links_enriched`, `pipeline.links_added`).

---

## 5. Namespacing rule — pipeline fields NEVER collide with user fields

**The load-bearing rule of the v2 contract.** Every field the pipeline
writes that did NOT exist as a user-level field in §1–§4 lives under
a `pipeline:` sub-mapping. Every field the pipeline writes that DID
exist as a user-level field in §1–§4 stays at top-level (those are
the legacy six + per-type enums + the optional set).

**Why two layers exist.** The §1–§4 fields were authored by prior
plans before namespacing was a concern. They are user-visible
(displayed in Bases, edited by Ricardo when correcting a title or
adding a date). Demoting them under `pipeline:` would break the 277
already-ingested files. So we accept the legacy split: the six
inherited fields stay at top-level; everything new the pipeline
writes is namespaced.

**Top-level (legacy, ADOPTed):** `title`, `source_file`,
`original_path`, `file_type`, `extracted_at`, `page_count`, `type`,
plus the §3 optional auxiliaries (`document_type`, `date`,
`slide_count`, `participants`, `meeting_date`, `domain`, `key_data`),
plus the §6.1 bitemporal pair (`document_date`,
`is_latest_version`) — required at top-level because Bases query
them.

**Namespaced under `pipeline:` (v2-only):**

```yaml
pipeline:
  run_id: 20260513T142233Z-7af9                    # supersession + recovery key
  sha256: 3f2a8b1c…ffull64hex                      # full SHA-256 of the binary original (not 8-char prefix per Codex H3)
  text_sha256: e3b0c44298fc1c14…fullhex            # SHA-256 of normalised extracted text: whitespace-collapsed, line-ending-normalised (\n), lowercased. Distinct from binary sha256 — two identical PDFs with different metadata produce the same text_sha256 but different sha256. Handlers MUST write it on every run; ManifestStore.has_text_sha() queries it for content-duplicate detection (Tier 2 dedup).
  extractor: pdfplumber@0.11.0                     # extractor binary + version
  staging_path: 90 System/_ingestion_pipeline/_staging/<run_id>/  # present only in-flight; removed on commit
  supersedes: ["a1b2c3d4…hashA", "9f8e7d6c…hashB"] # list of prior versions' SHA-256s (newest first)
  superseded_by: null                              # back-pointer; populated when a later version arrives
  manifest_offset: 4287                            # byte offset into _manifest.jsonl for this entry
  source_file_mtime: 2026-04-17T09:22:11Z          # mtime of the binary at ingest; null if unobtainable
  warnings: []                                     # extractor warnings; empty list if clean
  links_enriched: true                             # LD-02 — did enrich_links.py run successfully?
  links_added: 12                                  # LD-02 — count of NEW wikilinks woven into body this run
  see_also_added: true                             # LD-03 — was a "## See also" block appended?
  language: pt                                     # AL-05 — ISO 639-1 detected language ('pt' / 'en' / 'unknown')
  link_candidates:                                 # AL-04/AL-05 — Auto-linker proposals; see §12. Max 50 entries per source.
    - entity_id: "10 People/Susana Zumel Vara"
      matched_string: "Susana"
      confidence: "exact"                          # 'exact' (from _link_matcher.py — AL-03) | 'ner' (from spaCy NER — AL-05)
      offsets: [0, 6]                              # [start, end_exclusive] char offsets into the extracted body text
      proposed_wikilink: "[[Susana Zumel Vara]]"
    - entity_id: "20 Companies/Moeve"
      matched_string: "Moeve"
      confidence: "exact"
      offsets: [12, 17]
      proposed_wikilink: "[[Moeve]]"
```

**Collision rule.** If a `.md` file in `00 Inbox/_drop/` arrives with
existing user frontmatter (e.g. someone hand-edited tags, title, or
`document_date`), the pipeline:

1. Parses the existing frontmatter via `python-frontmatter`.
2. **Never overwrites a top-level field that has a non-null user
   value.** Pipeline-computed `title` is suppressed if the user
   already wrote one. Pipeline-computed `tags` are added to
   `pipeline.tags:`, never to top-level `tags:`. Pipeline-computed
   `document_date` is suppressed if user already wrote one.
3. **Always writes** the `pipeline:` namespace from scratch — that
   namespace is *the pipeline's* record, never user-edited; any user
   edit there is overwritten next run with a `warnings: ["user_edit_in_pipeline_ns"]`
   entry and a HARD ALERT at next session start.
4. **Refuses re-ingest** if `pipeline.provenance: ingestion-pipeline`
   is already present (early-exit per HT-01) — re-ingest of an
   already-ingested file goes to `99 Workspace/_inbox_quarantine/`
   with a one-line log entry. Re-ingest of a deliberately *new
   version* of an upstream doc is a different code path — see §7
   supersession.

**User fields always win on collision.** This is the asymmetric
default — user intent is sacred; pipeline output is recomputable.

**Tags merge example:**

```yaml
# Before user edit:
tags: [peninsula, pdf-source]              # written by pipeline at top-level via legacy compat

# After user adds 'urgent' to top-level:
tags: [peninsula, pdf-source, urgent]      # user-edited; pipeline never touches

# Next pipeline run computes tags fresh:
tags: [peninsula, pdf-source, urgent]      # UNCHANGED — user wins on top-level
pipeline:
  tags: [peninsula, pdf-source, moeve]     # pipeline writes here; freshly recomputed (moeve added)
```

The `enrich_links.py` script (ADOPTed from S00) MUST be updated to
write `pipeline.tags:` not top-level `tags:` (audit follow-up §8.5).
The S00 stub flagged this as the §5.2 MIGRATE; the operational fix
lands when S03 enrichment item runs.

## 6. MIGRATE deltas — reformats of inherited fields

These are NOT new fields. They reformat fields already in §1.

### 6.1 `original_path` → vault-relative

- **v1 wrote:** `"<YOUR_VAULT_PATH>/02_Final_Deliverables/file.pdf"`
- **v2 writes:** `"99 Workspace/_originals/a1b2c3d4_file.pdf"`

**Why MIGRATE.** Legacy `/Downloads/Galp/` freezes at T+30
(2026-06-08). Absolute paths become dangling. Vault-relative paths
survive the freeze and are portable across machines.

**Out-of-scope for v2.** Retro-rewriting the 277 existing files is a
separate session (flagged in audit Section 8.3 and Section 8 of this
contract — see §9 below).

### 6.2 Bitemporal pair carried at top-level (NOT namespaced)

`document_date` and `is_latest_version` were introduced by the
Bitemporal & Retrieval Hardening plan (S02 2026-05-11) and remain
**top-level** in v2 — not under `pipeline:` — because Bases query them
via `Latest Only.base` / `As Of.base` / `Version Chain.base`. Pipeline
writes them, user may correct them, user wins on collision.

`document_date` = date the document was authored / dated by its
producer (cover page, signed date, filename token).
`is_latest_version` = true unless §7 supersession says otherwise.

## 7. Supersession-detection algorithm (CRITICAL — Merged C4)

### 7.1 Stem-strip regex

At ingest time, the pipeline strips version / preread / variant
suffixes from the **original filename stem** (filename minus
extension) to compute a `supersession_stem`. Manifest is then queried
for any prior entry with the same stem.

**The regex** (Python `re`, applied iteratively to the stem until no
more matches):

```python
SUPERSESSION_STRIP = re.compile(
    r"""(?ix)                          # case-insensitive, verbose
    (
        [_\-\s]+v\d+(?:\.\d+)*          # _v2  -v3  v1.2
      | [_\-\s]+ver\d+(?:\.\d+)*        # _ver2
      | [_\-\s]+vPreread\d*             # _vPreread01
      | [_\-\s]+preread\d*              # _preread2
      | [_\-\s]+rev\d+                  # _rev3
      | [_\-\s]+draft\d*                # _draft  _draft2
      | [_\-\s]+final                   # _final  -final
      | [_\-\s]+clean                   # _clean
      | [_\-\s]+\d{4}[_\-]?\d{2}[_\-]?\d{2}   # _20260417  -2026-04-17
      | [_\-\s]+\d{6,8}                  # _260417  _20260417 (date-without-separators)
      | [_\-\s]+\(\d+\)                  # _(2)   (3)
      | [_\-\s]+copy\d*                  # _copy  copy2
    )+
    \s*$                                # at end of stem
    """,
)

def supersession_stem(filename: str) -> str:
    stem = Path(filename).stem
    prev = None
    while prev != stem:
        prev = stem
        stem = SUPERSESSION_STRIP.sub("", stem).strip(" _-")
    return stem.lower()
```

**Examples** (operate on the bare stem; extension dropped before
regex):

| Original filename | `supersession_stem(filename)` |
|-------------------|------------------------------|
| `Q1_report_v2.pdf` | `q1_report` |
| `Q1_report_v3.pdf` | `q1_report` |
| `260417_PNSL_Shareholders_Pres_vPreread01_1604_1610.pdf` | `pnsl_shareholders_pres` (date, vPreread01, and two time tokens stripped) |
| `Peninsula_Roadmap_2026-04-17_final.pdf` | `peninsula_roadmap` |
| `RACI_v1.2.xlsx` | `raci` |
| `meeting_notes_2026-05-13.docx` | `meeting_notes` |

**Window.** Manifest query restricts to entries with `extracted_at`
within the **last 90 days**. Older matches are NOT auto-superseded —
they go on a "possible long-window match" report at next session
start for Ricardo to decide manually.

### 7.2 Algorithm

```
on ingest(file):
    new_sha = sha256(file)
    stem = supersession_stem(file.name)

    # 1. dedup by hash — exact duplicate?
    if manifest.has_sha(new_sha):
        quarantine(file, reason="exact_duplicate")
        log("exact_duplicate", file, new_sha)
        return

    # 2. stem-based supersession query
    prior_entries = manifest.query_by_stem(stem, window_days=90)
    prior_entries = [e for e in prior_entries if e.sha != new_sha]

    if not prior_entries:
        # first version of this stem in window
        write_md(file, is_latest_version=True, supersedes=[])
        manifest.append(file, new_sha, stem, supersedes=[])
        return

    # 3. supersession path
    write_md(
        file,
        is_latest_version=True,
        supersedes=[e.sha for e in prior_entries],   # newest first
    )
    manifest.append(file, new_sha, stem, supersedes=[e.sha for e in prior_entries])

    # 4. queue prior versions for is_latest_version: false update
    for prior in prior_entries:
        queue_supersession_update(
            prior.md_path,
            superseded_by=new_sha,
            superseded_date=now_utc(),
        )

    # 5. HARD ALERT next session start
    next_session_alert(
        message=f"{len(prior_entries)} prior versions superseded by {file.name}",
        details=[(e.md_path, new_sha) for e in prior_entries],
    )
```

### 7.3 The HARD ALERT contract

When the alert fires (at next-session bootstrap, step 8 of the
session-bootstrap-discipline lifecycle), Ricardo sees:

```
⚠ SUPERSESSION QUEUE — N prior versions awaiting is_latest_version: false update.
  See 99 Workspace/_ingestion_supersession_queue.md for the list.
  Approve or amend before running new substantive work.
```

The queue file is auto-written by the pipeline run; Ricardo approves
(or amends — e.g. demotes the supersession to "side-by-side variant")
and a `--apply-queue` command runs the batch `is_latest_version:
false` + `superseded_by:` edits. Pipeline never auto-applies the
demotion — the demotion is a structural typed-zone edit and stays
trigger-only.

### 7.4 Why this matters

Without §7.2, every ingest defaults `is_latest_version: true` and the
`Latest Only.base` view (P-4 bitemporal contract) silently drifts to
showing two "latest" versions of the same doc. The audit trail loses
its single-truth property, which is the entire point of bitemporal
tracking. Merged C4 was rated CRITICAL for this reason.

The 90-day window is a calibration: longer would over-trigger on
unrelated docs that happen to share a stem (e.g. `meeting_notes` is
not unique); shorter would miss legitimate roll-ups (e.g. annual
budget v1 → v2 across a year). 90 days catches the realistic quarterly
+ project-revision cadence at Galp; long-window matches surface for
manual decision.

### 7.5 Semantic-neighbour soft-warning protocol (LOCKED DESIGN)

After content extraction, the pipeline queries Smart Connections for
the top-3 nearest existing vault notes by semantic similarity to the
newly extracted text. This lookup runs via `mcp__smart-connections__lookup`
with the extracted text as the query string.

**Soft-warning posture — this is a LOCKED design decision.** The
semantic-neighbour check:

1. **NEVER blocks ingest.** A high-similarity match is advisory only —
   the file proceeds to commit regardless of the score. This is an
   irrevocable posture for this contract; future sessions must not
   silently escalate the check to blocking without a structural contract
   revision (which requires Ricardo's explicit approval and a new
   `last_updated:` bump).

2. **Top-3 results written to `pipeline.semantic_neighbors`** in the
   ingested .md frontmatter. Shape:

   ```yaml
   pipeline:
     semantic_neighbors:
       - path: "50 Sources/pdfs/strategic/peninsula_shareholders_presentation_17_apr_2026.md"
         score: 0.91
       - path: "40 Meetings/2026-04-15_peninsula_board_prep.md"
         score: 0.84
       - path: "30 Projects/Peninsula.md"
         score: 0.72
   ```

   If the Smart Connections lookup fails (MCP unavailable, index stale,
   timeout), `pipeline.semantic_neighbors` is written as `[]` with a
   `pipeline.warnings:` entry `["semantic_lookup_unavailable"]`. Ingest
   continues; this is not a fatal error.

3. **Threshold ≥ 0.80 surfaces in `_ingestion_supersession_queue.md`**
   as a *soft duplicate candidate* — a separate row from the
   stem-based supersession entries. The row reads:

   ```
   [soft-duplicate] <new_md_path> ← score 0.91 → <neighbor_md_path>
   Action: Ricardo reviews; no --apply-queue needed (no is_latest_version flip).
   ```

   Ricardo may act (merge notes, add a cross-link, or dismiss) or do
   nothing — the pipeline does not require resolution before the next
   run. No HARD ALERT is fired; the queue entry is surfaced at session
   start alongside (but visually distinct from) hard supersession items.

4. **Threshold < 0.80** — written to `pipeline.semantic_neighbors` but
   NOT surfaced in the queue. This is the normal case for unrelated
   documents that happen to share vocabulary.

**Why lock this now.** The risk of silent escalation is real: a future
session (code or Claude) might "helpfully" add a blocking guard because
the semantic score looks alarming. Locking the posture here means any
deviation is a verifiable contract violation, not an ambiguous judgment
call. If the posture needs to change (e.g. move to blocking for a
specific file type), the change must be proposed, this section must be
updated, and `last_updated:` must be bumped — the audit trail then
shows who decided what and when.

**Scope — no retroactive backfill of `semantic_neighbors` (locked 2026-05-16).**
The 264 backfilled manifest entries (run_id `backfill-2026-05-16`, §11) do NOT
have `semantic_neighbors` computed retroactively. Decision rationale:

1. **No new ingest to compare against.** Backfill reconstructs manifest records
   for files already in the vault; no net-new content is being evaluated. A
   semantic-neighbour lookup at backfill time would compare existing vault notes
   *against each other* — not against a genuinely new document. That would surface
   false soft-duplicate alerts for files that have co-existed harmlessly for months.
2. **SC quota cost.** Running `query_neighbors()` for 264 entries would load the
   sentence-transformers model (~1 GB), embed 264 text snippets, and compute
   cosine similarity against 21k+ source embeddings — a ~10 s × 264 = ~44 min
   wall-clock job for zero actionable signal (see reason 1).
3. **Backfill entries carry `pipeline.semantic_neighbors: []`** implicitly (the
   field is absent; callers treat absent the same as empty). This is the correct
   representation: the check was not run, not that it ran and returned no matches.

Future behaviour: `semantic_neighbors` is computed for every **live** ingest run
(new files dropped into `00 Inbox/_drop/`) from S04 onwards. Backfill-mode entries
remain exempt permanently — re-running backfill does not add this field.

### 7.5.1 See-also promotion to body (LD-03 — 2026-05-16)

Frontmatter `pipeline.semantic_neighbors` is invisible to Obsidian's graph
view and to Step 3 of the retrieval cascade (wikilink BFS). Storing
semantic links in frontmatter alone means the graph + retrieval are blind to
them.

The pipeline therefore promotes high-confidence neighbours to **body
wikilinks** at ingest time under a `## See also` section. Threshold and
formatting are LOCKED:

1. **Threshold ≥ 0.85** (constant `SEMANTIC_SEE_ALSO_THRESHOLD` in
   `handlers/semantic.py`). Higher than the 0.80 soft-warning threshold
   because a body wikilink is structural (graph-visible, retrieval-followed)
   and noisier than a queue alert.

2. **Idempotent re-render markers.** The block is wrapped in HTML comments
   so a future re-enrich pass can detect + replace it without leaving
   orphans:

   ```markdown
   <!-- pipeline:see-also -->
   ## See also

   - [[Peninsula]] (score 0.92)
   - [[2026-04-15_board_prep]] (score 0.87)
   <!-- /pipeline:see-also -->
   ```

3. **Wikilink target = basename of vault-relative path.** Per Obsidian
   resolution: `30 Projects/Peninsula.md` → `[[Peninsula]]`. No path
   components, no `.md` extension.

4. **`pipeline.see_also_added: true | false`** is written into the
   pipeline namespace as the cheap test for whether a block was emitted.

5. **No fail-blocking.** If `format_see_also_block` raises (it
   shouldn't — pure-Python string assembly), `pipeline.warnings` gets a
   `see_also_skipped: <reason>` entry and `see_also_added: false`. The
   ingested .md still commits.

6. **Interaction with wikilink enrichment (LD-02).** The block is masked
   by `enrich_links.SEE_ALSO_BLOCK_RE` so the catalogue-driven enricher
   never double-links inside it. Order is: append See-Also → run
   enrich_links → render frontmatter → commit.

## 8. How to get the original — retrieval pattern (Merged F-06)

User requirement (Ricardo, S00 plan briefing): *"if I want to get the
file beyond the content I can get it easily."* The contract supports
this through three independent paths, in increasing manual effort:

### 8.1 Path A — Obsidian wikilink (preferred, zero-click)

The `**Open original:** [[<source_file>]]` body link resolves via
Obsidian's wikilink resolver to the binary at `99 Workspace/_originals/`.
In Obsidian, `Cmd+Click` on the wikilink opens the binary in the
system's default app. In Cowork, the same wikilink is followable in
preview.

**Required for this path:** `original_path:` frontmatter populated;
`**Open original:**` body link present. Both are mandatory per §1
and §4.

### 8.2 Path B — file-tree navigation (when Obsidian unavailable)

Read `original_path:` from the frontmatter (vault-relative — see §6.1).
Navigate to that path in Finder / Cowork file picker / `ls`. The
binary is at `99 Workspace/_originals/<sha[:8]>_<original_name>`.

The 8-character SHA prefix is **cosmetic only** — it disambiguates
two files with identical original names. Truth-for-dedup lives in
`90 System/_ingestion_pipeline/_manifest.jsonl` keyed by FULL
SHA-256 (per Codex H3, prefix collision risk above ~1500 files is too
high; manifest is authoritative).

### 8.3 Path C — integrity verification (when paranoid)

If the wikilink resolves to a file that has been tampered with or
corrupted, the contract supports verification:

```bash
sha256sum "99 Workspace/_originals/a1b2c3d4_file.pdf"
# Compare to pipeline.sha256 in the ingested .md frontmatter
```

A mismatch indicates either (a) the original was edited in place
(violating §9.4) or (b) the file is corrupted. Either way, the .md
is suspect; consult the manifest entry (`pipeline.run_id`) and
quarantine to `99 Workspace/_inbox_quarantine/` for re-ingest.

### 8.4 Round-trip identity

`source_file` → `original_path` → SHA-256 verify → manifest entry
→ run_id → log line. Five independent crosschecks for any ingested
.md. If any one fails, the entry is suspect.

## 9. Operational discipline (read-only originals; what is and isn't auto-write)

Per `.claude/rules/ingestion-pipeline-discipline.md` and P-14:

- **`00 Inbox/_drop/`** — drop zone. Auto-write OK for the pipeline;
  Ricardo also drops files here manually. NOT for ingested .md
  output; output goes to `00 Inbox/` (one level up).
- **`99 Workspace/_originals/`** — pipeline-managed. Auto-write OK
  for the pipeline (P-7 says `99 Workspace/` is auto-write). **Files
  here are read-only after write** — never edit, never overwrite,
  never delete except via Ricardo-approved cleanup. If you need an
  updated original, drop the new version into `00 Inbox/_drop/`;
  supersession (§7) handles the version chain.
- **`99 Workspace/_inbox_quarantine/`** — pipeline drops files here
  on dedup-hit, re-ingest-attempt, or extractor-failure. Auto-write
  OK. Ricardo reviews and decides delete / repair / manual ingest.
- **`90 System/_ingestion_pipeline/_staging/<run_id>/`** —
  in-flight extraction work. Cleaned up on successful commit;
  preserved on crash for `--recover` / `--rollback`.
- **`90 System/_ingestion_pipeline/_manifest.jsonl`** —
  append-only JSON-lines log. One line per ingested file with full
  SHA-256, stem, run_id, timestamps, supersession links. **Truth for
  dedup.** Never edited; regenerated only via offline rebuild from
  `_originals/` if corrupted.
- **`99 Workspace/_ingestion_log.md`** — human-readable session log
  of pipeline runs (one paragraph per run). Append-only.
- **`00 Inbox/<YYYY-MM-DD>-<slug>.md`** — the ingested .md output.
  Auto-write OK. P-10 promotes downstream to typed zones once
  approved.

**Anything outside this list is OUTSIDE the pipeline's auto-write
scope.** A pipeline run that wants to touch `30 Projects/`,
`50 Sources/`, `70 Decisions/`, or any other typed zone violates
P-14 and P-7 and must fail-fast with a clear error.

## 11. Backfill mode (one-shot manifest reconstruction)

**Purpose.** The vault accumulated 264 ingested `.md` files before the
v2 manifest (`_manifest.jsonl`) existed. These files are invisible to
the manifest-based dedup check — without backfill, every re-drop of a
pre-pipeline binary ingests as new. `--backfill` reconstructs manifest
entries for these files so the full corpus is dedup-visible.

**Trigger.** `--backfill` is **never auto-run**. It is invoked
explicitly by Ricardo (or by an S02 session prompt) as a one-shot
operation after the pipeline code is committed. It is idempotent —
running it twice on the same file produces the same manifest entry;
duplicates are detected and skipped with a log line.

**Algorithm.**

```
on backfill():
    typed_zones = ["50 Sources/", "40 Meetings/", "30 Projects/",
                   "70 Decisions/", "00 Inbox/"]

    for md_path in walk(typed_zones, ext=".md"):
        fm = parse_frontmatter(md_path)

        # skip files that are not ingested outputs
        if not fm.get("original_path"):
            continue
        # skip files already in the manifest
        if manifest.has_md_path(md_path):
            continue

        # prefer pipeline.sha256 if already written
        sha = fm.get("pipeline", {}).get("sha256") or None

        if sha is None:
            # recompute from the original binary
            orig = resolve_vault_relative(fm["original_path"])
            if orig.exists():
                sha = sha256(orig)
            else:
                # original not found — log and skip
                log_backfill_skip(md_path, reason="original_not_found")
                continue

        stem = supersession_stem(fm.get("source_file", md_path.name))

        manifest.append(
            md_path=md_path,
            sha256=sha,
            stem=stem,
            run_id=f"backfill-{today_iso()}",
            status="committed",
            supersedes=[],
        )

    log_backfill_summary(total, written, skipped)
```

**Manifest entry shape for backfilled files.**

```json
{
  "md_path": "50 Sources/pdfs/strategic/peninsula_shareholders_presentation_17_apr_2026.md",
  "sha256": "3f2a8b1c…fullhex",
  "stem": "pnsl_shareholders_pres",
  "run_id": "backfill-2026-05-16",
  "status": "committed",
  "extracted_at": null,
  "supersedes": [],
  "superseded_by": null
}
```

`extracted_at: null` signals that this entry was not produced by a live
pipeline run — it is a reconstructed record. Code that queries by
`extracted_at` must handle null gracefully (treat as epoch-zero for
window comparisons, so these entries are always within any window).

**What backfill does NOT do.**

- Does NOT write or modify any `.md` frontmatter (files are already
  ingested and may have user edits).
- Does NOT move any binary files (they are already in `_originals/` or
  at their legacy paths).
- Does NOT resolve supersession chains among the backfilled files
  (that is deferred — the 264 files are assumed independent at
  backfill time; a subsequent `--detect-supersession` pass can queue
  chains for Ricardo's approval).
- Does NOT trigger HARD ALERTs (backfill is a silent reconstruction
  operation, not a live ingest event).

**Audit output.** After completion, backfill writes one summary to
`99 Workspace/_auto_writes.md` (per auto-write discipline) and a
detailed run log to `99 Workspace/_ingestion_log.md` (one paragraph,
append-only):

```
Backfill run — 2026-05-16: 264 candidates walked; 247 entries written;
17 skipped (12 original_not_found, 5 already_in_manifest). Run ID:
backfill-2026-05-16. See _plan_ingestion_dedup_hardening_2026-05-16.html §S02 for context.
```

**Re-run safety.** Backfill detects existing manifest entries by
`md_path` key and skips them. It is safe to run after a partial failure
— it picks up from where it left off.

## 12. Auto-link candidates (AL-04 — 2026-05-17)

**Origin.** AL-04/AL-05 of the Frontier Adoption plan
(`99 Workspace/_plan_galp_frontier_adoption_2026-05-16.html`). Adds the
`pipeline.link_candidates` namespace field. The auto-linker runs at
ingest time — after content extraction, before .md write — and proposes
wikilinks for named entities (People, Companies, Concepts) recognised in
the body. Candidates land in frontmatter; Ricardo applies them via
`kb-curator apply-link-candidates --source <path>` (AL-07, S09).

### 12.1 Schema — one candidate per list entry

```yaml
pipeline:
  link_candidates:
    - entity_id:         "20 Companies/Moeve"        # catalog row id (zone-prefixed stem)
      matched_string:    "Moeve"                     # the substring of the body that matched
      confidence:        "exact"                     # 'exact' (Aho-Corasick / catalog stem+alias) | 'ner' (spaCy NER, not in catalog)
      offsets:           [12, 17]                    # [start, end_exclusive] char offsets into result.body
      proposed_wikilink: "[[Moeve]]"                 # the wikilink target to weave into body on apply
```

Field rules:

- **`entity_id`** — for `confidence: exact`, this is the catalog id from
  `99 Workspace/_entity_catalog.json` (zone-prefixed: `10 People/Susana
  Zumel Vara`, `20 Companies/Moeve`, `60 Concepts/Day 1`). For
  `confidence: ner`, the entity is not in the catalog yet; the id slot
  carries `ner/<surface-form>` (e.g. `ner/Lisbon`) so the apply step can
  spot it and offer Ricardo a "create entity?" path.
- **`matched_string`** — the exact substring of the *extracted body* that
  produced the match, preserving source casing. Used by the apply step to
  find-and-replace.
- **`confidence`** — closed enum: `exact` | `ner`. Future tiers may add
  `fuzzy` or `embedding`; adding a new value requires updating this
  section.
- **`offsets`** — `[start, end_exclusive]` char offsets into the body
  string the matcher saw (post-extraction, post-enrichment, post-See-Also
  promotion — see §12.2). Offsets are advisory: the apply step
  re-locates by `matched_string` to be robust to manual edits.
- **`proposed_wikilink`** — the target rendered as Obsidian wikilink. For
  exact matches, this is `[[<basename-of-entity_id>]]` (e.g.
  `[[Susana Zumel Vara]]`). For NER matches, the apply step asks Ricardo
  for the target (or "skip" / "edit").

### 12.2 Population order and cap

The pipeline populates `link_candidates` AFTER the §7.5.1 See-Also
promotion and AFTER §5 wikilink enrichment, so the body offsets reflect
the final body the .md will commit. The matcher passes are:

1. **`_link_matcher.py` (AL-03)** — case-sensitive Aho-Corasick over the
   stem + alias union from `_entity_catalog.json`. All hits land with
   `confidence: 'exact'`.
2. **spaCy NER (AL-05, optional)** — runs only when the spaCy large model
   for the detected language is installed and loadable. Recognises
   PERSON / ORG / LOC / GPE entity types; rejects entities whose
   surface form already appears in the catalog (exact pass already
   covered them); the remainder land with `confidence: 'ner'` and
   `entity_id: 'ner/<surface-form>'`.

**Deduplication.** Candidates with the same `(entity_id, matched_string)`
pair are deduplicated; the first occurrence (smallest `start` offset)
wins. Two different mentions of the same entity at different offsets
produce two list entries — the apply step decides which to wire.

**Cap — 50 candidates per source.** Sorted by `(confidence desc — 'exact'
first; then start asc)`. Anything beyond the cap is dropped with a
`pipeline.warnings: ["link_candidates_truncated: <N>"]` entry. Rationale:
ingested .md files are session-readable; 50 wikilink proposals already
exceeds what Ricardo will review in one apply pass. AL-07 batches the
review by source; running the apply step twice is cheaper than blowing
the frontmatter budget.

### 12.3 Empty / missing field

- **No catalog file.** If `99 Workspace/_entity_catalog.json` is missing
  or unreadable, the field is omitted entirely from frontmatter and
  `pipeline.warnings` gets `link_candidates_skipped:
  catalog_unavailable`. Ingest is never blocked.
- **Empty matches.** If both passes return nothing, the field is written
  as an explicit empty list `link_candidates: []` (distinguishable from
  "field not present because of error" — see above).
- **Body unavailable** (handler quarantine path). The field is never
  written; the .md never reaches the link-candidates phase.

### 12.4 Closed-loop integration (AL-06)

When the committed candidate list contains **≥5 entries**, the pipeline
appends a `tier: 2`, `category: 'link-candidates-review'` row to
`99 Workspace/_recommendations_open.jsonl`. Schema and emission discipline
per `_closed_loop_contract.md` §4 (category vocabulary updated 2026-05-17
to include `link-candidates-review`).

The `target_action` field on the row is canonical:
`kb-curator apply-link-candidates --source <md-vault-relative-path>`.

The 5-candidate threshold is a calibration:

- Under 5: the apply step is faster than the registry-bookkeeping
  overhead — Ricardo can act inline next time he opens the file (the
  frontmatter is visible in Bases via a `link_candidates_count` formula
  column to be added).
- 5 or more: the apply step is worth a dedicated 1–2 minute review pass;
  the registry surfaces it so it doesn't sit forgotten.

### 12.5 Idempotency on re-ingest

Re-ingest is refused by §5 (early-exit on `pipeline.provenance:
ingestion-pipeline` already present). If the apply step (AL-07) has
already consumed the candidates, the field is cleared (`link_candidates:
[]`) by the kb-curator subcommand — *not* by the pipeline. A fresh
pipeline run on the same content would never observe the cleared field
because it would early-exit before reaching this phase.

### 12.6 Cross-references

- `90 System/_link_matcher.py` — the AL-03 matcher (Aho-Corasick + word
  boundary + longest-match-wins)
- `99 Workspace/_entity_catalog.json` — the catalog input (AL-02)
- `90 System/_ingestion_pipeline/handlers/links.py` — the AL-05
  pipeline hook that produces this field
- `90 System/_closed_loop_contract.md` §4 — category vocabulary; the
  `link-candidates-review` category lives here
- `.claude/skills/kb-curator/scripts/apply_link_candidates.py` — AL-07
  consumer (S09)

## 10. Open items / follow-ups

1. **Retro-rewrite of 277 sidecar originals.** Existing files carry
   absolute-legacy paths in `original_path:`. After T+30 (2026-06-08)
   these become dangling. A separate one-shot session is needed to
   rewrite them vault-relative. Flagged in audit §8.3 + S00 handoff
   §3; out of scope for v2 itself.
2. **`enrich_links.py` migration to `pipeline.tags:`** — currently
   writes top-level `tags:`. The S00 audit ADOPTed it in place; S03
   (enrichment session in v2) will update line 304 (log_path) and
   the tags-writing logic per §5 of this contract.
3. **`type:` enum extension policy.** When a new handler needs a new
   `type:` value, the rule is: update this contract first, get
   Ricardo's nod, then the handler can write the new value. The
   `_smoke_test_retrieval.py` does not currently assert the enum;
   that's a possible future hardening item.

---

**End of contract.** Code under `90 System/_ingestion_pipeline/` from
S02 onwards reads this file as the spec. Changes here are structural
and must update `last_updated:` + surface in the next handoff.

## Related decisions

- [[2026-05-15_ingestion_go_live]] — go-live decision for the v2
  ingestion pipeline (active scheduled task `galp-vault-inbox-ingest`).
- [[2026-05-13_image_ocr_egress_policy]] — image OCR egress policy for
  pipeline-handled binaries (no cloud OCR on document content).
