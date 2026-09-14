# MASTER CANON — AskDoc (aidemo)
**Last Updated:** September 14, 2026 (session 2)
**Current Version:** v0.7.1
**Stack:** Python 3.11 · FastAPI · sentence-transformers · Anthropic Claude (swappable → OpenAI) · Docker · Coolify · Cloudflare · Hetzner

> Bootstrap canon. This project has no `_canon/apply.php` machinery — this file is
> maintained directly and committed via Claude Code. Canon-first: this file is the
> source of truth; `ROADMAP.md` is derived from it.

---

## SECTION 1 — SYSTEM IDENTITY

**Project:** AskDoc — AI document-Q&A demo ("Ask Your Document")
**Type:** Portfolio / sales-demo web app for the AI-integration service line
**Org / Billing / Market:** MCSP Consulting · `mcsp-web` GitHub org · USD · used as a live demo for Fiverr gigs and the mcspconsulting.com AI service page
**What it does:** upload a PDF → text is extracted, chunked, and embedded locally → ask a question → the closest chunks are retrieved by cosine similarity and sent to an LLM → the answer is generated **from those passages only**, with the source pages shown.
**Run surface:** public web app at `https://aidemo.mcspconsulting.com`. Local dev at `http://localhost:8000`.
**Local path:** `D:\laragon\www\Freelance\`
**Repo:** `github.com/mcsp-web/aidemo` (branch `main`) — **private** (OPEN-1 closed).

---

## SECTION 2 — SOURCE OF TRUTH REGISTRY

Authoritative files. Audit against these before changing anything.

| Role | File | Authority |
|---|---|---|
| Web app / routes | `app/main.py` | FastAPI app; routes `/`, `/upload`, `/ask`, `/health`; upload hardening (size cap + threadpool) |
| Retrieval engine | `app/rag.py` | Multi-format extraction (pdf/docx/txt/md), chunking, local embeddings, in-memory `DocumentIndex`, cosine search |
| Generation layer | `app/llm.py` | Provider-swappable answer generation; `SYSTEM_PROMPT`; answers from passages only |
| Frontend | `app/static/index.html` | Single-page UI — upload, chat, expandable sources |
| Package marker | `app/__init__.py` | Makes `app` an explicit package (empty) |
| Image build | `Dockerfile` | `python:3.11-slim`; **bakes the embedding model at build time** so the container needs no network for embeddings |
| CI build + publish | `.github/workflows/build-image.yml` | On push to `main` (image-affecting paths only): **test** job (suite, torch stubbed) → **build** job (`linux/amd64`) → pushes `ghcr.io/mcsp-web/aidemo` `:latest` + `:sha-*` with a registry buildcache. The **only** publisher of the image |
| Deploy config | `docker-compose.yml` | Service `askdoc`; `image: ghcr.io/mcsp-web/aidemo:latest` + `pull_policy: always` (pulls the CI-built image — no `build:`); `expose: 8000` (no host port); healthcheck on `/health`; env block; `restart: unless-stopped` |
| Local-run template | `docker-compose.override.yml.example` | Copied to the git-ignored `docker-compose.override.yml` for **local dev only**: `build: .` + `pull_policy: build` (builds from source), tags the result `aidemo-local:dev` so it can't target GHCR, republishes port 8000. Never pushed |
| Git hygiene | `.gitignore`, `.dockerignore` | `.env` + real override never committed; tests/README kept out of the image |
| Dependencies | `requirements.txt` | 9 pinned deps (`python-docx` added in v0.6.0) |
| Docs | `README.md` | Run + deploy instructions (kept out of the image via `.dockerignore`) |
| Tests | `test_pipeline.py`, `test_api.py` | Assert-scripts (not pytest); need dev-only `reportlab` + `httpx`; run from repo root |

**API contract (frontend ↔ backend):**
```
POST /upload  (multipart: file=<.pdf|.docx|.txt|.md>)  -> { filename, chunks, kind }
POST /ask     ({ question })                           -> { answer, sources:[{ page, score, text }], kind }
GET  /health                                           -> { status, document, ready }
GET  /                                                 -> index.html
```
`kind` is `"page"` (PDF) or `"part"` (synthesized units for DOCX/TXT/MD) — the UI labels sources "Page N" / "Part N" from it. Upload errors: unsupported type → 400; legacy `.doc` passes the gate → 422 "save as .docx"; no readable text → 422; > 20 MB → 413.

**Runtime config (env-driven, no code change to switch):**
| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | or `openai` |
| `LLM_MODEL` | `claude-haiku-4-5-20251001` | e.g. a Sonnet model for higher quality, or `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | — | required for Claude; **set in Coolify UI only, never in repo** |
| `OPENAI_API_KEY` | — | only if provider = openai |

---

## SECTION 3 — INFRASTRUCTURE REGISTRY

