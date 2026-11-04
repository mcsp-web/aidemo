"""
main_lite.py — the AskDoc Lite web app.

Same contract and same page as main.py (the RAG demo), so the UI is shared:

  GET  /         -> the single-page UI
  POST /upload   -> read a document, report how many pages/parts it has
  POST /ask      -> answer a question from the whole document, with citations
  GET  /health   -> liveness, plus which engine is running ("lite")

Lite sends the whole document with every question, so the public demo has
spending guards: a daily question cap for the whole site and a short-window
limit per visitor. Both are in memory and reset when the container restarts.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
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

# One shared document for the demo, as in the RAG demo (canon D-4).
document = LiteDocument()


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
def health() -> dict:
    return {"status": "ok", "engine": "lite", "document": document.filename, "ready": document.ready}


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(400, "Please upload a PDF, Word (.docx), text, or Markdown file.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (20 MB max)")
    try:
        n = await run_in_threadpool(document.build, data, file.filename)
    except TooLarge as e:
        raise HTTPException(413, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"filename": file.filename, "chunks": n, "kind": document.kind}


@app.post("/ask")
async def ask(req: AskRequest, request: Request) -> dict:
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "Ask a question first.")
    if len(question) > 1000:
        raise HTTPException(400, "Please keep questions under 1,000 characters.")
    if not document.ready:
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
