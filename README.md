# progsu Intelligence Agent

Every student org leader loses institutional knowledge when people graduate. This agent makes a year of org history instantly queryable and actionable.

Built for the [Google Cloud Rapid Agent Hackathon](https://rapid-agent.devpost.com), MongoDB track.

**Live demo:** https://frontend-coral-mu-47.vercel.app
**Devpost:** https://devpost.com/software/progsu-intelligence-agent

---

## The Problem

Student tech orgs run on Google Drive and Discord. Decisions get buried in threads. Event playbooks live in documents only the current leadership knows exist. When people graduate, the knowledge graduates with them.

progsu (ProgClub at Georgia State University) ran a $20,000-sponsored hackathon, a Claude Code workshop with 200+ attendees, and dozens of events across two semesters. Every lesson learned, every vendor negotiation, every logistics decision lives in scattered docs and Discord threads. The next Technical Director inherits a Drive folder and hopes for the best.

---

## What It Does

Four query modes, each matched to a different leadership need:

- **CHAT** Conversational questions, capability discovery, and small talk. No retrieval needed.
- **RECALL** "What happened at X?" Retrieves grounded, cited answers from actual org documents.
- **ANALYZE** "How have our metrics trended?" Synthesizes across multiple sources, surfacing real numbers and trends.
- **PLAN** "Help plan X." Retrieves, synthesizes, and produces a full sponsor packet: a Google Doc in Drive, a Gemini-drafted outreach email, and a Google Calendar event. Not just an answer. A complete set of artifacts.

Every RECALL and ANALYZE answer includes citations: source name, date, and a direct Drive link. PLAN mode shows a side panel with the full Google Doc inline.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM + Embeddings | Gemini 2.5 Flash + gemini-embedding-001 (768-dim) |
| Agent Orchestration | Google Cloud Agent Builder (Vertex AI) |
| Vector + Document Store | MongoDB Atlas with Atlas Vector Search |
| Agent-to-DB Bridge | MongoDB MCP Server |
| Drive Integration | Google Drive API v3 + Google Docs API |
| Calendar + Gmail | Google Calendar API v3 + Gmail API v1 |
| Discord Ingestion | Discord export parser with Gemini noise filter |
| Backend | Python 3.11 / FastAPI on Cloud Run (streaming SSE) |
| Frontend | React + Vite + TypeScript + Tailwind v4 on Vercel |

---

## Pipeline

```
User query
  → mode classifier (Gemini 2.5 Flash)
  → if CHAT: answer directly, no retrieval
  → metadata pre-filter (date, event, team, doc_type)
  → MongoDB Atlas vector search (top-k=10)
  → reranker (Gemini scores all 10 chunks in one call, keeps top-3)
  → Gemini agent streams response with citations [source_name, date, drive_link]
  → if PLAN mode:
      create_google_doc() via Drive + Docs API
      create_calendar_event() via Google Calendar API
      send_gmail() drafts outreach email via Gmail API
```

Mode classification and retrieval run in parallel. Responses stream token by token via SSE. PLAN mode skips the response cache so every planning request produces a fresh artifact.

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

## Demo Queries

The three queries run live at the demo, with the sources each one draws from:

| Query | Mode | Sources |
|---|---|---|
| "What were the key logistics challenges at Hacklanta and how did we solve them?" | RECALL | FAQs-Hacklanta, Operations Meeting Notes, Discord #hacklanta |
| "How has event attendance grown from Fall 2025 to Spring 2026, and which events drove the most engagement?" | ANALYZE | Combined Attendance, Involvement Fair Signups |
| "Draft a planning brief for our next major hackathon based on everything we learned from Hacklanta." | PLAN | Discord #hacklanta, Operations Meeting Notes + Google Doc, Calendar event, outreach email |

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
    mode_classifier.py       classifies query as CHAT / RECALL / ANALYZE / PLAN
    agent.py                 Gemini agent with parallel mode classification + retrieval, streaming
    tools/
      retrieve.py            retrieval tool
      create_doc.py          creates Google Doc in Drive
      create_calendar_event.py  creates Calendar event via Google Calendar API
      send_gmail.py          drafts and optionally sends outreach email via Gmail API
  api/
    server.py                FastAPI, POST /chat (SSE stream) + GET /health + POST /clear-cache
  frontend/
    src/
      App.tsx
      components/
        ChatInterface.tsx     main chat container with demo query chips
        MessageBubble.tsx     user/agent messages with inline markdown rendering
        ModeSelector.tsx      CHAT/RECALL/ANALYZE/PLAN legend strip
        CitationCard.tsx      collapsible source cards with Drive links
        DocPanel.tsx          slide-in side panel showing Google Doc content for PLAN mode
        ui/
          claude-style-chat-input.tsx  stop-capable chat input with attachment affordance
      utils/
        renderMarkdown.tsx   plain-text extraction for copy-to-clipboard
tests/
  eval/
    fixtures.py              labeled query fixtures for all eval dimensions
    eval_mode_classifier.py  mode classification accuracy across 18 labeled queries
    eval_retrieval.py        retrieval hit rate, precision@3, mean relevance score
    eval_answer_quality.py   Gemini-as-judge: faithfulness, relevance, hallucination rate
    run_eval.py              orchestrator — runs all suites, writes JSON report
    reports/                 eval output (latest.json written on each run)
docs/
  ARCHITECTURE.md            system design, prompts, index definitions
  DATA_MAP.md                all Drive file IDs with ingest/skip labels
  PII_RULES.md               data privacy policy and stripping logic
  DEMO_SCRIPT.md             3 demo queries and expected outputs
  DEVPOST_DRAFT.md           Devpost submission copy
  JUDGING_ALIGNMENT.md       criteria to feature mapping
```

---

## Metrics

Three eval suites measure quality across every layer of the pipeline. Run them all at once:

```bash
python -m tests.eval.run_eval
# report written to tests/eval/reports/latest.json
```

Or run any suite individually:

```bash
pytest tests/eval/eval_mode_classifier.py -v -s   # mode accuracy only
pytest tests/eval/eval_retrieval.py -v -s          # retrieval quality only
pytest tests/eval/eval_answer_quality.py -v -s     # answer quality only
```

**What each suite measures:**

| Suite | Metric | Threshold |
|---|---|---|
| Mode classifier | Overall accuracy across 18 labeled queries | 85% |
| Mode classifier | CHAT accuracy (pattern-matched queries) | 100% |
| Mode classifier | PLAN accuracy (misclassification breaks artifact creation) | 90% |
| Retrieval | Top-source hit rate (expected source in top-3) | 75% |
| Retrieval | Precision@3 (fraction of top-3 from expected sources) | 50% |
| Retrieval | Mean reranker relevance score | 6/10 |
| Answer quality | Faithfulness (Gemini judge, 1-5 scale) | 4/5 |
| Answer quality | Relevance (Gemini judge, 1-5 scale) | 4/5 |
| Answer quality | Hallucination-free rate across demo queries | 67% |

Suites skip cleanly when credentials are unavailable. All three require `GEMINI_API_KEY`; retrieval and answer quality also require `MONGODB_URI`.

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
GOOGLE_CALENDAR_ID=           # Calendar ID for PLAN mode event creation
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

## Broader Impact

progsu is one club at one university. The problem it solves is not.

Every ACM chapter, Google Developer Student Club, IEEE branch, NSBE chapter, and student org of any kind runs on the same two rails: Google Drive and Discord (or Slack). Leadership turns over every year. Every graduating class takes years of institutional knowledge with it: which vendors to avoid, what sponsorship pitch worked, how to staff a 400-person event, why the previous approach to outreach failed.

This agent is org-agnostic. Swap the Drive folder ID and the Discord export and it works for any organization that stores its history in documents and chat. The ingestion pipeline handles meeting notes, event logistics, financials, and message threads regardless of which org produced them. The retrieval layer does not know what progsu is. It knows what a chunk is.

The higher-order version of this is a platform: a single deployment where any student org can connect their Drive and Discord, ingest their data, and get an AI chief of staff that knows their full history. RECALL lets any new officer ask "what did we try before and why did it fail?" ANALYZE turns scattered attendance logs into trend reports without a data team. PLAN turns the collective memory of every past event into a draft brief for the next one, complete with artifacts, in under a minute.

The bottleneck to institutional knowledge transfer in student organizations has always been documentation inertia: things get written down inconsistently, and even when they do, nobody reads them. An agent that reads everything and answers in plain language removes that bottleneck. The value compounds with time: the longer the org runs, the richer the history, and the more useful the agent becomes to whoever inherits leadership next.

---

## Demo

The live deployment at https://frontend-coral-mu-47.vercel.app runs with `DEMO_MODE=true`. This enables rate limiting and injection blocking, and disables integrations that require write access to external services.

| Feature | Demo | Full deployment |
|---|---|---|
| Google Doc creation (PLAN mode) | On | On |
| Google Calendar event creation | Off | On |
| Gmail outreach email | Off | On |
| Rate limiting (10 req/IP/min) | On | Off |
| Injection blocking | On | Off |
| Download brief as Markdown | On | On |
| Copy response to clipboard | On | On |

When Calendar or Gmail would have triggered in the demo (e.g. a PLAN query that says "add to calendar"), the response includes a note that those features are not available in this demo. All other PLAN functionality (retrieval, synthesis, Google Doc creation, side-panel viewer) works normally.

To run without restrictions, deploy without setting `DEMO_MODE` (defaults to off).

---

## License

MIT. See [LICENSE](LICENSE).
