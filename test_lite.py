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
        if "pto" in question:
            content = [
                {"type": "text", "text": "Full-time employees get "},
                {"type": "text", "text": "15 days of paid time off a year", "citations": [CITED, CITED]},
                {"type": "text", "text": "."},
            ]
        else:
            content = [{"type": "text", "text": "I couldn't find that in the document."}]
        msg = {
            "id": "msg_test", "type": "message", "role": "assistant", "model": body["model"],
            "content": content, "stop_reason": "end_turn", "stop_sequence": None,
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
from app.lite import LiteDocument, TooLarge  # noqa: E402

doc = LiteDocument()
n = doc.build(HANDBOOK, "handbook.pdf")
assert n == 3 and doc.kind == "page" and doc.ready, (n, doc.kind)
print("[ok] a 3-page PDF loads as 3 citable pages")

req = doc.request("How much PTO?")
d = req["messages"][0]["content"][0]
assert d["type"] == "document" and d["source"]["type"] == "content"
assert len(d["source"]["content"]) == 3 and d["citations"] == {"enabled": True}
assert d["cache_control"] == {"type": "ephemeral"} and d["title"] == "handbook.pdf"
assert req["messages"][0]["content"][1] == {"type": "text", "text": "How much PTO?"}
print("[ok] request sends the whole document as citable blocks, cached, question last")

res = doc.ask("How much PTO do I get?")
assert res["answer"] == "Full-time employees get 15 days of paid time off a year.", res["answer"]
assert res["sources"] == [{"page": 2, "score": None, "text": CITED["cited_text"]}], res["sources"]
assert res["usage"]["cache_write"] == 1500
print("[ok] real SDK round trip: answer joined, citation mapped to page 2, duplicates removed")

res = doc.ask("Do we get a company car?")
assert res["answer"].startswith("I couldn't find") and res["sources"] == []
print("[ok] no citations -> plain not-found answer, no sources")

before = doc.filename
try:
    doc.build(pdf(["", ""]), "scan.pdf")
    raise AssertionError("empty PDF accepted")
except ValueError as e:
    assert "scanned PDF" in str(e)
assert doc.filename == before
print("[ok] scanned/empty PDF rejected; the loaded document stays")

os.environ["LITE_MAX_CHARS"] = "40"
try:
    LiteDocument().build(HANDBOOK, "handbook.pdf")
    raise AssertionError("oversized document accepted")
except TooLarge as e:
    assert "retrieval version" in str(e)
del os.environ["LITE_MAX_CHARS"]
print("[ok] oversized document refused with a pointer to the RAG version")

md = LiteDocument()
md.build(b"# Notes\n\nThe deadline is March 15.\n\nAnother paragraph.", "notes.md")
assert md.kind == "part" and md.units[0][0] == 1
print("[ok] Markdown loads as parts")

# ---------------------------------------------------------------- web app
from fastapi.testclient import TestClient  # noqa: E402
import app.main_lite as ml  # noqa: E402

for heavy in ("torch", "sentence_transformers", "numpy", "app.rag"):
    assert heavy not in sys.modules, f"Lite imported {heavy}"
print("[ok] Lite app imports no torch, sentence-transformers, numpy or RAG engine")

client = TestClient(ml.app)
h = client.get("/health").json()
assert h == {"status": "ok", "engine": "lite", "document": None, "ready": False}, h
assert client.post("/ask", json={"question": "hi"}).status_code == 409
assert client.post("/upload", files={"file": ("a.epub", b"x", "application/epub+zip")}).status_code == 400
assert client.post("/upload", files={"file": ("old.doc", b"x", "application/msword")}).status_code == 422
print("[ok] /health says lite; ask-before-upload 409; bad types 400/422")

r = client.post("/upload", files={"file": ("handbook.pdf", HANDBOOK, "application/pdf")})
assert r.status_code == 200 and r.json() == {"filename": "handbook.pdf", "chunks": 3, "kind": "page"}, r.text
r = client.post("/ask", json={"question": "How much PTO?"})
assert r.status_code == 200 and r.json()["sources"][0]["page"] == 2 and "usage" not in r.json(), r.text
assert "Lite" in client.get("/").text
print("[ok] upload + ask over HTTP; token usage stays in the logs, not the response")

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

server.shutdown()
print("\nALL LITE CHECKS PASSED")
