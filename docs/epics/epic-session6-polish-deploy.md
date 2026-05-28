# Epic: Polish + Deploy
**Session:** 6
**Status:** NOT STARTED
**Goal:** Demo ready. All 3 queries consistent. Deployed. Video recorded. Submitted.

---

## Context For Agents
This is the final session before the June 11 deadline. Focus is on stability,
consistency, and getting a clean demo recording. Agents should NOT introduce
new features. Fix, tune, deploy, document.

**Hard deadline:** June 11, 2026 @ 5:00pm EDT
**Read before starting:** `docs/DEMO_SCRIPT.md` and `docs/JUDGING_ALIGNMENT.md`

---

## Features

### Feature 1: Demo Consistency Testing
**Owner:** QA Agent
**No new files  -  validation only**

#### Tasks
- [ ] Run all 3 demo queries 5 times each against the full stack
- [ ] Log each result: did it return correct sources? Was the answer coherent?
- [ ] Flag any run where a query fails or returns irrelevant results
- [ ] Consistency target: 4 out of 5 runs correct per query minimum

---

### Feature 2: Noise Filter Tuning (If Needed)
**Owner:** Dev Agent
**Only do this if consistency testing flags retrieval issues**

#### Tasks
- [ ] If Query 1 fails more than once: check Hacklanta chunks in Atlas, verify event_name metadata
- [ ] If Query 2 fails more than once: verify attendance summary chunks were stored
- [ ] If noise filter pass rate from Session 2 was below 40%: loosen the Gemini prompt
- [ ] If noise filter pass rate was above 85%: tighten it  -  too much noise is getting through
- [ ] Re-ingest affected files if chunking or filtering changes are made
- [ ] Document all tuning changes in `docs/TUNING_LOG.md`

---

### Feature 3: Chunking Tuning for Large Files (If Needed)
**Owner:** Dev Agent
**Only do this if large file retrieval is poor**

#### Tasks
- [ ] Marketing Meetings file (26MB)  -  if retrieval misses it, reduce chunk size to 400 tokens
- [ ] Re-ingest with updated chunker settings
- [ ] Re-validate demo queries after re-ingestion

---

### Feature 4: Add Remaining Drive Files
**Owner:** Dev Agent + human to confirm file IDs
**Wait for human to confirm Priority 2-5 file IDs before running**

#### Tasks
- [ ] Human confirms Priority 2-5 file IDs from `docs/DATA_MAP.md`
- [ ] Run run_ingestion.py on Priority 2-5 files
- [ ] Verify chunk counts in Atlas increased as expected
- [ ] Re-run all 3 demo queries to confirm adding more data did not hurt results

---

### Feature 5: GitHub Repo Setup
**Owner:** Dev Agent

#### Tasks
- [ ] Verify `.gitignore` covers: `.env`, `*.pyc`, `__pycache__`, `node_modules`, `dist`
- [ ] Add MIT license file to root if not present
- [ ] Write `README.md` covering: what this is, how to run it locally, env vars needed
- [ ] README must include: architecture diagram description, the 3 demo queries, setup steps
- [ ] Make repo public (human does this  -  flag it as a manual step)

---

### Feature 6: Backend Deployment
**Owner:** Dev Agent
**Human must set Cloud Run env vars  -  flag this as a manual step**

#### Tasks
- [ ] Write `Dockerfile` for the FastAPI backend
- [ ] Build and test Docker image locally before deploying
- [ ] Write `cloudbuild.yaml` or deployment instructions for Cloud Run
- [ ] Document the manual env var steps the human must complete in Atlas and Cloud Run console
- [ ] Verify POST /chat works at the deployed Cloud Run URL
- [ ] Update CORS middleware in server.py to allow the deployed frontend URL
      (replace localhost:5173 with the Vercel/Firebase production URL)
- [ ] Update frontend API base URL to point to Cloud Run URL

---

### Feature 7: Frontend Deployment
**Owner:** Dev Agent

#### Tasks
- [ ] Build frontend: `npm run build`
- [ ] Deploy to Vercel or Firebase Hosting (prefer Vercel for simplicity)
- [ ] Verify all 3 demo queries work through the deployed frontend hitting Cloud Run backend
- [ ] Confirm no CORS errors in production

---

### Feature 8: Devpost Submission
**Owner:** Human  -  agents assist with draft only**

#### Tasks (Agent assists, human submits)
- [ ] Read `docs/JUDGING_ALIGNMENT.md` for the pitch framing
- [ ] Draft Devpost submission text covering: what it does, how it was built, what makes it unique
- [ ] Draft must highlight: RAG architecture, MCP tool use, Google Cloud stack, real artifact creation
- [ ] Human reviews draft, edits, and submits at devpost.com before June 11 5:00pm EDT
- [ ] Human records 3-minute demo video following `docs/DEMO_SCRIPT.md` exactly

---

## QA Checklist (QA Agent)
- [ ] All 3 demo queries return good results 4 out of 5 times
- [ ] Deployed frontend loads without errors
- [ ] PLAN mode creates a real Google Doc at the deployed URL
- [ ] README is complete and someone unfamiliar with the project can follow setup steps
- [ ] No API keys in any committed file
- [ ] MIT license is present

---

## Definition of Done
Project is deployed. All 3 demo queries are consistent. Demo video is recorded.
Devpost submission is submitted before June 11, 2026 @ 5:00pm EDT.
