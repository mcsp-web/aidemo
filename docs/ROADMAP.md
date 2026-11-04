# ROADMAP — AskDoc (aidemo)
**Derived from `MASTER_CANON.md` v0.8.0 · Nov 4, 2026**
**Status:** **AskDoc Lite** built, tested, pushed — awaiting first Coolify deploy at `aidemo.mcspconsulting.com` (canon D-5). **AskDoc RAG** still **SHELVED** (v0.7.2), revivable via Deploy, moves to its own subdomain on its own server.

> Canon is the source of truth; this file is derived from it. Feature IDs:
> `INFRA-*` infrastructure/deploy · `APP-*` application · `HARDEN-*` production hardening · `GTM-*` go-to-market.
> Status: ✅ done · ⏳ next · 🔜 soon · 💤 deferred.

---

## ✅ DONE (shipped this session)

| ID | Item | Landed |
|---|---|---|
| APP-01 | RAG pipeline — PDF → chunk → local embed → cosine retrieve → LLM answer with sources | v0.1.0 |
| APP-02 | Single-page UI — upload, chat, expandable source passages | v0.1.0 |
| APP-03 | Provider-swappable generation (Claude default, OpenAI via env) | v0.1.0 |
| APP-04 | Test scripts — pipeline + API (stubbed model/LLM) | v0.1.0 |
| HARDEN-01 | Repo hygiene — `.gitignore`, `.dockerignore`, explicit package | v0.2.0 |
| HARDEN-02 | Upload path — 20 MB cap + threadpool offload (loop stays responsive) | v0.2.0 |
| INFRA-01 | Compose made Coolify-safe (`expose`, `/health` healthcheck) + local override | v0.2.0 |
| INFRA-02 | Git init, `main` branch, initial commit, push to `mcsp-web/aidemo` | v0.3.0 |
| INFRA-03 | Coolify app via GitHub App source, Docker Compose build pack | v0.4.0 |
| INFRA-04 | Domain bound, HTTP→HTTPS, `ANTHROPIC_API_KEY` set — app **Running** | v0.4.0 |
| INFRA-07 | Repo `mcsp-web/aidemo` set **private** | v0.6.0 |
| APP-09 | Multi-format ingestion — DOCX/TXT/MD alongside PDF; `kind`-aware "Page N" / "Part N" source labels | v0.6.0 |
| APP-10 | Drop-zone border fix — `.drop` `display:block` (was a fragmented inline `<label>`) | v0.6.0 |
| HARDEN-05 | `build()` made atomic — a failed upload no longer leaves a torn index | v0.6.0 |
| HARDEN-06 | Tests cover multi-format + `.doc` 422 + `kind`; fixed cp1252 nonzero-exit bug | v0.6.0 |
| INFRA-06 | `aidemo` DNS proxied (orange) — confirmed via live `CF-RAY` header | v0.7.0 |
| INFRA-11 | Build-off-server migration — GitHub Actions → GHCR, Coolify pulls. Done via cloud CI (not local build) | v0.7.0 |
| INFRA-08 | Domain routing survives a redeploy — verified after the v0.7.0 pull redeploy (`GET /` 200, `/health` 200) | v0.7.0 |
| INFRA-10 | Runtime cost measured — 202 MiB RAM (5.3%), 0.12% CPU idle, ~3.2 GB image; stopping freed ~400 MiB RAM | v0.7.2 |
| APP-11 | AskDoc Lite engine — whole document to Claude with built-in citations + prompt caching; answers quote the passage and page | v0.8.0 |
| APP-12 | Shared extraction module `app/extract.py` (moved verbatim from `rag.py`, re-exported) | v0.8.0 |
| APP-13 | Shared UI made engine-aware (Lite mark, tagline, "quoted" sources) | v0.8.0 |
| HARDEN-07 | Lite spending guards — daily cap, per-visitor window, question/document/answer size caps; API errors → 502, no key → 503 | v0.8.0 |
| HARDEN-08 | `test_lite.py` — real SDK against a fake API server; asserts no torch/numpy/RAG import | v0.8.0 |
| INFRA-14 | Lite image pipeline — `Dockerfile.lite`, `docker-compose.lite.yml`, `build-lite.yml` → `ghcr.io/mcsp-web/aidemo-lite` | v0.8.0 |

