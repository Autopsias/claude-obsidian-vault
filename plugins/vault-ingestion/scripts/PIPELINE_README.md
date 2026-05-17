---
name: Ingestion Pipeline — README
description: Install, run-mode reference, troubleshooting, recovery, and rollback guide for the v2 ingestion pipeline.
type: system
cadence: stable
last_updated: 2026-05-13
provenance: S04 of the v2 ingestion pipeline plan.
source_type: reference
---

# Galp Vault — Ingestion Pipeline v2

Drops a supported binary into `00 Inbox/_drop/`, runs the pipeline, and the
file appears in `00 Inbox/YYYY-MM-DD-<slug>.md` (extracted text + metadata)
while the original is archived to `99 Workspace/_originals/`.

**Supported formats:** PDF · DOCX · PPTX · XLSX · TXT · MD · PNG/JPG/WEBP/HEIC
and other common image types.

---

## Quick-start

### 1 — System dependencies (install once, before pip)

```bash
# macOS (Ricardo's primary environment)
brew install tesseract tesseract-lang   # OCR engine + PT/ES language packs
brew install poppler                    # pdftotext fallback for scanned PDFs
brew install libheif                    # required by pillow-heif on Apple Silicon
```

Verify:

```bash
tesseract --version          # expect 5.x
pdftotext -v 2>&1 | head -1  # expect "pdftotext version ..."
```

Linux equivalents are documented in `requirements-system.md`.

### 2 — Python virtual environment

```bash
cd "90 System/_ingestion_pipeline"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt   # pulls in runtime deps via -r requirements.txt
```

Smoke-test the install:

```bash
python -c "import pdfplumber, mammoth, openpyxl, pptx, pytesseract, frontmatter, slugify; print('OK')"
```

All modules must print `OK` before the pipeline is trusted on real files.

### 3 — First run (dry-run / report-only)

```bash
source .venv/bin/activate
python ingest.py --root <YOUR_VAULT_PATH> \
                 --dry-run --report-only --verbose
```

Expected output against an empty `_drop/`: `Scanned 0 files — nothing to ingest.`

---

## Run modes

### Daily scheduled run (dry-run by default)

The scheduled task `galp-vault-inbox-ingest` fires at 07:00 daily with:

```
--dry-run --report-only --verbose
```

This scans `_drop/` and prints what *would* be ingested — **no files are
written, no originals are moved**. This is the safe default until you are
ready to go live.

To **promote to a live run**, update the scheduled task body to remove
`--dry-run --report-only` (leave `--verbose` for the log trail).

### Live run (writes files)

```bash
python ingest.py --root /path/to/Galp-Vault --verbose
```

Processes all files in `_drop/` oldest-first. Per-file lifecycle:

1. SHA-256 → dedup check against `_manifest.jsonl`
2. Size guard (100 MB per file; 1 GB per run)
3. Extract content → write staged `.md`
4. Commit: original → `99 Workspace/_originals/`, `.md` → `00 Inbox/`
5. Append manifest entry (COMMITTED)
6. Log to `_ingestion_log.md`, `_auto_writes.md`, `80 Daily/<date>.md`

### Cloud OCR opt-in (images only)

Cloud OCR is disabled by default. Three conditions must ALL hold to activate it:

1. Pass `--allow-cloud-ocr` on the CLI
2. File does NOT match `*.confidential.*`
3. `cloud_ocr.model` is set in `config.yaml` (currently `""` — disabled)

When cloud OCR is active, every API call is audit-logged to
`99 Workspace/_cloud_ocr_audit.jsonl`. See
`70 Decisions/2026-05-13_image_ocr_egress_policy.md` for the egress policy.

```bash
# To enable cloud OCR: edit config.yaml, set model, then:
python ingest.py --root ... --allow-cloud-ocr --max-api-calls 20 --verbose
```

`--max-api-calls N` caps cloud API calls per run (0 = no cap).

---

## Flags reference

