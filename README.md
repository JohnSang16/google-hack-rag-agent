# progsu Intelligence Agent

Every student org leader loses institutional knowledge when people graduate. This agent makes a year of org history instantly queryable and actionable.

Built for the [Google Cloud Rapid Agent Hackathon](https://rapid-agent.devpost.com), MongoDB track.

**Live demo:** https://frontend-coral-mu-47.vercel.app

---

## The Problem

Student tech orgs run on Google Drive and Discord. Decisions get buried in threads. Event playbooks live in documents only the current leadership knows exist. When people graduate, the knowledge graduates with them.

progsu (ProgClub at Georgia State University) ran a $20,000-sponsored hackathon, a Claude Code workshop with 200+ attendees, and dozens of events across two semesters. Every lesson learned, every vendor negotiation, every logistics decision lives in scattered docs and Discord threads. The next Technical Director inherits a Drive folder and hopes for the best.

---

## What It Does

Three query modes, each more powerful than the last:

- **RECALL** "What happened at X?" Retrieves grounded, cited answers from actual org documents.
- **ANALYZE** "How have our metrics trended?" Synthesizes across multiple sources, surfacing real numbers and trends.
- **PLAN** "Help plan X." Retrieves, synthesizes, and creates a real Google Doc in Drive. Not just an answer. An artifact.

Every answer includes citations: source name, date, and a direct Drive link.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM + Embeddings | Gemini 2.0 Flash + text-embedding-004 |
| Agent Orchestration | Google Cloud Agent Builder (Vertex AI) |
| Vector + Document Store | MongoDB Atlas with Atlas Vector Search |
| Agent-to-DB Bridge | MongoDB MCP Server |
| Drive Integration | Google Drive API v3 + Google Docs API |
| Discord Ingestion | Discord export parser with Gemini noise filter |
| Backend | Python 3.11 / FastAPI on Cloud Run |
| Frontend | React + Vite + TypeScript on Vercel |

---

## Pipeline

```
User query
  → mode classifier (Gemini)
  → metadata pre-filter (date, event, team, doc_type)
  → MongoDB Atlas vector search (top-k=10)
  → reranker (Gemini scores all 10 chunks in one call, keeps top-3)
  → Gemini agent reasons over chunks
  → response with citations [source_name, date, drive_link]
  → if PLAN mode: create_google_doc() via Drive + Docs API
```

Mode classification and retrieval run in parallel to minimize latency.

---

## Data Sources

The agent ingests two categories of org data:

**Google Drive** (via Drive API)
- Meeting notes, event logistics docs, sponsor/vendor guides
- Financial records and budget summaries
- The 22MB Progsu Master Doc, exported tab by tab via the Docs API

**Discord** (via server export)
- Channels filtered to organizationally meaningful content (#hacklanta, #announcements, #exec-interest-meeting, #spring-kickoff, #claude-workshop, #involvement-fair, and more)
- Off-topic channels (memes, bots, graphics, receipts) skipped automatically

**Data quality pipeline:**
Every chunk passes a Gemini YES/NO noise filter before storage. PII is stripped by regex then a Gemini pass before chunking. Spreadsheet rows are converted to structured text sentences before chunking.

---

## Performance

After batching the reranker from 10 sequential Gemini calls to 1:

| Query | Mode | Latency | Citations |
|---|---|---|---|
| "What were the key logistics challenges at Hacklanta?" | RECALL | ~25s | FAQs-Hacklanta, Operations Meeting Notes, Discord #hacklanta |
| "How has event attendance grown from Fall 2025 to Spring 2026?" | ANALYZE | ~15s | Combined Attendance, Involvement Fair Signups |
| "Draft a planning brief for our next major hackathon." | PLAN | ~38s + Google Doc created | Discord #hacklanta, Operations Meeting Notes |

---

## Project Structure

```
src/
  ingestion/
    drive_reader.py          reads Drive files, exports to text, handles multi-tab docs
    discord_reader.py        parses Discord export, filters noise channels
    run_ingestion.py         orchestrates Drive ingestion pipeline
    run_discord_ingestion.py orchestrates Discord ingestion pipeline
    chunker.py               splits text by doc_type rules
    pii_filter.py            strips PII before chunking
    noise_filter.py          Gemini YES/NO scoring per chunk
    embedder.py              calls text-embedding-004, returns 768-dim vectors
    storer.py                upserts chunks to MongoDB Atlas
    summarizer.py            Gemini summarizer for aggregate/spreadsheet files
    aggregate_router.py      routes file IDs to normal, aggregate, or tab-export path
  retrieval/
    vector_search.py         MongoDB Atlas $vectorSearch with metadata pre-filter
    reranker.py              batched Gemini reranking of top-k results
    retriever.py             combines search + rerank
  agent/
    mode_classifier.py       classifies query as RECALL / ANALYZE / PLAN
    agent.py                 Gemini agent with parallel mode classification + retrieval
    tools/
      retrieve.py            retrieval tool
      create_doc.py          creates Google Doc in Drive
  api/
    server.py                FastAPI, POST /chat + GET /health
  frontend/
    src/
      App.tsx
      components/
        ChatInterface.tsx     main chat container
        MessageBubble.tsx     user/agent messages with inline markdown
        ModeSelector.tsx      RECALL/ANALYZE/PLAN legend strip
        CitationCard.tsx      collapsible source cards with Drive links
tests/
  eval/                      evaluation pipeline for retrieval quality + hallucination detection
docs/
  ARCHITECTURE.md            system design, prompts, index definitions
  DATA_MAP.md                all Drive file IDs with ingest/skip labels
  PII_RULES.md               data privacy policy and stripping logic
  DEMO_SCRIPT.md             3 demo queries and expected outputs
  DEVPOST_DRAFT.md           Devpost submission copy
  JUDGING_ALIGNMENT.md       criteria to feature mapping
```

---

## Setup

```bash
git clone https://github.com/johnsang16/progsu-intelligence-agent
cd progsu-intelligence-agent
cp .env.example .env
# Fill in your API keys in .env
```

**Required environment variables:**

```
GEMINI_API_KEY=
MONGODB_URI=                  # Atlas connection string mongodb+srv://...
MONGODB_DB_NAME=progsu_intelligence
MONGODB_COLLECTION=chunks
GOOGLE_DRIVE_CREDENTIALS=     # path to service account JSON
DRIVE_INGESTION_FOLDER_ID=    # Drive folder to read source docs from
DRIVE_OUTPUT_FOLDER_ID=       # Drive folder where PLAN mode drops generated docs
GCP_PROJECT_ID=
GCP_REGION=us-central1
```

**Backend:**
```bash
pip install -r requirements.txt
python -m src.ingestion.run_ingestion --priority 1
python -m src.api.server
```

**Discord ingestion (optional):**
```bash
# Export your Discord server via DiscordChatExporter, place in discord_export/
python -m src.ingestion.run_discord_ingestion
```

**Frontend:**
```bash
cd src/frontend
npm install
npm run dev
# Proxies to FastAPI at localhost:8000 via vite.config.ts
```

---

## Deployment

**Backend:** Cloud Run via `gcloud run deploy progsu-agent --source . --region us-central1`

The Dockerfile builds the FastAPI app. Secrets (Drive OAuth token) are mounted via Secret Manager at `/secrets/`.

**Frontend:** Vercel. Set `VITE_API_URL` env var to the Cloud Run service URL.

**MongoDB Atlas:** M0 free tier. Atlas Vector Search index required (see `docs/ARCHITECTURE.md` for index definition). IP whitelist must include Cloud Run egress IPs or `0.0.0.0/0`.

---

## License

MIT. See [LICENSE](LICENSE).
