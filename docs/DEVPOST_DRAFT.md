# Devpost Submission Draft

Hackathon: Google Cloud Rapid Agent Hackathon (MongoDB Track)
Deadline: June 11, 2026 @ 5:00pm EDT

---

## Project Name

progsu Intelligence Agent

---

## Tagline

Every student org leader loses institutional knowledge when people graduate. This agent makes a year of org history instantly queryable and actionable.

---

## About the Project

### The Problem

Student tech orgs run on Google Drive and Discord. Decisions get buried in threads. Event playbooks live in documents that only the current leadership knows exist. When people graduate, the knowledge graduates with them.

As Technical Director of progsu (ProgClub at Georgia State University), we ran a $20,000-sponsored hackathon, a Claude Code workshop with 200+ attendees, and dozens of smaller events across two semesters. Every lesson we learned, every vendor negotiation, every logistics decision, lives in scattered docs and Discord threads.

The next Technical Director inherits a Drive folder and hopes for the best.

### The Solution

progsu Intelligence Agent ingests a full year of real organizational data and makes it instantly queryable and actionable. Ask what challenges came up at the last hackathon. Ask how attendance has grown. Ask the agent to draft a planning brief for the next event, and watch it create a real Google Doc from everything it learned.

Three query modes, each more powerful than the last:

- **RECALL**: "What were the key logistics challenges at Hacklanta?" The agent retrieves grounded, cited answers from actual org documents.
- **ANALYZE**: "How has our event attendance grown from Fall 2025 to Spring 2026?" The agent synthesizes across multiple sources, surfacing real numbers and trends.
- **PLAN**: "Draft a planning brief for our next major hackathon." The agent retrieves, synthesizes, and creates a real Google Doc in Drive. Not just an answer. An artifact.

This is not a generic RAG demo. It handles messy, heterogeneous data: Google Docs, spreadsheets, a 22MB master planning doc exported tab by tab, and a full Discord server export processed through a Gemini-powered noise filter that scores every chunk before storage. Only organizationally meaningful content makes it in.

---

## How We Built It

### Stack

- **LLM + Embeddings**: Gemini API (gemini-2.0-flash for generation, reranking, and noise filtering; text-embedding-004 for 768-dim embeddings)
- **Agent Orchestration**: Google Cloud Agent Builder (Vertex AI Agent Engine)
- **Vector + Document Store**: MongoDB Atlas with Atlas Vector Search
- **Agent-to-DB Bridge**: MongoDB MCP server
- **Drive Integration**: Google Drive API for ingestion and Google Docs API for artifact creation
- **Backend**: FastAPI on Cloud Run
- **Frontend**: React (Vite) + TypeScript on Vercel

### Pipeline

Every user query goes through a deliberate pipeline:

```
User query
  → mode classifier (Gemini)
  → metadata pre-filter (date, event, team, doc_type)
  → MongoDB Atlas vector search (top-k=10)
  → reranker (Gemini scores relevance, keeps top-3)
  → Gemini agent reasons over chunks
  → response with citations [source_name, date, drive_link]
  → if PLAN mode: create_google_doc() via Drive + Docs API
```

### Data Quality Decisions

Every chunk that enters Atlas passes a Gemini YES/NO noise filter before storage. For Discord data specifically, this is the difference between a useful knowledge base and a searchable meme archive. The noise filter pass rate is logged and visible during ingestion.

PII is stripped before chunking: regex for emails and phone numbers, Gemini pass for non-executive names. Author names in Discord messages are replaced with role labels.

Metadata-aware retrieval uses MongoDB compound pre-filters (event, team, semester, doc_type) before ANN search, making retrieval faster and more precise than pure vector search alone.

### The PLAN Mode Differentiator

When the agent classifies a query as PLAN, it retrieves from 5+ sources, synthesizes a structured brief, and calls create_google_doc() to produce a real artifact in the org's Google Drive folder. The Google Doc has formatted sections, bolded headings, and clickable source links. The user can share it, edit it, or send it directly to the next exec board.

---

## Challenges We Ran Into

**Async event loop blocking**: Sync Gemini SDK calls were blocking the FastAPI async event loop, dropping every socket connection mid-response. Fixed by wrapping all blocking calls in asyncio.to_thread().

**22MB Google Doc**: The Progsu Master Doc exports as a single enormous blob. Solved with tab-by-tab export via the Docs API, chunking each tab separately with heading-based splits.

**Discord noise**: Exporting a full Discord server gives you bot messages, reaction notifications, and two years of #memes alongside real strategic decisions. The Gemini noise filter handles this, but tuning the prompt to correctly distinguish "we decided to cap tickets at 300" from "lol okay" required iteration.

**Drive permissions for PLAN mode**: The service account had Viewer-only access to the output folder. Doc creation was silently failing with a 403. Switched to OAuth user credentials stored in Secret Manager, mounted into Cloud Run as a JSON secret.

---

## Accomplishments We Are Proud Of

- Built a working two-stage retrieval pipeline (vector search + Gemini reranker) that returns genuinely relevant results for all 3 demo queries
- PLAN mode creates real Google Docs with formatted content and hyperlinked citations, not just text output
- Noise filter keeps Discord data useful without manual curation
- All 3 demo queries pass consistency testing with correct mode classification and 2-3 high-quality citations every time
- Deployed end-to-end: Cloud Run backend, Vercel frontend, MongoDB Atlas, all wired together with real org data

---

## What We Learned

Retrieval quality is everything. A RAG system is only as good as the chunks it retrieves, and chunking strategy matters more than model choice. Splitting meeting notes by date header and event docs by heading (`##`) made a measurable difference in reranker scores versus naive paragraph splitting.

Metadata-aware pre-filtering is underrated. Adding doc_type, event_name, and semester filters to every chunk and using them as MongoDB pre-filters reduced noise in results dramatically, especially for the ANALYZE query which needs to distinguish Fall 2025 from Spring 2026 data.

---

## What's Next

progsu Intelligence Agent is a template, not a one-off. Every ACM chapter, GDSC, IEEE club, and independent student org faces the exact same problem: institutional knowledge that disappears when leadership graduates. The pipeline is generalizable. Swap the Drive folder ID and Discord server, and the agent works for any org.

Near-term: let incoming exec board members query two years of history before their first meeting. Long-term: a hosted version any student org can connect to their own Drive and Discord in under an hour.

---

## Built With

gemini-api, google-cloud-agent-builder, vertex-ai, mongodb-atlas, mongodb-mcp-server, google-drive-api, google-docs-api, fastapi, cloud-run, react, typescript, vite, python

---

## Live Demo

- Frontend: https://frontend-coral-mu-47.vercel.app
- Backend (health check): https://progsu-agent-346432646798.us-central1.run.app/health

---

## Demo Video

[3-minute walkthrough following DEMO_SCRIPT.md]

---

## Notes for Submission

- Open source: MIT license
- GitHub: [make repo public before submitting]
- The "Built With" tags above should be entered as individual tags on Devpost
- Project thumbnail: screenshot of the chat UI with a citation card open
- Team: solo submission
