# Architecture

## System Overview

```
Google Drive (docs, sheets, forms)
  + Discord (exec server export)
          ↓
    Ingestion Pipeline
    ┌─────────────────────────────────────┐
    │ 1. PII Strip (regex + Gemini)       │
    │ 2. Chunk (by doc_type rules)        │
    │ 3. Noise Filter (Gemini YES/NO)     │
    │ 4. Embed (text-embedding-004)       │
    │ 5. Tag metadata                     │
    │ 6. Store → MongoDB Atlas            │
    └─────────────────────────────────────┘
          ↓
    MongoDB Atlas
    ┌──────────────────────────┐
    │ Collection: chunks       │
    │ Vector index on embedding│
    │ Filter fields on metadata│
    └──────────────────────────┘
          ↓
    Query Pipeline
    ┌─────────────────────────────────────┐
    │ 1. Classify mode (RECALL/ANALYZE/   │
    │    PLAN) via Gemini                 │
    │ 2. Extract metadata filters from Q  │
    │ 3. MongoDB pre-filter + $vectorSearch│
    │    (k=10)                           │
    │ 4. Rerank with Gemini (→ top 3)     │
    │ 5. Gemini agent reasons + responds  │
    │ 6. If PLAN: also call create_doc()  │
    └─────────────────────────────────────┘
          ↓
    React Frontend
    ┌──────────────────────────┐
    │ Mode indicator badge     │
    │ Answer with citations    │
    │ Source doc link per cite │
    │ Google Doc link if PLAN  │
    └──────────────────────────┘
```

---

## MongoDB Atlas Vector Search Index Definition

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 768,
      "similarity": "cosine"
    },
    { "type": "filter", "path": "metadata.semester" },
    { "type": "filter", "path": "metadata.event_name" },
    { "type": "filter", "path": "metadata.doc_type" },
    { "type": "filter", "path": "metadata.team" },
    { "type": "filter", "path": "metadata.source_type" },
    { "type": "filter", "path": "metadata.date" }
  ]
}
```

Index name: `vector_index`
Collection: `chunks`

---

## Noise Filter Prompt

Call this with each chunk BEFORE embedding. Only embed and store if response is "YES".

```
You are evaluating whether a text chunk from a student tech organization contains useful organizational intelligence.

Score YES if the chunk contains ANY of:
- A decision that was made
- An action item or task assigned to someone
- An event detail (date, attendance count, logistics, outcome)
- A growth or attendance metric
- A sponsorship or partnership detail
- A lesson learned or retrospective insight
- A strategic plan or goal
- A process or how-to instruction
- Financial information (budget, spending, revenue)

Score NO if the chunk contains ONLY:
- Meme references, emoji spam, or reaction-only messages
- Duplicate content already present in the same document
- Filler or placeholder text ("TBD", "coming soon", empty template fields)
- Pure logistics with no context (a room number alone, a time alone)
- Template section headers with no filled content

Respond with exactly one word: YES or NO

Chunk:
{chunk_text}
```

---

## Reranker Prompt

Call this after vector search. Score each result 1-10 for relevance to the query.

```
You are scoring how relevant a retrieved document chunk is to a user's query.

Query: {query}

Chunk: {chunk_text}
Source: {file_title} ({date})

Score this chunk from 1-10 where:
10 = Directly and specifically answers the query with concrete details
7-9 = Highly relevant, contains most of what the query needs
4-6 = Somewhat relevant, tangentially related
1-3 = Barely relevant or only shares keywords
0 = Not relevant at all

Respond with only a number 1-10.
```

Keep chunks scoring >= 6. If fewer than 2 chunks score >= 6, keep top 2 regardless.

---

## Mode Classifier Prompt

```
Classify this query into exactly one of three modes:

RECALL: The user wants to know what happened, what was decided, or what exists. 
  Examples: "What were the logistics for Hacklanta?", "What sponsors did we have?", "What was decided in the last exec meeting?"

ANALYZE: The user wants trends, comparisons, or synthesis across multiple events/time periods.
  Examples: "How has our attendance grown?", "What events drove the most engagement?", "Compare Fall 2025 to Spring 2026"

PLAN: The user wants to create something new, draft a document, or plan a future event. This should produce a Google Doc.
  Examples: "Draft a planning brief for...", "Help me plan...", "Create a template for...", "Write a proposal for..."

Query: {query}

Respond with exactly one word: RECALL, ANALYZE, or PLAN
```

---

## Google Doc Creation (PLAN Mode)

When PLAN mode is triggered, call the Drive API to create a document:

```python
# Target folder for created docs - set DRIVE_OUTPUT_FOLDER_ID in .env
PLAN_OUTPUT_FOLDER_ID = os.environ["DRIVE_OUTPUT_FOLDER_ID"]  # e.g. "11eYr6RIieuw4EvCZCzaMBa8ib8llDr9-"

# Doc title format
title = f"[AI Generated] {query[:60]}  -  {datetime.now().strftime('%Y-%m-%d')}"
```

The created doc should include:
- Title section: what this plan is based on
- Cited sources section: list of Drive docs referenced
- Generated plan content
- Footer: "Generated by progsu Intelligence Agent"

---

## FastAPI Endpoint

```python
POST /chat
{
  "query": str,
  "filters": {           # optional - all fields optional
    "semester": str,
    "event_name": str,
    "team": str,
    "doc_type": str,
    "date_from": str,    # YYYY-MM-DD inclusive lower bound
    "date_to": str       # YYYY-MM-DD inclusive upper bound
  }
}

