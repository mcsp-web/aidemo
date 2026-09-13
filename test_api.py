"""Verify the HTTP endpoints wire up correctly, using the same stubs."""
import sys, types, io
import numpy as np
from reportlab.pdfgen import canvas

# stub embedder
class FakeModel:
    def __init__(self, *a, **k): pass
    def encode(self, texts, normalize_embeddings=False, show_progress_bar=False):
        out = []
        for t in texts:
            v = np.zeros(128, dtype=np.float32)
            for w in t.lower().split(): v[hash(w) % 128] += 1.0
            nrm = np.linalg.norm(v)
            if normalize_embeddings and nrm > 0: v = v / nrm
            out.append(v)
        return np.array(out, dtype=np.float32)
st = types.ModuleType("sentence_transformers"); st.SentenceTransformer = FakeModel
sys.modules["sentence_transformers"] = st
# stub anthropic
class B: type="text"; text="Stubbed answer."
class R: content=[B()]
class M:
    def create(self, **k): return R()
class A:
    def __init__(self,*a,**k): self.messages=M()
anth = types.ModuleType("anthropic"); anth.Anthropic = A
sys.modules["anthropic"] = anth

from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)

# health before upload
r = client.get("/health"); assert r.status_code == 200 and r.json()["ready"] is False
print("[ok] /health responds, ready=False before upload")

# home page serves
r = client.get("/"); assert r.status_code == 200 and "Ask Your Document" in r.text
print("[ok] / serves the UI")

# ask before upload -> 409
r = client.post("/ask", json={"question": "hi"}); assert r.status_code == 409
print("[ok] /ask returns 409 when no document loaded")

# build a pdf and upload -> real pages, so kind is "page"
buf = io.BytesIO(); c = canvas.Canvas(buf)
c.drawString(72, 780, "The project deadline is March 15, 2026."); c.showPage(); c.save()
r = client.post("/upload", files={"file": ("plan.pdf", buf.getvalue(), "application/pdf")})
assert r.status_code == 200, r.text
data = r.json()
assert data["kind"] == "page", data
print(f"[ok] /upload indexed {data['chunks']} chunk(s) from a PDF, kind=page")

# genuinely unsupported type still rejected at the gate
r = client.post("/upload", files={"file": ("book.epub", b"hello", "application/epub+zip")})
assert r.status_code == 400, r.text
assert "Markdown" in r.json()["detail"], r.text
print("[ok] /upload rejects .epub with 400")

# legacy .doc passes the gate so rag.py can give the useful message
r = client.post("/upload", files={"file": ("old.doc", b"\xd0\xcf\x11\xe0", "application/msword")})
assert r.status_code == 422, r.text
assert ".docx" in r.json()["detail"], r.text
print(f"[ok] /upload .doc -> 422: {r.json()['detail']}")

# ...and that failed upload left the PDF intact (build() is atomic)
r = client.get("/health"); assert r.json()["ready"] is True and r.json()["document"] == "plan.pdf"
print("[ok] failed .doc upload left the PDF indexed and queryable")

# ask against the PDF
r = client.post("/ask", json={"question": "What is the deadline?"})
assert r.status_code == 200, r.text
data = r.json()
assert "answer" in data and len(data["sources"]) >= 1
assert data["kind"] == "page", data
print(f"[ok] /ask returns answer + {len(data['sources'])} source(s), kind=page")

# plain text and markdown index as synthesized parts
for name, mime, body in [
    ("notes.txt", "text/plain", b"The project deadline is March 15, 2026.\n\nBudget is 40k."),
    ("notes.md", "text/markdown", b"# Plan\n\nThe project deadline is March 15, 2026."),
]:
    r = client.post("/upload", files={"file": (name, body, mime)})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "part", data
    print(f"[ok] /upload {name} -> {data['chunks']} chunk(s), kind=part")

    r = client.post("/ask", json={"question": "What is the deadline?"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "part", data
    assert len(data["sources"]) >= 1, data
    print(f"[ok] /ask after {name} -> kind=part, {len(data['sources'])} source(s)")

print("\nALL API CHECKS PASSED")
