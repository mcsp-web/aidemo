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

import re
from dataclasses import dataclass

import numpy as np
from sentence_transformers import SentenceTransformer

# Extraction lives in extract.py (shared with AskDoc Lite); re-exported here so
# existing imports of these names from app.rag keep working.
from .extract import (  # noqa: F401
    _EXTRACTORS,
    _PSEUDO_PAGE_CHARS,
    _clean,
    _extract_docx,
    _extract_pdf,
    _extract_text,
    _paginate,
    extract_pages,
)

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
