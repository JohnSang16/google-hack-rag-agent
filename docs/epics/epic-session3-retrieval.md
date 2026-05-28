# Epic: Retrieval Layer
**Session:** 3
**Status:** NOT STARTED
**Goal:** All 3 demo queries return relevant, reranked, well-sourced chunks.

---

## Context For Agents
The retrieval layer sits between Atlas and the agent. It takes a natural language query,
finds the top candidates via vector search, reranks them with Gemini, and returns
the top 3 most relevant chunks with source metadata.

**Read these before writing any code:**
- `docs/DEMO_SCRIPT.md`  -  the 3 exact demo queries judging will use
- `src/retrieval/vector_search.py`  -  already written in Session 1, may need updates
- `docs/ARCHITECTURE.md`  -  retrieval layer design

The three demo queries are:
1. RECALL: "What were the key logistics challenges at Hacklanta and how did we solve them?"
2. ANALYZE: "How has our event attendance grown from Fall 2025 to Spring 2026,
             and which events drove the most engagement?"
3. PLAN: "Draft a planning brief for our next major hackathon based on everything
          we learned from Hacklanta."

---

## Features

### Feature 1: Vector Search (Update Existing)
**Owner:** Dev Agent
**File:** `src/retrieval/vector_search.py`

#### Stories
- As the retrieval layer I want to retrieve top-10 candidate chunks for any query
  so that the reranker has enough candidates to find the best 3

#### Tasks
- [ ] Read existing vector_search.py from Session 1
- [ ] Confirm top_k defaults to 10 (already set in Session 1)  -  verify, do not change
- [ ] Confirm metadata pre-filter works for event_name, doc_type, and date range
- [ ] Return full chunk document including text, metadata, and similarity score
- [ ] Add optional date range filter: `date_from` and `date_to` as parameters
- [ ] Write or update `tests/test_vector_search.py` to cover top-10 return and date filter

---

### Feature 2: Reranker
**Owner:** Dev Agent
**File:** `src/retrieval/reranker.py`

#### Stories
- As the agent I want the 3 most relevant chunks from any query
  so that responses are precise and well sourced without irrelevant padding

#### Tasks
- [ ] Accept query string and list of up to 10 candidate chunks
- [ ] Use the exact reranker prompt from `docs/ARCHITECTURE.md`  -  do not write a new one
- [ ] Gemini returns an integer 1 - 10 per chunk  -  parse it as an int, not a float
- [ ] Keep chunks scoring >= 6. If fewer than 2 chunks score >= 6, keep top 2 regardless
      (this fallback logic is specified in ARCHITECTURE.md and must be implemented exactly)
- [ ] Sort kept chunks by score descending, return top 3
- [ ] Return each chunk with its integer rerank_score attached for citation display
- [ ] Write `tests/test_reranker.py` with a mock set of 10 chunks:
      - Test: chunks scoring >= 6 are returned, chunks scoring < 6 are dropped
      - Test: if only 1 chunk scores >= 6, the top 2 by score are returned (fallback)
      - Test: scores are sorted descending in the returned list

---

### Feature 3: Unified Retriever
**Owner:** Dev Agent
**File:** `src/retrieval/retriever.py`

#### Stories
- As the agent I want a single function call that handles the full retrieval flow
  so that the agent layer does not need to know how retrieval is implemented internally

#### Tasks
- [ ] Accept: query string and optional filters (event_name, doc_type, date range)
- [ ] Internally: call vector_search to get top 10, then reranker to get top 3
- [ ] Return: list of 3 chunks each with text, metadata, source name, date, rerank score
- [ ] If fewer than 3 results exist return whatever is available without erroring
- [ ] Write `tests/test_retriever.py` using mocked vector_search and reranker

---

### Feature 4: Demo Query Validation
**Owner:** Dev Agent + QA Agent
**No new file  -  this is a validation and tuning task**

#### Stories
- As a demo presenter I want all 3 demo queries to return correct relevant results
  so that the demo does not fail in front of judges

#### Tasks
- [ ] Run Query 1 (Hacklanta logistics) manually  -  verify results reference Hacklanta sources
- [ ] Run Query 2 (attendance growth) manually  -  verify results include attendance data chunks
- [ ] Run Query 3 (hackathon planning brief) manually  -  verify results include planning docs
- [ ] If Query 1 fails: check that Hacklanta Master Doc chunks are in Atlas with correct event_name
- [ ] If Query 2 fails: check that aggregate spreadsheet summaries were stored in Session 2
- [ ] If Query 3 fails: try reducing chunk size in chunker.py from 800 to 600 tokens and re-ingest
- [ ] Document tuning decisions made in `docs/TUNING_LOG.md` (create if it does not exist)

---

## QA Checklist (QA Agent)
- [ ] All 3 demo queries return at least 3 results with non-zero rerank scores
- [ ] Query 1 results include at least one chunk with event_name="hacklanta"
- [ ] Query 2 results include at least one chunk from an attendance spreadsheet summary
- [ ] Query 3 results include at least one chunk from a planning or retrospective document
- [ ] No chunk returned has a rerank score below 6 (on the 1 - 10 scale) for its matched query
- [ ] retriever.py returns in under 3 seconds for all 3 demo queries

---

## Definition of Done
All 3 demo queries return correct, relevant, well-sourced results through retriever.py.
Reranker scores are attached to each result. Performance under 3 seconds per query.

---

## Handoff To Session 4
Confirm before Session 4 starts:
- All 3 demo queries return correct results through retriever.py  -  Atlas data confirmed good for Session 4 agent wiring
- Tuning decisions documented in TUNING_LOG.md
