# progsu Intelligence Agent — CLAUDE.md

You are building a RAG agent for a Google Cloud hackathon. Read this entire file before writing any code.
Reference files: docs/ARCHITECTURE.md, docs/DATA_MAP.md, docs/PII_RULES.md, docs/DEMO_SCRIPT.md

---

## What This Is

An AI chief of staff for student tech org leaders. It ingests a year of organizational data from Google Drive and Discord, stores it in MongoDB Atlas, and lets a Gemini agent answer strategic questions with cited sources and take actions (like creating Google Docs).

One-line pitch: "Every student org leader loses institutional knowledge when people graduate. This agent makes a year of org history instantly queryable and actionable."

---

## Non-Negotiable Stack (Hackathon Requirements)

These are REQUIRED by the Google Cloud Rapid Agent Hackathon MongoDB track. Do not substitute:

- **LLM + Embeddings**: Gemini API (gemini-2.0-flash for generation, text-embedding-004 for embeddings)
- **Agent Orchestration**: Google Cloud Agent Builder (Vertex AI Agent Engine)
- **Vector + Document Store**: MongoDB Atlas with Atlas Vector Search
- **Agent-to-DB Bridge**: MongoDB MCP server (github.com/mongodb-js/mongodb-mcp-server) — this is how the agent calls the database
- **Drive Integration**: Google Drive API (already have OAuth via MCP) for ingestion + Google Doc creation
- **Frontend**: React (Vite) with TypeScript

Do not use: OpenAI, Pinecone, LangChain, ChromaDB, or any vector DB other than MongoDB Atlas.

---

## Three Agent Modes (Core UX — Required for Judging)

Every user query is classified into one of three modes before retrieval:

1. **RECALL** — "What happened at X?" → retrieval + cited answer
2. **ANALYZE** — "How have metrics trended?" → cross-document synthesis + data
3. **PLAN** — "Help plan X" → retrieval + synthesis + CREATE a Google Doc in Drive

Mode 3 (PLAN) is the agentic differentiator. It must produce a real artifact, not just text.

---

## Pipeline Architecture

```
User query
  → mode classifier (Gemini)
  → metadata pre-filter (date, event, team, doc_type)
  → MongoDB Atlas vector search (top-k=10)
  → reranker (Gemini scores relevance, keeps top-3)
  → Gemini agent reasons over chunks
  → response with citations [source_title, date, file_id]
  → if PLAN mode: also calls create_google_doc() tool
```

---

## MongoDB Document Schema

Every ingested chunk MUST have this exact structure:

```python
{
  "_id": ObjectId,
  "text": str,                    # the chunk content
  "embedding": [float],           # 768-dim vector from text-embedding-004
  "metadata": {
    "source_type": "google_drive" | "discord",
    "doc_type": "meeting_notes" | "event_logistics" | "blueprint" | "financial" | "growth" | "guide" | "wiki" | "feedback_aggregate",
    "semester": "fall_2025" | "spring_2026" | "all",
    "event_name": str | None,     # "hacklanta", "claude_workshop", etc.
    "date": str | None,           # "YYYY-MM-DD"
    "team": "exec" | "growth" | "tech" | "operations" | "outreach" | None,
    "file_id": str,               # Google Drive file ID
    "file_title": str,            # human-readable doc name
    "chunk_index": int            # position within source doc
  }
}
```

---

## Differentiators — Never Cut These

These are what separate this from a generic RAG demo. Every one must be implemented:

1. **Noise filter**: Before storing any chunk, call Gemini to score it YES/NO. Prompt is in docs/ARCHITECTURE.md. Only store YES chunks.
2. **PII stripping**: Before chunking, run regex + Gemini pass to remove emails, phone numbers, non-exec names. Rules in docs/PII_RULES.md.
3. **Metadata pre-filter**: Use MongoDB pre-filter on vector index before ANN search. Faster and more precise.
4. **Reranker**: After vector search returns top-10, score each against the query with a second Gemini call. Return top-3 to the agent.
5. **Citation UI**: Every answer displays source_title + date + a link icon. No answer without attribution.
6. **Google Doc creation**: PLAN mode must create a real Google Doc via Drive API.

---

## Chunking Rules

