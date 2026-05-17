"""
handlers/pdf.py — PDF ingestion handler.

Contract: 90 System/_ingestion_contract.md
  §1  — baseline fields (page_count)
  §5  — namespacing
  §9  — originals read-only; image extraction path

HT-02 deliverable (S02):
  - pdfplumber primary extractor
  - pdfminer.six fallback (when pdfplumber yields empty on a page)
  - Per-page: `## Page N` header + body text
  - Empty-text page (scanned): `## Page N (scanned — no text extracted)` marker
  - scanned_pages: [N, M, ...] in frontmatter top-level
  - NO whole-file quarantine for scanned pages — graceful mixed-content
  - Embedded image extraction to <hash>_<name>.pdf.images/
  - Footnotes, headers, footers extracted verbatim where available

Design notes
------------
pdfplumber exposes `page.extract_text()` which returns None or "" for
image-only pages. We fall back to pdfminer's extract_pages on a per-page
basis before declaring a page scanned. Both libraries share the same
underlying PDF parser (pdfminer is pdfplumber's dependency), so the
fallback is just "try harder" — pdfminer's layout analysis sometimes
recovers text that pdfplumber's simpler extractor misses (e.g. rotated
or oddly-encoded pages).

Image extraction uses pdfplumber's page.images (list of image dicts with
bbox + data). Images are written to an alongside directory:
    99 Workspace/_originals/<sha8>_<name>.pdf.images/<page>_<idx>.png
The handler returns the image directory path so the orchestrator can log
it; the handler does NOT move the binary to _originals/ itself.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Primary: pdfplumber ───────────────────────────────────────────────────────
try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

# ── Fallback: pdfminer.six ────────────────────────────────────────────────────
try:
    from pdfminer.high_level import extract_text_to_fp
    from pdfminer.layout import LAParams
    _HAS_PDFMINER = True
except ImportError:
    _HAS_PDFMINER = False

# ── Image: Pillow ─────────────────────────────────────────────────────────────
try:
    from PIL import Image as PILImage
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

from .text import HandlerResult

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

_MIN_TEXT_CHARS = 5   # fewer than this → treat page as scanned


# ──────────────────────────────────────────────────────────────────────────────
# pdfminer page-level fallback
# ──────────────────────────────────────────────────────────────────────────────

def _pdfminer_page_text(pdf_bytes: bytes, page_number: int) -> str:
    """Extract text for a single 1-indexed page using pdfminer.six.

    Returns empty string if pdfminer also finds nothing or if unavailable.
    """
    if not _HAS_PDFMINER:
        return ""
    try:
        out = io.StringIO()
        extract_text_to_fp(
            io.BytesIO(pdf_bytes),
            out,
            page_numbers=[page_number - 1],  # pdfminer is 0-indexed
            laparams=LAParams(),
        )
        return out.getvalue().strip()
    except Exception:
        return ""


# ──────────────────────────────────────────────────────────────────────────────
# Image extraction
# ──────────────────────────────────────────────────────────────────────────────

def _extract_page_images(
    page,  # pdfplumber Page
    page_number: int,
    images_dir: Path,
) -> list[str]:
    """Extract images from a pdfplumber page into images_dir.

    Returns list of relative filenames written (for manifest / warnings).
    Silently skips images that cannot be decoded.
    """
    written: list[str] = []
    if not _HAS_PIL:
        return written

    images_dir.mkdir(parents=True, exist_ok=True)

    for idx, img in enumerate(page.images, start=1):
        try:
            # pdfplumber img dict: keys include 'stream' (PDFStream object)
            stream = img.get("stream")
            if stream is None:
                continue
            raw_data = stream.get_data()
            # Try to decode via Pillow; many PDF images are JPEG or PNG
            pil_img = PILImage.open(io.BytesIO(raw_data))
            ext = pil_img.format.lower() if pil_img.format else "png"
            fname = f"p{page_number:04d}_img{idx:03d}.{ext}"
            dest = images_dir / fname
            pil_img.save(dest)
            written.append(fname)
        except Exception:
            # Non-decodable image (CMYK, JBIG2, etc.) — skip, no crash
            continue

    return written


# ──────────────────────────────────────────────────────────────────────────────
# Main handler
# ──────────────────────────────────────────────────────────────────────────────

def handle_pdf(
    source_path: Path,
    *,
    pipeline_computed: dict,
    pipeline_ns: dict,
    images_dir: Optional[Path] = None,
) -> HandlerResult:
    """Ingest a PDF file.

    Parameters
    ----------
    source_path : Path
        Path to the .pdf file (in _drop/ or staging).
    pipeline_computed : dict
        Top-level fields the pipeline computed (title, extracted_at, …).
    pipeline_ns : dict
        The pipeline: namespace dict.
    images_dir : Path | None
        Destination directory for extracted images. Defaults to
        ``source_path.parent / (source_path.stem + ".pdf.images")``.
        The orchestrator typically sets this to the _originals/ location
        after computing the content hash.

    Returns
    -------
    HandlerResult
        body: markdown string with ## Page N headers.
        frontmatter_top: includes scanned_pages list + page_count.
        pipeline_namespace: includes extractor + warnings.
    """
    if not _HAS_PDFPLUMBER:
        return HandlerResult(
            success=False,
            quarantine=True,
            quarantine_reason="missing_dependency_pdfplumber",
            warnings=["pdfplumber not installed"],
        )

    warnings: list[str] = []
    scanned_pages: list[int] = []
    page_sections: list[str] = []
    total_images_extracted = 0

    # Default images directory alongside source (orchestrator overrides)
    if images_dir is None:
        images_dir = source_path.parent / (source_path.stem + ".pdf.images")

    pdf_bytes = source_path.read_bytes()

    try:
        with pdfplumber.open(source_path) as pdf:
            total_pages = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                # ── Text extraction ────────────────────────────────────────
                text = page.extract_text() or ""
                text = text.strip()

                if len(text) < _MIN_TEXT_CHARS:
                    # pdfplumber found nothing; try pdfminer fallback
                    text = _pdfminer_page_text(pdf_bytes, page_num)

                if len(text) < _MIN_TEXT_CHARS:
                    # Both extractors found nothing → scanned page
                    scanned_pages.append(page_num)
                    page_sections.append(
                        f"## Page {page_num} (scanned — no text extracted)\n"
                    )
                else:
                    page_sections.append(f"## Page {page_num}\n\n{text}\n")

                # ── Image extraction ───────────────────────────────────────
                if page.images:
                    extracted = _extract_page_images(page, page_num, images_dir)
                    total_images_extracted += len(extracted)

    except Exception as exc:
        return HandlerResult(
            success=False,
            quarantine=True,
            quarantine_reason="pdf_extraction_error",
            warnings=[f"pdf_extraction_error: {exc}"],
        )

    # ── Assemble body ─────────────────────────────────────────────────────
    body = "\n".join(page_sections)

    # ── Frontmatter top-level ─────────────────────────────────────────────
    top: dict = {k: v for k, v in pipeline_computed.items()}
    top["file_type"] = "pdf"
    top["page_count"] = total_pages
    top.setdefault("type", "pdf-source")

    if scanned_pages:
        top["scanned_pages"] = scanned_pages
        warnings.append(
            f"scanned_pages: {len(scanned_pages)} of {total_pages} pages had no extractable text"
        )
    else:
        top["scanned_pages"] = []

    # ── Pipeline namespace ────────────────────────────────────────────────
    from .text import _PROVENANCE_VALUE, compute_text_sha256
    pipeline_ns["provenance"] = _PROVENANCE_VALUE
    pipeline_ns["extractor"] = f"pdfplumber@{_pdfplumber_version()}"
    pipeline_ns["image_count"] = total_images_extracted
    pipeline_ns["text_sha256"] = compute_text_sha256(body)   # CH-02
    pipeline_ns["warnings"] = warnings

    return HandlerResult(
        success=True,
        body=body,
        frontmatter_top=top,
        pipeline_namespace=pipeline_ns,
        warnings=warnings,
    )


def _pdfplumber_version() -> str:
    try:
        import importlib.metadata
        return importlib.metadata.version("pdfplumber")
    except Exception:
        return "unknown"
