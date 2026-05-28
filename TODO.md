# TODO  -  Session Tracker

Claude Code: Update this file at the end of every session. Mark completed items, add next steps, note any decisions made.

---

## Current Status: SESSION 1 IN PROGRESS

---

## Session 1  -  MongoDB Atlas Setup (DO THIS FIRST)
**Goal:** Full vector search loop working on dummy data in under 1 hour.

- [ ] Create MongoDB Atlas free cluster (cloud.mongodb.com)
- [ ] Create database: `progsu_intelligence`, collection: `chunks`
- [ ] Create Atlas Vector Search index using definition in docs/ARCHITECTURE.md
- [x] Write `src/ingestion/storer.py`  -  function to insert a chunk with embedding
- [x] Write `src/retrieval/vector_search.py`  -  function to query with $vectorSearch
- [ ] Test: insert 5 dummy chunks with fake embeddings, query returns correct ones (`tests/test_session1.py`)
- [ ] Verify metadata pre-filter works (filter by event_name="hacklanta")

**Done when:** `vector_search.py` returns the right dummy chunk for a test query.

---

## Session 2  -  Google Drive Ingestion Pipeline
**Goal:** Real Drive docs ingested, chunked, filtered, embedded, stored in Atlas.

- [ ] Write `src/ingestion/drive_reader.py`  -  authenticate with Drive API, export doc to text by file ID
- [ ] Write `src/ingestion/pii_filter.py`  -  regex strip + Gemini strip for emails/phones
- [ ] Write `src/ingestion/chunker.py`  -  split by doc_type rules from CLAUDE.md
- [ ] Write `src/ingestion/noise_filter.py`  -  Gemini YES/NO scoring per chunk
- [ ] Write `src/ingestion/embedder.py`  -  call text-embedding-004, return 768-dim vector
- [ ] Write `src/ingestion/run_ingestion.py`  -  orchestrate full pipeline for a list of file IDs
- [ ] Run on Priority 1 files from docs/DATA_MAP.md
- [ ] Log: chunk count, noise filter pass rate, any errors
- [ ] Aggregate files: implement summarizer for spreadsheet files (see docs/PII_RULES.md)

**Done when:** Hacklanta Master Doc and at least 5 other files are chunked and stored in Atlas.

---

## Session 3  -  Retrieval Layer
**Goal:** Query returns relevant, reranked chunks for all 3 demo queries.

- [ ] Write `src/retrieval/vector_search.py`  -  full $vectorSearch with metadata pre-filter
- [ ] Write `src/retrieval/reranker.py`  -  Gemini scoring, return top-3
- [ ] Write `src/retrieval/retriever.py`  -  combine search + rerank into one call
- [ ] Test all 3 demo queries from docs/DEMO_SCRIPT.md manually
- [ ] Tune: if Query 1 doesn't return Hacklanta sources, adjust chunk size or k
- [ ] Tune: if Query 2 doesn't find attendance data, check aggregate chunks were stored

**Done when:** All 3 demo queries return correct, relevant results with good sources.

---

## Session 4  -  Gemini Agent + MongoDB MCP
**Goal:** Agent answers questions with citations. MongoDB MCP is the tool it uses.

- [ ] Write `src/agent/mode_classifier.py`  -  classifies query to RECALL/ANALYZE/PLAN
- [ ] Write `src/agent/tools/retrieve.py`  -  the tool the agent calls (wraps retriever.py)
- [ ] Write `src/agent/tools/create_doc.py`  -  creates Google Doc via Drive API
- [ ] Write `src/agent/agent.py`  -  Gemini agent via Agent Builder with tools registered
- [ ] Configure MongoDB MCP server connection to Atlas
- [ ] Wire agent to call retrieval through MCP (not direct Python call)
- [ ] Write `src/api/server.py`  -  FastAPI POST /chat endpoint
- [ ] Test end-to-end: query → agent → MCP → Atlas → rerank → response with citations

**Done when:** POST /chat returns answer + citations for Query 1. PLAN mode creates a Google Doc.

---

## Session 5  -  React Frontend
**Goal:** Clean chat UI with mode badges, citations, and streaming.

- [ ] Scaffold Vite + React + TypeScript project in `src/frontend/`
- [ ] Write `ChatInterface.tsx`  -  main chat container
- [ ] Write `MessageBubble.tsx`  -  user vs agent messages
- [ ] Write `ModeSelector.tsx`  -  RECALL/ANALYZE/PLAN filter buttons
- [ ] Write `CitationCard.tsx`  -  source title, date, Drive link
- [ ] Implement streaming response display
- [ ] Show Google Doc link when PLAN mode returns created_doc_url
- [ ] Style: clean, minimal, mode badge color-coded (blue/purple/green)
- [ ] Connect to FastAPI backend at /chat

**Done when:** All 3 demo queries work end-to-end through the UI.

---

## Session 6  -  Polish + Demo Prep
**Goal:** Demo-ready. All 3 queries consistent. Video recorded.

- [ ] Run all 3 demo queries 5 times each  -  verify consistent good output
- [ ] Add remaining Drive files (Priority 2-5 from DATA_MAP.md)
- [ ] Tune noise filter prompt if too many irrelevant chunks pass through
- [ ] Tune chunking for Marketing Meetings (26MB)  -  chunk aggressively
- [ ] Set up public GitHub repo with OSS license (MIT)
- [ ] Deploy backend to Cloud Run or similar (needs hosted URL for submission)
- [ ] Deploy frontend to Vercel or Firebase Hosting
- [ ] Record 3-minute demo video following docs/DEMO_SCRIPT.md exactly
- [ ] Write Devpost submission using pitch from docs/JUDGING_ALIGNMENT.md
- [ ] Submit before June 11, 2026 @ 5:00pm EDT

---

## Decisions Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-27 | No dedicated people collection for v1 | Org structure and roles docs cover people queries implicitly once ingested. Scope risk not worth it before June 11. |
| 2026-05-27 | Progsu Org Structure + Roles docs moved to Priority 1 | People layer is free if these are ingested early. No architecture change needed. |
| 2026-05-27 | Bot integration deferred to post-hackathon | T&D Discord bot and Intelligence Agent to integrate after both ship independently. Noted in Devpost Potential Impact section. |
| 2026-05-27 | Demo leads with PLAN mode as climax | Judges want multi-step action-taking. PLAN mode creates a real Google Doc  -  the strongest proof point. |

---

## Known Issues

_None yet. Add as discovered._
