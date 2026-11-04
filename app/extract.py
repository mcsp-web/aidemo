"""
extract.py — turn an uploaded file into numbered units of text.

Shared by both engines: rag.py (AskDoc, retrieval) and lite.py (AskDoc Lite,
whole document). Moved here unchanged from rag.py so the Lite image can read
documents without importing torch or sentence-transformers.

Each unit is (number, text): real pages for PDF, ~3,000-character "parts" for
formats that have no pages (DOCX, TXT, MD).
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from pypdf import PdfReader

# Target size of one synthesized unit, for formats that have no real pages.
_PSEUDO_PAGE_CHARS = 3000


def _extract_pdf(data: bytes) -> list[tuple[int, str]]:
    """Return a list of (page_number, page_text). Page numbers start at 1."""
    reader = PdfReader(io.BytesIO(data))
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append((i, text))
    return pages


def _paginate(text: str) -> list[tuple[int, str]]:
    """
    Group a flat document into ~_PSEUDO_PAGE_CHARS units, numbered from 1.

    Formats without pages still have to produce the (number, text) shape the
    chunker consumes, and that number is what the UI cites back to the reader —
    so split on blank lines rather than mid-sentence. A single block longer than
    the target becomes its own oversized unit; chunk_pages windows it either way.
    """
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    pages: list[tuple[int, str]] = []
    buf: list[str] = []
    size = 0
    for block in blocks:
        if buf and size + len(block) > _PSEUDO_PAGE_CHARS:
            pages.append((len(pages) + 1, "\n\n".join(buf)))
            buf, size = [], 0
        buf.append(block)
        size += len(block) + 2
    if buf:
        pages.append((len(pages) + 1, "\n\n".join(buf)))
    return pages


def _extract_text(data: bytes) -> list[tuple[int, str]]:
    """Plain text and Markdown: decode, then synthesize units."""
    return _paginate(data.decode("utf-8", errors="replace"))


def _extract_docx(data: bytes) -> list[tuple[int, str]]:
    """Word documents: body paragraphs plus table cells, then synthesize units."""
    # Imported lazily, like the provider SDKs in llm.py, so the rest of this
    # module still works when python-docx isn't installed.
    from docx import Document

    doc = Document(io.BytesIO(data))
    blocks: list[str] = [p.text for p in doc.paragraphs if p.text.strip()]
    # doc.paragraphs skips anything inside a table, so walk those separately.
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))
    return _paginate("\n\n".join(blocks))


# extension -> (extractor, what one unit is called when we cite it)
_EXTRACTORS = {
    ".pdf": (_extract_pdf, "page"),
    ".docx": (_extract_docx, "part"),
    ".txt": (_extract_text, "part"),
    ".md": (_extract_text, "part"),
}


def extract_pages(data: bytes, filename: str) -> tuple[list[tuple[int, str]], str]:
    """
    Dispatch on the file extension.

    Returns (pages, kind): pages is the (number, text) list the chunker expects,
    and kind is "page" for real pages or "part" for synthesized units.
    """
    ext = Path(filename).suffix.lower()
    if ext == ".doc":
        raise ValueError("Legacy .doc isn't supported — please save as .docx.")
    if ext not in _EXTRACTORS:
        raise ValueError(
            f"Unsupported file type '{ext or filename}'. "
            "Supported formats: PDF, DOCX, TXT, MD."
        )
    extractor, kind = _EXTRACTORS[ext]
    return extractor(data), kind


def _clean(text: str) -> str:
    # Collapse runs of whitespace/newlines that PDFs love to produce.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


