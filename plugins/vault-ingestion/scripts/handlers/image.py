"""
handlers/image.py — Image ingestion handler.

Contract: 90 System/_ingestion_contract.md §1, §2, §5, §9
HR-03 deliverable (S03).
Policy: 70 Decisions/2026-05-13_image_ocr_egress_policy.md

Supported formats: .png, .jpg, .jpeg, .webp, .heic, .heif, .gif, .bmp, .tiff

DEFAULT mode — Tesseract local OCR (pytesseract):
  Always used unless all three conditions hold:
    1. `--allow-cloud-ocr` flag passed to the pipeline run
    2. Filename does NOT match the `*.confidential.*` glob
    3. config.yaml `cloud_ocr.model` is configured

CLOUD mode — Anthropic Vision API (opt-in):
  Used only when all three conditions above hold.
  Model name read from `config.yaml` cloud_ocr.model — NEVER hardcoded.
  Per-call audit log: `99 Workspace/_cloud_ocr_audit.jsonl` (one JSON line per call).
  `--max-api-calls N` cap enforced; pipeline refuses further cloud calls on breach
  with a HARD ALERT marker (not an exception — Tesseract fallback kicks in).

Output markdown structure (contract §4 extended for images):
    ## OCR (verbatim)
    <raw OCR text>

    ## Description
    <single-sentence description of the image>

    ![<filename>](<embed_path or filename>)

HEIC support: pillow-heif registered with Pillow before open.

Error handling:
  - OCR errors: message redacted in output (no raw exception text that may
    contain path info); warning logged; body contains the ## OCR section with
    a single `[OCR failed]` line.
  - Cloud errors: redacted similarly; Tesseract fallback kicks in automatically.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from PIL import Image as PILImage
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

try:
    import pytesseract
    _HAS_TESSERACT = True
except ImportError:
    _HAS_TESSERACT = False

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    _HAS_HEIF = True
except ImportError:
    _HAS_HEIF = False

from .text import HandlerResult, _PROVENANCE_VALUE

# ──────────────────────────────────────────────────────────────────────────────
# Config helpers
# ──────────────────────────────────────────────────────────────────────────────

_CONFIG_SEARCH_DIRS = [
    # Search relative to this file's location (the pipeline package dir)
    Path(__file__).parent.parent,
    # Also check one level up (vault root)
    Path(__file__).parent.parent.parent,
]

_CONFIDENTIAL_GLOB = "*.confidential.*"


def _load_config(config_path: Optional[Path] = None) -> dict:
    """Load pipeline config.yaml.

    If config_path is explicitly supplied, only that path is tried (caller's
    intent takes precedence — don't fall through to default dirs).
    If config_path is None, searches _CONFIG_SEARCH_DIRS in order.
    Returns empty dict if no config found (Tesseract-only mode).
    """
    if config_path is not None:
        search_paths = [config_path]
    else:
        search_paths = [p / "config.yaml" for p in _CONFIG_SEARCH_DIRS]

    for candidate in search_paths:
        if candidate.exists():
            try:
                import yaml  # PyYAML — optional; only needed for cloud OCR
                with candidate.open(encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except ImportError:
                # yaml not installed — read manually for the simple key we need
                text = candidate.read_text(encoding="utf-8")
                # Look for cloud_ocr.model: <value>
                m = re.search(r"cloud_ocr\s*:\s*\n\s+model\s*:\s*(.+)", text)
                if m:
                    return {"cloud_ocr": {"model": m.group(1).strip().strip("\"'")}}
                return {}
            except Exception:
                return {}
    return {}


def _cloud_ocr_model(config: dict) -> Optional[str]:
    """Extract cloud_ocr.model from config. None if not set."""
    return (config.get("cloud_ocr") or {}).get("model") or None


def _is_confidential(filename: str) -> bool:
    """Return True if filename matches the *.confidential.* glob."""
    return fnmatch.fnmatch(filename, _CONFIDENTIAL_GLOB)


def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pytesseract_version() -> str:
    try:
        import importlib.metadata
        return importlib.metadata.version("pytesseract")
    except Exception:
        return "unknown"


def _pillow_version() -> str:
    try:
        import importlib.metadata
        return importlib.metadata.version("Pillow")
    except Exception:
        return "unknown"


# ──────────────────────────────────────────────────────────────────────────────
# Cloud OCR audit log
# ──────────────────────────────────────────────────────────────────────────────

_AUDIT_LOG_SEARCH_DIRS = [
    Path(__file__).parent.parent.parent,  # vault root / 99 Workspace relative
]


def _audit_log_path() -> Path:
    """Return the path to the cloud OCR audit log.

    Resolves to 99 Workspace/_cloud_ocr_audit.jsonl relative to the vault root.
    """
    for d in _AUDIT_LOG_SEARCH_DIRS:
        candidate = d / "99 Workspace" / "_cloud_ocr_audit.jsonl"
        if candidate.parent.exists():
            return candidate
    # Fallback: write next to the handler package
    return Path(__file__).parent.parent / "_cloud_ocr_audit.jsonl"


def _append_audit_entry(
    filename: str,
    model: str,
    sha256: str,
    tokens_in: int,
    tokens_out: int,
    success: bool,
    error_code: Optional[str] = None,
) -> None:
    """Append a single JSON line to the cloud OCR audit log."""
    entry = {
        "ts": _now_utc(),
        "filename": filename,
        "model": model,
        "sha256_prefix": sha256[:16],  # enough for correlation, not full hash
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "success": success,
        "error_code": error_code,
    }
    log_path = _audit_log_path()
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Audit log failure must not break the pipeline


# ──────────────────────────────────────────────────────────────────────────────
# Image file SHA-256
# ──────────────────────────────────────────────────────────────────────────────

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# Tesseract OCR
# ──────────────────────────────────────────────────────────────────────────────

def _ocr_tesseract(img: "PILImage.Image") -> tuple[str, list[str]]:
    """Run Tesseract OCR on an already-open PIL Image.

    Returns (ocr_text, warnings).
    On failure: ocr_text = "[OCR failed]", warnings populated with redacted error.
    """
    warnings: list[str] = []
    try:
        text = pytesseract.image_to_string(img)
        return text.strip(), warnings
    except Exception:
        # Redacted: no raw exception text (may contain path info)
        warnings.append("tesseract_ocr_failed: OCR error — check Tesseract installation")
        return "[OCR failed]", warnings


# ──────────────────────────────────────────────────────────────────────────────
# Cloud Vision OCR (Anthropic)
# ──────────────────────────────────────────────────────────────────────────────

def _ocr_cloud(
    img_path: Path,
    model: str,
    file_sha256: str,
) -> tuple[str, str, int, int, Optional[str]]:
    """Run cloud Vision OCR via Anthropic API.

    Returns:
        (ocr_text, description, tokens_in, tokens_out, error_code)
    error_code is None on success; a short string like "api_error" on failure.
    """
    try:
        import anthropic
        import base64
    except ImportError:
        return "[OCR failed]", "", 0, 0, "missing_dependency_anthropic"

    # Read image as base64
    img_bytes = img_path.read_bytes()
    b64 = base64.standard_b64encode(img_bytes).decode("ascii")

    # Detect media type from suffix
    suffix = img_path.suffix.lower().lstrip(".")
    media_type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    media_type = media_type_map.get(suffix, "image/png")

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Please perform two tasks on this image:\n"
                                "1. OCR: Extract all visible text verbatim, preserving line breaks. "
                                "Output it between <ocr> and </ocr> tags.\n"
                                "2. Description: Write one sentence describing what this image shows. "
                                "Output it between <description> and </description> tags."
                            ),
                        },
                    ],
                }
            ],
        )

        full_text = response.content[0].text if response.content else ""
        tokens_in = response.usage.input_tokens if response.usage else 0
        tokens_out = response.usage.output_tokens if response.usage else 0

        # Parse OCR and description from tagged output
        ocr_match = re.search(r"<ocr>(.*?)</ocr>", full_text, re.DOTALL)
        desc_match = re.search(r"<description>(.*?)</description>", full_text, re.DOTALL)

        ocr_text = ocr_match.group(1).strip() if ocr_match else full_text.strip()
        description = desc_match.group(1).strip() if desc_match else ""

        return ocr_text, description, tokens_in, tokens_out, None

    except Exception:
        # Redacted error — no exception text (may contain API keys, paths)
        return "[OCR failed]", "", 0, 0, "api_error"


# ──────────────────────────────────────────────────────────────────────────────
# Simple image description via Tesseract metadata (no cloud)
# ──────────────────────────────────────────────────────────────────────────────

def _local_description(img: "PILImage.Image", filename: str) -> str:
    """Generate a minimal one-sentence description from image metadata only.

    No cloud call — just mode, size, format for a human-readable label.
    """
    mode = img.mode or "unknown"
    w, h = img.size
    fmt = img.format or Path(filename).suffix.lstrip(".").upper() or "image"
    return f"{fmt} image, {w}×{h} px, mode {mode}."


# ──────────────────────────────────────────────────────────────────────────────
# Main handler
# ──────────────────────────────────────────────────────────────────────────────

def handle_image(
    source_path: Path,
    *,
    pipeline_computed: dict,
    pipeline_ns: dict,
    allow_cloud_ocr: bool = False,
    max_api_calls: Optional[int] = None,
    api_calls_used: Optional[list] = None,  # mutable list; caller passes [0] to track
    config_path: Optional[Path] = None,
) -> HandlerResult:
    """Ingest an image file (.png, .jpg, .jpeg, .webp, .heic, .heif, .gif, .bmp, .tiff).

    Parameters
    ----------
    source_path : Path
        Path to the image file.
    pipeline_computed : dict
        Top-level fields the pipeline computed.
    pipeline_ns : dict
        The pipeline: namespace dict.
    allow_cloud_ocr : bool
        Whether the pipeline was invoked with --allow-cloud-ocr.
    max_api_calls : int | None
        Maximum cloud API calls per pipeline run. None = no cap.
    api_calls_used : list | None
        Mutable [int] counter shared across calls in a pipeline run.
        If None, cloud cap enforcement is disabled (single-call mode).
    config_path : Path | None
        Explicit path to config.yaml. Searched in default dirs if None.

    Output structure
    ----------------
    ## OCR (verbatim)

    <ocr text>

    ## Description

    <description sentence>

    ![<filename>](<filename>)
    """
    if not _HAS_PIL:
        return HandlerResult(
            success=False,
            quarantine=True,
            quarantine_reason="missing_dependency_pillow",
            warnings=["Pillow not installed"],
        )

    warnings: list[str] = []
    filename = source_path.name

    # ── SHA-256 (for audit log) ────────────────────────────────────────────
    try:
        file_sha256 = _sha256_file(source_path)
    except Exception:
        file_sha256 = "unknown"

    # ── Open image ─────────────────────────────────────────────────────────
    # HEIC: pillow-heif registers itself as an opener on import (top of file)
    try:
        img = PILImage.open(str(source_path))
        img.load()  # force decode
        img_format = img.format or source_path.suffix.lstrip(".").upper()
        img_width, img_height = img.size
        img_mode = img.mode
    except Exception:
        return HandlerResult(
            success=False,
            quarantine=True,
            quarantine_reason="image_open_error",
            warnings=["image_open_error: could not open image (format unsupported or corrupt)"],
        )

    # ── Decide OCR mode ────────────────────────────────────────────────────
    # Cloud mode requires ALL THREE:
    #   1. allow_cloud_ocr is True
    #   2. filename does NOT match *.confidential.*
    #   3. config has cloud_ocr.model set
    use_cloud = False
    cloud_model: Optional[str] = None

    if allow_cloud_ocr and not _is_confidential(filename):
        config = _load_config(config_path)
        cloud_model = _cloud_ocr_model(config)
        if cloud_model:
            # Check API call cap
            if max_api_calls is not None and api_calls_used is not None:
                if api_calls_used[0] >= max_api_calls:
                    warnings.append(
                        f"cloud_ocr_cap_reached: max_api_calls={max_api_calls} "
                        f"already consumed; falling back to Tesseract"
                    )
                    # HARD ALERT marker in pipeline_ns (checked at session bootstrap)
                    pipeline_ns["cloud_ocr_cap_alert"] = (
                        f"HARD_ALERT: cloud OCR cap of {max_api_calls} calls reached "
                        f"during this pipeline run"
                    )
                else:
                    use_cloud = True
            else:
                use_cloud = True

    # ── OCR ───────────────────────────────────────────────────────────────
    if use_cloud:
        # Convert HEIC/non-web-format to PNG in memory before sending to API
        api_path = source_path
        _tmp_converted = None
        if source_path.suffix.lower() in (".heic", ".heif", ".bmp", ".tiff"):
            import io as _io
            buf = _io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            # Write to a temp path that won't persist (caller's staging dir)
            _tmp_path = source_path.parent / (source_path.stem + "_converted_for_api.png")
            _tmp_path.write_bytes(buf.getvalue())
            api_path = _tmp_path
            _tmp_converted = _tmp_path

        ocr_text, description, tok_in, tok_out, error_code = _ocr_cloud(
            api_path, cloud_model, file_sha256
        )

        # Clean up converted temp file
        if _tmp_converted and _tmp_converted.exists():
            try:
                _tmp_converted.unlink()
            except Exception:
                pass

        # Audit log (always, success or failure)
        _append_audit_entry(
            filename=filename,
            model=cloud_model,
            sha256=file_sha256,
            tokens_in=tok_in,
            tokens_out=tok_out,
            success=(error_code is None),
            error_code=error_code,
        )

        if error_code is not None:
            warnings.append(f"cloud_ocr_error: {error_code}; fell back to Tesseract")
            # Fall back to Tesseract
            use_cloud = False

        if use_cloud and api_calls_used is not None:
            api_calls_used[0] += 1

        if use_cloud:
            ocr_mode = "cloud"
        else:
            # Tesseract fallback after cloud failure
            if not _HAS_TESSERACT:
                warnings.append("tesseract_not_installed: cloud failed, no fallback available")
                ocr_text = "[OCR failed]"
                description = _local_description(img, filename)
            else:
                ocr_text, tess_warnings = _ocr_tesseract(img)
                warnings.extend(tess_warnings)
                description = _local_description(img, filename)
            ocr_mode = "tesseract_fallback"

    else:
        # Tesseract (default)
        if not _HAS_TESSERACT:
            warnings.append("tesseract_not_installed: install pytesseract + Tesseract binary")
            ocr_text = "[OCR failed — Tesseract not installed]"
        else:
            ocr_text, tess_warnings = _ocr_tesseract(img)
            warnings.extend(tess_warnings)

        description = _local_description(img, filename)
        ocr_mode = "tesseract"

    # ── Build body ─────────────────────────────────────────────────────────
    body_parts: list[str] = [
        "## OCR (verbatim)",
        "",
        ocr_text if ocr_text else "[no text detected]",
        "",
        "## Description",
        "",
        description or f"{filename} — no description available.",
        "",
        f"![{filename}]({filename})",
    ]
    body = "\n".join(body_parts)

    # ── Frontmatter ────────────────────────────────────────────────────────
    top: dict = {k: v for k, v in pipeline_computed.items()}
    top["file_type"] = source_path.suffix.lstrip(".").lower()
    top.setdefault("type", "image-ocr")
    top["page_count"] = None  # not applicable to images

    # ── Pipeline namespace ─────────────────────────────────────────────────
    from .text import compute_text_sha256   # CH-02
    # Image content hash uses OCR text (the extracted content) if present and
    # not an error marker; otherwise empty string (contract: "no content hash
    # possible" — image with no OCR produces deterministic sha256("")).
    _ocr_for_hash = (
        ocr_text
        if ocr_text and ocr_text not in ("[OCR failed]", "[OCR failed — Tesseract not installed]",
                                         "[no text detected]")
        else ""
    )
    pipeline_ns["provenance"] = _PROVENANCE_VALUE
    pipeline_ns["extractor"] = (
        f"pytesseract@{_pytesseract_version()}+Pillow@{_pillow_version()}"
        if ocr_mode in ("tesseract", "tesseract_fallback")
        else f"anthropic-vision/{cloud_model}+Pillow@{_pillow_version()}"
    )
    pipeline_ns["ocr_mode"] = ocr_mode
    pipeline_ns["image_width"] = img_width
    pipeline_ns["image_height"] = img_height
    pipeline_ns["image_mode"] = img_mode
    pipeline_ns["image_format"] = img_format
    pipeline_ns["confidential"] = _is_confidential(filename)
    pipeline_ns["text_sha256"] = compute_text_sha256(_ocr_for_hash)   # CH-02
    pipeline_ns["warnings"] = warnings

    if use_cloud and cloud_model:
        pipeline_ns["cloud_model"] = cloud_model

    return HandlerResult(
        success=True,
        body=body,
        frontmatter_top=top,
        pipeline_namespace=pipeline_ns,
        warnings=warnings,
    )