| Item | Value |
|---|---|
| VPS | Hetzner CPX21 · `see coolify.mcspconsulting.com / Hetzner console` · 4 GB RAM nominal (~3.7 GB usable) · 3 vCPU · 80 GB — **shared with PureOps, MinIO, and client sites** |
| Coolify | `https://coolify.mcspconsulting.com` · project **aidemo** / environment **production** |
| App resource | Application (Docker Compose build pack), source = **GitHub App** (`mcsp-web`), repo `aidemo`, branch `main` |
| Auth to GitHub | **GitHub App source** (not a deploy key) — enables auto-deploy webhooks. Org deploy-keys policy left **Disabled** |
| Auto-deploy | **Manual** (auto-deploy off); Actions-triggered deploy planned (INFRA-12) |
| Build | GitHub Actions builds → GHCR; Coolify pulls `ghcr.io/mcsp-web/aidemo:latest` (`pull_policy: always`). **VPS never builds.** |
| Domain | `aidemo.mcspconsulting.com` → Cloudflare A record → `see coolify.mcspconsulting.com / Hetzner console` |
| DNS state | **Proxied (orange)** — confirmed live via `Server: cloudflare` + `CF-RAY` response headers (OPEN-2 closed) |
| Domain binding | Added in Coolify UI: `https://aidemo.mcspconsulting.com` on service `askdoc`, internal port `8000`. HTTP→HTTPS redirect enabled |
| Secrets | `ANTHROPIC_API_KEY` in Coolify Environment Variables UI — the only secret; never in the repo |

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

---

## SECTION 6 — DECISIONS

- **D-1 — Deploy via Coolify, not Launchpad.** Launchpad clones a fixed Laravel `site-template`, builds with `serversideup/php`, and requires a shared-Postgres database it can't skip. AskDoc is Python/FastAPI with no database. Launchpad can't point at an existing repo and would produce a broken Laravel shell. A hand-made Coolify Docker-Compose resource is the correct tool; it shares the same VPS/Coolify but is not in Launchpad's ledger, so no interference.
- **D-2 — `expose` over `ports` in base compose.** Lets Coolify's proxy route by domain and avoids host-port collisions on a shared box. Local dev port is restored by a git-ignored override so both workflows stay correct.
- **D-3 — Provider-swappable LLM + local embeddings.** Only `ANTHROPIC_API_KEY` is needed to run; embeddings are free and local; one env line switches to OpenAI. Doubles as a client-facing selling point.
- **D-4 — Known limitation, accepted for a demo:** one document held in memory, shared across all visitors — two simultaneous users overwrite each other. Per-session storage / a vector DB is a future feature, not a bug to fix now. The 20 MB cap bounds embedding input, not peak RAM; the reverse-proxy body limit is the real guard (OPEN-4).

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

### ⏳ OPEN — do these next
- **OPEN-3 — Live smoke test (BOLD, James):** load the URL, upload a PDF, ask a question, confirm a real Claude answer **and** the sources panel. This is the only proof the key + live LLM call work.
- **OPEN-4 — Set the Coolify reverse-proxy client-body-size to ~25 MB** — the real backstop behind the in-app 20 MB cap. *(James)*
- **OPEN-6 — Tidy domains.** Ensure only `aidemo.mcspconsulting.com` remains — delete the auto `*.sslip.io` domain and the unused `www.aidemo` variant if still present.
- **OPEN-7 — Watch runtime RAM + disk on the shared box.** The VPS no longer builds — images come from GitHub Actions → GHCR — so the original build-time RAM risk is gone. What remains is the running container's footprint (torch + the embedding model in memory) on a 4 GB (~3.7 GB usable) box shared with PureOps, MinIO, and client sites, plus disk for pulled image layers (~3.2 GB each). Check container memory in Coolify after deploys and prune old images. INFRA-13 (OPEN-9) shrinks the image and pull; don't assume it cuts RAM without measuring. *(James)*
- **OPEN-8 — Actions-triggered deploy (INFRA-12).** Add a `deploy` job (`needs: build`) to `build-image.yml` that calls Coolify's deploy webhook after a green build — restores push-to-deploy without the build race; Coolify's git auto-deploy stays off. Needs `COOLIFY_TOKEN` + `COOLIFY_DEPLOY_URL` as repo secrets, and `coolify.mcspconsulting.com` reachable from GitHub runners. *(James: token + secrets · CLI: workflow job)*
- **OPEN-9 — CPU-only torch (INFRA-13).** Install torch from the CPU wheel index to drop ~1 GB of CUDA/triton from the ~3.2 GB image (smaller pull + disk). Changes image contents and forces a full CI rebuild — its own concern, propose-first. *(CLI)*

### 🔗 CROSS-PROJECT LOOPS (opened this session, tracked elsewhere)
- **mcspconsulting AI service page** — build brief written; awaiting its recon report. Its "see a live demo" link is gated on one config value and turns on once **OPEN-3** confirms the URL is live.
- **GTM assets** — once the demo is confirmed live: screenshot it for the Fiverr gallery (image 3) and record the 30-second demo video.

*End of MASTER CANON — AskDoc v0.7.1*