| Flag | Description |
|---|---|
| `--root PATH` | Vault root (default: auto-detect via GALP_VAULT_ROOT env or CLAUDE.md search) |
| `--dry-run` | Full extraction but no files written. Staged output is discarded. |
| `--report-only` | Scan + plan only — skips handler dispatch entirely. Implies `--dry-run`. Fastest mode. |
| `--verbose` | Per-file progress + result lines to stdout. |
| `--allow-cloud-ocr` | Opt-in to cloud Vision OCR for images (requires config.yaml model set). |
| `--max-api-calls N` | Cap cloud API calls per run (overrides config.yaml). |
| `--recover RUN_ID` | Resume a crashed run: commits any staged files that have intent-but-not-committed manifest entries. |
| `--rollback RUN_ID` | Undo a committed run: removes `.md` files, moves originals back to `_drop/`, marks entries `rolled_back`. |

---

## Manifest and dedup

`99 Workspace/_ingestion_pipeline/_manifest.jsonl` is the append-only
source of truth for dedup and recovery. Every entry carries:

- `run_id` — UUID of the pipeline run
- `sha256` — full SHA-256 of the source file
- `status` — `intent` | `committed` | `quarantined` | `rolled_back`
- `src_name`, `src_size`, `supersession_stem`
- `orig_vault_rel`, `md_vault_rel` — vault-relative paths after commit

**Dedup uses full SHA-256.** Partial hash (8-char prefix) was rejected
(Codex H3: collision risk above ~1,500 files).

---

## Recovery and rollback

### `--recover` — resume a crashed run

Use when the pipeline crashed or was killed mid-run.

```bash
python ingest.py --root ... --recover <RUN_ID> --verbose
```

The orchestrator finds all manifest entries with `status=intent` and no
corresponding `COMMITTED_<sha8>` marker in the staging directory. For each,
it completes the commit step (binary → `_originals/`, `.md` → `00 Inbox/`).

Get the run ID from the last lines of `99 Workspace/_ingestion_log.md` or
from `_manifest.jsonl` (`grep "intent" _manifest.jsonl | tail -5`).

### `--rollback` — undo a run

Use when a run produced bad output and you want to revert it cleanly.

```bash
python ingest.py --root ... --rollback <RUN_ID> --verbose
```

For each `status=committed` entry in the run:

1. Removes `00 Inbox/<md_file>.md`
2. Moves `99 Workspace/_originals/<sha8>_<name>` back to `00 Inbox/_drop/`
3. Appends a `rolled_back` manifest entry

The files reappear in `_drop/` and will be re-processed on the next run.

**Note:** supersession-queue entries from the rolled-back run are NOT
reversed (the queue is advisory; no `.md` files are auto-demoted by the
queue).

### Dry-run both modes

Both `--recover` and `--rollback` honour `--dry-run` — pass it to preview
what would happen without committing.

```bash
python ingest.py --root ... --recover <RUN_ID> --dry-run --verbose
python ingest.py --root ... --rollback <RUN_ID> --dry-run --verbose
```

---

## Quarantine

Files that cannot be processed land in
`99 Workspace/_inbox_quarantine/YYYY-MM-DD/<sha8>_<name>` with a sidecar
`.md` note. Quarantine reasons:

| Reason | Cause |
|---|---|
| `file_too_large` | File exceeds 100 MB |
| `exact_duplicate` | Full SHA-256 already committed |
| `unsupported_file_type` | Extension not in the handler map |
| `extraction_error` | Handler raised an exception |
| `missing_dependency_*` | A required Python package is not installed |

Quarantine notes contain **no raw file content** — error details are
redacted for security.

Empty quarantine subdirectories older than 30 days are automatically
cleaned up on each run.

---

## Supersession queue

When a new file matches the stem of a previously-ingested file (within a
90-day window), the prior version(s) are added to
`99 Workspace/_ingestion_supersession_queue.md`.

**Prior versions are NEVER auto-demoted.** Ricardo reviews the queue and
applies demotions with `--apply-queue` (S05 deliverable — not yet
implemented).

---

## Troubleshooting

