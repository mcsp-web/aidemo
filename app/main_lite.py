"""
main_lite.py — the AskDoc Lite web app.

  GET  /, /hoa, /dental     -> the Lite page (any business, HOA, dental office);
                               /fr/... and /es/... the same in French and Spanish
  POST /upload              -> add a document to the visitor's library (up to 5)
  POST /remove              -> take one document out of the library
  POST /samples/{pack}      -> load a ready-made sample pack (hoa, dental, general)
  POST /ask                 -> answer from every document in the library, with citations
  GET  /health              -> liveness, the engine name, and this visitor's documents

Each visitor has their own library, keyed by a random session cookie, so files one
visitor uploads are never visible to another. Libraries live in memory, expire
after an hour unused, and the oldest are dropped beyond a fixed count.

Lite sends every document with every question, so the public demo has spending
guards: a daily question cap for the whole site and a short-window limit per
visitor. Loading a sample pack costs nothing (no AI call), so it is not counted as a
question; uploads and sample loads have their own per-visitor limit, because reading
a 20 MB file costs the shared server CPU and memory. Visitors are told apart by the
address Cloudflare reports (IPv6 by its /64 network, which one person controls). The
day's question count is in memory; with LITE_GUARD_FILE set (a file on a volume) it
survives restarts and redeploys.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import secrets
import threading
import time
from collections import OrderedDict, deque
from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .lite import LiteFile, LiteLibrary, TooLarge, TooMany, read_file

log = logging.getLogger("askdoc.lite")

app = FastAPI(title="AskDoc Lite")

STATIC_DIR = Path(__file__).parent / "static"
SAMPLES_DIR = STATIC_DIR / "samples"
PACKS = ("hoa", "dental", "general")
ALLOWED_EXTENSIONS = (".pdf", ".docx", ".doc", ".txt", ".md")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
COOKIE = "askdoc_session"


class AskRequest(BaseModel):
    question: str


class RemoveRequest(BaseModel):
    filename: str


class DocumentStore:
    """One library per visitor session. Thread-safe; expires unused libraries
    and drops the least recently used beyond LITE_MAX_DOCS."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.docs: OrderedDict[str, tuple[LiteLibrary, float]] = OrderedDict()

    def _prune(self, now: float) -> None:
        ttl = int(os.getenv("LITE_DOC_TTL_SECONDS", "3600"))
        for sid in [s for s, (_, used) in self.docs.items() if now - used > ttl]:
            del self.docs[sid]
        limit = int(os.getenv("LITE_MAX_DOCS", "40"))
        while len(self.docs) > limit:
            self.docs.popitem(last=False)

    def get(self, sid: str | None) -> LiteLibrary | None:
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

    def put(self, sid: str, lib: LiteLibrary) -> None:
        now = time.monotonic()
        with self.lock:
            self.docs[sid] = (lib, now)
            self.docs.move_to_end(sid)
            self._prune(now)


store = DocumentStore()


def session_id(request: Request) -> str | None:
    value = request.cookies.get(COOKIE)
    return value if value and 20 <= len(value) <= 64 else None


def keep_session(request: Request, response: Response) -> str:
    """The visitor's session id, minting one (and its cookie) on first use."""
    sid = session_id(request) or secrets.token_urlsafe(24)
    response.set_cookie(
        COOKIE, sid, httponly=True, samesite="lax",
        secure=request.url.scheme == "https",
        max_age=int(os.getenv("LITE_DOC_TTL_SECONDS", "3600")),
    )
    return sid


def library_state(lib: LiteLibrary | None) -> dict:
    files = lib.summary() if lib else []
    return {"documents": files, "ready": bool(files)}


@lru_cache(maxsize=None)
def sample_pack(pack: str) -> tuple[LiteFile, ...]:
    """Read a sample pack once; every visitor who loads it shares the result."""
    paths = sorted(p for p in (SAMPLES_DIR / pack).iterdir() if p.suffix.lower() in ALLOWED_EXTENSIONS)
    return tuple(read_file(p.read_bytes(), p.name) for p in paths)


