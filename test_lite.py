"""AskDoc Lite checks. Runs the real Anthropic SDK against a local fake API server,
so the request we send and the citations we parse are both exercised end to end.

Needs requirements-lite.txt plus the dev-only reportlab + httpx. Run from repo root:
    python test_lite.py
"""
import io
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from reportlab.pdfgen import canvas

LAST = {}

CITED = {
    "type": "content_block_location",
    "cited_text": "Full-time employees earn 15 days of paid time off per year.",
    "document_index": 0,
    "document_title": "handbook.pdf",
    "start_block_index": 1,
    "end_block_index": 2,
}


class FakeAnthropic(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        LAST["body"] = body
        question = body["messages"][0]["content"][-1]["text"].lower()
        if "fail" in question:
            self.send_response(500)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"type":"error","error":{"type":"api_error","message":"boom"}}')
            return
        docs = [b for b in body["messages"][0]["content"] if b["type"] == "document"]
        LAST["docs"] = docs
        stop = "end_turn"
        if "long" in question:
            content = [{"type": "text", "text": "The fee is $50. The committee decides in 30 days. The Board adopts the annual"}]
            stop = "max_tokens"
        elif "both" in question:
            content = [{"type": "text", "text": "Both files say so.", "citations": [
                {"type": "content_block_location", "cited_text": d["source"]["content"][0]["text"],
                 "document_index": i, "document_title": d["title"], "start_block_index": 0, "end_block_index": 1}
                for i, d in enumerate(docs)]}]
        elif "pto" in question:
            content = [
                {"type": "text", "text": "Full-time employees get "},
                {"type": "text", "text": "15 days of paid time off a year", "citations": [CITED, CITED]},
                {"type": "text", "text": "."},
            ]
        else:
            content = [{"type": "text", "text": "I couldn't find that in the document."}]
        msg = {
            "id": "msg_test", "type": "message", "role": "assistant", "model": body["model"],
            "content": content, "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 40, "output_tokens": 18,
                      "cache_creation_input_tokens": 1500, "cache_read_input_tokens": 0},
        }
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(msg).encode())

    def log_message(self, *a):
        pass


