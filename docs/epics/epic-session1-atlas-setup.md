# Epic: MongoDB Atlas Setup
**Session:** 1
**Status:** IN PROGRESS
**Goal:** Full vector search loop working on dummy data. Unblocks everything downstream.

---

## Context For Agents
This is a RAG-based AI chief of staff for a student tech org. We store document chunks
with 768-dimensional embeddings in MongoDB Atlas and query them via $vectorSearch.
Two files are already written: `src/ingestion/storer.py` and `src/retrieval/vector_search.py`.
The Atlas cluster does NOT exist yet  -  that is a manual step the human must complete first.

**DO NOT attempt to run any DB tests until the human confirms Atlas is live.**

---

## Manual Steps (Human Only  -  Agents Cannot Do These)
These require browser access and sensitive credentials. Flag these to the human and wait.

1. Create free Atlas cluster at cloud.mongodb.com
2. Create database `progsu_intelligence`, collection `chunks`
3. Create Vector Search index using definition in `docs/ARCHITECTURE.md`
4. Paste the Atlas connection string into `.env` as `MONGODB_URI`

---

## Features

### Feature 1: Validate Existing Storer
**Owner:** Dev Agent
**Depends on:** Atlas cluster being live (human step above)

#### Stories
- As a developer I want storer.py to insert a chunk document with all required fields
  so that downstream retrieval has consistent data to query against
- As a developer I want idempotent upserts using file_id + chunk_index as the key
  so that re-running ingestion does not create duplicate chunks

#### Tasks
- [ ] Read `src/ingestion/storer.py` and verify schema matches the canonical schema in CLAUDE.md:
      `{ text, embedding: [768 floats], metadata: { source_type, doc_type, semester, event_name,
      date, team, file_id, file_title, chunk_index } }`
- [ ] If any metadata field is missing add it with a sensible default (None for optional fields)
- [ ] Confirm upsert key is `file_id` + `chunk_index` combined

---

### Feature 2: Validate Existing Vector Search
**Owner:** Dev Agent
**Depends on:** Atlas Vector Search index created (human step above)

#### Stories
- As a developer I want vector_search.py to return the most semantically similar chunk
  so that retrieval produces relevant results
- As a developer I want metadata pre-filtering by event_name
  so that queries can be scoped to specific events like Hacklanta

#### Tasks
- [ ] Read `src/retrieval/vector_search.py` and verify $vectorSearch pipeline is correct
- [ ] Confirm metadata pre-filter accepts `event_name` as an optional parameter
- [ ] Confirm `numCandidates` and `limit` are configurable, not hardcoded

---

### Feature 3: Smoke Test Suite
**Owner:** Dev Agent + Test Agent
**Depends on:** Features 1 and 2 complete, Atlas live

#### Stories
- As a developer I want a passing smoke test so that I know the full insert-query loop works
  before building the real ingestion pipeline on top of it

#### Tasks
- [ ] Write `tests/test_session1.py` if it does not exist, or review if it does
- [ ] Test must: insert 5 dummy chunks with fake 768-dim embeddings
- [ ] Test must: query and verify the most similar chunk is returned correctly
- [ ] Test must: verify metadata pre-filter returns only chunks where event_name="hacklanta"
- [ ] Test must: verify a filter mismatch returns zero results

---

### Feature 4: Environment Setup Validation
**Owner:** Dev Agent
**Depends on:** Nothing, can run immediately

#### Stories
- As a developer I want a validated .env.example so that any agent or teammate
  knows exactly what credentials are needed without exposing real values

#### Tasks
- [ ] Check if `.env.example` exists
- [ ] If not, create it with all keys from CLAUDE.md env vars section:
      `GEMINI_API_KEY=your_gemini_api_key_here`
      `MONGODB_URI=your_atlas_connection_string_here`
      `MONGODB_DB_NAME=progsu_intelligence`
      `MONGODB_COLLECTION=chunks`
      `GOOGLE_DRIVE_CREDENTIALS=path_to_your_service_account_json`
      `GCP_PROJECT_ID=your_gcp_project_id`
      `GCP_REGION=us-central1`
      `AGENT_ENGINE_ENDPOINT=your_vertex_agent_engine_endpoint`
      `NOISE_FILTER_THRESHOLD=0.5`
- [ ] Verify `.env` is in `.gitignore`  -  add it if missing
- [ ] Verify `.env.example` is NOT in `.gitignore`

---

## QA Checklist (QA Agent)
- [ ] storer.py inserts without errors against live Atlas
- [ ] vector_search.py returns results without errors against live Atlas
- [ ] All 4 test assertions in test_session1.py pass
- [ ] No real credentials appear anywhere in tracked files
- [ ] .env is gitignored

---

## Definition of Done
`vector_search.py` returns the correct dummy chunk for a test query.
All smoke tests pass. `.env.example` is present and complete.

---

## Handoff To Session 2
Confirm these are true before Session 2 starts:
- Atlas cluster is live and reachable via MONGODB_URI
- test_session1.py passes fully
- storer.py and vector_search.py are confirmed correct
