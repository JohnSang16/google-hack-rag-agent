# Epic: Gemini Agent + API
**Session:** 4
**Status:** NOT STARTED
**Goal:** Agent answers questions with citations. PLAN mode creates a real Google Doc.

---

## Context For Agents
This is the brain layer. A Gemini agent receives a query, classifies its mode,
calls the retrieval tool, and generates a response with citations. In PLAN mode
it additionally creates a real Google Doc via the Drive API and returns the link.

The agent talks to Atlas through the MongoDB MCP server, not through direct Python calls.
This is intentional — it demonstrates MCP tool use for the hackathon judges.

**Read these before writing any code:**
- `docs/ARCHITECTURE.md` — agent design and tool definitions
- `docs/DEMO_SCRIPT.md` — the exact 3 queries and expected response shapes
- `src/retrieval/retriever.py` — what the retrieval tool wraps
- `docs/JUDGING_ALIGNMENT.md` — what judges are looking for

---

## Features

### Feature 1: Mode Classifier
**Owner:** Dev Agent
**File:** `src/agent/mode_classifier.py`

#### Stories
- As the agent I want to know whether a query is RECALL, ANALYZE, or PLAN
  so that I can route it to the right response behavior

#### Tasks
- [ ] Accept a query string as input
- [ ] Call Gemini with a classification prompt
- [ ] Return one of three strings: "RECALL", "ANALYZE", or "PLAN"
- [ ] Classification rules:
      RECALL = asking about a specific past event or decision
      ANALYZE = asking for patterns, trends, or comparisons across time
      PLAN = asking to create, draft, or produce a document or action plan
- [ ] Default to RECALL if classification is ambiguous
- [ ] Write `tests/test_mode_classifier.py` with 2 test cases per mode plus 1 ambiguous case

---

### Feature 2: Retrieval Tool
**Owner:** Dev Agent
**File:** `src/agent/tools/retrieve.py`

#### Stories
- As the agent I want a registered tool that fetches relevant chunks for any query
  so that my responses are grounded in real org data not hallucinated

#### Tasks
- [ ] Wrap `src/retrieval/retriever.py` as an agent-callable tool
- [ ] Tool input schema: `{ query: string, filters: { event_name?, doc_type?, date_from?, date_to? } }`
- [ ] Tool output schema: list of `{ text, source_name, date, drive_link?, rerank_score }`
- [ ] Register as a Gemini function calling tool with a clear description
- [ ] Write `tests/test_retrieve_tool.py` using mocked retriever

---

### Feature 3: Create Doc Tool
**Owner:** Dev Agent
**File:** `src/agent/tools/create_doc.py`

#### Stories
- As the agent in PLAN mode I want to create a real Google Doc with my output
  so that judges see a tangible artifact being produced not just a chat response

#### Tasks
- [ ] Authenticate with Google Drive API using service account credentials
- [ ] Accept: document title and content as markdown string
- [ ] Create a new Google Doc in the org Drive folder
- [ ] Return the public view link to the created doc
- [ ] Handle authentication errors gracefully with a clear log message
- [ ] Write `tests/test_create_doc_tool.py` using a mocked Drive API

---

### Feature 4: Gemini Agent
**Owner:** Dev Agent
**File:** `src/agent/agent.py`

#### Stories
- As a user I want to ask any org intelligence question and receive a grounded answer
  so that I can make better decisions based on institutional knowledge

#### Tasks
- [ ] Initialize Gemini agent via Vertex AI Agent Builder
- [ ] Register retrieve tool and create_doc tool
- [ ] Configure MongoDB MCP server as the DB bridge for retrieval
- [ ] System prompt must instruct the agent to:
      Always cite sources using the source_name and date from retrieved chunks
      Never answer from general knowledge — only from retrieved chunks
      In PLAN mode: always create a Google Doc and return the link
      In ANALYZE mode: structure response with clear trends and data points
      In RECALL mode: answer directly and concisely with citations
- [ ] Agent response shape:
      `{ mode, answer, citations: [{ source_name, date, drive_link? }], created_doc_url? }`
- [ ] Write `tests/test_agent.py` with mocked tools for all 3 modes

---

### Feature 5: FastAPI Server
**Owner:** Dev Agent
**File:** `src/api/server.py`

