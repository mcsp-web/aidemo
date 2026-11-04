"""
lite.py — AskDoc Lite: the whole-document engine.

No embeddings, no vector search, no torch. The full text of the document is
sent to Claude as a "custom content" document, one content block per page (or
per part for DOCX/TXT/MD), with Claude's built-in citations switched on. Every
answer comes back with the exact quoted passage and the block it came from,
which maps straight to a page number.

The document block is marked for prompt caching, so after the first question
the document is re-read from cache at a fraction of the normal input price.

Trade-off against the RAG engine (rag.py): Lite reads the whole document on
every question, so it handles summaries and cross-section questions well and
needs a tiny server, but it is capped by how much text fits in one request.
Large document libraries are what the RAG engine is for.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .extract import _clean, extract_pages

SYSTEM_PROMPT = (
    "You answer questions about the document provided, using only that document. "
    "If the answer is not in the document, say you couldn't find it in the document "
    "rather than guessing. When a question needs a calculation, say which figures from "
    "the document you used and why. If the document does not cover the exact situation "
    "asked about, say so before giving the closest answer it supports. Be concise, quote "
    "figures exactly, and write plain text without Markdown formatting."
)

NOT_FOUND = "I couldn't find that in the document."


def max_chars() -> int:
    # About 4 characters per token: 400,000 characters is roughly 100k tokens,
    # or around 200 typical pages. Comfortably inside the model's context window.
    return int(os.getenv("LITE_MAX_CHARS", "400000"))


def model() -> str:
    return os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")


class TooLarge(ValueError):
    """The document has more text than one request can carry."""


@dataclass
class LiteDocument:
    """One document held in memory: its units of text, ready to send whole."""

    units: list[tuple[int, str]] = field(default_factory=list)
    filename: str | None = None
    # How to label a unit when citing it: "page" (PDF) or "part" (synthesized).
    kind: str = "page"

    @property
    def ready(self) -> bool:
        return bool(self.units)

    @property
    def chars(self) -> int:
        return sum(len(t) for _, t in self.units)

    def build(self, data: bytes, filename: str) -> int:
        # Built into locals and committed at the end, like rag.DocumentIndex:
        # a failed upload never replaces a document that is already loaded.
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

        total = sum(len(t) for _, t in units)
        if total > max_chars():
            raise TooLarge(
                f"This document has about {total // 2000:,} pages of text, more than "
                f"AskDoc Lite reads at once (about {max_chars() // 2000:,}). Large "
                "document libraries are what AskDoc's retrieval version is built for."
            )

        self.units = units
        self.kind = kind
        self.filename = filename
        return len(units)

    def request(self, question: str) -> dict:
        """The Messages API request. Public so tests can check its shape directly."""
        return {
            "model": model(),
            "max_tokens": int(os.getenv("LITE_MAX_TOKENS", "800")),
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "content",
                                # One block per page or part: each is one citable unit.
                                "content": [{"type": "text", "text": t} for _, t in self.units],
                            },
                            "title": self.filename or "Document",
                            "citations": {"enabled": True},
                            # Same document for every question: cached after the first.
                            "cache_control": {"type": "ephemeral"},
                        },
                        {"type": "text", "text": question},
                    ],
                }
            ],
        }

    def ask(self, question: str, client=None) -> dict:
        """Answer from the whole document; sources come from Claude's citations."""
        if not self.ready:
            raise RuntimeError("No document loaded yet.")
        if client is None:
            from anthropic import Anthropic

            client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment

        resp = client.messages.create(**self.request(question))

        parts: list[str] = []
        sources: list[dict] = []
        seen: set[tuple[int, str]] = set()
        for block in resp.content:
            if getattr(block, "type", None) != "text":
                continue
            parts.append(block.text)
            for c in getattr(block, "citations", None) or []:
                if getattr(c, "type", None) != "content_block_location":
                    continue
                idx = c.start_block_index
                if not 0 <= idx < len(self.units):
                    continue
                page = self.units[idx][0]
                key = (page, c.cited_text.strip())
                if key in seen:
                    continue
                seen.add(key)
                sources.append({"page": page, "score": None, "text": c.cited_text.strip()})

        text = "".join(parts).strip() or NOT_FOUND
        usage = getattr(resp, "usage", None)
        return {
            "answer": text,
            "sources": sources[:6],
            "kind": self.kind,
            "usage": {
                "input": getattr(usage, "input_tokens", None),
                "cache_read": getattr(usage, "cache_read_input_tokens", None),
                "cache_write": getattr(usage, "cache_creation_input_tokens", None),
                "output": getattr(usage, "output_tokens", None),
            },
        }