- Meeting notes → split by date header or "---" separator
- Event logistics → split by heading (##)
- Large docs (>1MB) → heading split, max 800 tokens, 100 token overlap
- Small docs (<50KB) → single chunk or paragraph split
- Spreadsheets → convert rows to structured text sentences before chunking
- Progsu Master doc (22MB) → export tab by tab via Docs API, chunk each tab separately

---

## Environment Variables Required

```
GEMINI_API_KEY=
MONGODB_URI=             # Atlas connection string mongodb+srv://...
MONGODB_DB_NAME=progsu_intelligence
MONGODB_COLLECTION=chunks
GOOGLE_DRIVE_CREDENTIALS= # path to service account JSON
GCP_PROJECT_ID=
GCP_REGION=us-central1
```

---

## Project Structure

```
src/
  ingestion/
    drive_reader.py      # reads Drive files by ID, exports to text
    chunker.py           # splits text by doc_type rules above
    pii_filter.py        # strips PII before chunking
    noise_filter.py      # Gemini YES/NO scoring per chunk
    embedder.py          # calls text-embedding-004
    storer.py            # upserts chunks to MongoDB
    run_ingestion.py     # orchestrates the full pipeline
  retrieval/
    vector_search.py     # MongoDB Atlas $vectorSearch with pre-filter
    reranker.py          # Gemini reranking of top-k results
    retriever.py         # combines search + rerank
  agent/
    mode_classifier.py   # classifies query as RECALL/ANALYZE/PLAN
    agent.py             # Gemini agent via Agent Builder
    tools/
      retrieve.py        # tool: query the retrieval layer
      create_doc.py      # tool: create Google Doc in Drive
  api/
    server.py            # FastAPI server, exposes /chat endpoint
  frontend/
    src/
      App.tsx
      components/
        ChatInterface.tsx
        ModeSelector.tsx
        CitationCard.tsx
        MessageBubble.tsx
```

---

## Session Workflow

At the start of every session:
1. Read this file
2. Check TODO.md for current task
3. Build only the scoped task — do not refactor other components
4. Update TODO.md when task is complete

At the end of every session:
- Update TODO.md with what was completed and what is next
- Note any decisions made that affect other components

---

## Code Standards

- Python 3.11+ for backend
- Async where possible (ingestion can be sync, retrieval should be async)
- Type hints on every function
- Every external API call wrapped in try/except with informative error messages
- Never hardcode credentials — always use environment variables
- Log chunk counts, noise filter pass rates, embedding times for demo visibility

---

## Demo Queries (Know These)

See docs/DEMO_SCRIPT.md for full detail. The three queries that will be run live:
1. "What were the key logistics challenges at Hacklanta and how did we solve them?"
2. "How has our event attendance grown from Fall 2025 to Spring 2026, and which events drove the biggest spikes?"
3. "Draft a planning brief for our next major hackathon based on everything we learned from Hacklanta." ← triggers PLAN mode, creates Google Doc

Every retrieval component must return good results for these three queries. Tune metadata, chunking, and reranker with these in mind.

---

## Multi-Agent Orchestration Instructions

### How To Run A Session
When told to "start session N" or "run epic session N":
1. Read this file fully first
2. Read the full epic at docs/epics/epic-session[N]-*.md
3. Check the prerequisite handoff conditions from the previous epic
4. Flag any manual steps to the human before starting
5. Spawn subagents per feature using the relevant bmad skill per agent type
6. Run QA review using bmad-code-review at the end
7. Update TODO.md when the epic definition of done is met
8. Report back only when complete or a blocker needs human input

### Agent Role To BMAD Skill Mapping
- Dev Agent        -> .claude/skills/bmad-agent-dev
- QA Agent         -> .claude/skills/bmad-code-review
- Architect        -> .claude/skills/bmad-agent-architect
- Analyst          -> .claude/skills/bmad-agent-analyst

### Sensitive Operations — Always Flag To Human
Never do these autonomously:
- Create or modify Atlas clusters, databases, or indexes
- Commit or push to main branch
- Make the GitHub repo public
- Deploy to Cloud Run or any production environment
- Submit the Devpost entry

### Credentials Rule
Never read, write, print, or handle the contents of .env
All code reads credentials from environment variables only
Mock all credentials in tests

### Epic Files Location
docs/epics/epic-session1-atlas-setup.md
docs/epics/epic-session2-ingestion.md
docs/epics/epic-session3-retrieval.md
docs/epics/epic-session4-agent-api.md
docs/epics/epic-session5-frontend.md
docs/epics/epic-session6-polish-deploy.md
