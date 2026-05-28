# Judging Alignment

Every build decision maps back to these four criteria. When in doubt about what to prioritize, refer here.

---

## Criterion 1: Technological Implementation
"Does the interaction with Google Cloud and Partner services demonstrate quality software development?"

### Required to Score Here

**Google Cloud (must use all three):**
- Gemini API: `gemini-2.0-flash` for generation, classification, reranking, noise filter. `text-embedding-004` for embeddings.
- Google Cloud Agent Builder (Vertex AI Agent Engine): the agent is DEPLOYED here, not just running locally. This is what "Google Cloud" means to judges.
- Google Drive API: both for ingestion AND for the PLAN mode doc creation action.

**MongoDB (partner track requirement):**
- MongoDB Atlas with Atlas Vector Search: all chunks live here
- MongoDB MCP Server: the agent calls the database through MCP. This is the integration point judges check.

**Quality signals that impress technical judges:**
- Metadata pre-filtering before vector search (shows you understand MongoDB's compound index)
- Two-stage retrieval (vector search → reranker) shows pipeline sophistication
- Noise filter pass rate logged and visible (shows you thought about data quality)
- Async ingestion pipeline (shows production-quality thinking)
- Type hints and error handling throughout

### What Would Hurt Here
- Running the agent locally without Agent Builder deployment
- Not using the MongoDB MCP server (just querying Atlas directly from Python)
- No error handling on API calls
- Hardcoded credentials

---

## Criterion 2: Design
"Is the user experience and design of the project well thought out?"

### Required to Score Here

**Interface elements that show intentional design:**
- Mode badge on every response (RECALL / ANALYZE / PLAN)  -  tells the user what the agent is doing
- Citation cards under every answer  -  source title, date, clickable Drive link
- Streaming answer text  -  shows the agent is "thinking"
- Google Doc link that appears after PLAN mode  -  a tangible artifact the user can touch
- Empty state with suggested example queries  -  lowers the onboarding barrier

**What "well thought out" means to judges:**
- The UI has opinions. It doesn't just have a generic chat box.
- Every element serves a function. Mode badges tell users what to expect. Citations prove grounding. The PLAN action shows the agent did something real.
- It's demonstrably designed for a specific user (a student org Technical Director), not a generic user.

### What Would Hurt Here
- Generic chat interface with no mode indicator
- Answers with no citations (feels hallucinated even if it isn't)
- No visual difference between RECALL and PLAN responses
- The Google Doc creation happening silently with no UI feedback

---

## Criterion 3: Potential Impact
"How big of an impact could the project have on target communities?"

### The Pitch

**Primary community:** Student tech org leaders
- Thousands of ACM chapters, IEEE clubs, GDSCs, independent orgs nationally
- Every one has: a Google Drive, a Discord, leadership turnover every 1-2 years, institutional knowledge loss
- The problem is universal and recurring

**Secondary community:** Any small org with institutional knowledge problems
- The pipeline is generalizable  -  swap the Drive folder ID and the agent works for any org
- This is a template, not a one-off

**Quantified impact in your case:**
- progsu: $15k+ in sponsors secured, $5k in prizes distributed, 400+ attendees, Claude Code workshop with 200+ attendees
- Without this agent: the playbook for running a $15k hackathon lives in John's head and scattered docs
- With this agent: the next Technical Director has instant access to every decision, every vendor negotiation, every lesson learned

**How to communicate this to judges:**
- The demo close explicitly names the target community
- The Devpost submission description opens with the community problem, not the tech stack
- The README quantifies: "Built on 1 year of real organizational data from a student tech org that ran a $20k-sponsored hackathon"

### What Would Hurt Here
- Framing it as "a personal tool for one org"  -  too narrow
- Not naming the target community in the demo close
- No quantification of the problem or scale

---

## Criterion 4: Quality of the Idea
"How creative and unique is the project?"

### What Makes This Not a Generic RAG Demo

Most RAG demos:
1. Load a PDF
2. Ask a question
3. Get an answer

This agent:
1. Ingests multiple heterogeneous data sources (structured Drive docs + messy Discord)
2. Applies a noise filter to clean Discord data before storage
3. Uses metadata-aware retrieval to find temporally and categorically relevant chunks
4. Reranks results for actual query relevance
5. Classifies query intent and adapts behavior (not just retrieval)
6. Takes an action  -  creates a real Google Doc that a user can use immediately

**The framing:**
"Org OS"  -  the idea that every org's accumulated knowledge becomes an intelligence layer that survives leadership turnover. This is a memorable concept with a clear problem statement.

**The differentiator judges will remember:**
The noise filter on Discord data. Handling messy conversational data well is hard. Most teams don't try. This team built a Gemini-powered filter that scores every Discord message before storage. Judges from MongoDB and Google understand why that's technically meaningful.

### One-Paragraph Pitch for Devpost

"Student tech orgs run on Google Drive and Discord. Decisions get buried in threads. Event playbooks live in documents that only the current leadership knows exist. When people graduate, the knowledge graduates with them. progsu Intelligence Agent ingests a year of real organizational data  -  meeting notes, event logistics, sponsor outreach, Discord decisions, financial records  -  and makes it instantly queryable. Ask what challenges came up at the last hackathon. Ask how attendance has grown. Ask the agent to draft a planning brief for the next event, and watch it create a real Google Doc from everything it learned. Built on Gemini, Google Cloud Agent Builder, and MongoDB Atlas. Designed for any student tech org that wants their history to work for them."
