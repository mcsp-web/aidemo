"""
lite.py — AskDoc Lite: the whole-document engine.

No embeddings, no vector search, no torch. Every file in a visitor's library is
sent to Claude as its own "custom content" document, one content block per page
(or per part for DOCX/TXT/MD), with Claude's built-in citations switched on. Each
citation names the document and the block it came from, which map straight to a
file name and a page number.

The document blocks are marked for prompt caching, so after the first question
the library is re-read from cache at a fraction of the normal input price.

Trade-off against the RAG engine (rag.py): Lite reads everything on every
question, so it handles summaries and questions that join several files well and
needs a tiny server, but the library is capped by how much text fits in one
request. Large document libraries are what the RAG engine is for.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .extract import _clean, extract_pages

SYSTEM_PROMPT = (
    "You answer questions about the documents provided, using only those documents. "
    "If the answer is not in the documents, say you couldn't find it in the documents "
    "rather than guessing. When a question needs a calculation, say which figures from "
    "the documents you used and why. If the documents do not cover the exact situation "
    "asked about, say so before giving the closest answer they support. If two documents "
    "disagree, say so and give both. Be concise: answer in about 150 words or fewer "
    "unless the question asks for detail. Quote figures exactly, and write plain text "
    "without Markdown formatting. Answer in the language the question is asked in, even when the "
    "documents are in another language; keep quoted passages as they are written."
)

NOT_FOUND = "I couldn't find that in the documents."
CUT_SHORT = "(Answer shortened. Ask a narrower question for more detail.)"


def end_cleanly(text: str) -> str:
    """An answer stopped by the length limit ends mid-sentence: keep the complete
    sentences and say it was shortened."""
    cut = max(text.rfind(". "), text.rfind(".\n"), text.rfind("? "), text.rfind("! "))
    if text.rstrip().endswith((".", "?", "!")):
        cut = len(text.rstrip()) - 1
    kept = text[: cut + 1].rstrip() if cut > 0 else text.rstrip()
    return f"{kept}\n\n{CUT_SHORT}"


def max_chars() -> int:
    # About 4 characters per token: 400,000 characters is roughly 100k tokens,
    # or around 200 typical pages, across all of a visitor's files together.
    return int(os.getenv("LITE_MAX_CHARS", "400000"))


def max_files() -> int:
    return int(os.getenv("LITE_MAX_FILES", "5"))


def model() -> str:
    return os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")


class TooLarge(ValueError):
    """The library would hold more text than one request can carry."""


class TooMany(ValueError):
    """The library already holds the most files allowed."""


@dataclass
class LiteFile:
    """One readable file: its name, how to label its units, and their text."""

    filename: str
    kind: str  # "page" (PDF) or "part" (synthesized units for DOCX/TXT/MD)
    units: list[tuple[int, str]]

    @property
    def chars(self) -> int:
        return sum(len(t) for _, t in self.units)

    def summary(self) -> dict:
        return {"filename": self.filename, "chunks": len(self.units), "kind": self.kind}


def read_file(data: bytes, filename: str) -> LiteFile:
    """Extract and clean a file, or explain why it can't be read."""
    pages, kind = extract_pages(data, filename)
    units = [(n, _clean(t)) for n, t in pages]
    units = [(n, t) for n, t in units if t]
    if not units:
        if kind == "page":
            raise ValueError(
                "No readable text found. This looks like a scanned PDF — "
                "it would need OCR first."
            )
        raise ValueError("No readable text found in this file.")
    return LiteFile(filename=filename, kind=kind, units=units)


def _too_large(total: int) -> TooLarge:
    return TooLarge(
        f"Together these documents have about {total // 2000:,} pages of text, more than "
        f"AskDoc Lite reads at once (about {max_chars() // 2000:,}). Remove a document, or "
        "use AskDoc's retrieval version, which is built for large libraries."
    )


@dataclass
class LiteLibrary:
    """A visitor's documents, read together for every question."""

    files: list[LiteFile] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return bool(self.files)

    @property
    def chars(self) -> int:
        return sum(f.chars for f in self.files)

    def summary(self) -> list[dict]:
        return [f.summary() for f in self.files]

    def add(self, new: LiteFile) -> None:
        """Add a file, replacing one with the same name. All checks run before
        anything changes, so a refused file leaves the library as it was."""
        kept = [f for f in self.files if f.filename != new.filename]
        if len(kept) >= max_files():
            raise TooMany(
                f"You can load up to {max_files()} documents at a time. "
                "Remove one to add another."
            )
        files = kept + [new]
        total = sum(f.chars for f in files)
        if total > max_chars():
            raise _too_large(total)
        self.files = files

    def remove(self, filename: str) -> bool:
        before = len(self.files)
        self.files = [f for f in self.files if f.filename != filename]
        return len(self.files) < before

    def replace_all(self, files: list[LiteFile]) -> None:
        total = sum(f.chars for f in files)
        if len(files) > max_files():
            raise TooMany(f"You can load up to {max_files()} documents at a time.")
        if total > max_chars():
            raise _too_large(total)
        self.files = list(files)

    def request(self, question: str) -> dict:
        """The Messages API request. Public so tests can check its shape directly."""
        docs = []
        for i, f in enumerate(self.files):
            block = {
                "type": "document",
                "source": {
                    "type": "content",
                    # One block per page or part: each is one citable unit.
                    "content": [{"type": "text", "text": t} for _, t in f.units],
                },
                "title": f.filename,
                "citations": {"enabled": True},
            }
            if i == len(self.files) - 1:
                # The cache covers everything up to and including this block, so
                # one breakpoint on the last document caches the whole library.
                block["cache_control"] = {"type": "ephemeral"}
            docs.append(block)
        return {
            "model": model(),
            "max_tokens": int(os.getenv("LITE_MAX_TOKENS", "1024")),
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": docs + [{"type": "text", "text": question}]}],
        }

    def ask(self, question: str, client=None) -> dict:
        """Answer from the whole library; sources come from Claude's citations."""
        if not self.ready:
            raise RuntimeError("No documents loaded yet.")
        if client is None:
            from anthropic import Anthropic

            client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment

        resp = client.messages.create(**self.request(question))

        parts: list[str] = []
        sources: list[dict] = []
        seen: set[tuple[str, int, str]] = set()
        for block in resp.content:
            if getattr(block, "type", None) != "text":
                continue
            parts.append(block.text)
            for c in getattr(block, "citations", None) or []:
                if getattr(c, "type", None) != "content_block_location":
                    continue
                d = getattr(c, "document_index", 0) or 0
                if not 0 <= d < len(self.files):
                    continue
                f = self.files[d]
                idx = c.start_block_index
                if not 0 <= idx < len(f.units):
                    continue
                page = f.units[idx][0]
                text = c.cited_text.strip()
                key = (f.filename, page, text)
                if key in seen:
                    continue
                seen.add(key)
                sources.append({"file": f.filename, "page": page, "kind": f.kind, "score": None, "text": text})

        text = "".join(parts).strip() or NOT_FOUND
        if getattr(resp, "stop_reason", None) == "max_tokens":
            text = end_cleanly(text)
        usage = getattr(resp, "usage", None)
        return {
            "answer": text,
            "sources": sources[:6],
            "kind": self.files[0].kind,
            "usage": {
                "input": getattr(usage, "input_tokens", None),
                "cache_read": getattr(usage, "cache_read_input_tokens", None),
                "cache_write": getattr(usage, "cache_creation_input_tokens", None),
                "output": getattr(usage, "output_tokens", None),
            },
        }
