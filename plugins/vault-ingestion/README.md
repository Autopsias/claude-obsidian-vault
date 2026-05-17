# vault-ingestion

Multi-format ingestion pipeline. Drop a file at `00 Inbox/_drop/`, get a
typed markdown note Claude can retrieve, cite, and reason over.

## What it ships

```
vault-ingestion/
├── .claude-plugin/plugin.json
├── skills/vault-ingestion/SKILL.md
├── templates/
│   └── ingestion-contract-template.md     # Frontmatter contract
└── scripts/
    ├── ingest.py                         # Main pipeline entry point
    ├── config.yaml                       # Paths, thresholds
    ├── requirements.txt                  # Python deps
    ├── requirements-system.md            # System deps (tesseract, etc.)
    ├── backfill_manifest.py             # One-time migration utility
    └── handlers/
        ├── pdf.py / docx.py / pptx.py / xlsx.py
        ├── html.py / text.py / image.py
        ├── semantic.py / links.py
        └── __init__.py
```

## Supported formats

PDF / DOCX / PPTX / XLSX / HTML / MD / TXT / image (PNG, JPG, TIFF).

## Three-tier dedup

| Tier | Check | Hit outcome |
|---|---|---|
| Binary | SHA-256 of bytes | Refuse |
| Text | SHA-256 of normalised extracted text | Refuse if exact |
| Semantic | Smart Connections cosine ≥0.80 | Soft-warn to queue |

## How it composes

- `vault-framework` provides the `inbox-discipline.md` and
  `auto-write-discipline.md` rules the pipeline writes through.
- `vault-eval` runs a smoke test post-ingestion when the manifest grows.
- `vault-skills/kb-curator` runs `audit-writes` to reconcile the manifest
  against the filesystem if drift is suspected.

## Operational requirements

- Python 3.10+; tesseract-ocr binary on PATH for image / scanned-PDF OCR.
- Optional: cloud OCR provider config for low-confidence fallback.
- Cron / launchd / systemd-timer recommended for `--drop` mode.

## Version

`0.1.0` — pipeline-v2 (`_plan_ingestion_pipeline_v2_2026-05-13`). Battle-
tested at ~230 files across 7 formats with no silent regressions through
the 7-day observation window.
