# progsu Intelligence Agent

[![CI](https://github.com/JohnSang16/progsu-intelligence-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/JohnSang16/progsu-intelligence-agent/actions/workflows/ci.yml)

**Live demo:** https://frontend-coral-mu-47.vercel.app · **Devpost:** https://devpost.com/software/progsu-intelligence-agent

---

## The Problem

Student orgs run on Google Drive and Discord. Meeting notes, event playbooks, vendor negotiations, sponsor decks — scattered across hundreds of documents and threads that only the current leadership knows exist. When people graduate, the knowledge graduates with them, and the org relearns the same lessons every year.

## What It Does

Ingests an org's Drive and Discord history, embeds it into a searchable knowledge base, and answers questions grounded in what the org actually did — with citations back to the source, not a guess. Four modes, auto-classified from the question:

- **RECALL** — "What happened at X?" Cited answer from the actual docs/messages.
- **ANALYZE** — "How have our metrics trended?" Synthesizes across sources with real numbers.
- **PLAN** — "Help plan X." Retrieves + synthesizes, then creates a real Google Doc, Calendar event, and Gmail draft.
- **CHAT** — small talk / capability questions, skips retrieval entirely.

Access is tiered by Discord role (anonymous → member → exec → admin), so financial data and leadership-only sources stay gated without needing a separate private deployment.

## How It Works

```
Google Drive + Discord
        │
        ▼
  Ingestion            PII strip → chunk → noise filter → access-classify →
                        embed → store. Runs on a schedule; only re-processes
                        what changed since last run.
        │
        ▼
  MongoDB Atlas         Vector search index + per-chunk access_level tag
        │
        ▼
  Query pipeline        classify mode → retrieve (vector search) → rerank →
                        confidence gate → generate → verify → act (PLAN only)
        │
        ▼
  React frontend        Streamed answer, citations, mode badge, doc/calendar/
                        email links when PLAN fires
```

Every answer is grounded: a confidence gate blocks generation on weak retrieval, and a post-generation check flags claims that don't trace back to a cited source. Full prompt-level detail lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Repo at a Glance

```
src/
  ingestion/     Drive + Discord readers, chunking, PII/noise filters,
                 access classifier, weekly delta sync
  retrieval/     Vector search + reranker
  agent/         Mode classification, generation, PLAN tools (Doc/Calendar/Gmail)
  api/           FastAPI server, auth, rate limiting
  frontend/      React + Vite + TypeScript UI
docs/            Architecture, PII policy, data map, testing
tests/           Unit + integration + eval suites
org_config.json  Org-specific values (gitignored) — swap this, not the code,
                 to point the agent at a different org
```

## Running It

```bash
git clone https://github.com/johnsang16/progsu-intelligence-agent
cd progsu-intelligence-agent
cp .env.example .env && cp org_config.example.json org_config.json
# fill in API keys and your org's values

pip install -r requirements.txt
python -m src.ingestion.run_ingestion --priority 1   # first ingest
python -m src.api.server                             # backend

cd src/frontend && npm install && npm run dev        # frontend

python -m src.ingestion.run_weekly_sync --dry-run    # preview a refresh
python -m src.ingestion.run_weekly_sync              # Drive delta + Discord window
```

Discord auth and the weekly sync are optional — everything falls back to a single-tier public demo if those env vars are unset.

## Tech Stack

| Layer | Technology |
|---|---|
| LLM + Embeddings | Gemini 2.5 Flash + gemini-embedding-001 (768-dim) |
| Vector + Document Store | MongoDB Atlas Vector Search |
| Auth | Discord OAuth, role-mapped access tiers |
| Drive / Calendar / Gmail | Google APIs |
| Backend | Python 3.11 / FastAPI on Cloud Run (streaming SSE) |
| Frontend | React + Vite + TypeScript + Tailwind v4 on Vercel |

## Future Scope

- **Hybrid retrieval** — combine vector + keyword search (Atlas `$rankFusion`) so exact-phrase queries stop losing to pure semantic similarity
- **Critic agent** — a second pass that reviews PLAN output against historical data and flags gaps before it ships
- **Discord `/ask` slash command** — meet members where they already are instead of requiring the web UI
- **Move in-memory state to Atlas** — cache, rate limiter, and daily cap currently reset on every Cloud Run cold start
- **Permission overrides** — grant a member temporary elevated access for one task without a full role change

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design, prompts, deployment
- [docs/PII_RULES.md](docs/PII_RULES.md) — privacy and financial data classification policy
- [docs/DATA_MAP.md](docs/DATA_MAP.md) — Drive file inventory
- [docs/TESTING.md](docs/TESTING.md) — eval suites and quality thresholds

## License

MIT. See [LICENSE](LICENSE).