server = HTTPServer(("127.0.0.1", 0), FakeAnthropic)
threading.Thread(target=server.serve_forever, daemon=True).start()
os.environ["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{server.server_port}"
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["ANTHROPIC_MAX_RETRIES"] = "0"


def pdf(pages):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for text in pages:
        c.drawString(72, 760, text)
        c.showPage()
    c.save()
    return buf.getvalue()


HANDBOOK = pdf([
    "Welcome to the company handbook.",
    "Full-time employees earn 15 days of paid time off per year.",
    "Expenses must be submitted within 30 days.",
])

# ---------------------------------------------------------------- engine
from app.lite import LiteFile, LiteLibrary, TooLarge, TooMany, read_file  # noqa: E402

hb = read_file(HANDBOOK, "handbook.pdf")
assert len(hb.units) == 3 and hb.kind == "page", (len(hb.units), hb.kind)
print("[ok] a 3-page PDF reads as 3 citable pages")

lib = LiteLibrary()
lib.add(hb)
req = lib.request("How much PTO?")
d = req["messages"][0]["content"][0]
assert d["type"] == "document" and d["source"]["type"] == "content"
assert len(d["source"]["content"]) == 3 and d["citations"] == {"enabled": True}
assert d["cache_control"] == {"type": "ephemeral"} and d["title"] == "handbook.pdf"
assert req["messages"][0]["content"][1] == {"type": "text", "text": "How much PTO?"}
print("[ok] request sends the whole document as citable blocks, cached, question last")

res = lib.ask("How much PTO do I get?")
assert res["answer"] == "Full-time employees get 15 days of paid time off a year.", res["answer"]
assert res["sources"] == [{"file": "handbook.pdf", "page": 2, "kind": "page", "score": None, "text": CITED["cited_text"]}], res["sources"]
assert res["usage"]["cache_write"] == 1500
print("[ok] real SDK round trip: answer joined, citation mapped to file + page 2, duplicates removed")

res = lib.ask("Do we get a company car?")
assert res["answer"].startswith("I couldn't find") and res["sources"] == []
print("[ok] no citations -> plain not-found answer, no sources")

from app.lite import CUT_SHORT  # noqa: E402
res = lib.ask("Give me the long version")
assert res["answer"] == f"The fee is $50. The committee decides in 30 days.\n\n{CUT_SHORT}", res["answer"]
print("[ok] an answer stopped by the length limit ends on a full sentence and says it was shortened")

notes = read_file(b"# Notes\n\nThe deadline is March 15.\n\nAnother paragraph.", "notes.md")
assert notes.kind == "part" and notes.units[0][0] == 1
lib.add(notes)
req = lib.request("x")
blocks = [b for b in req["messages"][0]["content"] if b["type"] == "document"]
assert [b["title"] for b in blocks] == ["handbook.pdf", "notes.md"]
assert "cache_control" not in blocks[0] and blocks[1]["cache_control"] == {"type": "ephemeral"}
res = lib.ask("What do both files say?")
assert [(s["file"], s["page"], s["kind"]) for s in res["sources"]] == [("handbook.pdf", 1, "page"), ("notes.md", 1, "part")], res["sources"]
print("[ok] two files: one document block each, one cache breakpoint on the last, citations name the right file")

lib.add(read_file(b"Updated notes.", "notes.md"))
assert [f.filename for f in lib.files] == ["handbook.pdf", "notes.md"] and lib.files[1].units[0][1] == "Updated notes."
print("[ok] adding a file with the same name replaces it")

try:
    read_file(pdf(["", ""]), "scan.pdf")
    raise AssertionError("empty PDF accepted")
except ValueError as e:
    assert "scanned PDF" in str(e)
print("[ok] scanned/empty PDF rejected with the OCR message")

os.environ["LITE_MAX_FILES"] = "2"
try:
    lib.add(read_file(b"Third.", "third.txt"))
    raise AssertionError("third file accepted")
except TooMany as e:
    assert "Remove one" in str(e)
assert len(lib.files) == 2
del os.environ["LITE_MAX_FILES"]
os.environ["LITE_MAX_CHARS"] = str(lib.chars + 5)
try:
    lib.add(read_file(b"This sentence is longer than five characters.", "big.txt"))
    raise AssertionError("oversized library accepted")
except TooLarge as e:
    assert "retrieval version" in str(e)
assert [f.filename for f in lib.files] == ["handbook.pdf", "notes.md"]
del os.environ["LITE_MAX_CHARS"]
print("[ok] file-count and combined-size limits refuse without changing the library")

assert lib.remove("notes.md") and not lib.remove("notes.md") and len(lib.files) == 1
print("[ok] remove takes one file out")

# ---------------------------------------------------------------- web app
from fastapi.testclient import TestClient  # noqa: E402
import app.main_lite as ml  # noqa: E402

for heavy in ("torch", "sentence_transformers", "numpy", "app.rag"):
    assert heavy not in sys.modules, f"Lite imported {heavy}"
print("[ok] Lite app imports no torch, sentence-transformers, numpy or RAG engine")

client = TestClient(ml.app)
h = client.get("/health").json()
assert h == {"status": "ok", "engine": "lite", "document": None, "kind": None, "documents": [], "ready": False}, h
assert client.post("/ask", json={"question": "hi"}).status_code == 409
assert client.post("/upload", files={"file": ("a.epub", b"x", "application/epub+zip")}).status_code == 400
assert client.post("/upload", files={"file": ("old.doc", b"x", "application/msword")}).status_code == 422
print("[ok] /health says lite; ask-before-upload 409; bad types 400/422")

r = client.post("/upload", files={"file": ("handbook.pdf", HANDBOOK, "application/pdf")})
assert r.status_code == 200, r.text
j = r.json()
assert (j["filename"], j["chunks"], j["kind"], j["ready"]) == ("handbook.pdf", 3, "page", True), j
assert j["documents"] == [{"filename": "handbook.pdf", "chunks": 3, "kind": "page"}], j
r = client.post("/ask", json={"question": "How much PTO?"})
assert r.status_code == 200 and r.json()["sources"][0]["file"] == "handbook.pdf" and "usage" not in r.json(), r.text
print("[ok] upload + ask over HTTP; token usage stays in the logs, not the response")

r = client.post("/upload", files={"file": ("notes.md", b"# Notes\n\nThe deadline is March 15.", "text/markdown")})
assert [d["filename"] for d in r.json()["documents"]] == ["handbook.pdf", "notes.md"]
r = client.post("/ask", json={"question": "What do both say?"})
assert {s["file"] for s in r.json()["sources"]} == {"handbook.pdf", "notes.md"}, r.text
assert len(LAST["docs"]) == 2
print("[ok] a second upload adds to the library; one question reads both files")

os.environ["LITE_MAX_FILES"] = "2"
r = client.post("/upload", files={"file": ("third.txt", b"Third file.", "text/plain")})
assert r.status_code == 409 and "Remove one" in r.json()["detail"], r.text
del os.environ["LITE_MAX_FILES"]
print("[ok] over the file limit -> 409 with a clear message")

r = client.post("/remove", json={"filename": "notes.md"})
assert r.status_code == 200 and [d["filename"] for d in r.json()["documents"]] == ["handbook.pdf"]
assert client.post("/remove", json={"filename": "notes.md"}).status_code == 404
print("[ok] remove one document; removing it again -> 404")

# ---------------------------------------------------------------- sample packs and pages
for pack, count in (("hoa", 3), ("dental", 4), ("general", 2)):
    files = ml.sample_pack(pack)
    assert len(files) == count and all(f.units for f in files), (pack, len(files))
total = sum(f.chars for p in ml.PACKS for f in ml.sample_pack(p))
assert total < 60000, total
print("[ok] the three sample packs read cleanly (9 files) and are small")

ml.guard = ml.Guard()
os.environ["LITE_DAILY_QUESTIONS"] = "0"
visitor = TestClient(ml.app)
r = visitor.post("/samples/hoa")
assert r.status_code == 200 and len(r.json()["documents"]) == 3, r.text
assert "askdoc_session=" in r.headers["set-cookie"]
assert visitor.get("/health").json()["documents"][0]["filename"].startswith("Palm-Hollow")
r = visitor.post("/samples/dental")
assert [d["filename"] for d in r.json()["documents"]][0].startswith("Brightside"), r.text
del os.environ["LITE_DAILY_QUESTIONS"]
assert visitor.post("/samples/legal").status_code == 404
print("[ok] loading a sample pack replaces the library, needs no question allowance; unknown pack 404")

for path in ("/", "/hoa", "/dental"):
    r = client.get(path)
    assert r.status_code == 200 and "Ask Your Document" in r.text and "data-tab=\"hoa\"" in r.text, path
assert client.get("/static/samples/hoa/Palm-Hollow-HOA-Bylaws.pdf").status_code == 200
print("[ok] /, /hoa and /dental serve the Lite page; sample PDFs can be opened")

# ---------------------------------------------------------------- one library per visitor
up = client.post("/upload", files={"file": ("handbook.pdf", HANDBOOK, "application/pdf")})
sc = up.headers["set-cookie"].lower()
assert "askdoc_session=" in sc and "httponly" in sc and "samesite=lax" in sc, sc
h = client.get("/health").json()
assert h["ready"] and h["document"] == "handbook.pdf" and h["kind"] == "page", h
print("[ok] upload sets an HttpOnly session cookie; a refresh still finds the visitor's documents")

stranger = TestClient(ml.app)
h = stranger.get("/health").json()
assert h["ready"] is False and h["documents"] == [], h
r = stranger.post("/ask", json={"question": "How much PTO?"}, headers={"cf-connecting-ip": "9.9.9.9"})
assert r.status_code == 409, r.text
assert stranger.post("/remove", json={"filename": "handbook.pdf"}).status_code == 404
forged = TestClient(ml.app, cookies={"askdoc_session": "x" * 32})
assert forged.get("/health").json()["ready"] is False
print("[ok] another visitor (or a guessed cookie) sees no documents and cannot ask about or remove them")

stranger.post("/upload", files={"file": ("notes.md", b"# Notes\n\nThe deadline is March 15.", "text/markdown")})
assert stranger.get("/health").json()["document"] == "notes.md"
assert client.get("/health").json()["document"] == "handbook.pdf"
print("[ok] two visitors keep separate libraries")

r = client.post("/upload", files={"file": ("scan.pdf", pdf(["", ""]), "application/pdf")})
assert r.status_code == 422 and [d["filename"] for d in client.get("/health").json()["documents"]] == ["handbook.pdf"]
print("[ok] a failed upload leaves the visitor's documents in place")

st = ml.DocumentStore()
os.environ["LITE_MAX_DOCS"] = "2"
for sid in ("a" * 24, "b" * 24, "c" * 24):
    lb = LiteLibrary(); lb.add(read_file(HANDBOOK, sid[0] + ".pdf")); st.put(sid, lb)
assert st.get("a" * 24) is None and st.get("c" * 24) is not None
del os.environ["LITE_MAX_DOCS"]
os.environ["LITE_DOC_TTL_SECONDS"] = "0"
import time as _t; _t.sleep(0.01)
assert st.get("c" * 24) is None
del os.environ["LITE_DOC_TTL_SECONDS"]
print("[ok] store drops the oldest beyond LITE_MAX_DOCS and expires unused libraries")

from app.lite import SYSTEM_PROMPT  # noqa: E402
assert "calculation" in SYSTEM_PROMPT and "exact situation" in SYSTEM_PROMPT and "disagree" in SYSTEM_PROMPT
print("[ok] system prompt: figures behind calculations, uncovered cases, disagreeing documents")

r = client.post("/ask", json={"question": "please fail"})
assert r.status_code == 502 and "try again" in r.json()["detail"], r.text
print("[ok] AI service error -> friendly 502, no stack trace")

key = os.environ.pop("ANTHROPIC_API_KEY")
assert client.post("/ask", json={"question": "How much PTO?"}).status_code == 503
os.environ["ANTHROPIC_API_KEY"] = key
print("[ok] missing API key -> 503")

ml.guard = ml.Guard()
os.environ["LITE_VISITOR_QUESTIONS"] = "2"
codes = [client.post("/ask", json={"question": "PTO?"}, headers={"cf-connecting-ip": "1.1.1.1"}).status_code for _ in range(3)]
assert codes == [200, 200, 429], codes
assert client.post("/ask", json={"question": "PTO?"}, headers={"cf-connecting-ip": "2.2.2.2"}).status_code == 200
del os.environ["LITE_VISITOR_QUESTIONS"]
print("[ok] per-visitor limit: third quick question refused, other visitors unaffected")

ml.guard = ml.Guard()
os.environ["LITE_DAILY_QUESTIONS"] = "1"
assert client.post("/ask", json={"question": "PTO?"}).status_code == 200
r = client.post("/ask", json={"question": "PTO?"}, headers={"cf-connecting-ip": "3.3.3.3"})
assert r.status_code == 429 and "tomorrow" in r.json()["detail"]
del os.environ["LITE_DAILY_QUESTIONS"]
print("[ok] daily cap for the whole demo")

assert client.post("/ask", json={"question": "x" * 1001}).status_code == 400
print("[ok] overlong question refused")

# ---------------------------------------------------------------- OPEN-17: limits that hold on a public demo
ml.guard = ml.Guard()
os.environ["LITE_VISITOR_QUESTIONS"] = "2"
v6 = [client.post("/ask", json={"question": "PTO?"}, headers={"cf-connecting-ip": f"2001:db8:aa:bb::{n}"}).status_code for n in (1, 2, 3)]
assert v6 == [200, 200, 429], v6
assert client.post("/ask", json={"question": "PTO?"}, headers={"cf-connecting-ip": "2001:db8:aa:cc::1"}).status_code == 200
del os.environ["LITE_VISITOR_QUESTIONS"]
print("[ok] IPv6: rotating addresses inside one /64 counts as one visitor; another /64 is someone else")


class _Req:
    def __init__(self, headers, host="10.0.0.1"):
        self.headers = headers
        self.client = type("C", (), {"host": host})()


assert ml.visitor_id(_Req({"cf-connecting-ip": "::ffff:1.2.3.4"})) == "1.2.3.4"
assert ml.visitor_id(_Req({"cf-connecting-ip": "203.0.113.9"})) == "203.0.113.9"
assert ml.visitor_id(_Req({})) == "10.0.0.1"
print("[ok] visitor address: IPv4 as is, IPv4-mapped IPv6 as IPv4, no header -> the connection's address")

import tempfile  # noqa: E402
guard_file = os.path.join(tempfile.mkdtemp(), "guard.json")
os.environ["LITE_GUARD_FILE"] = guard_file
ml.guard = ml.Guard()
os.environ["LITE_DAILY_QUESTIONS"] = "2"
assert client.post("/ask", json={"question": "PTO?"}, headers={"cf-connecting-ip": "4.4.4.4"}).status_code == 200
assert client.post("/ask", json={"question": "PTO?"}, headers={"cf-connecting-ip": "4.4.4.5"}).status_code == 200
ml.guard = ml.Guard()  # a restart or redeploy
r = client.post("/ask", json={"question": "PTO?"}, headers={"cf-connecting-ip": "4.4.4.6"})
assert r.status_code == 429 and "tomorrow" in r.json()["detail"], r.text
with open(guard_file, "w") as f:
    json.dump({"day": "2000-01-01", "used": 99}, f)
ml.guard = ml.Guard()  # yesterday's file: a new day starts at zero
assert client.post("/ask", json={"question": "PTO?"}, headers={"cf-connecting-ip": "4.4.4.7"}).status_code == 200
with open(guard_file, "w") as f:
    f.write("not json")
assert ml.Guard().used == 0
del os.environ["LITE_GUARD_FILE"], os.environ["LITE_DAILY_QUESTIONS"]
ml.guard = ml.Guard()
print("[ok] with LITE_GUARD_FILE the day's count survives a restart; an old or broken file starts the day at zero")

ml.uploads = ml.UploadLimit()
os.environ["LITE_VISITOR_UPLOADS"] = "2"
up = TestClient(ml.app)
small = pdf(["Short page."])
codes = [up.post("/upload", files={"file": ("a.pdf", small, "application/pdf")}, headers={"cf-connecting-ip": "5.5.5.5"}).status_code for _ in range(2)]
r = up.post("/samples/hoa", headers={"cf-connecting-ip": "5.5.5.5"})
assert codes == [200, 200] and r.status_code == 429 and "a few minutes" in r.json()["detail"], (codes, r.text)
assert up.post("/samples/hoa", headers={"cf-connecting-ip": "5.5.5.6"}).status_code == 200
del os.environ["LITE_VISITOR_UPLOADS"]
ml.uploads = ml.UploadLimit()
print("[ok] uploads and sample loads: a per-visitor limit; other visitors unaffected")

import zipfile as _zip  # noqa: E402
from app import extract as ex  # noqa: E402
bomb = io.BytesIO()
with _zip.ZipFile(bomb, "w", _zip.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", "<Types/>")
    z.writestr("word/document.xml", "0" * (ex.MAX_DOCX_EXPANDED_BYTES + 1))
assert len(bomb.getvalue()) < 1_000_000  # small on disk, huge once unzipped
r = up.post("/upload", files={"file": ("bomb.docx", bomb.getvalue(), "application/octet-stream")}, headers={"cf-connecting-ip": "6.6.6.6"})
assert r.status_code == 422 and "too large to read once opened" in r.json()["detail"], r.text
r = up.post("/upload", files={"file": ("broken.docx", b"not a zip", "application/octet-stream")}, headers={"cf-connecting-ip": "6.6.6.7"})
assert r.status_code == 422 and "can't be read" in r.json()["detail"], r.text
saved_pages = ex.MAX_PDF_PAGES
ex.MAX_PDF_PAGES = 2
r = up.post("/upload", files={"file": ("long.pdf", pdf(["p1", "p2", "p3"]), "application/pdf")}, headers={"cf-connecting-ip": "6.6.6.8"})
assert r.status_code == 422 and "pages" in r.json()["detail"], r.text
ex.MAX_PDF_PAGES = saved_pages
print("[ok] files checked before parsing: a Word file that unzips past 50 MB, a broken one, a PDF over the page limit -> 422")

server.shutdown()
print("\nALL LITE CHECKS PASSED")
