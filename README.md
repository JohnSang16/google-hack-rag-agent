# progsu Intelligence Agent

[![CI](https://github.com/JohnSang16/progsu-intelligence-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/JohnSang16/progsu-intelligence-agent/actions/workflows/ci.yml)

Every student org leader loses institutional knowledge when people graduate. This agent makes a year of org history instantly queryable and actionable.

Built for the [Google Cloud Rapid Agent Hackathon](https://rapid-agent.devpost.com), MongoDB track, then hardened into a production system: role-based access control via Discord OAuth, ingestion-time data governance with redaction, and a fully automated weekly knowledge refresh.

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

## Beyond the Hackathon

The hackathon build proved the idea. The work since turned demo code into a system safe to open to a whole organization:

**Role-based access via Discord OAuth.** The org already lives in Discord, so Discord is the user database. Members log in with Discord (identify scope only), the backend maps their server roles to a tier, and every capability is gated per request: `anonymous` gets the public demo, `member` gets cited search, `exec` adds PLAN artifacts and financial data, `admin` adds email send and admin endpoints. Sessions are stateless HMAC-signed tokens; tiers re-resolve through a cached role lookup, so removing someone's role revokes their access with zero admin work. With no Discord credentials configured, everything falls back to the original single-switch demo behavior.

**Ingestion-time data governance.** Every chunk is access-classified when it enters the system, not when it leaves. A cheap keyword trigger routes suspicious chunks to a Gemini judge that distinguishes real financial data ("sponsorship came in at $20,000") from figurative language ("the venue cost us a lot of stress"), tags the verdict as metadata, and produces a redacted rendition with figures masked. Restricted tiers get the redacted text instead of losing the whole chunk. Classifier failure over-restricts rather than leaks. Newly discovered spreadsheets default to an aggregate-summary path so roster data is never stored raw.

**Automated weekly knowledge refresh.** A scheduled job replaces all manual ingestion. Drive: a recursive walk re-ingests only files whose modifiedTime changed, sweeps chunks for deleted files, and cleans orphaned chunks when documents shrink. Discord: the bot fetches a rolling 14-day window per channel over REST (no export tool), and chunks are keyed by their own date, so overlapping windows re-upsert idempotently and edits to old messages self-correct. Text hashing skips all Gemini spend on unchanged content. Per-source sync state means failures retry automatically next run, and an optional webhook posts run summaries to a Discord channel.

**One pipeline, structured intent.** The streaming and non-streaming paths are a single implementation (the non-streaming API is a thin consumer of the stream), which revived the production grounding check and eliminated an entire class of drift bugs. Mode and action detection is one structured Gemini call returning `{mode, wants_calendar, wants_email, send_now}` with a schema-enforced response, replacing six keyword heuristics. Emails are only ever drafted by PLAN mode; sending requires an explicit confirmation turn and admin capability.

**Observability and CI.** Every request logs mode, latency, confidence, tier, and an IP hash to a `query_logs` collection with a 90-day TTL. GitHub Actions runs the unit suite (79 tests) on every push. Org-specific configuration (authoritative sources, sensitive phrases, demo seeds) lives in a private `org_config.json`, making the public codebase a generic org-knowledge engine.

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
User query (+ bearer token -> tier resolution via cached Discord role lookup)
  -> structured intent classifier (one Gemini call: mode + action flags)
  -> if CHAT: answer directly, no retrieval
  -> metadata pre-filter (date, event, team, doc_type)
  -> MongoDB Atlas vector search (top-k=10)
  -> reranker (Gemini scores all chunks in one batched call, keeps top-3)
  -> confidence gate (best score < 5 returns "not enough info", never guesses)
  -> tier gate (financial chunks served redacted or dropped for restricted tiers)
  -> Gemini agent streams response with citations [source_name, date, drive_link]
  -> grounding check on PLAN answers (unsupported claims get a disclaimer)
  -> if PLAN mode (exec tier and up):
      create_google_doc() via Drive + Docs API
      create_calendar_event() via Google Calendar API
      draft outreach email via Gmail API (send requires explicit confirm + admin)
```

Intent classification and retrieval run in parallel. Responses stream token by token via SSE. PLAN mode skips the response cache so every planning request produces a fresh artifact. Reranker failure degrades below the confidence gate, so a scoring outage returns "not enough info" instead of ungated generation.

---

## Data Sources

The agent ingests two categories of org data:

**Google Drive** (via Drive API)
- Meeting notes, event logistics docs, sponsor/vendor guides
- Financial records and budget summaries
- The 22MB Progsu Master Doc, exported tab by tab via the Docs API

**Discord** (via bot REST API, weekly)
- The bot fetches a rolling 14-day window per channel; no export tool, no manual steps
- Channels filtered to organizationally meaningful content; off-topic channels (memes, bots, graphics, receipts) skipped automatically
- Chunks keyed by their own date, so edits to already-ingested days self-correct on the next sync

**Data quality pipeline:**
Every chunk passes a Gemini YES/NO noise filter before storage. PII is stripped by regex then a Gemini pass before chunking. Spreadsheet rows are converted to structured text sentences before chunking, and unrecognized spreadsheets are summarized to aggregate stats rather than stored raw. Financial content is access-classified at ingestion with a redacted rendition stored alongside the original.

**Keeping it fresh:**
```bash
python -m src.ingestion.run_weekly_sync            # Drive delta + Discord window
python -m src.ingestion.run_weekly_sync --dry-run  # report only, no API spend
```
Deployed as a Cloud Run Job on a weekly Cloud Scheduler trigger. Sync state lives in Atlas (`ingestion_state`, `sync_runs`), so failed sources retry automatically on the next run.

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
  access.py                  tier capability matrix (anonymous/member/exec/admin)
  financial_signals.py       shared cheap trigger for financial content
  org_config.py              loads org-specific config from private org_config.json
  ingestion/
    drive_reader.py          reads Drive files, exports to text, handles multi-tab docs
    drive_walker.py          recursive Drive walk with change detection + deletion sweep
    discord_reader.py        groups messages into date-keyed daily chunks
    discord_fetcher.py       bot-token REST fetch of rolling channel windows
    access_classifier.py     ingestion-time financial judgment + redaction
    run_ingestion.py         Drive ingestion pipeline (manual/full)
    run_discord_ingestion.py Discord export ingestion (legacy manual path)
    run_weekly_sync.py       scheduled weekly refresh: Drive delta + Discord delta
    sync_state.py            ingestion_state + sync_runs collections
    chunker.py               splits text by doc_type rules
    pii_filter.py            strips PII before chunking
    noise_filter.py          Gemini YES/NO scoring per chunk
    embedder.py              gemini-embedding-001, 768-dim vectors
    storer.py                upserts chunks to MongoDB Atlas
  retrieval/
    vector_search.py         MongoDB Atlas $vectorSearch with metadata pre-filter
    reranker.py              batched Gemini reranking of top-k results
    retriever.py             combines search + rerank
  agent/
    mode_classifier.py       structured intent classifier (mode + action flags)
    agent.py                 unified streaming pipeline with tier-gated actions
    tools/
      retrieve.py            retrieval tool
      create_doc.py          creates Google Doc in Drive
      create_calendar_event.py  creates Calendar event via Google Calendar API
      send_gmail.py          drafts outreach email; send is confirm + admin gated
  api/
    auth.py                  Discord OAuth flow, signed tokens, tier resolution
    server.py                FastAPI: /chat + /chat/stream (SSE), /auth/*, /admin/stats, /health
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
cp org_config.example.json org_config.json
# Fill in your API keys in .env, and your org's values in org_config.json
```

`org_config.json` holds everything org-specific (authoritative source file ids, sensitive phrase filters, event keyword mappings, demo seeds, Drive root folder id). It is gitignored; the codebase itself is org-agnostic.

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

**Discord auth + weekly sync (optional):**
Set the `DISCORD_*` variables documented in `.env.example` (OAuth app credentials, bot token, guild id, role-to-tier mappings, `SESSION_SECRET`). With all five core variables set, the login button appears and tiers activate; with any missing, the deployment behaves exactly like the original demo. The same bot token powers the weekly Discord ingestion:
```bash
python -m src.ingestion.run_weekly_sync --dry-run   # see what would sync first
python -m src.ingestion.run_weekly_sync             # full refresh
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

### Cost Protection (set these in Cloud Run env vars before publishing)

```
DEMO_MODE=true              # enables per-IP rate limiting, query guard, and injection blocking
DAILY_REQUEST_CAP=300       # hard daily cap across all IPs; returns 503 when exhausted; 0 to disable
ALLOWED_ORIGINS=https://your-frontend.vercel.app  # comma-separated; restricts CORS to your frontend only
```

Additionally, set a hard quota on the Gemini API in GCP Console:
1. Go to APIs and Services, click Gemini API, then Quotas and System Limits
2. Filter for `gemini-2.0-flash` (covers 2.5-flash calls in GCP's quota grouping)
3. Set "Request limit per model per day" to 500 and "Request limit per model per minute (paid tier 1)" to 60
4. Set a billing budget alert at Billing, Budgets and alerts with a monthly ceiling

---

## Broader Impact

progsu is one club at one university. The problem it solves is not.

Every ACM chapter, Google Developer Student Club, IEEE branch, NSBE chapter, and student org of any kind runs on the same two rails: Google Drive and Discord (or Slack). Leadership turns over every year. Every graduating class takes years of institutional knowledge with it: which vendors to avoid, what sponsorship pitch worked, how to staff a 400-person event, why the previous approach to outreach failed.

This agent is org-agnostic. Swap the Drive folder ID and the Discord export and it works for any organization that stores its history in documents and chat. The ingestion pipeline handles meeting notes, event logistics, financials, and message threads regardless of which org produced them. The retrieval layer does not know what progsu is. It knows what a chunk is.

The higher-order version of this is a platform: a single deployment where any student org can connect their Drive and Discord, ingest their data, and get an AI chief of staff that knows their full history. RECALL lets any new officer ask "what did we try before and why did it fail?" ANALYZE turns scattered attendance logs into trend reports without a data team. PLAN turns the collective memory of every past event into a draft brief for the next one, complete with artifacts, in under a minute.

The bottleneck to institutional knowledge transfer in student organizations has always been documentation inertia: things get written down inconsistently, and even when they do, nobody reads them. An agent that reads everything and answers in plain language removes that bottleneck. The value compounds with time: the longer the org runs, the richer the history, and the more useful the agent becomes to whoever inherits leadership next.

---

## Demo

The live deployment at https://frontend-coral-mu-47.vercel.app runs the public demo experience: rate limiting and injection blocking on, write integrations off, financial data restricted.

With Discord auth configured, capabilities are per-tier instead of per-deployment:

| Capability | anonymous | member | exec | admin |
|---|---|---|---|---|
| RECALL / ANALYZE with citations | Yes | Yes | Yes | Yes |
| Financial data | Restricted (redacted or refused) | Restricted | Full, flagged internal | Full |
| PLAN (Google Doc creation) | No | No | Yes | Yes |
| Calendar event creation | No | No | Yes | Yes |
| Gmail outreach email | No | No | Draft only | Draft + explicit-confirm send |
| Rate limiting | Strict | Standard | Relaxed | Relaxed |
| /admin/stats (query log viewer) | No | No | No | Yes |

Tiers come from Discord server roles at login and re-resolve on a one-hour cache, so role changes and removals take effect without re-login. Without auth configured, `DEMO_MODE=true` reproduces the anonymous experience deployment-wide.

---

## License

MIT. See [LICENSE](LICENSE).
