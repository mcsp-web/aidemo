# ROADMAP — AskDoc (aidemo)
**Derived from `MASTER_CANON.md` v0.7.1 · Sept 14, 2026**

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

---

## ⏳ NEXT (finish the deploy — mostly James, small surface)

| ID | Item | Owner | Canon ref |
|---|---|---|---|
| INFRA-05 | Live smoke test: upload a PDF, ask a question, confirm answer + sources | **James** | OPEN-3 |
| HARDEN-03 | Coolify reverse-proxy client-body-size ~25 MB (upload backstop) | **James** | OPEN-4 |
| INFRA-09 | Tidy domains — keep only `aidemo.mcspconsulting.com` | **James** | OPEN-6 |
| INFRA-10 | Watch runtime RAM + image disk on the shared box — VPS no longer builds, pulls only | James | OPEN-7 |
| INFRA-12 | Actions-triggered deploy — workflow calls Coolify's deploy webhook after a green build, restoring push-to-deploy without the build-race (Coolify git auto-deploy stays off). Needs `COOLIFY_TOKEN` + `COOLIFY_DEPLOY_URL` as repo secrets | James + CLI | OPEN-8 |
| INFRA-13 | Switch to CPU-only torch wheel to drop ~1 GB CUDA/triton from the 3.2 GB image (cuts pull time + disk) | CLI | OPEN-9 |

---

## 🔜 SOON (go-to-market — unblocked once INFRA-05 confirms live)

| ID | Item | Notes |
|---|---|---|
| GTM-01 | Screenshot the live demo for the Fiverr gallery (image 3, sources panel open) | Needs live URL |
| GTM-02 | Record the 30-second demo video (own voice + screen recording) | Script already drafted |
| GTM-03 | Turn on the "see a live demo" link in the mcspconsulting AI service page | Gated on the live URL |
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

---

## Milestone line
`v0.1.0 built → v0.2.0 hardened → v0.3.0 pushed → v0.4.0 live on Coolify → v0.5.0 governance → v0.6.0 multi-format + fixes → v0.7.0 build-off-server CI/CD (live via pull, proxied) → (next) push-to-deploy (INFRA-12) + smoke-tested + demo linked`

*End of ROADMAP — AskDoc*
