---
paths:
  - "00 Inbox/**/*.md"
  - "00 Inbox/_drop/**/*"
---

# Inbox discipline

`00 Inbox/` is the vault's quick-capture zone — untyped, frontmatter-light
notes. Auto-write OK without per-file approval (subject to
`auto-write-discipline.md`).

## Lifecycle (markdown notes)

1. **Capture.** Drop a note as `00 Inbox/YYYY-MM-DD-<slug>.md`. Frontmatter
   may be minimal (`type: inbox` or absent). Body is freeform.
2. **Triage.** A handoff-freshness check flags items >7 days old at the
   weekly/daily check. Triage moves: promote to a typed zone via the
   promotion ritual (P-10), merge into an existing note, or delete.
3. **Promote** via `propose-cleanup` once the note has decision-relevant
   content; quality filter per the promotion quality guide.

Inbox notes do NOT count toward Bases coverage (they are explicitly excluded
in the verifier's allow-list of expected-empty types).

## Binary drop zone (`00 Inbox/_drop/`)

`00 Inbox/_drop/` is the **pipeline-managed binary drop zone** — separate
discipline from the markdown quick-capture above. Anything dropped there
(PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, image) is processed by the
ingestion pipeline (`90 System/_ingestion_pipeline/`), not by Claude
directly.

**Full rules:** `ingestion-pipeline-discipline.md` (the operational kernel
of P-14). The pointers below are the bare minimum needed to keep
`00 Inbox/_drop/` from being misused:

1. **Drop, don't edit.** Files in `_drop/` are mid-transit. Do NOT edit
   them in place, do NOT read from `_drop/` to answer a query (file may
   be mid-extraction). Read the ingested .md in `00 Inbox/<date>-<slug>.md`
   instead, or query the manifest at
   `99 Workspace/_ingestion_pipeline/_manifest.jsonl`.
2. **Lifecycle is drop → ingest → move → log.** The pipeline:
   (a) picks the file up from `_drop/`,
   (b) extracts content into `00 Inbox/<date>-<slug>.md` per the
       frontmatter contract at `90 System/_ingestion_contract.md`,
   (c) moves the binary to `99 Workspace/_originals/<sha[:8]>_<name>`
       (read-only after write),
   (d) appends a manifest line + writes a one-paragraph run summary to
       `99 Workspace/_ingestion_log.md`.
3. **Markdown notes still go one level up.** A handwritten `.md` thought-
   dump goes into `00 Inbox/YYYY-MM-DD-<slug>.md` (markdown lifecycle
   above), NOT `00 Inbox/_drop/`. The drop zone is for the pipeline.
   Putting a markdown note in `_drop/` will trigger the pipeline's `.md`
   handler, which may early-exit if the note already carries
   `pipeline.provenance:` (re-ingest refused) or otherwise add a
   `pipeline:` namespace to a hand-written note — usually not what the
   author wanted.
4. **`_drop/` is auto-write for the pipeline AND for {{USER_FIRST_NAME}}**
   dropping files manually. Both write paths follow
   `auto-write-discipline.md` logging; the pipeline's logging is
   centralised in `_ingestion_log.md` (one summary line per run, not per
   file — bulk pattern).

The drop zone is **not** a Bases-covered location — files there are
mid-transit, not vault content. The ingested .md output is what shows up
in Bases.

## Cross-references

- `ingestion-pipeline-discipline.md` — full P-14 operational kernel
- `90 System/_ingestion_contract.md` — the frontmatter contract the pipeline writes to
- `auto-write-discipline.md` — auto-write logging applies to both markdown notes and pipeline runs
- `90 System/_operating_guide.md` — P-14 (Ingestion) designation
