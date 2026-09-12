# CLAUDE.md — AskDoc (aidemo)

Auto-loaded by Claude Code. **Before scoping any work, read `docs/MASTER_CANON.md` (source of truth) and `docs/ROADMAP.md` (derived from it).**

## What this is
AskDoc — an AI document-Q&A demo: upload a document, ask questions, get answers grounded in the file with sources shown. FastAPI · local sentence-transformers embeddings · Claude (provider-swappable to OpenAI). Live at https://aidemo.mcspconsulting.com. A sales/portfolio asset for MCSP's AI-integration service line. Full identity: canon Section 1.

## Operating protocol
- **Recon first.** Read live source before scoping anything that touches it. No blind edits.
- **Propose-first** on any request-validation contract, the shared extraction path, or a production event: propose the plan and wait for the go before writing.
- **One concern per box, one concern per commit.** Never bundle unrelated changes.
- **CLI delivery:** one prompt per copy box, the run instruction lives inside the box, paste output back before the next is assumed run. Track open loops — never let a handed-off prompt pass silently without a report back.
- **Production-access rule:** read-only prod checks (container status, logs, `curl` of a route, response headers) may be run directly. Anything needing a secret or credential → James. Anything the CLI can't actually verify — visual/UX, "does it look right", rendered output — is stated in **BOLD** for James and never handed to the CLI.
- **Tests before push:** `test_pipeline.py` and `test_api.py` must pass before every push and before every canon write. A change to the upload/validation contract or the shared extraction path triggers a full test run at commit. (Tests need dev-only `reportlab` + `httpx`; run from repo root.)
- **Canon-first:** `docs/MASTER_CANON.md` is the source of truth; `docs/ROADMAP.md` is derived. On "update canon": append a dated, versioned entry (files, reason, outcome), bump the header version, reconcile the roadmap.

## Build & deploy
- Repo: `mcsp-web/aidemo` (private), branch `main`. Coolify project `aidemo` → production. Auth via GitHub App source; auto-deploy on push.
- **Rebuild cost:** any change to `requirements.txt` busts the pip layer and forces a full rebuild (torch ~2–2.5 GB) on the 4 GB shared VPS. Don't rebuild under load. Planned: build locally and push a prebuilt image (see ROADMAP `INFRA-11`); until then, if a server rebuild struggles, build the image locally and push it.
- Deploy is NOT via Launchpad — Launchpad is a Laravel-only factory (canon Decision D-1). This is a hand-made Coolify Docker-Compose resource.
- Secrets live only in Coolify env (`ANTHROPIC_API_KEY`). Never in the repo.

## Never commit
`.env`, the real `docker-compose.override.yml`, any secret. Enforced by `.gitignore`.
