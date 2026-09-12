"""
rag.py — the retrieval half of the system.

Pipeline:
  PDF bytes -> extract text -> split into overlapping chunks
           -> embed each chunk into a vector -> keep vectors in memory
  question  -> embed -> cosine-similarity search -> return top matching chunks

Embeddings run locally with a small sentence-transformers model, so there is
no per-query cost and no second API vendor. The only external call in the whole
app is the final answer generation (see llm.py).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

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


def extract_text_by_page(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """Return a list of (page_number, page_text). Page numbers start at 1."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append((i, text))
    return pages


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

    @property
    def ready(self) -> bool:
        return self.vectors is not None and len(self.chunks) > 0

    def build(self, pdf_bytes: bytes, filename: str) -> int:
        pages = extract_text_by_page(pdf_bytes)
        self.chunks = chunk_pages(pages)
        if not self.chunks:
            raise ValueError(
                "No readable text found. This looks like a scanned PDF — "
                "it would need OCR first."
            )
        model = _get_model()
        embeddings = model.encode(
            [c.text for c in self.chunks],
            normalize_embeddings=True,  # lets us use a plain dot product for cosine
            show_progress_bar=False,
        )
        self.vectors = np.asarray(embeddings, dtype=np.float32)
        self.filename = filename
        return len(self.chunks)

    def search(self, question: str, top_k: int = 4) -> list[tuple[Chunk, float]]:
        if not self.ready:
            raise RuntimeError("No document indexed yet.")
        model = _get_model()
        q = model.encode([question], normalize_embeddings=True)[0].astype(np.float32)
        scores = self.vectors @ q  # cosine similarity (vectors are normalized)
        top = np.argsort(scores)[::-1][:top_k]
        return [(self.chunks[i], float(scores[i])) for i in top]
