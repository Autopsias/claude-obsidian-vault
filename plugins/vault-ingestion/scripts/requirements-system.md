---
name: Ingestion Pipeline — System Dependencies
description: Non-pip dependencies the pipeline needs at runtime (Tesseract binary, poppler-utils for pdftotext fallback). Installed via Homebrew on macOS; apt on Linux. Documented here so a clean-venv `pip install` is reproducible end-to-end.
type: system
cadence: stable
last_updated: 2026-05-13
provenance: S01 F-04 of the v2 ingestion pipeline plan (Merged M3 — Codex M2 finding that v1 spec was incomplete and internally inconsistent across runtime / dev / system deps).
source_type: reference
---

# System dependencies — install BEFORE `pip install -r requirements.txt`

The Python dependencies in `requirements.txt` and `requirements-dev.txt`
depend on **system-level binaries** that are NOT installable via pip.
Install these first; the pip step will then succeed in a clean venv.

## macOS (Ricardo's primary environment)

```bash
# Tesseract — OCR engine used by pytesseract for image-ocr handler
brew install tesseract
brew install tesseract-lang   # adds Portuguese + Spanish + multilingual models

# Poppler — provides pdftotext, pdftohtml; fallback when pdfplumber fails
brew install poppler

# (Optional) ImageMagick — used by some HEIC paths via pillow-heif
brew install libheif          # required for pillow-heif wheel resolution on Apple Silicon
```

After install, verify:

```bash
tesseract --version            # expect 5.x
pdftotext -v 2>&1 | head -1    # expect "pdftotext version ..."
```

## Linux (if the pipeline ever runs on a server)

```bash
sudo apt-get update
sudo apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-por \
    tesseract-ocr-spa \
    poppler-utils \
    libheif-dev
```

## Verification — the clean-install gate (Merged M3)

Before S02 codes against the contract, the following sequence must
succeed end-to-end on a fresh machine:

```bash
# 1. System deps
brew install tesseract tesseract-lang poppler libheif

# 2. Python venv
python3 -m venv .venv
source .venv/bin/activate

# 3. Pip install (runtime + dev)
pip install --upgrade pip
pip install -r requirements-dev.txt   # pulls in runtime via -r requirements.txt

# 4. Smoke test
python -c "import pdfplumber, mammoth, openpyxl, pptx, pytesseract, frontmatter, slugify; print('OK')"
tesseract --version
```

All four steps must exit zero before S02 is unblocked. If any step
fails, the failure is a contract bug (over-pinning, missing system
dep, version skew) — fix the manifest, don't paper over.

## Why three files instead of one

- **`requirements.txt`** is the runtime audit surface. Anything in
  this file is in the live pipeline's import graph and is a
  production attack surface. Minimal.
- **`requirements-dev.txt`** is the test surface. Authored fixtures
  use libraries the runtime doesn't need (`python-docx`, `reportlab`).
- **`requirements-system.md`** is the bootstrapping surface — the
  *out-of-band* dependencies pip cannot install. Documented in
  markdown (not a `requirements-*.txt`) because there is no standard
  pip syntax for "first run `brew install X`".

Merged M3 (Codex M2) caught that v1 conflated these — the original
`setup_pipeline.sh` script tried to do all three in one bash file,
which hid which steps required sudo, which needed Homebrew, and
which were pure Python. The split makes each surface independently
auditable.

## Re-evaluation cadence

- **Quarterly:** check for security advisories on listed packages
  (`pip-audit -r requirements.txt`).
- **T+180 substrate review (2026-11-05):** re-evaluate pinning
  strategy and whether any system dep can be replaced with a pure-pip
  alternative.
- **On extractor regression:** if `pdfplumber` (or any other
  extractor) produces materially different output for the per-format
  golden fixtures, pin tighter and surface in the next handoff.

## Cross-references

- `90 System/_ingestion_contract.md` — the contract the code reads
- `90 System/_ingestion_pipeline/requirements.txt` — runtime deps
- `90 System/_ingestion_pipeline/requirements-dev.txt` — test deps
- `.claude/rules/ingestion-pipeline-discipline.md` — operational kernel
- `90 System/_plugin_security.md` — adjacent dependency audit pattern (Smart Connections)
