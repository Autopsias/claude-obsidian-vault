"""
handlers/docx.py — DOCX ingestion handler.

Contract: 90 System/_ingestion_contract.md §1, §5, §9
HT-03 deliverable (S02).

Uses mammoth's HTML output (convert_to_html) + a stdlib-only HTML→markdown
converter. This approach is necessary because mammoth's convert_to_markdown
does not produce pipe tables or nested list indentation — both required by
the HT-03 spec ("tables (markdown tables)", "lists (nested)").

Preserved features:
  - Heading levels H1–H6
  - Bold / italic inline
  - Lists: ordered + bulleted, nested (via HTML <ul>/<ol>/<li> indentation)
  - Tables → markdown pipe tables
  - Images → extracted to <images_dir> with sequential names
  - Tracked-change-accepted state (mammoth's default)
  - Footnotes / endnotes → [^N] markdown footnotes at end of body
  - Comments → `> [comment by <author>]: <text>` blockquotes (via raw XML)
"""

from __future__ import annotations

import io
import re
import textwrap
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

try:
    import mammoth
    _HAS_MAMMOTH = True
except ImportError:
    _HAS_MAMMOTH = False

try:
    from PIL import Image as PILImage
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

from .text import HandlerResult, _PROVENANCE_VALUE


# ──────────────────────────────────────────────────────────────────────────────
# Mammoth style map
# ──────────────────────────────────────────────────────────────────────────────

_STYLE_MAP = """
p[style-name='Heading 1'] => h1:fresh
p[style-name='Heading 2'] => h2:fresh
p[style-name='Heading 3'] => h3:fresh
p[style-name='Heading 4'] => h4:fresh
p[style-name='Heading 5'] => h5:fresh
p[style-name='Heading 6'] => h6:fresh
p[style-name='heading 1'] => h1:fresh
p[style-name='heading 2'] => h2:fresh
p[style-name='heading 3'] => h3:fresh
p[style-name='Title'] => h1:fresh
p[style-name='Subtitle'] => h2:fresh
r[style-name='Strong'] => strong
r[style-name='Emphasis'] => em
"""


# ──────────────────────────────────────────────────────────────────────────────
# HTML → Markdown converter (stdlib html.parser, no extra deps)
# ──────────────────────────────────────────────────────────────────────────────

