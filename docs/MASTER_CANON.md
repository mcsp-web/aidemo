# MASTER CANON — AskDoc (aidemo)
**Last Updated:** September 13, 2026 (session 2)
**Current Version:** v0.6.0
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
**Repo:** `github.com/mcsp-web/aidemo` (branch `main`) — visibility to be confirmed (see OPEN-1).

---

## SECTION 2 — SOURCE OF TRUTH REGISTRY

Authoritative files. Audit against these before changing anything.

| Role | File | Authority |
|---|---|---|
| Web app / routes | `app/main.py` | FastAPI app; routes `/`, `/upload`, `/ask`, `/health`; upload hardening (size cap + threadpool) |
| Retrieval engine | `app/rag.py` | PDF extraction, chunking, local embeddings, in-memory `DocumentIndex`, cosine search |
| Generation layer | `app/llm.py` | Provider-swappable answer generation; `SYSTEM_PROMPT`; answers from passages only |
| Frontend | `app/static/index.html` | Single-page UI — upload, chat, expandable sources |
| Package marker | `app/__init__.py` | Makes `app` an explicit package (empty) |
| Image build | `Dockerfile` | `python:3.11-slim`; **bakes the embedding model at build time** so the container needs no network for embeddings |
| Deploy config | `docker-compose.yml` | Service `askdoc`; `expose: 8000` (no host port); healthcheck on `/health`; env block; `restart: unless-stopped` |
| Local-run template | `docker-compose.override.yml.example` | Copied to the git-ignored `docker-compose.override.yml` to republish port 8000 locally |
| Git hygiene | `.gitignore`, `.dockerignore` | `.env` + real override never committed; tests/README kept out of the image |
| Dependencies | `requirements.txt` | 8 pinned deps |
| Docs | `README.md` | Run + deploy instructions (kept out of the image via `.dockerignore`) |
| Tests | `test_pipeline.py`, `test_api.py` | Assert-scripts (not pytest); need dev-only `reportlab` + `httpx`; run from repo root |

**API contract (frontend ↔ backend):**
```
POST /upload  (multipart: file=<pdf>)  -> { filename, chunks }
POST /ask     ({ question })           -> { answer, sources:[{ page, score, text }] }
GET  /health                           -> { status, document, ready }
GET  /                                 -> index.html
```

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
| VPS | Hetzner CPX21 · `see coolify.mcspconsulting.com / Hetzner console` · 4 GB RAM · 3 vCPU · 80 GB — **shared with PureOps, MinIO, and client sites** |
| Coolify | `https://coolify.mcspconsulting.com` · project **aidemo** / environment **production** |
| App resource | Application (Docker Compose build pack), source = **GitHub App** (`mcsp-web`), repo `aidemo`, branch `main` |
| Auth to GitHub | **GitHub App source** (not a deploy key) — enables auto-deploy webhooks. Org deploy-keys policy left **Disabled** |
| Auto-deploy | On push to `main` (webhook) |
| Build | Coolify builds the image on the server from `Dockerfile` via compose. **First build pulls torch (~2–2.5 GB)** — the resource risk on a 4 GB shared box |
| Domain | `aidemo.mcspconsulting.com` → Cloudflare A record → `see coolify.mcspconsulting.com / Hetzner console` |
| DNS state | **Currently grey-cloud / DNS-only** (set for first cert issuance) — **must flip back to proxied** once HTTPS is confirmed (OPEN-2) |
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

### [v0.6.0] — Sept 13, 2026 — Multi-format ingestion + hardening
**Summary:** accept DOCX, TXT, MD alongside PDF; fix two adjacent defects found during the work.
- `rag.py`: `extract_pages(data, filename)` dispatches by extension and returns `(pages, kind)` where `kind` is `"page"` (pdf) or `"part"` (synthesized ~3000-char units for non-paged formats). DOCX walks paragraphs **and** tables. `build()` made **atomic** — commits to `self` only after embedding succeeds (fixes torn state where a failed upload after a good one left `ready=True` with mismatched chunks/vectors).
- `main.py`: upload gate widened to pdf/docx/doc/txt/md; `.doc` admitted deliberately so `rag.py` owns the single "save as .docx" 422; top-level `"kind"` added to `/upload` and `/ask` responses.
- `requirements.txt`: `python-docx==1.1.2` (pulls `lxml`, `typing-extensions`).
- Frontend: accept list + JS validation mirror the backend gate; `sourceLabel()` renders "Page N" / "Part N" from `kind`; copy generalized from PDF to document. Also fixed the drop-zone border — `.drop` is a `<label>` (default `display:inline`) with block children, which fragmented the inline box; `display:block` restores the dashed border and its vertical padding.
- Tests: multi-format + `.doc`-422 + `kind` coverage; fixed a non-ASCII char that made both scripts exit nonzero on cp1252 consoles despite passing.
- **Outcome:** feature complete across 7 commits, verified against stubs plus a real `python-docx` extraction. **Not yet deployed** — commits are local only.

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

### ⏳ OPEN — do these next
- **OPEN-1 — Confirm repo visibility.** Set `mcsp-web/aidemo` **private** — the README carries infra notes (VPS IP) and GTM strategy. *(James)*
- **OPEN-2 — Flip DNS back to proxied** (orange) once the cert issues on `aidemo.mcspconsulting.com`. Currently grey/DNS-only. *(James)*
- **OPEN-3 — Live smoke test (BOLD, James):** load the URL, upload a PDF, ask a question, confirm a real Claude answer **and** the sources panel. This is the only proof the key + live LLM call work.
- **OPEN-4 — Set the Coolify reverse-proxy client-body-size to ~25 MB** — the real backstop behind the in-app 20 MB cap. *(James)*
- **OPEN-5 — Verify routing survives a rebuild.** Confirm whether the domain binding persists on redeploy, or whether `docker-compose.yml` needs `SERVICE_FQDN_ASKDOC_8000` committed for the route to survive. Check on the next deploy.
- **OPEN-6 — Tidy domains.** Ensure only `aidemo.mcspconsulting.com` remains — delete the auto `*.sslip.io` domain and the unused `www.aidemo` variant if still present.
- **OPEN-7 — Watch RAM after first build.** torch is heavy on a shared 4 GB box; if a rebuild struggles, build the image elsewhere and push it instead.

### 🔗 CROSS-PROJECT LOOPS (opened this session, tracked elsewhere)
- **mcspconsulting AI service page** — build brief written; awaiting its recon report. Its "see a live demo" link is gated on one config value and turns on once **OPEN-3** confirms the URL is live.
- **GTM assets** — once the demo is confirmed live: screenshot it for the Fiverr gallery (image 3) and record the 30-second demo video.

*End of MASTER CANON — AskDoc v0.6.0*
