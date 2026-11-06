# MASTER CANON — AskDoc (aidemo)
**Last Updated:** November 4, 2026 (session 4)
**Current Version:** v0.9.0
**Status:** Two editions. **AskDoc Lite** is **LIVE** at `aidemo.mcspconsulting.com` (deployed Nov 4, 2026; D-5), one library per visitor (D-6). v0.9.0 adds up to 5 documents per visitor and industry pages `/hoa` and `/dental` with sample packs (D-7) — pushed, needs a Redeploy and a smoke test. **AskDoc RAG** stays **SHELVED** (v0.7.2), revivable via Deploy; it moves to its own subdomain when it gets its own server.
**Stack:** Python 3.11 · FastAPI · Anthropic Claude · Docker · Coolify · Cloudflare · Hetzner. RAG edition adds sentence-transformers/torch (swappable → OpenAI); Lite edition needs neither.

> Bootstrap canon. This project has no `_canon/apply.php` machinery — this file is
> maintained directly and committed via Claude Code. Canon-first: this file is the
> source of truth; `ROADMAP.md` is derived from it.

---

## SECTION 1 — SYSTEM IDENTITY

**Project:** AskDoc — AI document-Q&A demo ("Ask Your Document")
**Type:** Portfolio / sales-demo web app for the AI-integration service line
**Org / Billing / Market:** MCSP Consulting · `mcsp-web` GitHub org · USD · used as a live demo for Fiverr gigs and the mcspconsulting.com AI service page
**What it does:** upload a document (PDF/DOCX/TXT/MD), ask questions, get answers grounded in the file with the sources shown. Two editions share the UI, the extraction code and the API contract:
- **AskDoc Lite** (`app/main_lite.py` + `app/lite.py` + `app/static/lite.html`) — every document in the visitor's library (up to 5) goes to Claude with every question, each as its own citable "custom content" document (one block per page/part), with Claude's built-in citations and prompt caching. Answers quote the exact passage, file and page. No embeddings, no torch, tiny image and RAM. Capped at `LITE_MAX_CHARS` (~200 pages) for the whole library. Three industry pages: `/` (any business), `/hoa`, `/dental`, each with a fictional sample pack. The default offer for small businesses.
- **AskDoc RAG** (`app/main.py` + `app/rag.py` + `app/llm.py`) — text is chunked and embedded locally, the closest chunks are retrieved by cosine similarity and sent to an LLM, which answers **from those passages only**. Built for large document libraries and heavy use. The "big brother" offer.
**Run surface:** Lite at `https://aidemo.mcspconsulting.com` (from v0.8.0, D-5). RAG offline (shelved); on revive it gets its own subdomain (e.g. `rag.mcspconsulting.com`). Local dev at `http://localhost:8000`.
**Local path:** `D:\laragon\www\Freelance\`
**Repo:** `github.com/mcsp-web/aidemo` (branch `main`) — **private** (OPEN-1 closed).

---

## SECTION 2 — SOURCE OF TRUTH REGISTRY

Authoritative files. Audit against these before changing anything.

| Role | File | Authority |
|---|---|---|
| Web app / routes (RAG) | `app/main.py` | FastAPI app; routes `/`, `/upload`, `/ask`, `/health`; upload hardening (size cap + threadpool) |
| Shared extraction | `app/extract.py` | Multi-format extraction (pdf/docx/txt/md) → `extract_pages(data, filename) -> (pages, kind)`, plus `_clean`. Used by **both** editions (moved verbatim out of `rag.py` in v0.8.0) |
| Retrieval engine (RAG) | `app/rag.py` | Chunking, local embeddings, in-memory `DocumentIndex`, cosine search; re-exports the extraction names from `extract.py` so existing imports keep working |
| Web app / routes (Lite) | `app/main_lite.py` | Routes `/`, `/hoa`, `/dental` (all serve `lite.html`), `/upload` (adds to the library), `/remove`, `/samples/{pack}`, `/ask`, `/health`; `DocumentStore` = one library per visitor (HttpOnly `askdoc_session` cookie, 1 h idle expiry, LRU cap); `sample_pack()` reads each pack once and shares it; spending `Guard` (daily cap + per-visitor window; sample loads not counted); API errors → 502, no key → 503 |
| Whole-document engine (Lite) | `app/lite.py` | `read_file` → `LiteFile` (citable units; refuses scanned/empty files). `LiteLibrary`: up to `LITE_MAX_FILES` files (`TooMany` → 409) and `LITE_MAX_CHARS` combined (`TooLarge` → 413), checked before anything changes; same file name replaces; builds the Messages request (one document block per file, `citations` on, one `cache_control` breakpoint on the last block), maps `content_block_location` citations → file (`document_index`) + page (`start_block_index`) |
| Generation layer | `app/llm.py` | Provider-swappable answer generation; `SYSTEM_PROMPT`; answers from passages only |
| Frontend (RAG) | `app/static/index.html` | RAG single-page UI — upload, chat, expandable sources. Still contains the v0.8 Lite branches (harmless: RAG never reports `engine: "lite"`) |
| Frontend (Lite) | `app/static/lite.html` | Lite's own page since v0.9.0 (D-7): industry tabs (Any business / HOA / Dental office) chosen by the address, accent colour per industry, sample pack card with "Load sample documents" and links to read each PDF, file list with remove, add up to 5 files, starter questions per industry, sources labelled file + page. Restores the library after a refresh |
| Sample packs | `app/static/samples/{hoa,dental,general}/` | Fictional PDFs: Palm Hollow HOA (CC&Rs, bylaws, rules and fees), Brightside Family Dental (office manual, PPO and HMO plan summaries, sterilization SOP), Harbor Logistics (handbook, operations SOPs). Every page footer says "Fictional sample for demonstration" |
| Sample generator | `tools/samples/make_samples.py` | Rebuilds the sample PDFs from the text in the script (reportlab, dev-only). Not in the image |
| Package marker | `app/__init__.py` | Makes `app` an explicit package (empty) |
| Image build | `Dockerfile` | `python:3.11-slim`; **bakes the embedding model at build time** so the container needs no network for embeddings |
| CI build + publish | `.github/workflows/build-image.yml` | On push to `main` (image-affecting paths only): **test** job (suite, torch stubbed) → **build** job (`linux/amd64`) → pushes `ghcr.io/mcsp-web/aidemo` `:latest` + `:sha-*` with a registry buildcache. The **only** publisher of the image |
| Deploy config | `docker-compose.yml` | Service `askdoc`; `image: ghcr.io/mcsp-web/aidemo:latest` + `pull_policy: always` (pulls the CI-built image — no `build:`); `expose: 8000` (no host port); healthcheck on `/health`; env block; `restart: unless-stopped` |
| Lite image build | `Dockerfile.lite` | `python:3.11-slim` + `requirements-lite.txt` + `app/`; runs `uvicorn app.main_lite:app` with proxy headers. No model download, no torch |
| Lite CI build + publish | `.github/workflows/build-lite.yml` | On push to `main` (Lite-affecting paths): **test** job (`test_lite.py`) → **build** job → pushes `ghcr.io/mcsp-web/aidemo-lite` `:latest` + `:sha-*`. The **only** publisher of the Lite image |
| Lite deploy config | `docker-compose.lite.yml` | Service `askdoc-lite`; `image: ghcr.io/mcsp-web/aidemo-lite:latest` + `pull_policy: always`; `expose: 8000`; healthcheck on `/health`; env block (key + Lite limits); `restart: unless-stopped` |
| Local-run template | `docker-compose.override.yml.example` | Copied to the git-ignored `docker-compose.override.yml` for **local dev only**: `build: .` + `pull_policy: build` (builds from source), tags the result `aidemo-local:dev` so it can't target GHCR, republishes port 8000. Never pushed |
| Git hygiene | `.gitignore`, `.dockerignore` | `.env` + real override never committed; tests/README kept out of the image |
| Dependencies | `requirements.txt` | RAG: 9 pinned deps (`python-docx` added in v0.6.0) |
| Dependencies (Lite) | `requirements-lite.txt` | 6 pinned deps: fastapi, uvicorn, python-multipart, pypdf, python-docx, anthropic. Changing it rebuilds only the small Lite image |
| Docs | `README.md` | Run + deploy instructions (kept out of the image via `.dockerignore`) |
| Tests | `test_pipeline.py`, `test_api.py`, `test_lite.py` | Assert-scripts (not pytest); need dev-only `reportlab` + `httpx`; run from repo root. `test_lite.py` runs the real Anthropic SDK against a local fake API server (request shape, multi-file citations → file + page, limits, remove, sample packs, pages, per-visitor isolation, guards, error codes) and asserts the Lite app imports no torch/numpy/RAG engine |

**API contract (frontend ↔ backend):**
```
POST /upload  (multipart: file=<.pdf|.docx|.txt|.md>)  -> { filename, chunks, kind }
POST /ask     ({ question })                           -> { answer, sources:[{ page, score, text }], kind }
GET  /health                                           -> { status, document, ready }            (RAG)
                                                          { status, engine:"lite", document, kind, documents:[{filename, chunks, kind}], ready }  (Lite — this visitor's library only; document/kind = the first file, kept for v0.8 clients)

Lite only (v0.9.0):
POST /upload        -> adds to the library: { filename, chunks, kind, documents:[…], ready }
POST /remove        ({ filename })  -> { documents:[…], ready }; 404 if not loaded
POST /samples/{pack}  (hoa | dental | general)  -> { documents:[…], ready }; replaces the library; 404 unknown pack
POST /ask           -> sources:[{ file, page, kind, score:null, text }]
GET  / , /hoa , /dental  -> lite.html
GET  /                                                 -> index.html
```
`kind` is `"page"` (PDF) or `"part"` (synthesized units for DOCX/TXT/MD) — the UI labels sources "Page N" / "Part N" from it. Upload errors: unsupported type → 400; legacy `.doc` passes the gate → 422 "save as .docx"; no readable text → 422; > 20 MB → 413. **Lite only:** more text than `LITE_MAX_CHARS` across the library → 413 (message points to the RAG edition); more than `LITE_MAX_FILES` files → 409; `sources[].score` is `null` (citations are quoted, not scored); `/ask` adds 400 for questions over 1,000 characters, 429 from the spending guard, 503 when no API key is set, 502 when the AI service fails.

**Runtime config (env-driven, no code change to switch):**
| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | or `openai` |
| `LLM_MODEL` | `claude-haiku-4-5-20251001` | e.g. a Sonnet model for higher quality, or `gpt-4o-mini`. **Live Lite resource: `claude-haiku-5-5`** (set in Coolify, Nov 4, 2026) |
| `ANTHROPIC_API_KEY` | — | required for Claude; **set in Coolify UI only, never in repo** |
| `OPENAI_API_KEY` | — | only if provider = openai (RAG only; Lite is Claude-only because it relies on Claude's citations) |
| `LITE_DAILY_QUESTIONS` | `300` | Lite: questions per day for the whole demo (in memory, resets on restart) |
| `LITE_VISITOR_QUESTIONS` / `LITE_VISITOR_WINDOW_SECONDS` | `15` / `600` | Lite: questions per visitor (Cloudflare client IP) per window |
| `LITE_MAX_CHARS` | `400000` | Lite: most text a visitor's library may hold, all files together (~100k tokens, ~200 pages) |
| `LITE_MAX_FILES` | `5` | Lite: most documents in one visitor's library |
| `LITE_MAX_TOKENS` | `800` | Lite: answer length cap |
| `LITE_DOC_TTL_SECONDS` | `3600` | Lite: a visitor's document is dropped after this long unused (also the cookie lifetime) |
| `LITE_MAX_DOCS` | `40` | Lite: most visitor libraries held at once; the least recently used is dropped first (40 × ~200 pages ≈ tens of MB) |

---

## SECTION 3 — INFRASTRUCTURE REGISTRY

| Item | Value |
|---|---|
| VPS | Hetzner CPX21 · `see coolify.mcspconsulting.com / Hetzner console` · 4 GB RAM nominal (~3.7 GB usable) · 3 vCPU · 80 GB — **shared with PureOps, MinIO, and client sites** |
| Coolify | `https://coolify.mcspconsulting.com` · project **aidemo** / environment **production** |
| App resource | Application (Docker Compose build pack), source = **GitHub App** (`mcsp-web`), repo `aidemo`, branch `main` |
| Auth to GitHub | **GitHub App source** (not a deploy key) — enables auto-deploy webhooks. Org deploy-keys policy left **Disabled** |
| Auto-deploy | RAG: **Manual** (auto-deploy off). Lite: was created with **Deploy on push (webhooks)** — must be switched off (OPEN-13), because a push deploys before CI has published the new image. Actions-triggered deploy planned for both (INFRA-12) |
| Build | GitHub Actions builds → GHCR; Coolify pulls `ghcr.io/mcsp-web/aidemo:latest` (`pull_policy: always`). **VPS never builds.** |
| Domain | `aidemo.mcspconsulting.com` → Cloudflare A record → `see coolify.mcspconsulting.com / Hetzner console` |
| DNS state | **Proxied (orange)** — confirmed live via `Server: cloudflare` + `CF-RAY` response headers (OPEN-2 closed) |
| Domain binding | Added in Coolify UI: `https://aidemo.mcspconsulting.com` on service `askdoc`, internal port `8000`. HTTP→HTTPS redirect enabled |
| Secrets | `ANTHROPIC_API_KEY` in Coolify Environment Variables UI — the only secret; never in the repo |
| Lite resource | Coolify Docker Compose resource `aidemo:main-uiiw0gw69oxffm3avkqs0e…` in project **aidemo** (source: GitHub App, `main`, compose file `/docker-compose.lite.yml`), service `askdoc-lite` port `8000`, pulls `ghcr.io/mcsp-web/aidemo-lite:latest`. Domain `https://aidemo.mcspconsulting.com` (D-5). **Running** since Nov 4, 2026 |
| RAG resource | `aidemo:main-qojy3hbeuf0jhfbskoynx1l3`, **stopped**. Its domain was moved to `https://rag.mcspconsulting.com:8000` (placeholder, no DNS yet) because Coolify won't save an empty domain |

---

## SECTION 4 — OPERATIONAL PROTOCOLS

### 4.1 Lifecycle (every change follows this)
1. **Recon:** read live source before scoping anything that touches it. No blind edits.
2. **Propose-first:** on any data path or production event, propose the plan and wait for the go before writing.
3. **Build:** implement one concern at a time; append/patch, don't refactor unrelated logic without authorization.
4. **Verify:** run what can be verified; state clearly what can't.
5. **Version:** update this canon (date + version bump) and reconcile `ROADMAP.md`.

### 4.2 CLI delivery format
- **One CLI prompt per copy box.** The run instruction lives inside the box.
- **One concern per box / per commit.** Never bundle unrelated changes.
- **Paste the CLI output back before anything is assumed run.** Open loops are tracked, not dropped.

### 4.3 Production-access rule
- Read-only prod checks (container status, logs, `curl` of a route, response headers) — the CLI may run these itself.
- **Anything needing a secret or credential → James.** The CLI never handles secrets.
- **Anything the CLI can't actually do — visual/UX smoke tests, "does it look right", rendered output — is stated in BOLD for James** and never handed to the CLI.

### 4.4 Deploy protocol
- **Deploy via Coolify (manual Docker Compose resource), NOT Launchpad.** Launchpad is a Laravel-site factory (fixed `site-template`, `serversideup/php` image, required shared Postgres) — structurally wrong for a Python/FastAPI app with no DB (see D-1).
- Base `docker-compose.yml` uses `expose` (not `ports`) so Coolify's proxy routes by domain and no host port collides with other services on the box.
- Local dev restores the host port via the git-ignored `docker-compose.override.yml` (from the `.example`), which Coolify never reads.
- Secrets go in the Coolify env UI. DNS grey-cloud for first cert, then flip to proxied.
- **Images come from CI, never a laptop or the VPS.** GitHub Actions (`.github/workflows/build-image.yml`) builds and pushes `ghcr.io/mcsp-web/aidemo` (`:latest` + `:sha-*`); `docker-compose.yml` pulls `:latest` with `pull_policy: always`.
- **GHCR login — once per host, before the first pull:** on the Coolify host run `docker login ghcr.io -u <github-username>` and paste a token scoped only to `read:packages` at the prompt (keeps it out of shell history). The package is private, so without this the pull fails `unauthorized`. **Track the token's expiry** — an expired token breaks deploys at the pull step. *(James — credential)*
- **Deploy is manual** (Coolify auto-deploy off): wait for the Actions run on the target commit to go green, then Deploy in Coolify and confirm the log shows a **pull**, not a build. Push-to-deploy returns with INFRA-12 (OPEN-8).
- **Rollback:** point `image:` at a previous `:sha-*` tag and deploy. Never restore `build: .` — that brings the server-side torch build back.
- **Lite follows the same rules:** `ghcr.io/mcsp-web/aidemo-lite` is published only by `build-lite.yml`; Coolify pulls it via `docker-compose.lite.yml`; manual deploy after the Actions run is green. A push touching `app/**` rebuilds **both** images (shared code) — expected.
- **Tests before push:** all three scripts — `test_pipeline.py`, `test_api.py`, `test_lite.py`.

### 4.5 Canon update
On "update canon": append a dated, versioned entry to Section 5 with the files changed, the reason, and the outcome; bump the version in the header; reconcile `ROADMAP.md`.

---

## SECTION 5 — CHANGE LOG

### [v0.1.0] — Sept 12, 2026 — Initial build
**Summary:** built the AskDoc RAG demo end to end and verified the pipeline.
- **Created** `app/main.py`, `app/rag.py`, `app/llm.py`, `app/static/index.html`, `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `README.md`, `.env.example`, `test_pipeline.py`, `test_api.py`.
- **Design decisions:** local sentence-transformers embeddings (no per-query cost, no second vendor); Claude for generation, provider-swappable to OpenAI; in-memory vector store (numpy cosine); sources returned with every answer.
- **Verified:** pipeline test (PDF → chunk → embed → retrieve → prompt assembly) and API test (`/health`, `/upload`, `/ask`, non-PDF rejection) both pass with stubbed model + LLM.
- **Outcome:** working, tested demo package.

### [v0.2.0] — Sept 12, 2026 — Repo hygiene + deploy hardening
**Summary:** made the project safe to commit and safe on a public URL.
- **Added** `.gitignore` (`.env`, caches, venvs, IDE), `.dockerignore`, empty `app/__init__.py` (explicit package).
- **`docker-compose.yml`:** `ports: 8000:8000` → `expose: 8000` (Coolify proxy routes by domain, avoids host-port collision on the shared box); added a `/health` healthcheck using `python` (curl absent in slim image).
- **Local-run:** added `docker-compose.override.yml.example`; git-ignored the real override; README updated with the `cp …example …` step.
- **`app/main.py` hardening:** 20 MB upload cap (returns 413); moved the CPU-bound embed/build off the event loop via `run_in_threadpool` so `/health` stays responsive during indexing.
- **Reason:** the URL is public and the box is shared; a healthcheck flap mid-upload was a real risk.
- **Outcome:** clean fresh-clone story; loop-safe upload path.

### [v0.3.0] — Sept 12, 2026 — Version control
**Summary:** local Git established and pushed.
- `git init` → verified `.env` untracked (`git check-ignore`) and no secrets in blob contents → single initial commit `320259f` (15 files) → renamed branch `master` → `main`.
- Added remote `github.com/mcsp-web/aidemo`, pushed `main`; local HEAD, `origin/main`, and live `ls-remote` SHAs all matched.
- **Outcome:** repo live, upstream tracking set.

### [v0.4.0] — Sept 12, 2026 — Live on Coolify
**Summary:** deployed to Coolify and reached Running.
- App recreated to authenticate via the **GitHub App source** (a first deploy-key attempt failed — "Failed to read Git source" — because the org has no deploy keys and the raw URL had no auth; the GitHub App path also restores auto-deploy webhooks).
- Build pack set to **Docker Compose**; compose location corrected to `/docker-compose.yml` (Coolify defaulted to `.yaml`).
- Resolved **"No services available"** on the Domains tab; bound `https://aidemo.mcspconsulting.com` to service `askdoc` on port `8000`, HTTP→HTTPS redirect on.
- `ANTHROPIC_API_KEY` set in the Coolify env UI. DNS set grey-cloud for first cert.
- **Outcome:** app status **Running**. Live Q&A path not yet smoke-tested (OPEN-3).

### [v0.5.0] — Sept 12, 2026 — Governance + protocols
**Summary:** track canon + roadmap under `docs/`, add `CLAUDE.md`, redact the VPS IP.
- Moved `MASTER_CANON.md` + `ROADMAP.md` into `docs/` (tracked); added root `CLAUDE.md` (auto-loaded protocols); `.dockerignore` excludes `docs/` + `CLAUDE.md`.
- Redacted the VPS public IP from the canon; the placeholder points to the Coolify/Hetzner console.
- **Outcome:** repo self-documents its own discipline; no infra address in tracked files.

### [v0.6.0] — Sept 13, 2026 — Multi-format ingestion + hardening
**Summary:** accept DOCX, TXT, MD alongside PDF; fix two adjacent defects found during the work.
- `rag.py`: `extract_pages(data, filename)` dispatches by extension and returns `(pages, kind)` where `kind` is `"page"` (pdf) or `"part"` (synthesized ~3000-char units for non-paged formats). DOCX walks paragraphs **and** tables. `build()` made **atomic** — commits to `self` only after embedding succeeds (fixes torn state where a failed upload after a good one left `ready=True` with mismatched chunks/vectors).
- `main.py`: upload gate widened to pdf/docx/doc/txt/md; `.doc` admitted deliberately so `rag.py` owns the single "save as .docx" 422; top-level `"kind"` added to `/upload` and `/ask` responses.
- `requirements.txt`: `python-docx==1.1.2` (pulls `lxml`, `typing-extensions`).
- Frontend: accept list + JS validation mirror the backend gate; `sourceLabel()` renders "Page N" / "Part N" from `kind`; copy generalized from PDF to document. Also fixed the drop-zone border — `.drop` is a `<label>` (default `display:inline`) with block children, which fragmented the inline box; `display:block` restores the dashed border and its vertical padding.
- Tests: multi-format + `.doc`-422 + `kind` coverage; fixed a non-ASCII char that made both scripts exit nonzero on cp1252 consoles despite passing.
- **Outcome:** feature complete across 7 commits, verified against stubs plus a real `python-docx` extraction. **Not yet deployed** — commits are local only.

### [v0.7.0] — Sept 13, 2026 — Build-off-server CI/CD migration (INFRA-11)
**Summary:** image builds moved off both the laptop and the VPS to GitHub Actions → GHCR; Coolify now pulls a prebuilt image instead of building.
- `.github/workflows/build-image.yml`: on push to `main`, a **test** job runs the suite (torch stubbed), then a **build** job builds `linux/amd64` and pushes `ghcr.io/mcsp-web/aidemo` (`:latest` + `:sha-*`) with a registry buildcache. First build 5m31s; cached rebuilds ~1m.
- `docker-compose.yml`: `build: .` → `image: ghcr.io/mcsp-web/aidemo:latest` + `pull_policy: always`. `build: .` moved to `docker-compose.override.yml.example` (local dev only), which now tags local builds `aidemo-local:dev` so a stray push can't target the published image.
- VPS authenticates to GHCR with a `read:packages` token; deploys **pull** (seconds) instead of building (~2m).
- Guard docs (`CLAUDE.md` / `README.md` / override example): image publishing is **CI-only**.
- **Reason:** the torch build (~3.2 GB image) froze the 8 GB laptop and threatened the 4 GB (~3.7 GB usable) shared VPS; neither should build it. Cloud runners have the headroom.
- **Outcome:** v0.6.0 multi-format confirmed live via the pulled image (`/health` shows a `.docx`). Coolify auto-deploy stays **OFF**; deploys are manual pending INFRA-12.

### [v0.7.1] — Sept 14, 2026 — Canon reconciliation (no code)
**Summary:** post-v0.7.0 documentation cleanup, no application change.
- Closed OPEN-5 (routing survives redeploy, re-verified 200 on `/` and `/health` via the domain); rewrote OPEN-7 (build-time RAM risk obsolete; runtime RAM + image disk still unmeasured).
- §1 repo marked private (OPEN-1); §2 file registry refreshed (workflow file, GHCR deploy config, 9 deps, multi-format API contract + `kind` + error codes); §4.4 full deploy flow (CI-only, GHCR login, manual deploy, rollback).
- Added OPEN-8 (INFRA-12) and OPEN-9 (INFRA-13); standardised RAM as "4 GB nominal (~3.7 GB usable)".
- **Outcome:** canon and roadmap internally consistent; no image or deploy change.

### [v0.7.2] — Sept 16, 2026 — Shelved (resource conservation), no code change
**Summary:** AskDoc container stopped in Coolify to free resources on the shared 4 GB VPS; app config, domain, and env vars retained — this is a pause, not a teardown.
- Measured runtime cost before stopping (closes OPEN-7): 202 MiB RAM (5.3%), 0.12% CPU idle; ~3.2 GB image on disk. Stopping freed ~400 MiB RAM total and dropped swap from ~524 MiB to ~165 MiB.
- **Reason:** 4 GB nominal (~3.7 GB usable) box shared with PureOps + client sites; removing AskDoc's idle footprint and (more importantly) its under-load spike risk. Revisit when on a larger VPS.
- Coolify "Stop" also ran Docker cleanup, pruning the parked image; revive re-pulls from GHCR.
- **Revive procedure:** Coolify → `aidemo` → **Deploy** (re-pulls `ghcr.io/mcsp-web/aidemo:latest`, ~minutes) → confirm **Running** + `/health` 200 → re-enable the demo link (set `AI_DEMO_URL` in the mcspconsulting app). No rebuild needed; the image is in GHCR. If the pull fails `unauthorized`, the host's GHCR token has expired — re-run the §4.4 `docker login ghcr.io` first. A new/larger VPS needs that login before its first deploy.
- **Outcome:** AskDoc offline — `aidemo.mcspconsulting.com` returns 503 "no available server" (observed Sept 16, 2026). Config, domain, env vars, and the GHCR image are preserved; revivable without a rebuild.

### [v0.8.0] — Nov 4, 2026 — AskDoc Lite (whole-document edition) + shared extraction module
**Summary:** added a second, lighter edition of AskDoc that sends the whole document to Claude with built-in citations and prompt caching instead of retrieving chunks. Same UI, same API contract, its own slim image. Built so a live demo can run on the shared 4 GB VPS without torch, and as the default small-business offer.
- **Shared extraction path (moved, unchanged):** the extraction functions (`_extract_pdf`, `_extract_docx`, `_extract_text`, `_paginate`, `_EXTRACTORS`, `extract_pages`, `_clean`, `_PSEUDO_PAGE_CHARS`) moved verbatim from `app/rag.py` to the new `app/extract.py`; `rag.py` re-exports them, so every existing import still resolves. No behaviour change: `test_pipeline.py` and `test_api.py` pass unchanged.
- **New:** `app/lite.py` (`LiteDocument`), `app/main_lite.py` (routes + spending `Guard`), `requirements-lite.txt`, `Dockerfile.lite`, `docker-compose.lite.yml`, `.github/workflows/build-lite.yml` (CI → `ghcr.io/mcsp-web/aidemo-lite`), `test_lite.py`.
- **Changed:** `app/static/index.html` is engine-aware via `/health` (Lite mark, tagline, "quoted" sources); RAG rendering unchanged.
- **How Lite answers:** one `document` block (source type `content`, one text block per page/part), `citations: {enabled: true}`, `cache_control: ephemeral`, question after it. Citations come back as `content_block_location`; `start_block_index` maps to the page/part number; duplicates removed; at most 6 sources. Scanned PDFs (no text layer) are refused with the OCR message.
- **Public-demo spending guards:** 300 questions/day for the site, 15 per visitor per 10 minutes, 1,000-character questions, ~200-page documents, 800-token answers — all env-tunable. Token usage (incl. cache reads/writes) is logged, never returned to the browser.
- **Reason:** RAG is shelved because torch (~3.2 GB image, ~200 MiB idle, spikes under load) doesn't fit the shared VPS; the domain has been returning 503 while still linked from the MCSP site and the Fiverr gig. Most small-business documents fit in one request, where whole-document reading also answers summary and cross-section questions better than top-4 retrieval.
- **Verified:** `test_lite.py` ALL LITE CHECKS PASSED (real Anthropic SDK against a fake API server: request shape, citation → page 2 mapping + dedupe, not-found fallback, scanned/oversized refusals, 400/409/422/413/429/502/503, no torch/numpy/RAG import); `test_pipeline.py` and `test_api.py` pass.
- **Outcome:** committed and pushed; Lite image publishes from CI. **Not yet deployed** — needs the new Coolify resource and domain move (OPEN-10), then a live smoke test (OPEN-11, James).

### [v0.8.1] — Nov 4, 2026 — Lite deployed + smoke-tested; one document per visitor
**Summary:** AskDoc Lite went live at `aidemo.mcspconsulting.com`; James's smoke test surfaced a privacy gap (one shared document) and a weak calculation answer, both fixed here.
- **Deploy (James, Coolify):** new Docker Compose resource from `docker-compose.lite.yml` (Coolify now labels the source "Git Repository (with GitHub App)" and the path field "Compose file"); domain moved from the stopped RAG resource, which needed a placeholder (`rag.mcspconsulting.com:8000`) because the field can't be empty. Pulled the CI image, Running; the live page showed the Lite mark (only rendered when `/health` reports `engine: "lite"`). The CLI could not curl the domain (session egress allowlist), so that rendered page is the verification.
- **Smoke test (James, test PDF "Bayside Pet Clinic Guide 2026", 5 pages):** 10/12 AI answers passed — single facts incl. a table cell, multi-page answers, the three not-in-document questions (no invention). **Failed:** a two-figure total ($118 instead of $103: used the second-miss deposit instead of the $35 late-cancellation fee; the question's "missed" vs the document's "late cancellation" was also ambiguous). **Found:** after a refresh the previous upload was still answerable — every visitor shared one document (D-4 carried over from RAG).
- **Fix 1 — one document per visitor (D-6):** `DocumentStore` in `main_lite.py` keyed by an HttpOnly, SameSite=Lax, Secure-on-HTTPS cookie `askdoc_session` (random 24-byte token), set on upload. `/health` and `/ask` see only the visitor's own document; a guessed or foreign cookie sees nothing. Documents expire after `LITE_DOC_TTL_SECONDS` (3600) unused; beyond `LITE_MAX_DOCS` (40) the least recently used is dropped. Uploads still build into a fresh document first, so a failed upload keeps the current one. The UI restores "Ready · still loaded" after a refresh.
- **Fix 2 — calculation instruction:** `SYSTEM_PROMPT` now asks for the document figures behind any calculation and to say when the document doesn't cover the exact situation.
- **Model:** still the default `claude-haiku-4-5-20251001`; James is trying `LLM_MODEL=claude-haiku-5-5` via Coolify env (no code change).
- **Files:** `app/main_lite.py`, `app/lite.py`, `app/static/index.html`, `test_lite.py` (cookie flags, refresh, stranger/forged cookie, two visitors, failed upload, LRU + expiry, prompt).
- **Verified:** all three test scripts pass; browser check: refresh keeps the visitor's file, a second browser context sees none.
- **Outcome:** committed and pushed; goes live on the next manual Redeploy of the Lite resource.

### [v0.8.2] — Nov 4, 2026 — Lite smoke test complete; deploy race found; restored-document UI
**Summary:** v0.8.1 is live and every smoke test passes; one deploy-order trap and one small UI leftover fixed or logged.
- **Deploy race:** the Lite resource was created with Coolify auto-deploy **on** ("Deploy on push (webhooks)"). The v0.8.1 push deployed `36956a0` at once and pulled the *previous* `aidemo-lite:latest`, because `build-lite` only finished minutes later; the refresh test then failed against old code. A manual Redeploy after the green build fixed it. Rule (already §4.4 for RAG): CI green → then Deploy. Auto-deploy to be switched off (OPEN-13) until INFRA-12 deploys from the workflow.
- **Smoke test (James, live, `LLM_MODEL=claude-haiku-5-5`):** total-cost calculation passed (Q8 now correct, figures shown), bundle + consultation total passed, refresh keeps the document ("Ready · still loaded"), a private window sees no document, a `.jpg` is refused with the file-type message, parking fee → "couldn't find" with no invention. With v0.8.1's 10/12, all checks pass (OPEN-11 closed). `www.aidemo` domain removed (OPEN-12 closed).
- **UI fix:** after a refresh restores the visitor's document, the "Upload a document to begin" prompt is now removed (`app/static/index.html`).
- **Watch item:** one restored-session answer repeated its first sentence ("The current medical director is Dr. Samuel Okafor. The current medical director is…"). Text blocks are joined exactly as the API returns them, so this is model output around a citation, not a join bug; re-check if it recurs (OPEN-14).
- **Verified:** all three test scripts pass.
- **Outcome:** committed and pushed; goes live on a manual Redeploy after `build-lite` is green.

### [v0.9.0] — Nov 6, 2026 — Several documents per visitor; HOA, dental and any-business pages with sample packs
**Summary:** James approved (Nov 6) up to 5 documents per visitor and three industry pages, each with its own sample documents, so prospects see their own industry and the multi-file product. Built after the marketplace research showed industry buyers are reached directly, with a demo link per industry.
- **Engine (`app/lite.py`):** `LiteDocument` replaced by `read_file` → `LiteFile` and `LiteLibrary`. One document block per file, each with citations; one `cache_control` breakpoint on the last block caches the whole library. Citations map `document_index` → file and `start_block_index` → page/part. Limits: `LITE_MAX_FILES` (5) → `TooMany` (409), `LITE_MAX_CHARS` (400,000, now for the whole library) → `TooLarge` (413), both checked before the library changes. A file with the same name replaces the old one. System prompt now plural, and says to report when two documents disagree.
- **Routes (`app/main_lite.py`):** `/upload` adds to the library; new `/remove` and `/samples/{pack}`; `/`, `/hoa`, `/dental` serve `lite.html`; `/health` adds `documents` (keeps `document`/`kind` as the first file for v0.8 clients). Sample packs are read once and shared; loading one makes no AI call, so it doesn't count against the question guard.
- **UI (`app/static/lite.html`, new — D-7):** Lite gets its own page; `index.html` stays RAG's. Industry tabs, accent per industry (teal / green / blue), sample pack card with "Load sample documents" and links to open each PDF, file list with remove, up to 5 uploads (several at once), starter questions per industry, sources labelled with file and page. Phone: no sideways scroll, and the chat scrolls into view when a question is asked.
- **Sample packs (`app/static/samples/`, `tools/samples/make_samples.py`, committed in 2c226ed):** 9 fictional PDFs, 23 pages, about 18,000 characters in total.
- **Shared extraction path:** unchanged.
- **Verified:** `test_lite.py` ALL LITE CHECKS PASSED (29 checks, incl. two-file citations, replace by name, limits that leave the library untouched, remove, the three packs, page routes, sample PDFs served, isolation incl. remove by a stranger); `test_pipeline.py` and `test_api.py` pass. Browser run against a fake API: each tab loads its pack, answers cite file + page, refresh keeps the library, remove works, phone width 390 px with no overflow.
- **Outcome:** committed and pushed; goes live on a manual Redeploy after `build-lite` is green. Live smoke test is OPEN-15.

---

## SECTION 6 — DECISIONS

- **D-1 — Deploy via Coolify, not Launchpad.** Launchpad clones a fixed Laravel `site-template`, builds with `serversideup/php`, and requires a shared-Postgres database it can't skip. AskDoc is Python/FastAPI with no database. Launchpad can't point at an existing repo and would produce a broken Laravel shell. A hand-made Coolify Docker-Compose resource is the correct tool; it shares the same VPS/Coolify but is not in Launchpad's ledger, so no interference.
- **D-2 — `expose` over `ports` in base compose.** Lets Coolify's proxy route by domain and avoids host-port collisions on a shared box. Local dev port is restored by a git-ignored override so both workflows stay correct.
- **D-3 — Provider-swappable LLM + local embeddings.** Only `ANTHROPIC_API_KEY` is needed to run; embeddings are free and local; one env line switches to OpenAI. Doubles as a client-facing selling point.
- **D-4 — Known limitation, accepted for a demo:** one document held in memory, shared across all visitors — two simultaneous users overwrite each other. Per-session storage / a vector DB is a future feature, not a bug to fix now. The 20 MB cap bounds embedding input, not peak RAM; the reverse-proxy body limit is the real guard (OPEN-4). Lite inherits the same one-shared-document model.
- **D-5 — Two editions; Lite takes the public domain (Nov 4, 2026).** AskDoc Lite lives in this repo (shares UI, extraction and tests) as a second image, and takes over `aidemo.mcspconsulting.com`, the URL already linked from the MCSP site and the Fiverr gig. AskDoc RAG is presented as the "big brother" for large document libraries and heavy use; it returns on its own subdomain (e.g. `rag.mcspconsulting.com`) when it has its own server. Client hosting default: MCSP builds and runs a new dedicated server for the client and charges for maintaining it; building on the client's own VPS/server is offered as an option, never assumed.
- **D-6 — Lite keeps one document per visitor (Nov 4, 2026).** Supersedes D-4 for Lite: on a public demo a shared document would let one prospect read another's upload. Session cookie + in-memory store with expiry and an LRU cap; no database, still one small container. RAG keeps D-4 until it is revived (APP-05).
- **D-7 — Lite has its own page and multi-document libraries (Nov 6, 2026).** The Lite UI (industry tabs, sample packs, a file list) no longer matches RAG's, so `lite.html` replaces the shared `index.html` for Lite; extraction and tests stay shared. A visitor may hold up to 5 files read together, because real buyers' questions span documents (CC&Rs + fee schedule, office manual + insurance plan). Industry pages share one codebase; only words, questions, samples and the accent colour differ.

---

## ►► START HERE NEXT SESSION ◄◄

### ✅ DONE
- Built, tested, hardened, committed, pushed (`mcsp-web/aidemo`, `main`).
- Coolify app live (**Running**) via GitHub App source, Docker Compose build pack.
- Domain bound (`aidemo.mcspconsulting.com` → `askdoc:8000`), HTTP→HTTPS on, `ANTHROPIC_API_KEY` set.
- Repo `mcsp-web/aidemo` set **private**; VPS IP redacted from the canon (OPEN-1 closed).
- Image builds moved to GitHub Actions → GHCR; Coolify pulls the prebuilt image (INFRA-11, v0.7.0).
- DNS **proxied** (orange) confirmed — `CF-RAY` header observed live on `aidemo.mcspconsulting.com` (OPEN-2 closed).
- Domain routing survives a redeploy — after the v0.7.0 pull redeploy, `GET /` via the domain returned 200 and `/health` returned 200; re-checked Sept 14 (OPEN-5 closed). `SERVICE_FQDN_ASKDOC_8000` is committed in `docker-compose.yml`.
- Runtime cost measured before shelving: 202 MiB RAM (5.3%), 0.12% CPU idle, ~3.2 GB image; stopping freed ~400 MiB RAM and cut swap ~524 → ~165 MiB (OPEN-7 closed).
- **Shelved** (v0.7.2): container stopped in Coolify to conserve the shared VPS; revive via Deploy — see §5 v0.7.2.
- **AskDoc Lite built** (v0.8.0): whole-document + citations edition, shared extraction module, own CI image `ghcr.io/mcsp-web/aidemo-lite`; all three test scripts green; pushed.
- **AskDoc Lite live** at `aidemo.mcspconsulting.com` (v0.8.1, OPEN-10 closed); per-visitor documents + calculation prompt live.
- **Lite smoke test passed in full** (v0.8.2, OPEN-11 and OPEN-12 closed); `LLM_MODEL=claude-haiku-5-5` on the live resource.
- **Several documents + industry pages built** (v0.9.0): `/hoa`, `/dental`, `/` with sample packs, up to 5 files per visitor; all three test suites green; pushed.

### ⏳ OPEN — do these next
- **OPEN-13 — Switch off auto-deploy on the Lite resource (James, Coolify):** Configuration → Advanced → Deployment → Auto deploy → the off/manual option → Save. Then every deploy is: `build-lite` green → Redeploy.
- **OPEN-15 — v0.9.0 live smoke test (BOLD, James):** after `build-lite` is green, Redeploy. On `/hoa`: Load sample documents → ask "Can I put up a wood fence, and what does it cost to apply?" → expect "no, vinyl or aluminum only" + $50, quoting the CC&Rs and the Rules and Fees file. On `/dental`: the third-cleaning question → quotes the PPO summary. On `/`: the $3,000 purchase question → department head. Then: add one of your own files (6th file refused), remove one, refresh (library stays), open a private window (empty).
- **OPEN-14 — Watch for repeated sentences in answers** (one seen on Nov 4). If it recurs, capture the raw API content blocks from the log and decide on a fix. *(CLI)*
- **OPEN-3 — Live smoke test (BOLD, James):** load the URL, upload a PDF, ask a question, confirm a real Claude answer **and** the sources panel. This is the only proof the key + live LLM call work.
- **OPEN-4 — Set the Coolify reverse-proxy client-body-size to ~25 MB** — the real backstop behind the in-app 20 MB cap. *(James)*
- **OPEN-6 — Tidy domains.** Ensure only `aidemo.mcspconsulting.com` remains — delete the auto `*.sslip.io` domain and the unused `www.aidemo` variant if still present.
- **OPEN-8 — Actions-triggered deploy (INFRA-12).** Add a `deploy` job (`needs: build`) to `build-image.yml` that calls Coolify's deploy webhook after a green build — restores push-to-deploy without the build race; Coolify's git auto-deploy stays off. Needs `COOLIFY_TOKEN` + `COOLIFY_DEPLOY_URL` as repo secrets, and `coolify.mcspconsulting.com` reachable from GitHub runners. *(James: token + secrets · CLI: workflow job)*
- **OPEN-9 — CPU-only torch (INFRA-13).** Install torch from the CPU wheel index to drop ~1 GB of CUDA/triton from the ~3.2 GB image (smaller pull + disk). Changes image contents and forces a full CI rebuild — its own concern, propose-first. *(CLI)*

### 🔗 CROSS-PROJECT LOOPS (opened this session, tracked elsewhere)
- **Portfolio** (`mcsp-web/portfolio`) — "AskDoc Lite" listed as its own project, the little brother of AskDoc (RAG). Once OPEN-11 passes, its live link can be switched on.
- **mcspconsulting AI service page** — once OPEN-11 passes, re-enable the demo link (`AI_DEMO_URL` = `https://aidemo.mcspconsulting.com`).
- **mcspconsulting AI service page** — build brief written; awaiting its recon report. Its "see a live demo" link is gated on one config value and turns on once **OPEN-3** confirms the URL is live.
- **GTM assets** — once the demo is confirmed live: screenshot it for the Fiverr gallery (image 3) and record the 30-second demo video.

*End of MASTER CANON — AskDoc v0.9.0*