#### Stories
- As the frontend I want a POST /chat endpoint that accepts a query and returns a response
  so that the React UI can display agent answers with citations

#### Tasks
- [ ] Create FastAPI app with POST /chat endpoint
- [ ] Request body: `{ query: string, filters?: object }`
- [ ] Response body: `{ mode, answer, citations, created_doc_url? }`
- [ ] Call mode_classifier then agent.py internally
- [ ] Add CORS middleware allowing localhost:5173 for local dev
- [ ] Add basic error handling: return 500 with error message if agent fails
- [ ] Write `tests/test_server.py` using FastAPI TestClient with mocked agent

---

### Feature 6: MongoDB MCP Wiring
**Owner:** Dev Agent
**No new file — configuration and integration task**

#### Tasks
- [ ] Configure MongoDB MCP server connection using MONGODB_URI from .env
- [ ] Wire the MCP server as the agent's database bridge in agent.py
- [ ] Verify agent can call retrieve tool through MCP not through direct Python import
- [ ] Document MCP configuration in `docs/ARCHITECTURE.md` under the agent section

---

### Feature 7: Vertex AI Agent Engine Deployment
**Owner:** Dev Agent
**No new file — deployment and configuration task**

**Why this must happen in Session 4, not Session 6:** Judges verify the agent is hosted on
Vertex AI Agent Engine, not running locally. Deploying here — while the agent is being built —
catches auth, tool registration, and API permission issues while there is still time to fix them.
Leaving this to Session 6 risks a last-day blocker with no recovery time before June 11.

#### Stories
- As a hackathon judge I want the agent deployed on Google Cloud Agent Builder
  so that the project qualifies for the "Google Cloud" technology criterion

#### Tasks
- [ ] Enable the Vertex AI Agent Engine API in GCP project (flag to human — requires console access)
- [ ] Ensure `GCP_PROJECT_ID` and `GCP_REGION` env vars are set (already in CLAUDE.md)
- [ ] Package agent.py for deployment: confirm all tool definitions and system prompt are
      expressed as Agent Builder-compatible tool schemas (not raw Python callables)
- [ ] Deploy agent to Vertex AI Agent Engine using the `google-cloud-aiplatform` SDK:
      ```python
      from google.cloud import aiplatform
      aiplatform.init(project=GCP_PROJECT_ID, location=GCP_REGION)
      # register and deploy agent with tools
      ```
- [ ] Verify the deployed agent endpoint responds to a test query via the Agent Engine API
- [ ] Update agent.py to call the deployed Agent Engine endpoint when
      `AGENT_ENGINE_ENDPOINT` env var is set, falling back to local Gemini SDK when not set
- [ ] Add `AGENT_ENGINE_ENDPOINT` to `.env.example`
- [ ] Run Query 1 against the deployed Agent Engine endpoint — confirm same response
      as local

#### Manual Steps (Flag To Human Before Starting)
- Enable Vertex AI Agent Engine API at console.cloud.google.com
- Grant the service account the `roles/aiplatform.user` IAM role
- Confirm GCP billing is active on the project

---

## QA Checklist (QA Agent)
- [ ] POST /chat returns correct shape for all 3 demo queries
- [ ] PLAN mode response includes a real created_doc_url pointing to a live Google Doc
- [ ] All citations include source_name and date
- [ ] Agent never answers without retrieving — verify by checking citations are always present
- [ ] Server returns 500 with useful error message if Atlas is unreachable
- [ ] Mode classifier correctly classifies all 3 demo queries
- [ ] Agent Engine endpoint responds to Query 1 with correct citations
- [ ] `AGENT_ENGINE_ENDPOINT` env var switches agent.py between local and deployed mode

---

## Definition of Done
POST /chat returns a grounded answer with citations for Query 1.
PLAN mode creates a real Google Doc and returns the link.
All 3 demo queries produce correct responses end to end.
Agent is deployed on Vertex AI Agent Engine and responding via the hosted endpoint.

---

## Handoff To Session 5
Confirm before Session 5 starts:
- server.py running locally at localhost:8000
- All 3 demo queries work via curl or Postman
- PLAN mode creates a real Google Doc every time
- Response shape matches what CitationCard.tsx will expect
- Agent Engine endpoint URL is in .env as AGENT_ENGINE_ENDPOINT
- Query 1 returns correct response from the deployed endpoint
