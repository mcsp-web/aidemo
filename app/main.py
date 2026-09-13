"""
main.py — the web app.

Routes:
  GET  /         -> the single-page UI
  POST /upload   -> accept a document, index it, report how many chunks were built
  POST /ask      -> answer a question against the indexed document
  GET  /health   -> simple liveness check for the VPS / Coolify

State is intentionally simple: one document held in memory at a time. That is
perfect for a demo. For a real client you'd store per-user documents in a
vector database — worth mentioning when you talk to buyers.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .rag import DocumentIndex
from .llm import answer

app = FastAPI(title="Ask Your Document")

STATIC_DIR = Path(__file__).parent / "static"

# Gate on the extension here; rag.extract_pages owns the real dispatch and the
# per-format error messages. ".doc" is deliberately let through: rag.py turns it
# into a 422 that says to save as .docx, which beats a generic 400 from here.
ALLOWED_EXTENSIONS = (".pdf", ".docx", ".doc", ".txt", ".md")

# One shared index for the demo.
index = DocumentIndex()


class AskRequest(BaseModel):
    question: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "document": index.filename, "ready": index.ready}


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF, Word (.docx), text, or Markdown file.",
        )
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (20 MB max)")
    try:
        # Extraction + embedding is CPU-bound; off the event loop so /health and
        # other requests stay responsive while a document is being indexed.
        n = await run_in_threadpool(index.build, data, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"filename": file.filename, "chunks": n, "kind": index.kind}


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Ask a question first.")
    if not index.ready:
        raise HTTPException(status_code=409, detail="Upload a document first.")

    results = index.search(question, top_k=4)
    passages = [c.text for c, _ in results]
    reply = answer(question, passages)

    sources = [
        {"page": c.page, "score": round(score, 3), "text": c.text}
        for c, score in results
    ]
    # kind ("page" or "part") is what the UI pairs with each source's number.
    return {"answer": reply, "sources": sources, "kind": index.kind}


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Serve any other static assets (none needed now, but handy later).
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
