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

# build a pdf and upload
buf = io.BytesIO(); c = canvas.Canvas(buf)
c.drawString(72, 780, "The project deadline is March 15, 2026."); c.showPage(); c.save()
r = client.post("/upload", files={"file": ("plan.pdf", buf.getvalue(), "application/pdf")})
assert r.status_code == 200, r.text
print(f"[ok] /upload indexed {r.json()['chunks']} chunk(s)")

# non-pdf rejected
r = client.post("/upload", files={"file": ("x.txt", b"hello", "text/plain")})
assert r.status_code == 400
print("[ok] /upload rejects non-PDF")

# ask now works
r = client.post("/ask", json={"question": "What is the deadline?"})
assert r.status_code == 200, r.text
data = r.json()
assert "answer" in data and "sources" in data and len(data["sources"]) >= 1
print(f"[ok] /ask returns answer + {len(data['sources'])} source(s)")

print("\nALL API CHECKS PASSED ✅")
