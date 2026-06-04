# TODO — Session Tracker

Claude Code: Update this file at the end of every session. Mark completed items, add next steps, note any decisions made.

---

## Current Status: SESSION 2 COMPLETE — starting Session 3

---

## Session 1 — MongoDB Atlas Setup ✓ DONE (2026-05-30)
**Goal:** Full vector search loop working on dummy data in under 1 hour.

- [x] Create MongoDB Atlas free cluster (cloud.mongodb.com)
- [x] Create database: `progsu_intelligence`, collection: `chunks`
- [x] Create Atlas Vector Search index using definition in docs/ARCHITECTURE.md
- [x] Write `src/ingestion/storer.py` — function to insert a chunk with embedding
- [x] Write `src/retrieval/vector_search.py` — function to query with $vectorSearch
- [x] Test: insert 5 dummy chunks with fake embeddings, query returns correct ones
- [x] Verify metadata pre-filter works (filter by event_name="hacklanta")

**Result:** 5/5 tests passed. `$vectorSearch` with pre-filter confirmed working on M0 free tier.

---

## Session 2 — Google Drive Ingestion Pipeline ✓ DONE (2026-06-04)
**Goal:** Real Drive docs ingested, chunked, filtered, embedded, stored in Atlas.

- [x] Write `src/ingestion/drive_reader.py` — authenticate with Drive API, export doc to text by file ID
- [x] Write `src/ingestion/pii_filter.py` — regex strip + Gemini strip for emails/phones/names
- [x] Write `src/ingestion/chunker.py` — split by doc_type rules from CLAUDE.md
- [x] Write `src/ingestion/noise_filter.py` — Gemini YES/NO scoring per chunk
- [x] Write `src/ingestion/embedder.py` — call text-embedding-004, return 768-dim vector
- [x] Write `src/ingestion/run_ingestion.py` — orchestrate full pipeline for a list of file IDs
- [ ] Run on Priority 1 files from docs/DATA_MAP.md ← **DO THIS NEXT**
- [ ] Log: chunk count, noise filter pass rate, any errors
- [ ] Aggregate files: summarizer implemented in run_ingestion.py (ready to run)

**Run command:** `python -m src.ingestion.run_ingestion --priority 1`
**Faster (skip per-chunk Gemini PII):** `python -m src.ingestion.run_ingestion --priority 1 --skip-gemini-pii`

**Done when:** Hacklanta Master Doc and at least 5 other files are chunked and stored in Atlas.

**Decisions:**
- Used `google-genai` SDK (new, replaces deprecated `google-generativeai`)
- Gemini PII pass is per-chunk, skipped for chunks > 8KB (regex-only for large docs)
- `--skip-gemini-pii` flag available for faster runs (regex PII only)
- AGGREGATE files go through Gemini summarizer, stored as 1 chunk each
- All Priority 1-5 + aggregate file specs hardcoded in run_ingestion.py

---

## Session 3 — Retrieval Layer
**Goal:** Query returns relevant, reranked chunks for all 3 demo queries.

- [ ] Write `src/retrieval/vector_search.py` — full $vectorSearch with metadata pre-filter
- [ ] Write `src/retrieval/reranker.py` — Gemini scoring, return top-3
- [ ] Write `src/retrieval/retriever.py` — combine search + rerank into one call
- [ ] Test all 3 demo queries from docs/DEMO_SCRIPT.md manually
- [ ] Tune: if Query 1 doesn't return Hacklanta sources, adjust chunk size or k
- [ ] Tune: if Query 2 doesn't find attendance data, check aggregate chunks were stored

**Done when:** All 3 demo queries return correct, relevant results with good sources.

---

## Session 4 — Gemini Agent + MongoDB MCP
**Goal:** Agent answers questions with citations. MongoDB MCP is the tool it uses.

- [ ] Write `src/agent/mode_classifier.py` — classifies query to RECALL/ANALYZE/PLAN
- [ ] Write `src/agent/tools/retrieve.py` — the tool the agent calls (wraps retriever.py)
- [ ] Write `src/agent/tools/create_doc.py` — creates Google Doc via Drive API
- [ ] Write `src/agent/agent.py` — Gemini agent via Agent Builder with tools registered
- [ ] Configure MongoDB MCP server connection to Atlas
- [ ] Wire agent to call retrieval through MCP (not direct Python call)
- [ ] Write `src/api/server.py` — FastAPI POST /chat endpoint
- [ ] Test end-to-end: query → agent → MCP → Atlas → rerank → response with citations

**Done when:** POST /chat returns answer + citations for Query 1. PLAN mode creates a Google Doc.

---

## Session 5 — React Frontend
**Goal:** Clean chat UI with mode badges, citations, and streaming.

- [ ] Scaffold Vite + React + TypeScript project in `src/frontend/`
- [ ] Write `ChatInterface.tsx` — main chat container
- [ ] Write `MessageBubble.tsx` — user vs agent messages
- [ ] Write `ModeSelector.tsx` — RECALL/ANALYZE/PLAN filter buttons
- [ ] Write `CitationCard.tsx` — source title, date, Drive link
- [ ] Implement streaming response display
- [ ] Show Google Doc link when PLAN mode returns created_doc_url
- [ ] Style: clean, minimal, mode badge color-coded (blue/purple/green)
- [ ] Connect to FastAPI backend at /chat

**Done when:** All 3 demo queries work end-to-end through the UI.

---

## Session 6 — Polish + Demo Prep
**Goal:** Demo-ready. All 3 queries consistent. Video recorded.

- [ ] Run all 3 demo queries 5 times each — verify consistent good output
- [ ] Add remaining Drive files (Priority 2-5 from DATA_MAP.md)
- [ ] Tune noise filter prompt if too many irrelevant chunks pass through
- [ ] Tune chunking for Marketing Meetings (26MB) — chunk aggressively
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
| — | — | — |

---

## Known Issues

_None yet. Add as discovered._