---

## ⏳ NEXT (put Lite live — James, small surface)

| ID | Item | Owner | Canon ref |
|---|---|---|---|
| INFRA-15 | Deploy Lite: new Coolify Compose resource from `docker-compose.lite.yml`, `ANTHROPIC_API_KEY`, move `aidemo.mcspconsulting.com` from the RAG resource to `askdoc-lite:8000`, Deploy (pull) | **James** (CLI verifies `/health` → `engine: "lite"`) | OPEN-10 |
| INFRA-16 | Lite live smoke test: page-specific question shows a "quoted" source on the right page; off-document question → "couldn't find" | **James** | OPEN-11 |
| INFRA-05 | RAG live smoke test (on revive, on its own subdomain) | **James** | OPEN-3 |
| HARDEN-03 | Coolify reverse-proxy client-body-size ~25 MB (upload backstop) | **James** | OPEN-4 |
| INFRA-09 | Tidy domains — keep only `aidemo.mcspconsulting.com` | **James** | OPEN-6 |
| INFRA-12 | Actions-triggered deploy — workflow calls Coolify's deploy webhook after a green build, restoring push-to-deploy without the build-race (Coolify git auto-deploy stays off). Needs `COOLIFY_TOKEN` + `COOLIFY_DEPLOY_URL` as repo secrets | James + CLI | OPEN-8 |
| INFRA-13 | Switch to CPU-only torch wheel to drop ~1 GB CUDA/triton from the 3.2 GB image (cuts pull time + disk) | CLI | OPEN-9 |

---

## 🔜 SOON (go-to-market — unblocked once INFRA-05 confirms live)

| ID | Item | Notes |
|---|---|---|
| GTM-01 | Screenshot the live Lite demo for the Fiverr gallery (image 3, sources panel open) | After INFRA-16 |
| GTM-02 | Record the 30-second demo video (own voice + screen recording) | Script already drafted |
| GTM-03 | Turn on the "see a live demo" link in the mcspconsulting AI service page (`AI_DEMO_URL`) | After INFRA-16 |
| GTM-05 | Switch on the AskDoc Lite live link in the portfolio admin | After INFRA-16 |
| GTM-04 | Publish the Fiverr gig with the demo linked | After GTM-01/02 |

---

## 💤 DEFERRED (real features, not needed for a demo)

| ID | Item | Why deferred |
|---|---|---|
| APP-05 | Per-session / multi-user document storage (vector DB: pgvector, Qdrant, Pinecone) | Demo holds one shared in-memory doc — fine for a portfolio piece; this is the first real client upgrade |
| APP-06 | Multiple documents / a document library | Feature-tier work |
| APP-07 | Answer confidence + click-through to the exact source page | Polish |
| HARDEN-04 | Stream-and-reject oversized uploads before full read (chunked read / Content-Length) | Proxy body limit (HARDEN-03) covers the demo |
| APP-08 | Reskin the frontend in Vue to match the mcspconsulting stack | Optional on-brand v2; standalone app is a fine showcase now |
| INFRA-17 | RAG on its own server + subdomain (e.g. `rag.mcspconsulting.com`) | When a larger VPS or a client RAG build justifies it (D-5) |
| APP-14 | Lite: OCR for scanned PDFs (or Claude PDF document input) | Scanned files are refused with a clear message today |

---

## Milestone line
`v0.1.0 built → v0.2.0 hardened → v0.3.0 pushed → v0.4.0 live on Coolify → v0.5.0 governance → v0.6.0 multi-format + fixes → v0.7.0 build-off-server CI/CD (live via pull, proxied) → v0.7.2 shelved (container stopped, revivable) → v0.8.0 AskDoc Lite built (whole-document + citations) → Lite live at aidemo (INFRA-15/16) → demo linked → (RAG on revive: own subdomain, push-to-deploy INFRA-12, smoke-tested)`

*End of ROADMAP — AskDoc*