class _HtmlToMarkdown(HTMLParser):
    """Convert the HTML that mammoth produces into markdown.

    Handles: h1-h6, p, strong, em, ul/ol/li (nested), table/tr/th/td,
    a (links + footnote refs/defs), sup, br, img (replaced by saved path),
    blockquote.

    Does NOT try to handle arbitrary HTML — only the predictable subset that
    mammoth 1.8.x emits.
    """

    def __init__(self, image_handler=None):
        super().__init__()
        self._buf: list[str] = []          # fragment buffer
        self._output: list[str] = []       # completed lines / blocks
        self._stack: list[str] = []        # open tag stack

        # List state: stack of (tag, indent_level)
        self._list_stack: list[tuple[str, int]] = []
        self._in_li = False
        self._li_buf: list[str] = []

        # Table state
        self._in_table = False
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._cell_buf: list[str] = []
        self._in_cell = False
        self._header_row_done = False

        # Heading
        self._heading_level = 0

        # Link
        self._link_href: str | None = None
        self._link_buf: list[str] = []
        self._in_link = False

        # Image handler: callable(src) → markdown string
        self._image_handler = image_handler

        # Footnote definitions accumulated at end
        self._footnote_defs: list[str] = []

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _flush_buf(self) -> str:
        t = "".join(self._buf).strip()
        self._buf = []
        return t

    def _emit(self, text: str):
        self._output.append(text)

    def _current_list_indent(self) -> int:
        return len(self._list_stack)

    # ── Tag handlers ──────────────────────────────────────────────────────────

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self._stack.append(tag)

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._heading_level = int(tag[1])
            self._buf = []

        elif tag == "p":
            self._buf = []

        elif tag in ("strong", "b"):
            self._buf.append("**")

        elif tag in ("em", "i"):
            self._buf.append("*")

        elif tag == "sup":
            self._buf.append("")  # footnote refs handled in <a>

        elif tag == "br":
            self._buf.append("  \n")

        elif tag in ("ul", "ol"):
            self._list_stack.append((tag, 0))

        elif tag == "li":
            self._in_li = True
            self._li_buf = []

        elif tag == "table":
            self._in_table = True
            self._table_rows = []
            self._current_row = []
            self._header_row_done = False

        elif tag == "tr":
            self._current_row = []

        elif tag in ("th", "td"):
            self._in_cell = True
            self._cell_buf = []

        elif tag == "a":
            href = attrs_dict.get("href", "")
            aid = attrs_dict.get("id", "")
            self._link_href = href
            self._link_buf = []
            self._in_link = True

        elif tag == "img":
            src = attrs_dict.get("src", "")
            alt = attrs_dict.get("alt", "image")
            if self._image_handler:
                md = self._image_handler(src, alt)
            else:
                md = f"![{alt}]({src})"
            self._buf.append(md)

        elif tag == "blockquote":
            self._buf = []

    def handle_endtag(self, tag):
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = self._flush_buf()
            if text:
                prefix = "#" * self._heading_level
                self._emit(f"\n{prefix} {text}\n")
            self._heading_level = 0

        elif tag == "p":
            if self._in_table:
                # Inside a table cell — accumulate
                text = self._flush_buf()
                if self._in_cell:
                    self._cell_buf.append(text)
            elif self._in_li:
                text = self._flush_buf()
                self._li_buf.append(text)
            else:
                text = self._flush_buf()
                if text:
                    self._emit(f"\n{text}\n")

        elif tag in ("strong", "b"):
            self._buf.append("**")

        elif tag in ("em", "i"):
            self._buf.append("*")

        elif tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            if not self._list_stack:
                self._emit("")  # blank line after list end

        elif tag == "li":
            self._in_li = False
            indent = "  " * max(0, len(self._list_stack) - 1)
            list_type = self._list_stack[-1][0] if self._list_stack else "ul"
            bullet = "-" if list_type == "ul" else "1."
            li_text = " ".join(self._li_buf).strip()
            # Also include anything in _buf (inline content not in nested <p>)
            buf_text = self._flush_buf().strip()
            combined = " ".join(filter(None, [li_text, buf_text]))
            self._emit(f"{indent}{bullet} {combined}")
            self._li_buf = []

        elif tag in ("th", "td"):
            self._in_cell = False
            cell_text = " ".join(self._cell_buf).strip()
            # Also any buffered inline content
            buf_text = self._flush_buf().strip()
            combined = " ".join(filter(None, [cell_text, buf_text])) or " "
            self._current_row.append(combined.replace("|", "\\|"))
            self._cell_buf = []

        elif tag == "tr":
            self._table_rows.append(list(self._current_row))
            self._current_row = []

        elif tag == "table":
            self._in_table = False
            md_table = self._render_table(self._table_rows)
            self._emit("\n" + md_table + "\n")
            self._table_rows = []

        elif tag == "a":
            self._in_link = False
            href = self._link_href or ""
            text = "".join(self._link_buf).strip()
            # Footnote reference pattern: href="#footnote-N"
            if href.startswith("#footnote-") and not href.startswith("#footnote-ref"):
                fn_id = href.replace("#footnote-", "")
                self._buf.append(f"[^{fn_id}]")
            # Footnote back-ref: href="#footnote-ref-N" → skip (just arrow)
            elif href.startswith("#footnote-ref-"):
                pass
            elif href:
                self._buf.append(f"[{text}]({href})")
            else:
                self._buf.append(text)
            self._link_href = None
            self._link_buf = []

        elif tag == "blockquote":
            text = self._flush_buf()
            if text:
                quoted = "\n".join(f"> {line}" for line in text.splitlines())
                self._emit(f"\n{quoted}\n")

    def handle_data(self, data):
        if self._in_link:
            self._link_buf.append(data)
        elif self._in_cell:
            self._cell_buf.append(data)
        elif self._in_li:
            self._li_buf.append(data)
        else:
            self._buf.append(data)

    # ── Table rendering ───────────────────────────────────────────────────────

    @staticmethod
    def _render_table(rows: list[list[str]]) -> str:
        if not rows:
            return ""
        # Determine column count from widest row
        ncols = max(len(r) for r in rows)
        # Pad rows
        padded = [r + [""] * (ncols - len(r)) for r in rows]
        # Compute column widths
        widths = [
            max(len(padded[row_i][col_i]) for row_i in range(len(padded)))
            for col_i in range(ncols)
        ]
        widths = [max(w, 3) for w in widths]

        def fmt_row(cells):
            return "| " + " | ".join(
                c.ljust(widths[i]) for i, c in enumerate(cells)
            ) + " |"

        lines = []
        for i, row in enumerate(padded):
            lines.append(fmt_row(row))
            if i == 0:
                # Header separator
                lines.append("| " + " | ".join("-" * widths[j] for j in range(ncols)) + " |")
        return "\n".join(lines)

    # ── Result ────────────────────────────────────────────────────────────────

    def get_markdown(self) -> str:
        # Flush anything remaining in buf
        remainder = self._flush_buf()
        if remainder:
            self._output.append(remainder)
        text = "\n".join(self._output)
        # Clean up: collapse 3+ consecutive blank lines to 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_markdown(html: str, image_handler=None) -> str:
    """Convert mammoth-generated HTML to markdown."""
    parser = _HtmlToMarkdown(image_handler=image_handler)
    parser.feed(html)
    return parser.get_markdown()


