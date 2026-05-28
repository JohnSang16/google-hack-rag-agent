# Epic: React Frontend
**Session:** 5
**Status:** NOT STARTED
**Goal:** Clean chat UI with mode badges, citations, streaming, and Google Doc link.

---

## Context For Agents
A Vite + React + TypeScript single page app that talks to the FastAPI backend at /chat.
Clean and minimal. Mode is color coded (blue=RECALL, purple=ANALYZE, green=PLAN).
Citations render as cards with source name, date, and a Drive link if available.
PLAN mode shows a clickable link to the created Google Doc.

**Backend response shape to build against:**
```typescript
{
  mode: "RECALL" | "ANALYZE" | "PLAN",
  answer: string,
  citations: Array<{
    source_name: string,
    date: string,
    drive_link?: string,
    rerank_score: number
  }>,
  created_doc_url?: string
}
```

**Backend runs at:** `http://localhost:8000/chat`

---

## Features

### Feature 1: Project Scaffold
**Owner:** Dev Agent

#### Tasks
- [ ] Scaffold Vite + React + TypeScript in `src/frontend/`
- [ ] Install dependencies: axios for API calls, nothing else unless needed
- [ ] Set up proxy in vite.config.ts pointing /chat to localhost:8000
- [ ] Create base App.tsx that renders ChatInterface

---

### Feature 2: Chat Interface
**Owner:** Dev Agent
**File:** `src/frontend/src/components/ChatInterface.tsx`

#### Stories
- As an org leader I want a clean chat interface so that I can ask questions naturally
  without needing to understand the underlying system

#### Tasks
- [ ] Full page chat layout with message history at top, input at bottom
- [ ] Manage messages state: array of `{ role: "user" | "agent", content, mode?, citations?, created_doc_url? }`
- [ ] On submit: add user message, call POST /chat, add agent response
- [ ] Show loading indicator while waiting for response
- [ ] Auto scroll to latest message
- [ ] Handle API errors gracefully with an inline error message

---

### Feature 3: Message Bubble
**Owner:** Dev Agent
**File:** `src/frontend/src/components/MessageBubble.tsx`

#### Stories
- As a user I want to clearly distinguish my messages from agent responses
  so that the conversation is easy to follow

#### Tasks
- [ ] User messages: right aligned, solid background
- [ ] Agent messages: left aligned, light background
- [ ] Agent messages show mode badge (blue RECALL, purple ANALYZE, green PLAN)
- [ ] Agent messages render answer text with basic markdown support (bold, lists)
- [ ] If created_doc_url is present show a prominent "View Google Doc" button below the answer

---

### Feature 4: Mode Legend
**Owner:** Dev Agent
**File:** `src/frontend/src/components/ModeSelector.tsx`

**Note:** Mode is classified automatically by the agent  -  users do not pick it manually.
The three mode labels are shown here as a legend so users understand what each badge means
before they start chatting. No toggle, no override, no POST /chat field needed.

#### Stories
- As a new user I want to understand what RECALL, ANALYZE, and PLAN mean
  so that I know what to expect from different types of questions

#### Tasks
- [ ] Render three static color-coded chips: RECALL (blue), ANALYZE (purple), PLAN (green)
- [ ] Each chip has a one-line tooltip: what kind of question triggers this mode
      RECALL: "What happened, what was decided"
      ANALYZE: "Trends, comparisons, growth over time"
      PLAN: "Draft a doc, plan an event  -  creates a Google Doc"
- [ ] No toggle state, no click handler, no POST /chat field
- [ ] Position above the chat input as a passive reference strip

---

### Feature 5: Citation Card
**Owner:** Dev Agent
**File:** `src/frontend/src/components/CitationCard.tsx`

#### Stories
- As a user I want to see where the agent's answer came from
  so that I can verify information and read the original source

#### Tasks
- [ ] Render below each agent message
- [ ] Show: source_name, formatted date, relevance indicator based on rerank_score
- [ ] If drive_link is present make source_name a clickable link opening in new tab
- [ ] If multiple citations collapse them under a "Sources (3)" expandable section
- [ ] Keep cards compact  -  this is supporting info not the main content

---

### Feature 6: Streaming Response Display
**Owner:** Dev Agent

#### Stories
- As a user I want to see the agent's response appear progressively
  so that the UI feels responsive and I do not stare at a blank screen

#### Tasks
- [ ] Check if FastAPI backend supports streaming (Server Sent Events or chunked transfer)
- [ ] If backend supports streaming: implement progressive text display in MessageBubble
- [ ] If backend does not support streaming: implement a typing indicator animation
  while waiting then render the full response at once
- [ ] Do not block citation rendering waiting for streaming to complete

---

## QA Checklist (QA Agent)
- [ ] All 3 demo queries work end to end through the UI without errors
- [ ] Mode badges render correctly for each query type
- [ ] Citations render with source names and dates
- [ ] PLAN mode shows a working Google Doc link
- [ ] UI is usable on a 1280px wide browser window
- [ ] No console errors during a normal demo flow
- [ ] Loading state is visible and the app does not appear frozen during API calls

---

## Definition of Done
All 3 demo queries work end to end through the UI.
Mode badges, citations, and Google Doc link all render correctly.

---

## Handoff To Session 6
Confirm before Session 6 starts:
- Frontend running at localhost:5173
- All 3 demo queries work through the UI
- No console errors during demo flow
- UI looks clean enough to screen record for the demo video