Response:
{
  "mode": "RECALL" | "ANALYZE" | "PLAN",
  "answer": str,
  "citations": [
    {
      "source_name": str,       # human-readable doc title (file_title from chunk metadata)
      "date": str,
      "drive_link": str | null, # constructed from file_id: https://drive.google.com/file/d/{file_id}
      "rerank_score": int       # 1-10 from reranker, only chunks >= 6 are included
    }
  ],
  "created_doc_url": str | null   # only for PLAN mode
}
```

---

## Ingestion Run Order

Run in this order. Each step depends on the previous:

1. `python src/ingestion/run_ingestion.py --file-ids-file config/file_ids.txt`
   (extract Priority 1-5 file IDs from DATA_MAP.md into a plain text file - one ID per line)
2. Verify chunk count in Atlas: should be 800-2000 chunks total
3. Spot check: manually query 3 chunks, confirm metadata is correct
4. Run Atlas vector search quickstart query to confirm index is working
5. Then wire the retrieval layer

---

## Key Decisions and Tradeoffs

**Why cosine similarity over dotProduct**: normalized embeddings, cosine is more stable for text
**Why k=10 then rerank to 3**: vector search casts wide net, reranker focuses on true relevance
**Why Gemini for reranking instead of a cross-encoder**: fewer dependencies, same API, fast enough for 10 docs
**Why FastAPI over Flask**: async support, auto docs at /docs, cleaner for agent tool integration
**Why Vite+React over Next.js**: simpler deployment for hackathon, faster setup, no SSR complexity needed

---

## Post-Hackathon Architecture (2026-07)

The hackathon architecture above still describes the core retrieval design. Everything below was added afterward. The single source of truth for status and remaining work is the vault roadmap, not this file.

**Identity and access (src/access.py, src/api/auth.py).** Discord OAuth login with roles mapped to four tiers (anonymous, member, exec, admin), each carrying a capability object (can_plan, can_calendar, can_gmail_send, financial_access, guarded, is_admin). Sessions are stateless HMAC-signed bearer tokens (stdlib crypto); tiers re-resolve per request through a 1-hour cached guild-member lookup via the bot token. With auth env vars unset, everything falls back to the original DEMO_MODE global.

**Unified pipeline (src/agent/agent.py).** run() is a thin consumer of run_stream(); there is exactly one pipeline. Intent comes from one structured Gemini call (classify_intent) returning {mode, wants_calendar, wants_email, send_now} with a schema-enforced response; failure degrades to RECALL with all action flags false. The grounding check runs on PLAN answers in the production streaming path. PLAN only drafts email; sending requires an explicit confirmation turn plus admin capability.

**Data governance (src/ingestion/access_classifier.py, src/financial_signals.py).** Chunks are access-classified at ingestion: a keyword/regex trigger routes suspicious chunks to a Gemini judge, verdicts stored as metadata.access_level with a redacted rendition (figures masked as [amount]) alongside the original text. Query-time enforcement in _filter_sensitive_chunks trusts the tag, serves redacted text to restricted tiers, and keeps the keyword scan only as a backstop for untagged legacy chunks.

**Weekly refresh (src/ingestion/run_weekly_sync.py).** Drive: recursive walk with modifiedTime delta, deletion sweep, orphaned-chunk cleanup, unknown spreadsheets routed to the aggregate-summary path. Discord: bot-token REST fetch of a rolling 14-day window per channel, date-keyed chunk indexes (date_chunk_key) making overlap re-upserts idempotent, channel-ID keying so renames don't orphan chunks, text-hash skip for unchanged days. State in ingestion_state, run history in sync_runs, optional webhook summary post. Deployed as a Cloud Run Job on a weekly Cloud Scheduler trigger.

**Config (src/org_config.py).** All org-specific constants (authoritative file ids, sensitive phrases, event keyword map, demo seeds, Drive root folder id) live in a gitignored org_config.json; .gcloudignore ships it to Cloud Run. The committed org_config.example.json documents the shape.

**Observability.** query_logs collection (mode, latency, confidence, tier, user id, IP hash; 90-day TTL), /admin/stats endpoint (admin tier), GitHub Actions CI on every push.

---

## Deployment

**Backend:** Cloud Run via `gcloud run deploy progsu-agent --source . --region us-central1`. The Dockerfile builds the FastAPI app; secrets (Drive OAuth token) mount via Secret Manager at `/secrets/`. `.gcloudignore` deliberately ships the gitignored `org_config.json` with the deploy.

**Frontend:** Vercel. Set `VITE_API_URL` to the Cloud Run service URL.

**MongoDB Atlas:** M0 free tier. Requires the Atlas Vector Search index (see the architecture diagram above for field definitions). IP whitelist must include Cloud Run's egress range, or `0.0.0.0/0` as an interim step.

**Env vars to set on Cloud Run before publishing** (full list with descriptions in `.env.example`):

```
DEMO_MODE=true
DAILY_REQUEST_CAP=300
ALLOWED_ORIGINS=https://your-frontend.vercel.app
ADMIN_TOKEN=
TRUSTED_PROXY_HOPS=1
DISCORD_CLIENT_ID= / DISCORD_CLIENT_SECRET= / DISCORD_BOT_TOKEN= / DISCORD_GUILD_ID= / SESSION_SECRET=
DISCORD_EXEC_ROLE_IDS= / DISCORD_ADMIN_ROLE_IDS= / DISCORD_ADMIN_USER_IDS=
FRONTEND_URL=
```

Also set a hard quota on the Gemini API in GCP Console: APIs and Services, Gemini API, Quotas and System Limits, cap request-per-day and request-per-minute, and set a billing budget alert under Billing, Budgets and alerts.
