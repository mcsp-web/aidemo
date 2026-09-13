"""
rag.py — the retrieval half of the system.

Pipeline:
  file bytes -> extract text (PDF / DOCX / TXT / MD) -> split into overlapping
           chunks -> embed each chunk into a vector -> keep vectors in memory
  question  -> embed -> cosine-similarity search -> return top matching chunks

Embeddings run locally with a small sentence-transformers model, so there is
no per-query cost and no second API vendor. The only external call in the whole
app is the final answer generation (see llm.py).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

# Small, fast, well-proven embedding model (~90MB). Downloaded once, then cached.
_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Loaded lazily so importing this module (e.g. in tests) is cheap.
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_EMBED_MODEL_NAME)
    return _model


@dataclass
class Chunk:
    text: str
    page: int


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


def chunk_pages(
    pages: list[tuple[int, str]],
    chunk_size: int = 900,
    overlap: int = 150,
) -> list[Chunk]:
    """
    Split each page's text into overlapping windows of ~chunk_size characters.
    Overlap keeps sentences that straddle a boundary retrievable from either side.
    """
    chunks: list[Chunk] = []
    for page_no, raw in pages:
        text = _clean(raw)
        if not text:
            continue
        start = 0
        while start < len(text):
            end = start + chunk_size
            window = text[start:end]
            # Try not to cut mid-sentence: back up to the last period if we can.
            if end < len(text):
                last_period = window.rfind(". ")
                if last_period > chunk_size * 0.5:
                    window = window[: last_period + 1]
                    end = start + last_period + 1
            window = window.strip()
            if window:
                chunks.append(Chunk(text=window, page=page_no))
            start = end - overlap
            if start <= 0:
                start = end
    return chunks


class DocumentIndex:
    """Holds the chunks and their embeddings for one uploaded document."""

    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.vectors: np.ndarray | None = None
        self.filename: str | None = None
        # How to label a chunk's number when citing it: "page" or "part".
        self.kind: str = "page"

    @property
    def ready(self) -> bool:
        return self.vectors is not None and len(self.chunks) > 0

    def build(self, data: bytes, filename: str) -> int:
        # Build into locals only. If extraction, chunking or embedding raises,
        # self is untouched — a document already loaded stays queryable, and a
        # first failed upload leaves the index empty rather than half-built.
        pages, kind = extract_pages(data, filename)
        chunks = chunk_pages(pages)
        if not chunks:
            if kind == "page":
                raise ValueError(
                    "No readable text found. This looks like a scanned PDF — "
                    "it would need OCR first."
                )
            raise ValueError("No readable text found in this file.")
        model = _get_model()
        embeddings = model.encode(
            [c.text for c in chunks],
            normalize_embeddings=True,  # lets us use a plain dot product for cosine
            show_progress_bar=False,
        )
        vectors = np.asarray(embeddings, dtype=np.float32)

        # Commit as one final step, once nothing left can fail.
        self.chunks = chunks
        self.vectors = vectors
        self.kind = kind
        self.filename = filename
        return len(chunks)

    def search(self, question: str, top_k: int = 4) -> list[tuple[Chunk, float]]:
        if not self.ready:
            raise RuntimeError("No document indexed yet.")
        model = _get_model()
        q = model.encode([question], normalize_embeddings=True)[0].astype(np.float32)
        scores = self.vectors @ q  # cosine similarity (vectors are normalized)
        top = np.argsort(scores)[::-1][:top_k]
        return [(self.chunks[i], float(scores[i])) for i in top]
