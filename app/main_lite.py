"""
main_lite.py — the AskDoc Lite web app.

Same contract and same page as main.py (the RAG demo), so the UI is shared:

  GET  /         -> the single-page UI
  POST /upload   -> read a document, report how many pages/parts it has
  POST /ask      -> answer a question from the whole document, with citations
  GET  /health   -> liveness, plus which engine is running ("lite")

Each visitor has their own document, keyed by a random session cookie, so a
file one visitor uploads is never visible to another. Documents live in memory,
expire after an hour unused, and the oldest are dropped beyond a fixed count.

Lite sends the whole document with every question, so the public demo has
spending guards: a daily question cap for the whole site and a short-window
limit per visitor. All of this is in memory and resets when the container restarts.
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from collections import OrderedDict, deque
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .lite import LiteDocument, TooLarge

log = logging.getLogger("askdoc.lite")

app = FastAPI(title="AskDoc Lite")

STATIC_DIR = Path(__file__).parent / "static"
ALLOWED_EXTENSIONS = (".pdf", ".docx", ".doc", ".txt", ".md")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

COOKIE = "askdoc_session"


class DocumentStore:
    """One document per visitor session. Thread-safe; expires unused documents
    and drops the least recently used beyond LITE_MAX_DOCS."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.docs: OrderedDict[str, tuple[LiteDocument, float]] = OrderedDict()

    def _prune(self, now: float) -> None:
        ttl = int(os.getenv("LITE_DOC_TTL_SECONDS", "3600"))
        for sid in [s for s, (_, used) in self.docs.items() if now - used > ttl]:
            del self.docs[sid]
        limit = int(os.getenv("LITE_MAX_DOCS", "40"))
        while len(self.docs) > limit:
            self.docs.popitem(last=False)

    def get(self, sid: str | None) -> LiteDocument | None:
        if not sid:
            return None
        now = time.monotonic()
        with self.lock:
            self._prune(now)
            entry = self.docs.get(sid)
            if entry is None:
                return None
            self.docs[sid] = (entry[0], now)
            self.docs.move_to_end(sid)
            return entry[0]

    def put(self, sid: str, doc: LiteDocument) -> None:
        now = time.monotonic()
        with self.lock:
            self.docs[sid] = (doc, now)
            self.docs.move_to_end(sid)
            self._prune(now)


store = DocumentStore()


def session_id(request: Request) -> str | None:
    value = request.cookies.get(COOKIE)
    return value if value and 20 <= len(value) <= 64 else None


class AskRequest(BaseModel):
    question: str


class Guard:
    """Daily cap for the site + a sliding window per visitor. Thread-safe."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.day = date.today()
        self.used = 0
        self.recent: dict[str, deque] = {}

    def check(self, visitor: str) -> None:
        daily = int(os.getenv("LITE_DAILY_QUESTIONS", "300"))
        per_window = int(os.getenv("LITE_VISITOR_QUESTIONS", "15"))
        window = int(os.getenv("LITE_VISITOR_WINDOW_SECONDS", "600"))
        now = time.monotonic()
        with self.lock:
            if date.today() != self.day:
                self.day, self.used = date.today(), 0
            if self.used >= daily:
                raise HTTPException(429, "The demo has answered all the questions it can today. Please try again tomorrow.")
            q = self.recent.setdefault(visitor, deque())
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= per_window:
                raise HTTPException(429, "You've asked a lot of questions in a short time. Please wait a few minutes.")
            q.append(now)
            self.used += 1


guard = Guard()


def visitor_id(request: Request) -> str:
    # Behind Cloudflare and Traefik the client address is in the forwarded headers.
    for header in ("cf-connecting-ip", "x-forwarded-for"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.get("/health")
def health(request: Request) -> dict:
    # "document" and "ready" describe this visitor's own document only.
    doc = store.get(session_id(request))
    return {
        "status": "ok",
        "engine": "lite",
        "document": doc.filename if doc else None,
        "ready": bool(doc and doc.ready),
        "kind": doc.kind if doc else None,
    }


@app.post("/upload")
async def upload(request: Request, response: Response, file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(400, "Please upload a PDF, Word (.docx), text, or Markdown file.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (20 MB max)")
    # Built into a fresh document first: a failed upload leaves the visitor's
    # current document in place.
    doc = LiteDocument()
    try:
        n = await run_in_threadpool(doc.build, data, file.filename)
    except TooLarge as e:
        raise HTTPException(413, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))

    sid = session_id(request) or secrets.token_urlsafe(24)
    store.put(sid, doc)
    response.set_cookie(
        COOKIE, sid, httponly=True, samesite="lax",
        secure=request.url.scheme == "https",
        max_age=int(os.getenv("LITE_DOC_TTL_SECONDS", "3600")),
    )
    return {"filename": file.filename, "chunks": n, "kind": doc.kind}


@app.post("/ask")
async def ask(req: AskRequest, request: Request) -> dict:
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "Ask a question first.")
    if len(question) > 1000:
        raise HTTPException(400, "Please keep questions under 1,000 characters.")
    document = store.get(session_id(request))
    if document is None or not document.ready:
        raise HTTPException(409, "Upload a document first.")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "The AI service isn't configured on this server.")
    guard.check(visitor_id(request))

    try:
        result = await run_in_threadpool(document.ask, question)
    except Exception as e:  # network, rate limit or API error: never a stack trace to the visitor
        log.warning("Lite answer failed: %s", e)
        raise HTTPException(502, "The AI service didn't answer. Please try again in a moment.")

    log.info("Lite answer: tokens %s", result.pop("usage"))
    return result


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
