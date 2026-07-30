# progsu Intelligence Agent

[![CI](https://github.com/JohnSang16/progsu-intelligence-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/JohnSang16/progsu-intelligence-agent/actions/workflows/ci.yml)

Every student org loses institutional knowledge when people graduate. This agent ingests a year of Drive and Discord history and makes it instantly queryable and actionable, with cited answers and real Google Doc, Calendar, and email outputs.

Built for the [Google Cloud Rapid Agent Hackathon](https://rapid-agent.devpost.com), MongoDB track, then hardened for production use: Discord OAuth access tiers, ingestion-time data governance, and an automated weekly refresh. Details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

**Live demo:** https://frontend-coral-mu-47.vercel.app
**Devpost:** https://devpost.com/software/progsu-intelligence-agent

---

## What It Does

Four query modes:

- **CHAT** Small talk and capability questions, no retrieval.
- **RECALL** "What happened at X?" Grounded, cited answers from org documents.
- **ANALYZE** "How have our metrics trended?" Synthesizes across sources with real numbers.
- **PLAN** "Help plan X." Retrieves, synthesizes, and creates a Google Doc, Calendar event, and email draft.

Access is tiered by Discord role: anonymous visitors get a restricted public demo, members get cited search, exec board gets PLAN artifacts and financial data, admins get everything. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full tier breakdown.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM + Embeddings | Gemini 2.5 Flash + gemini-embedding-001 (768-dim) |
| Vector + Document Store | MongoDB Atlas with Atlas Vector Search |
| Auth | Discord OAuth, role-mapped access tiers |
| Drive / Calendar / Gmail | Google APIs (Docs, Calendar, Gmail) |
| Backend | Python 3.11 / FastAPI on Cloud Run (streaming SSE) |
| Frontend | React + Vite + TypeScript + Tailwind v4 on Vercel |

---

## Setup

```bash
git clone https://github.com/johnsang16/progsu-intelligence-agent
cd progsu-intelligence-agent
cp .env.example .env
cp org_config.example.json org_config.json
# fill in API keys in .env and your org's values in org_config.json
```

`org_config.json` holds everything org-specific (authoritative sources, sensitive phrase filters, event map, demo seeds). It is gitignored; the codebase itself is org-agnostic. Discord auth and the weekly sync are optional, documented inline in `.env.example`.

**Backend:**
```bash
pip install -r requirements.txt
python -m src.ingestion.run_ingestion --priority 1
python -m src.api.server
```

**Frontend:**
```bash
cd src/frontend
npm install
npm run dev
```

**Keeping data fresh:**
```bash
python -m src.ingestion.run_weekly_sync --dry-run   # preview, no spend
python -m src.ingestion.run_weekly_sync             # Drive delta + Discord window
```

---

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), system design, pipeline, post-hackathon hardening, and deployment
- [docs/PII_RULES.md](docs/PII_RULES.md), privacy and financial data classification policy
- [docs/DATA_MAP.md](docs/DATA_MAP.md), Drive file inventory
- [docs/TESTING.md](docs/TESTING.md), eval suites and quality thresholds

---

## License

MIT. See [LICENSE](LICENSE).
