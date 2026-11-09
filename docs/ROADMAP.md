# ROADMAP — AskDoc (aidemo)
**Derived from `MASTER_CANON.md` v0.10.0 · Nov 8, 2026**
**Status:** **AskDoc Lite LIVE** at `aidemo.mcspconsulting.com` (canon D-5); one library per visitor (D-6); v0.9.0 adds up to 5 documents and the `/hoa`, `/dental` and `/` pages with sample packs (D-7), pushed, needs a Redeploy + smoke test. **AskDoc RAG** still **SHELVED** (v0.7.2), revivable via Deploy, moves to its own subdomain on its own server.

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
| INFRA-15 | Lite deployed in Coolify; `aidemo.mcspconsulting.com` moved from the RAG resource (RAG placeholder `rag.mcspconsulting.com:8000`) | v0.8.1 |
| HARDEN-09 | One document per visitor — session cookie, 1 h expiry, LRU cap (D-6); refresh keeps it, other visitors never see it | v0.8.1 |
| APP-15 | Calculation instruction in the Lite prompt (smoke-test Q8) | v0.8.1 |
| INFRA-16 | Lite live smoke test — all checks pass on `claude-haiku-5-5` | v0.8.2 |
| INFRA-18 | `www.aidemo.mcspconsulting.com` removed from the Lite resource | v0.8.2 |
| APP-16 | Restored document hides the "Upload a document to begin" prompt | v0.8.2 |
| APP-18 | Up to 5 documents per visitor, read together; citations name file + page; remove a file | v0.9.0 |
| APP-19 | Industry pages `/hoa`, `/dental`, `/` on Lite's own page (`lite.html`), accent + starter questions per industry | v0.9.0 |
| APP-20 | Fictional sample packs (HOA, dental, any business) loadable in one click, readable as PDFs | v0.9.0 |
| APP-21 | Starter questions follow the loaded documents (switch offer on another tab; generic questions for own files) | v0.9.1 |
| APP-22 | Answers capped at ~150 words by prompt, 1024 tokens; a capped answer ends on a full sentence with a note | v0.9.1 |

---

## ⏳ NEXT (AskDoc Client Edition — the product behind Upwork Gig C; D-8, plan in canon v0.10.0)

| ID | Item | Owner |
|---|---|---|
| CLIENT-01 | `app/main_client.py` skeleton + SQLite schema on `/data` + `/health` | CLI |
| CLIENT-02 | Passwordless sign-in (Resend), roles admin/staff, invite and remove staff | CLI |
| CLIENT-03 | Documents persist on the volume; admin page to add, replace, remove; `LITE_MAX_FILES` raised for clients, ~200-page cap kept | CLI |
| CLIENT-04 | Usage log with cost per question, month totals, CSV; monthly dollar cap with admin email | CLI |
| CLIENT-05 | `client.html`: staff chat + admin tabs (Files, Staff, Usage, Settings), client name and colour | CLI |
| CLIENT-06 | `docker-compose.client.yml`, README deploy recipe, `DEMO_MODE` (admin-view button, nightly reset, low cap) | CLI |
| CLIENT-07 | **Resend sending address; demo Anthropic key with spend limit; `askdoc` subdomain + Coolify resource** | **James** |
| CLIENT-08 | Deploy the sales demo at `askdoc.mcspconsulting.com` (D-9); screenshots for the Gig C gallery | James + CLI |
| LIB-01 | Library edition (D-10): revive RAG locally, document sets, swappable embeddings (local or API), shared accounts/usage/cap | CLI |

---

## ⏳ NEXT (put Lite live — James, small surface)

| ID | Item | Owner | Canon ref |
|---|---|---|---|
| INFRA-20 | Redeploy for v0.9.1 after `build-lite` is green, then smoke-test the three pages (v0.9.0 is live; first look done) | **James** | OPEN-15 |
| INFRA-19 | Switch off Coolify auto-deploy on the Lite resource (a push deploys before CI publishes the image) | **James** | OPEN-13 |
| APP-17 | Watch for repeated sentences in answers; capture raw blocks if it recurs | CLI | OPEN-14 |
| INFRA-05 | RAG live smoke test (on revive, on its own subdomain) | **James** | OPEN-3 |
| HARDEN-03 | Coolify reverse-proxy client-body-size ~25 MB (upload backstop) | **James** | OPEN-4 |
| INFRA-09 | Tidy domains — keep only `aidemo.mcspconsulting.com` | **James** | OPEN-6 |
| INFRA-12 | Actions-triggered deploy — workflow calls Coolify's deploy webhook after a green build, restoring push-to-deploy without the build-race (Coolify git auto-deploy stays off). Needs `COOLIFY_TOKEN` + `COOLIFY_DEPLOY_URL` as repo secrets | James + CLI | OPEN-8 |
| INFRA-13 | Switch to CPU-only torch wheel to drop ~1 GB CUDA/triton from the 3.2 GB image (cuts pull time + disk) | CLI | OPEN-9 |

---

## 🔜 SOON (go-to-market — unblocked once INFRA-05 confirms live)

| ID | Item | Notes |
|---|---|---|
| GTM-01 | Screenshot the live Lite demo for the Fiverr gallery (image 3, sources panel open) | Unblocked |
| GTM-02 | Record the 30-second demo video (own voice + screen recording) | Script already drafted |
| GTM-03 | Turn on the "see a live demo" link in the mcspconsulting AI service page (`AI_DEMO_URL`) | Unblocked |
| GTM-05 | Switch on the AskDoc Lite live link in the portfolio admin | Unblocked |
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