# ──────────────────────────────────────────────────────────────────────────────
# Image conversion callback for mammoth
# ──────────────────────────────────────────────────────────────────────────────

class _ImageCollector:
    """Mammoth image handler: saves images, returns src path for HTML."""

    def __init__(self, images_dir: Path):
        self.images_dir = images_dir
        self.count = 0
        self._src_map: dict[str, str] = {}  # src → saved filename

    def mammoth_handler(self, image):
        """Called by mammoth for each embedded image."""
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.count += 1
        content_type = image.content_type or "image/png"
        ext = content_type.split("/")[-1].split(";")[0].strip() or "png"
        fname = f"img{self.count:03d}.{ext}"
        dest = self.images_dir / fname
        with image.open() as img_stream:
            dest.write_bytes(img_stream.read())
        return {"src": str(dest)}

    def markdown_handler(self, src: str, alt: str) -> str:
        """Called by the HTML→MD converter to turn <img src=…> into ![alt](path)."""
        return f"![{alt}]({src})"


# ──────────────────────────────────────────────────────────────────────────────
# Comment extraction from raw OOXML (zip-based, no extra deps)
# ──────────────────────────────────────────────────────────────────────────────

def _extract_comments_from_docx(docx_path: Path) -> list[dict]:
    """Return list of dicts: {author, date, id, text}."""
    try:
        import zipfile
        import xml.etree.ElementTree as ET

        comments: list[dict] = []
        W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

        with zipfile.ZipFile(docx_path) as zf:
            if "word/comments.xml" not in zf.namelist():
                return []
            root = ET.fromstring(zf.read("word/comments.xml"))
            for comment in root.findall(f"{{{W}}}comment"):
                cid = comment.get(f"{{{W}}}id", "")
                author = comment.get(f"{{{W}}}author", "Unknown")
                date = comment.get(f"{{{W}}}date", "")
                texts = [t.text or "" for t in comment.findall(f".//{{{W}}}t")]
                text = " ".join(texts).strip()
                comments.append({"id": cid, "author": author, "date": date, "text": text})
        return comments
    except Exception:
        return []


# ──────────────────────────────────────────────────────────────────────────────
# Comment injection into body
# ──────────────────────────────────────────────────────────────────────────────

def _append_comments_section(body: str, comments: list[dict]) -> str:
    """Append `## Comments` section with blockquote entries."""
    if not comments:
        return body
    lines = ["\n\n## Comments\n"]
    for c in comments:
        author = c.get("author", "Unknown")
        text = c.get("text", "").replace("\n", " ")
        lines.append(f"> [comment by {author}]: {text}\n")
    return body + "".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Footnote post-processing (mammoth emits [^N] via our HTML converter)
# ──────────────────────────────────────────────────────────────────────────────

def _reformat_footnotes(markdown: str) -> str:
    """Ensure footnote defs are in [^N]: form.

    mammoth emits footnote definitions as numbered list items at the end:
      1. <a id="footnote-1"></a>text [↑](#footnote-ref-1)
    Our HTML→MD converter emits them as plain list items with a [^N] ref.
    This function finds definitions and reformats them.
    """
    # Our converter already emits [^N] refs inline; definitions appear as
    # list items: "1. text ↑" at end. Convert "1. <text>" → "[^1]: <text>"
    def replace_def(m):
        num = m.group(1)
        text = m.group(2).strip()
        # Strip the back-ref arrow if present (↑ or ↑)
        text = re.sub(r"\s*↑.*$", "", text).strip()
        return f"[^{num}]: {text}"

    markdown = re.sub(r"^(\d+)\.\s+(.+)$", replace_def, markdown, flags=re.MULTILINE)
    return markdown


# ──────────────────────────────────────────────────────────────────────────────
# Feature-counting helpers
# ──────────────────────────────────────────────────────────────────────────────

