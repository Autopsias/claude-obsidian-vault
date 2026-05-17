---
name: vault-ingestion
description: Multi-format ingestion of files dropped at 00 Inbox/_drop/ into typed .md notes — supports PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, image. Pipeline classifies purpose, extracts content, writes typed frontmatter, preserves the original at 99 Workspace/_originals/, and dedups against the manifest in three tiers (binary SHA / text-hash / semantic warn). Triggers on "ingest this file", "drop and ingest", "process the inbox", "run ingestion", "ingestion pipeline", or when files appear in 00 Inbox/_drop/. Do NOT use to ingest text-content from chat (use save-conversation) or to re-process already-ingested files unless explicitly forced.
---

# Vault Ingestion

The pipeline that turns a binary or text file dropped at `00 Inbox/_drop/`
into a typed markdown note Claude can retrieve, cite, and reason over.

## When to use

- Files dropped at `00 Inbox/_drop/` — auto-ingest on cron, or manual run.
- A user-provided file the conversation references — ingest before reading.
- Bulk import of accumulated reference material — point `ingest.py` at the
  source directory and it walks the contents.

**Do NOT use:**
- For mid-conversation text capture — that's `save-conversation`.
- For re-ingestion of already-manifested files — the pipeline refuses by
  default (binary SHA dedup). Pass `--force` only if you intend to override.

## The lifecycle

```
drop ──> extract ──> classify ──> frontmatter ──> typed-md ──> manifest + log
  ↓
preserve original at 99 Workspace/_originals/<sha[:8]>_<name>
```

1. **Drop.** File arrives at `00 Inbox/_drop/<filename>`. Do NOT edit
   files in `_drop/`; they are mid-transit.
2. **Extract.** Format-specific handler runs:
   - `pdf` → pdfplumber + pytesseract OCR fallback
   - `docx` → python-docx + table extraction
   - `pptx` → python-pptx slide-text walk
   - `xlsx` → openpyxl per-sheet table emission
   - `html` → BeautifulSoup body extraction
   - `md`/`txt` → direct copy with frontmatter injection
   - `image` → pytesseract OCR
3. **Classify.** `purpose.md` classifier infers the document's purpose
   (reference / meeting note / source-of-truth / draft / external) and
   suggests target zone.
4. **Frontmatter.** Per the `_ingestion_contract.md` schema: `type:
   source`, `source_kind`, `document_date`, `is_latest_version: true`,
   `document_version: v1`, `ingested_at:`, `sha256:`, `text_sha256:`,
   `pipeline:` namespace with run-id + handler-version + extraction
   confidence.
5. **Write typed-md.** Lands at `00 Inbox/<YYYY-MM-DD>-<slug>.md` per
   `inbox-discipline.md`. Existing markdown notes with `pipeline.provenance:`
   already set are refused (no double-ingestion).
6. **Preserve original.** Binary moves to `99 Workspace/_originals/<sha[:8]>_<name>`
   (read-only after write).
7. **Log.** Append a manifest line to
   `99 Workspace/_ingestion_pipeline/_manifest.jsonl` + a one-paragraph run
   summary to `99 Workspace/_ingestion_log.md`.

## Three-tier dedup

| Tier | Check | Outcome on hit |
|---|---|---|
| **1 (binary)** | SHA-256 of the bytes | **Refuse** ingestion; log skip-reason |
| **2 (text)** | SHA-256 of the extracted text (after normalisation) | **Refuse** if exact match; soft-warn otherwise |
| **3 (semantic)** | Cosine similarity vs existing notes via Smart Connections (≥0.80) | **Soft-warn** to `_ingestion_supersession_queue.md` — Ricardo dispositions before --apply-queue |

## Files

- `scripts/ingest.py` — main entry point; supports `--drop` (process all in `_drop/`), `--file <path>` (single file), `--apply-queue` (process the supersession queue after manual review)
- `scripts/config.yaml` — paths, classifier thresholds, dedup thresholds
- `scripts/handlers/` — per-format extractors (pdf/docx/pptx/xlsx/html/text/image/semantic/links)
- `scripts/backfill_manifest.py` — reconcile existing files into the manifest (one-time migration)
- `templates/ingestion-contract-template.md` — the frontmatter contract the pipeline writes to (89 KB; lift into `90 System/_ingestion_contract.md` in the vault on install)
- `scripts/requirements.txt` + `requirements-system.md` — Python and system-level deps (pdfplumber, pytesseract, python-docx, python-pptx, openpyxl, BeautifulSoup, tesseract-ocr binary)

## Install steps

1. Install `vault-framework` first (this plugin uses its
   `inbox-discipline.md` and `auto-write-discipline.md` rules).
2. Run `pip install -r scripts/requirements.txt` in a venv.
3. Install tesseract per `scripts/requirements-system.md`.
4. Copy `templates/ingestion-contract-template.md` to
   `90 System/_ingestion_contract.md` in the vault and customise any
   project-specific frontmatter additions.
5. Create `00 Inbox/_drop/` if absent.
6. Schedule the pipeline: cron `0 7 * * *` (daily 07:00 local) calling
   `python ingest.py --drop --vault <vault-path>` is the reference cadence.

## Operational notes

- **Cloud OCR fallback** — if local OCR confidence is below threshold and a
  cloud OCR provider is configured, the pipeline routes the file via cloud
  OCR with explicit user-approval gate. Audit at `_cloud_ocr_audit.jsonl`.
- **Manifest is append-only.** Never edit `_manifest.jsonl` by hand;
  corruption invalidates dedup. Use `backfill_manifest.py` to add legacy
  files.
- **`pipeline.provenance:` is load-bearing** — its absence on a markdown
  note means the pipeline hasn't seen it. Its presence is the refusal trigger
  for re-ingestion.

## Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Handler exception on PDF | encrypted / scan-only with bad OCR confidence | Manual review; route via cloud OCR |
| File ingested twice | `--force` flag bypassed dedup | Restore from manifest; remove the duplicate typed-md |
| Soft-warn flood | semantic threshold too low for this corpus | Raise threshold in `config.yaml`; re-run |
| Manifest line missing | hook fired but write failed | `backfill_manifest.py --file <path>` |

## When NOT to ingest

- Files with PII or controlled content — handle outside the vault
- Audio / video — use the upstream transcription pipeline first, then
  ingest the .txt transcript
- Files whose source-of-truth is a live system (Notion, Jira, Slack) —
  ingest a snapshot only if you accept the staleness contract
