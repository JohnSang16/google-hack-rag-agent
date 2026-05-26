# progsu Intelligence Agent

An AI agent that turns a year of student tech org data into queryable, actionable intelligence.

Built for the [Google Cloud Rapid Agent Hackathon](https://rapid-agent.devpost.com) — MongoDB track.

---

## What It Does

Student tech org leaders spend hours every week trying to remember what was decided, what worked at past events, and how to plan what's next. When people graduate, all that knowledge graduates with them.

This agent ingests a year of real organizational data — meeting notes, event logistics, Discord decisions, financial records, sponsor outreach — and makes it instantly queryable. Ask what went wrong at the last hackathon. Ask how attendance has grown. Ask the agent to draft a planning brief for the next event, and it creates a real Google Doc from everything it learned.

**Three modes:**
- **RECALL** — "What happened at X?" → retrieval with cited sources
- **ANALYZE** — "How have our metrics trended?" → cross-document synthesis
- **PLAN** — "Help plan X" → synthesis + creates a Google Doc in Drive

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM + Embeddings | Gemini 2.0 Flash + text-embedding-004 |
| Agent Orchestration | Google Cloud Agent Builder (Vertex AI) |
| Vector + Document Store | MongoDB Atlas with Atlas Vector Search |
| Agent-to-DB | MongoDB MCP Server |
| Drive Integration | Google Drive API v3 |
| Backend | Python / FastAPI |
| Frontend | React + Vite + TypeScript |

---

## Setup

```bash
git clone https://github.com/<your-username>/progsu-intelligence-agent
cd progsu-intelligence-agent
cp .env.example .env
# Fill in your API keys in .env
```

**Backend:**
```bash
cd src
pip install -r requirements.txt
python ingestion/run_ingestion.py
python api/server.py
```

**Frontend:**
```bash
cd src/frontend
npm install
npm run dev
```

---

## Project Structure

```
CLAUDE.md           — AI agent instructions (Claude Code context)
TODO.md             — build progress tracker
docs/
  ARCHITECTURE.md   — system design, prompts, index definitions
  DATA_MAP.md       — all Drive file IDs with ingest/skip labels
  PII_RULES.md      — data privacy policy and stripping code
  DEMO_SCRIPT.md    — 3 demo queries and expected outputs
  JUDGING_ALIGNMENT.md — criteria to feature mapping
src/
  ingestion/        — Drive reader, chunker, noise filter, embedder
  retrieval/        — vector search, reranker, retriever
  agent/            — Gemini agent, tools, mode classifier
  api/              — FastAPI server
  frontend/         — React chat interface
```

---

## License

MIT — see [LICENSE](LICENSE)