def _count_markdown_tables(body: str) -> int:
    """Count markdown tables by counting separator rows (|---|)."""
    return len(re.findall(r"^\|[-| :]+\|", body, re.MULTILINE))


def _max_list_depth(body: str) -> int:
    """Maximum nesting depth of markdown lists (1-based). 0 if no lists."""
    max_depth = 0
    for line in body.splitlines():
        m = re.match(r"^([ \t]*)(?:[-*+]|\d+\.)\s", line)
        if m:
            indent = m.group(1).replace("\t", "    ")
            depth = 1 + len(indent) // 2
            max_depth = max(max_depth, depth)
    return max_depth


def _mammoth_version() -> str:
    try:
        import importlib.metadata
        return importlib.metadata.version("mammoth")
    except Exception:
        return "unknown"


# ──────────────────────────────────────────────────────────────────────────────
# Main handler
# ──────────────────────────────────────────────────────────────────────────────

def handle_docx(
    source_path: Path,
    *,
    pipeline_computed: dict,
    pipeline_ns: dict,
    images_dir: Optional[Path] = None,
) -> HandlerResult:
    """Ingest a DOCX file.

    Parameters
    ----------
    source_path : Path
    pipeline_computed : dict
    pipeline_ns : dict
    images_dir : Path | None
        Defaults to ``source_path.parent / (source_path.stem + ".docx.images")``.
    """
    if not _HAS_MAMMOTH:
        return HandlerResult(
            success=False,
            quarantine=True,
            quarantine_reason="missing_dependency_mammoth",
            warnings=["mammoth not installed"],
        )

    warnings: list[str] = []

    if images_dir is None:
        images_dir = source_path.parent / (source_path.stem + ".docx.images")

    # ── Comment extraction (raw XML, before mammoth) ──────────────────────
    comments = _extract_comments_from_docx(source_path)

    # ── Image collector ────────────────────────────────────────────────────
    img_collector = _ImageCollector(images_dir)

    # ── Mammoth: convert to HTML (preserves tables + nested lists) ─────────
    try:
        with source_path.open("rb") as docx_file:
            result = mammoth.convert_to_html(
                docx_file,
                style_map=_STYLE_MAP,
                convert_image=mammoth.images.img_element(img_collector.mammoth_handler),
            )
        html = result.value
        mammoth_msgs = [str(m) for m in result.messages]
        # Filter out expected warnings about missing footnote styles
        for msg in mammoth_msgs:
            if "FootnoteText" not in msg and "footnote" not in msg.lower():
                warnings.append(msg)

    except Exception as exc:
        return HandlerResult(
            success=False,
            quarantine=True,
            quarantine_reason="docx_extraction_error",
            warnings=[f"docx_extraction_error: {exc}"],
        )

    # ── Convert HTML → markdown ────────────────────────────────────────────
    body = html_to_markdown(html, image_handler=img_collector.markdown_handler)

    # ── Post-process: reformat footnote definitions ────────────────────────
    body = _reformat_footnotes(body)

    # ── Append comments section ────────────────────────────────────────────
    body = _append_comments_section(body, comments)

    # ── Count features ─────────────────────────────────────────────────────
    table_count = _count_markdown_tables(body)
    footnote_count = len(re.findall(r"\[\^\w+\]:", body))
    list_nesting_depth = _max_list_depth(body)

    # ── Frontmatter ────────────────────────────────────────────────────────
    top: dict = {k: v for k, v in pipeline_computed.items()}
    top["file_type"] = "docx"
    top.setdefault("type", "working-document")
    top["page_count"] = None

    # ── Pipeline namespace ─────────────────────────────────────────────────
    from .text import compute_text_sha256   # CH-02
    pipeline_ns["provenance"] = _PROVENANCE_VALUE
    pipeline_ns["extractor"] = f"mammoth@{_mammoth_version()}"
    pipeline_ns["image_count"] = img_collector.count
    pipeline_ns["comment_count"] = len(comments)
    pipeline_ns["table_count"] = table_count
    pipeline_ns["footnote_count"] = footnote_count
    pipeline_ns["list_nesting_depth"] = list_nesting_depth
    pipeline_ns["text_sha256"] = compute_text_sha256(body)   # CH-02
    pipeline_ns["warnings"] = warnings

    return HandlerResult(
        success=True,
        body=body,
        frontmatter_top=top,
        pipeline_namespace=pipeline_ns,
        warnings=warnings,
    )
