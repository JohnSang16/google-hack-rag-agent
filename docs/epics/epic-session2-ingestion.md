# Epic: Ingestion Pipeline
**Session:** 2
**Status:** NOT STARTED
**Goal:** Real Google Drive docs ingested, chunked, filtered, embedded, and stored in Atlas.

---

## Context For Agents
This pipeline takes a list of Google Drive file IDs and produces clean, embedded chunks
stored in MongoDB Atlas. It runs in this exact order:

```
drive_reader -> pii_filter -> chunker -> noise_filter -> embedder -> storer
```

Each module is independent. Build and test each one before wiring them together
in run_ingestion.py. Chunking rules and PII rules live in docs referenced below.
Do NOT hardcode any API keys. All credentials come from environment variables in `.env`.

**Read these files before writing any code:**
- `docs/ARCHITECTURE.md` — overall system design
- `docs/DATA_MAP.md` — Priority 1 files to run on at the end
- `CLAUDE.md` — chunking rules per doc_type
- `docs/PII_RULES.md` — what counts as PII and how to handle it

---

## Features

### Feature 1: Google Drive Reader
**Owner:** Dev Agent
**File:** `src/ingestion/drive_reader.py`

#### Stories
- As the pipeline I want to authenticate with Google Drive using a service account
  so that I can export documents programmatically without manual intervention
- As the pipeline I want to export any Drive doc to plain text by file ID
  so that downstream modules receive consistent string input regardless of file type

#### Tasks
- [ ] Authenticate using service account JSON at path in `GOOGLE_DRIVE_CREDENTIALS` env var
- [ ] Export Google Docs to plain text via Drive API export endpoint
- [ ] Export Google Sheets to CSV text (for attendance spreadsheets)
- [ ] Handle 403 permission errors gracefully with a clear log message
- [ ] Return: `{ file_id, file_name, doc_type, raw_text, mime_type }`
- [ ] Write `tests/test_drive_reader.py` using a mock Drive API response

---

### Feature 2: PII Filter
**Owner:** Dev Agent
**File:** `src/ingestion/pii_filter.py`

#### Stories
- As the org I want all PII stripped before storage so that member privacy is protected
  and we comply with responsible data handling

#### Tasks
- [ ] Read `docs/PII_RULES.md` for the full list of what counts as PII in this project
- [ ] Regex pass: strip email addresses, phone numbers, student ID patterns
- [ ] Gemini pass: second sweep for names and sensitive phrases regex misses
- [ ] Gemini prompt must be conservative: only strip clear PII, never strip org content
- [ ] Return cleaned text and a log of what was stripped (type only, not the actual value)
- [ ] Write `tests/test_pii_filter.py` with at least 5 PII test cases and 3 clean text cases

---

### Feature 3: Chunker
**Owner:** Dev Agent
**File:** `src/ingestion/chunker.py`

#### Stories
- As the pipeline I want documents split into focused retrievable chunks
  so that vector search returns specific relevant passages not entire documents
- As the pipeline I want chunking rules to vary by doc_type
  so that meeting notes split differently from event planning docs

#### Tasks
- [ ] Read `CLAUDE.md` for the chunking rules per doc_type
- [ ] Implement date header splitting for meeting notes (new chunk at each date)
- [ ] Implement ## heading splitting for planning docs
- [ ] Enforce 800 token max per chunk — split further if needed
- [ ] Add 50 token overlap between adjacent chunks to preserve context at boundaries
- [ ] Each chunk gets metadata: `{ file_id, chunk_index, doc_type, source_heading, token_count }`
- [ ] Write `tests/test_chunker.py` covering: normal split, oversized chunk, overlap, each doc_type

---

### Feature 4: Noise Filter
**Owner:** Dev Agent
**File:** `src/ingestion/noise_filter.py`

#### Stories
- As the retrieval layer I want only relevant chunks stored
  so that search results are not polluted with boilerplate, headers, or filler content

#### Tasks
- [ ] Call Gemini with a YES/NO prompt per chunk
- [ ] Prompt must ask: does this chunk contain meaningful org intelligence?
  Examples of noise: "Page 1 of 3", attendance headers with no data, blank agenda slots
- [ ] Log pass rate: how many chunks passed vs total
- [ ] Batch Gemini calls where possible to reduce latency and cost
- [ ] Write `tests/test_noise_filter.py` with 3 noise examples and 3 signal examples
- [ ] Noise filter threshold is configurable via env var `NOISE_FILTER_THRESHOLD` default 0.5

---

### Feature 5: Embedder
**Owner:** Dev Agent
**File:** `src/ingestion/embedder.py`

#### Stories
- As the pipeline I want each chunk converted to a 768-dimensional vector
  so that it can be stored and retrieved via semantic similarity search

#### Tasks
- [ ] Call Google text-embedding-004 model via Gemini API
- [ ] Input: chunk text string
- [ ] Output: list of 768 floats
- [ ] Validate output dimension is exactly 768 — raise if not
- [ ] Handle API rate limits with exponential backoff, max 3 retries
- [ ] Write `tests/test_embedder.py` using a mocked API response to avoid real API calls in CI

---

### Feature 6: Spreadsheet Summarizer
**Owner:** Dev Agent
**File:** `src/ingestion/summarizer.py`

#### Stories
- As the pipeline I want spreadsheet files summarized before chunking
  so that attendance data and structured data is readable by the retrieval layer
  instead of being stored as raw CSV rows that lose context

#### Tasks
- [ ] Read `docs/PII_RULES.md` for spreadsheet specific handling rules
- [ ] Accept CSV text as input
- [ ] Use Gemini to produce a structured summary: total rows, key columns, notable patterns
- [ ] Output summary as a single text block that gets passed to chunker like any other doc
- [ ] Write `tests/test_summarizer.py` with a sample attendance CSV

---

### Feature 7: Pipeline Orchestrator
**Owner:** Dev Agent
**File:** `src/ingestion/run_ingestion.py`

#### Stories
- As a developer I want to run the full pipeline for a list of file IDs in one command
  so that I can ingest all Priority 1 files without running each module manually

#### Tasks
- [ ] Accept a list of file IDs as input (from command line or config file)
- [ ] Run each file through: drive_reader -> pii_filter -> chunker (or summarizer for sheets)
      -> noise_filter -> embedder -> storer
- [ ] Log per file: file name, chunks produced, chunks passing noise filter, errors
- [ ] If any single file fails, log the error and continue to the next file
- [ ] At the end print a summary: total files, total chunks stored, total errors
- [ ] Write `tests/test_run_ingestion.py` using mocked versions of all sub-modules

---

## QA Checklist (QA Agent)
- [ ] Each module has its own test file with at least 3 meaningful test cases
- [ ] No API keys or credentials appear in any source or test file
- [ ] All modules read credentials from environment variables only
- [ ] run_ingestion.py processes a sample file list without crashing
- [ ] Chunk count logged matches chunks visible in Atlas after a real run
- [ ] noise filter pass rate is logged and above 40% (if below, prompt needs tuning)
- [ ] PII strip log shows at least one strip on any file containing member data

---

## Definition of Done
Hacklanta Master Doc and at least 5 other Priority 1 files from `docs/DATA_MAP.md`
are chunked, filtered, embedded, and stored in Atlas. run_ingestion.py logs show
chunk counts, noise filter pass rate, and zero unhandled errors.

---

## Handoff To Session 3
Confirm these before Session 3 starts:
- At least 500 chunks stored in Atlas with correct metadata
- All three demo query sources are present in Atlas as chunks
- Noise filter pass rate logged and acceptable
- No PII visible in any stored chunk when spot checked in Atlas UI