class Guard:
    """Daily cap for the site + a sliding window per visitor. Thread-safe.
    With LITE_GUARD_FILE set, the day's count is written there and read back at start,
    so a restart or redeploy does not reset it."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.day = date.today()
        self.used = 0
        self.recent: dict[str, deque] = {}
        self._load()

    def _file(self) -> Path | None:
        path = os.getenv("LITE_GUARD_FILE", "").strip()
        return Path(path) if path else None

    def _load(self) -> None:
        path = self._file()
        if path is None:
            return
        try:
            saved = json.loads(path.read_text())
            if saved.get("day") == self.day.isoformat():
                self.used = max(0, int(saved.get("used", 0)))
        except (OSError, ValueError, TypeError, AttributeError):
            pass  # no file yet, or unreadable: start the day at zero

    def _save(self) -> None:
        path = self._file()
        if path is None:
            return
        try:
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps({"day": self.day.isoformat(), "used": self.used}))
            tmp.replace(path)
        except OSError as e:
            log.warning("Could not save the day's question count: %s", e)

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
            self._save()


guard = Guard()


class UploadLimit:
    """Per-visitor window for uploads and sample loads (no AI cost, but CPU and memory). Thread-safe."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.recent: dict[str, deque] = {}

    def check(self, visitor: str) -> None:
        per_window = int(os.getenv("LITE_VISITOR_UPLOADS", "20"))
        window = int(os.getenv("LITE_VISITOR_WINDOW_SECONDS", "600"))
        now = time.monotonic()
        with self.lock:
            q = self.recent.setdefault(visitor, deque())
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= per_window:
                raise HTTPException(429, "You've added a lot of files in a short time. Please wait a few minutes.")
            q.append(now)
            # Forget visitors with nothing recent, so the map cannot grow without bound.
            if len(self.recent) > 5000:
                for v in [v for v, d in self.recent.items() if not d or now - d[-1] > window]:
                    del self.recent[v]


uploads = UploadLimit()


def visitor_id(request: Request) -> str:
    # Behind Cloudflare and Traefik the client address is in the forwarded headers. The server
    # takes web traffic from Cloudflare only, and Cloudflare sets CF-Connecting-IP itself, so a
    # visitor cannot choose it.
    address = request.client.host if request.client else "unknown"
    for header in ("cf-connecting-ip", "x-forwarded-for"):
        value = request.headers.get(header)
        if value:
            address = value.split(",")[0].strip()
            break
    # One person usually holds a whole IPv6 /64 and can rotate addresses inside it: count the network.
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address
    if ip.version == 6:
        if ip.ipv4_mapped:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


@app.get("/health")
def health(request: Request) -> dict:
    # Document fields describe this visitor's own library only.
    lib = store.get(session_id(request))
    state = library_state(lib)
    first = state["documents"][0] if state["documents"] else None
    return {
        "status": "ok",
        "engine": "lite",
        # Kept for clients of the single-document contract (v0.8).
        "document": first["filename"] if first else None,
        "kind": first["kind"] if first else None,
        **state,
    }


@app.post("/upload")
async def upload(request: Request, response: Response, file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(400, "Please upload a PDF, Word (.docx), text, or Markdown file.")
    uploads.check(visitor_id(request))
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (20 MB max)")
    try:
        new = await run_in_threadpool(read_file, data, file.filename)
    except ValueError as e:
        raise HTTPException(422, str(e))

    # Every check runs before the library changes: a refused file leaves the
    # visitor's current documents in place.
    lib = store.get(session_id(request)) or LiteLibrary()
    try:
        lib.add(new)
    except TooMany as e:
        raise HTTPException(409, str(e))
    except TooLarge as e:
        raise HTTPException(413, str(e))
    store.put(keep_session(request, response), lib)
    return {**new.summary(), **library_state(lib)}


@app.post("/remove")
def remove(req: RemoveRequest, request: Request) -> dict:
    lib = store.get(session_id(request))
    if lib is None or not lib.remove(req.filename):
        raise HTTPException(404, "That document isn't loaded.")
    return library_state(lib)


@app.post("/samples/{pack}")
def load_samples(pack: str, request: Request, response: Response) -> dict:
    if pack not in PACKS:
        raise HTTPException(404, "Unknown sample pack.")
    uploads.check(visitor_id(request))
    lib = store.get(session_id(request)) or LiteLibrary()
    lib.replace_all(list(sample_pack(pack)))
    store.put(keep_session(request, response), lib)
    return library_state(lib)


@app.post("/ask")
async def ask(req: AskRequest, request: Request) -> dict:
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "Ask a question first.")
    if len(question) > 1000:
        raise HTTPException(400, "Please keep questions under 1,000 characters.")
    lib = store.get(session_id(request))
    if lib is None or not lib.ready:
        raise HTTPException(409, "Upload a document first.")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "The AI service isn't configured on this server.")
    guard.check(visitor_id(request))

    try:
        result = await run_in_threadpool(lib.ask, question)
    except Exception as e:  # network, rate limit or API error: never a stack trace to the visitor
        log.warning("Lite answer failed: %s", e)
        raise HTTPException(502, "The AI service didn't answer. Please try again in a moment.")

    log.info("Lite answer: %d files, tokens %s", len(lib.files), result.pop("usage"))
    return result


# The same page serves every industry and language; it reads both from the address.
@app.get("/")
@app.get("/hoa")
@app.get("/dental")
@app.get("/fr")
@app.get("/fr/hoa")
@app.get("/fr/dental")
@app.get("/es")
@app.get("/es/hoa")
@app.get("/es/dental")
def page() -> FileResponse:
    return FileResponse(STATIC_DIR / "lite.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
