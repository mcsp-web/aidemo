# Ask Your Document — AI document Q&A demo

A small, production-shaped RAG app: upload a PDF, ask questions, get answers
grounded **only** in that document, with the source passages shown so answers
are verifiable.

**Stack:** FastAPI · local sentence-transformers embeddings · Claude (swappable to GPT) · one Docker container.

---

## How it works

1. **Upload** — the PDF's text is extracted and split into overlapping chunks.
2. **Embed** — each chunk becomes a vector, using a small model that runs
   locally (no cost, no second vendor).
3. **Ask** — your question is embedded, the closest chunks are retrieved by
   cosine similarity, and those passages + your question go to the LLM.
4. **Answer** — the model replies using only those passages, and the app shows
   which pages the answer came from.

The only external API call in the whole app is the final answer step.

---

## Run it locally

```bash
cp .env.example .env        # then paste your Anthropic key into .env
cp docker-compose.override.yml.example docker-compose.override.yml
docker compose up --build
```

Open http://localhost:8000

The compose file uses `expose` rather than a published port, so Coolify's proxy
can route to it by domain. That second copy is what republishes port 8000 on
your own machine — it's git-ignored, so each clone needs it once.

> First build takes a few minutes — it downloads the embedding model once and
> bakes it into the image. After that, startup is instant.

Get a key at https://console.anthropic.com → Settings → API Keys. Demo usage
costs a fraction of a cent per question on the default Haiku model.

---

## Deploy to your VPS (Coolify)

1. Push this folder to a Git repo.
2. In Coolify: **New Resource → Docker Compose**, point it at the repo.
3. Add an environment variable **`ANTHROPIC_API_KEY`** with your key.
4. Set a domain (e.g. `demo.yourdomain.com`) and deploy.

That public URL is what goes in your Fiverr gallery.

---

## Swapping the model or provider

Everything is env-driven — no code changes:

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | or `openai` |
| `LLM_MODEL` | `claude-haiku-4-5-20251001` | e.g. `claude-sonnet-5` for higher quality, or `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | — | required for Claude |
| `OPENAI_API_KEY` | — | required only if using OpenAI |

Being able to switch providers in one line is a genuine selling point — show it.

---

## Tests (optional)

`test_pipeline.py` and `test_api.py` verify the retrieval and HTTP layers using
lightweight stubs (they need `reportlab`, a dev-only dependency). Run with:

```bash
pip install reportlab httpx
python test_pipeline.py && python test_api.py
```

---

## Ideas for turning this into paid work

- Per-user documents stored in a real vector database (Pinecone, pgvector, Qdrant)
- Multiple documents at once / a document library
- Show answer confidence and let users click through to the exact source page
- Wrap it into an existing Laravel/Vue app instead of a standalone page