### Lock file stuck

```
LockError: lock held (N.N min)
```

Stale locks (>30 minutes) are auto-taken-over. If the lock is fresh, another
run is active — wait for it to finish, or:

```bash
# Only if you're certain no other run is active:
rm "00 Inbox/_drop/.lock"
```

### Missing Python package

```
ImportError: No module named 'mammoth'
```

Activate the venv and reinstall:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Missing system binary (Tesseract / pdftotext)

```
TesseractNotFoundError
```

Install the system dep (see §1 above) and verify the binary is on `$PATH`.

### Manifest appears corrupt

Never edit `_manifest.jsonl` by hand. If it is corrupt (invalid JSON on a
line), quarantine the bad line:

```bash
python -c "
import json, pathlib
lines = pathlib.Path('99 Workspace/_ingestion_pipeline/_manifest.jsonl').read_text().splitlines()
for i, l in enumerate(lines, 1):
    try: json.loads(l)
    except: print(f'BAD line {i}: {l[:80]}')
"
```

Move the corrupt lines to a sidecar `.bad` file and raise with Ricardo
before running again. Do not delete them — they are evidence.

### Handler import error at startup

The pipeline imports handlers lazily (inside dispatch functions). A
`ModuleNotFoundError` on a handler means the relevant package is missing —
it will only surface when a file of that type is processed, not at startup.
Check `pip list | grep <package>` in the active venv.

---

## File layout

```
90 System/_ingestion_pipeline/
├── ingest.py               ← orchestrator (this session's deliverable)
├── config.yaml             ← runtime config (cloud OCR model, API caps)
├── requirements.txt        ← runtime Python deps
├── requirements-dev.txt    ← test/fixture deps (-r requirements.txt)
├── requirements-system.md  ← system deps (Tesseract, poppler, libheif)
├── pytest.ini              ← test runner config
├── README.md               ← this file
├── handlers/
│   ├── text.py             ← HandlerResult, build_output_md, md + txt handlers
│   ├── pdf.py              ← PDF handler (pdfplumber + pdfminer.six fallback)
│   ├── docx.py             ← DOCX handler (mammoth)
│   ├── pptx.py             ← PPTX handler (python-pptx)
│   ├── xlsx.py             ← XLSX handler (openpyxl)
│   └── image.py            ← Image handler (Tesseract + optional cloud OCR)
└── tests/
    └── ...                 ← pytest suite (per-format + orchestrator tests)

00 Inbox/_drop/             ← binary drop zone (pipeline-managed)
99 Workspace/_originals/    ← archived originals (read-only after write)
99 Workspace/_ingestion_pipeline/_manifest.jsonl   ← dedup + recovery truth
99 Workspace/_ingestion_log.md                     ← per-run summaries
99 Workspace/_ingestion_supersession_queue.md      ← versions to review
99 Workspace/_cloud_ocr_audit.jsonl                ← cloud OCR audit log
99 Workspace/_inbox_quarantine/                    ← quarantine dir
```

---

## Scope-creep stop rule

If the session building this pipeline exceeds 4 hours, the minimum viable
deliverables are:

1. `ingest.py` (orchestrator) — fully working with manifest, recover, rollback
2. `--dry-run --report-only` scheduled task wired up
3. This README

Deferred to the next session: quarantine tidy edge-cases, `--apply-queue`,
per-format handler tuning, live pytest run on vault environment.

---

## Operational contracts

- **`90 System/_ingestion_contract.md`** — frontmatter fields, type enum,
  pipeline: namespace, supersession algorithm
- **`.claude/rules/ingestion-pipeline-discipline.md`** — five load-bearing
  operational rules (drop zone, originals read-only, manifest as dedup truth,
  frontmatter namespacing, supersession never auto-applied)
- **`70 Decisions/2026-05-13_image_ocr_egress_policy.md`** — cloud OCR egress
  policy and go-live decision record
- **`90 System/_maintenance_automation.md`** — scheduled task registry
  (includes `galp-vault-inbox-ingest`)
