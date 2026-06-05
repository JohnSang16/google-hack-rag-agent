# TODO — Session Tracker

Claude Code: Update this file at the end of every session. Mark completed items, add next steps, note any decisions made.

---

## Current Status: SESSION 5 COMPLETE — starting Session 6

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

## Session 3 — Retrieval Layer ✓ DONE (2026-06-04)
**Goal:** Query returns relevant, reranked chunks for all 3 demo queries.

- [x] Write `src/retrieval/vector_search.py` — full $vectorSearch with metadata pre-filter (Session 1)
- [x] Write `src/retrieval/reranker.py` — Gemini scoring, return top-3
- [x] Write `src/retrieval/retriever.py` — combine search + rerank into one call
- [x] Test all 3 demo queries from docs/DEMO_SCRIPT.md manually
- [x] Query 1: 3 results, scores 8-9, correct Hacklanta sources
- [x] Query 3: 3 results, scores 9, correct Hacklanta sources
- [~] Query 2: only 2 results, scores 4-6 — attendance aggregate files not yet ingested

**Known gap:** Query 2 (attendance trends) needs AGGREGATE files ingested.
Share these with the service account and run `--priority aggregate`:
- Combined Attendance, Hacklanta Check in, Involvement Fair Signups

---

## Session 4 — Gemini Agent + FastAPI ✓ DONE (2026-06-04)
**Goal:** Agent answers questions with citations. MongoDB MCP is the tool it uses.

- [x] Write `src/agent/mode_classifier.py` — classifies query to RECALL/ANALYZE/PLAN
- [x] Write `src/agent/tools/retrieve.py` — calls retriever.py pipeline
- [x] Write `src/agent/tools/create_doc.py` — creates Google Doc via Drive + Docs API
- [x] Write `src/agent/agent.py` — Gemini agent with JSON-mode answer generation + citation enrichment
- [x] Write `src/api/server.py` — FastAPI POST /chat + GET /health
- [x] Tested Query 1 end-to-end: RECALL mode, 3 citations, correct Hacklanta content
- [x] Tested Query 3 end-to-end: PLAN mode, generates full structured brief

**NEEDS USER ACTION before Google Doc creation works:**
- Re-share Drive root folder `11eYr6RIieuw4EvCZCzaMBa8ib8llDr9-` with service account
  as **Editor** (currently Viewer only — create fails with 403)
- Service account: `progsu-agent@gen-lang-client-0169091300.iam.gserviceaccount.com`

**Deferred:** Vertex AI Agent Engine deployment (requires enabling API + IAM in GCP console)

**Run server:** `python -m src.api.server`

---

## Session 5 — React Frontend ✓ DONE (2026-06-05)
**Goal:** Clean chat UI with mode badges, citations, and streaming.

- [x] Scaffold Vite + React + TypeScript project in `src/frontend/`
- [x] Write `ChatInterface.tsx` — main chat container with loading state + error handling
- [x] Write `MessageBubble.tsx` — user/agent/error messages with inline markdown rendering
- [x] Write `ModeSelector.tsx` — static RECALL/ANALYZE/PLAN legend strip with tooltips
- [x] Write `CitationCard.tsx` — collapsible "Sources (N)" with relevance labels and Drive links
- [x] Typing indicator animation (no streaming — full response renders on completion)
- [x] Show "View Google Doc" button when PLAN mode returns created_doc_url
- [x] Style: clean minimal design, mode badge color-coded (blue/purple/green)
- [x] Proxy to FastAPI backend at /chat via vite.config.ts
- [x] Write `src/types.ts` — shared TypeScript types matching actual API response shape

**Run frontend:** `cd src/frontend && npm run dev` (localhost:5173)
**Run backend:** `python -m src.api.server` (localhost:8000)

**Bug fixed this session:** Socket dropped on every query — sync Gemini SDK calls were
blocking the async event loop. Fixed with asyncio.to_thread() in agent.py and retriever.py.

**Still blocked (human action needed):**
- Drive folder re-share as Editor for PLAN mode doc creation (see Session 4 blocker)
- Aggregate files not yet ingested — Query 2 returns weak results (see Session 3 gap)

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
