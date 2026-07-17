import asyncio
import json
import logging
import re
import os
from typing import Optional

from google import genai
from dotenv import load_dotenv

from src.access import Access, legacy_default
from src.org_config import cfg_dict, cfg_list
from src.agent.mode_classifier import classify_intent, _is_chat as _is_chat_query
from src.agent.tools.retrieve import retrieve_context, format_context_for_prompt
from src.agent.tools.create_doc import create_google_doc
from src.agent.tools.create_calendar_event import create_calendar_event
from src.agent.tools.send_gmail import (
    create_gmail_draft,
    send_gmail_draft,
    build_plan_email_body,
    is_send_to_email_intent,
)

load_dotenv()

logger = logging.getLogger(__name__)

_DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"
_DEMO_DISABLED_MSG = "\n\n---\n*Calendar and email features are not available in this demo.*"

# Org-specific phrase filters and event mappings live in org_config.json
# (private, gitignored), not in public source.
_SENSITIVE_PHRASES = tuple(cfg_list("sensitive_phrases"))


# Financial data guard. A doc_type filter alone is not enough: dollar figures
# mentioned casually inside ordinary Discord or meeting-note chunks are never
# tagged financial, so chunk text is scanned too. Chunk filtering applies only
# in DEMO_MODE (unauthenticated public deployment); the full club deployment
# keeps financial context and the prompt adds an internal-figures caveat.
_FINANCIAL_KEYWORDS = (
    "budget", "expense", "cost", "invoice", "receipt", "bookkeeping",
    "sponsor amount", "dollars", "payment", "reimbursement",
)
_DOLLAR_RE = re.compile(r"\$\s?\d")

_FINANCIAL_RESTRICTED_MSG = "Detailed financial records are restricted in this demo. Ask your exec board directly."

_FINANCIAL_QUERY_TERMS = (
    "budget", "expense", "cost", "invoice", "receipt", "bookkeeping",
    "revenue", "spent", "spend", "paid", "money", "dollar",
)


def _is_financial_chunk(chunk: dict) -> bool:
    if chunk.get("metadata", {}).get("doc_type") == "financial":
        return True
    text_lower = chunk.get("text", "").lower()
    if _DOLLAR_RE.search(text_lower):
        return True
    return any(k in text_lower for k in _FINANCIAL_KEYWORDS)


def _is_financial_query(query: str) -> bool:
    q = query.lower()
    return bool(_DOLLAR_RE.search(q)) or any(t in q for t in _FINANCIAL_QUERY_TERMS)


def _filter_sensitive_chunks(chunks: list[dict], restrict_financial: Optional[bool] = None) -> list[dict]:
    """Drop chunks that contain sensitive internal political content, and any
    chunk carrying financial data when the caller's access restricts it."""
    if restrict_financial is None:
        restrict_financial = _DEMO_MODE
    safe = []
    for c in chunks:
        text_lower = c.get("text", "").lower()
        if any(phrase in text_lower for phrase in _SENSITIVE_PHRASES):
            logger.info("Filtered sensitive chunk: %s", c.get("metadata", {}).get("file_title", "unknown"))
            continue
        if restrict_financial and _is_financial_chunk(c):
            logger.info("Filtered financial chunk (restricted access): %s", c.get("metadata", {}).get("file_title", "unknown"))
            continue
        safe.append(c)
    return safe


_FINANCIAL_RULE_RESTRICTED = (
    "- **Never output specific dollar amounts, budgets, sponsorship totals, or any financial figures**, "
    "even if present in retrieved context. If asked for financial details, say detailed financial records "
    "are restricted and to ask the exec board directly."
)
_FINANCIAL_RULE_INTERNAL = (
    "- Financial figures from context are internal. When outputting specific dollar amounts, "
    "note that they are internal figures not for external sharing."
)

_PLAN_GATED_MSG = (
    "PLAN mode (creating docs and calendar events) requires exec access. "
    "Ask an exec board member to run this, or try a RECALL or ANALYZE question instead."
)

_STREAM_ANSWER_PROMPT = """You are the institutional memory of progsu, a student tech org at Georgia State University. You have deep knowledge of every event, meeting, decision, financial detail, and team dynamic in the org's history. You think and speak like a senior member who has been here since day one, knowledgeable, direct, and genuinely invested in the org's success.

Mode: {mode}

Response rules. Apply to every answer:
- Open with 1-2 sentences that directly answer the question. No preamble, no "great question."
- Then unpack the detail using bullets or short paragraphs. Summary before depth, always.
- Keep language plain and conversational. A new member should be able to follow it.
- Never pad. If 3 bullets cover it, don't write 3 paragraphs.
- Consolidate closely related points into one bullet.
- Attribute decisions to the team or role, not individual first names from meeting notes.
- **Never name external individuals (people outside progsu leadership) by name, especially in conflict, resistance, or institutional politics contexts.** Use "a university stakeholder", "an external party", or "university administration" instead.
- **Never output phone numbers, email addresses, or raw personal contact information**, even if present in retrieved context. Say the information is not available for privacy reasons if asked directly.
- The first Hacklanta event (Spring 2026) is Hacklanta 1. Any future hackathon is Hacklanta II.
- **HARD FACT: Hacklanta 1 is progsu's first and only hackathon ever. No prior hackathons exist. Never write "historically", "prior hackathons", "past hackathons", or any phrase implying earlier hackathons.**
- **Never invent numbers or attendance figures.** Only use numbers verbatim from the retrieved context.
{financial_rule}

Mode-specific output:
- RECALL: Be specific and concrete. Make challenges feel real before explaining how they were addressed.
- ANALYZE: Lead with the trend in 1-2 sentences. Follow with a markdown table with exactly 2 columns: Event or Period, and the key number. Use ONLY 3-dash separators like |:---|:---|. One line per cell, no extra columns, no notes column. Close with a 2-3 sentence narrative.
- PLAN: Write a full structured document with ## section headings. Every section must be actionable. Ground every recommendation in real org history. Do NOT include draft emails, email templates, or outreach copy in the document body.

{history_section}Retrieved context:
{context}

User query: {query}

Output your response in markdown format only. Do not wrap in JSON. Do not add citation markers."""

_STREAM_NO_CONTEXT_PROMPT = """You are the institutional memory of progsu. Nothing relevant came up for this query.

User query: {query}

Respond: I don't have anything on that in the org's records. Try asking about a specific event, meeting, or decision. I know Hacklanta, the Claude Workshop, our attendance growth, exec meetings, sponsorship strategy, and more."""

_CHAT_PROMPT = """You are the progsu Intelligence Agent, the institutional memory of progsu (ProgClub at Georgia State University).

The user is asking something conversational or about what you can do. Respond naturally and helpfully.

If they ask for example questions or prompts, return exactly this and nothing else:
Here are three good ones to start with:

- "What were the key logistics challenges at Hacklanta?"
- "How has our event attendance grown over time?"
- "Draft a planning brief for our next major hackathon."

Otherwise respond in 1-3 sentences. You operate in three modes: RECALL (what happened), ANALYZE (trends), PLAN (creates a Google Doc).

User: {query}

Respond with plain text only. No JSON, no markdown fences."""


def _normalize_table_separators(text: str) -> str:
    """Collapse long markdown table separator cells to 3 dashes so they don't eat token budget."""
    def _shorten(m: re.Match) -> str:
        return re.sub(r':?-{4,}:?', '---', m.group(0))
    return re.sub(r'^\|[\s:|-]+\|?$', _shorten, text, flags=re.MULTILINE)


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def _enrich_citations(citations: list[dict], chunks: list[dict]) -> list[dict]:
    """Add source URLs and display metadata to each citation."""
    by_file_id: dict[str, dict] = {}
    by_title: dict[str, dict] = {}
    for c in chunks:
        meta = c.get("metadata", {})
        fid = meta.get("file_id", "")
        title = meta.get("file_title", "")
        if fid:
            by_file_id[fid] = meta
        if title:
            by_title[title.lower()] = meta

    enriched = []
    for cite in citations:
        file_id = cite.get("file_id", "")
        title = cite.get("title", "")
        meta = by_file_id.get(file_id) or by_title.get(title.lower()) or {}
        resolved_fid = file_id or meta.get("file_id", "")
        source_type = meta.get("source_type", "google_drive")
        enriched.append({
            "title": cite.get("title") or meta.get("file_title", "Unknown"),
            "date": cite.get("date") or meta.get("date"),
            "file_id": resolved_fid,
            "source_type": source_type,
            "drive_url": (
                f"https://drive.google.com/file/d/{resolved_fid}/view"
                if resolved_fid and source_type != "discord"
                else None
            ),
            "discord_url": meta.get("discord_url"),
            "messages": meta.get("messages"),
            "relevance_score": cite.get("relevance_score", 0),
        })
    return enriched


_PLAN_INTENT_RE = re.compile(
    r'\b(draft|write\s+a|create\s+a|make\s+a|plan\s+for|planning\s+brief|proposal|template)\b',
    re.IGNORECASE,
)


async def _rewrite_query_for_retrieval(query: str, history: list[dict], client: genai.Client) -> str:
    """Rewrite a vague follow-up query into a self-contained search query using conversation history."""
    if not history or len(query.split()) > 12:
        return query
    # Preserve explicit planning intent — rewriting strips PLAN keywords and breaks classification
    if _PLAN_INTENT_RE.search(query):
        return query
    last_user = next((h["content"] for h in reversed(history) if h["role"] == "user"), "")
    if not last_user:
        return query
    prompt = (
        f"Given this conversation, rewrite the follow-up as a single self-contained ANALYTICAL "
        f"search query for a document retrieval system. The query must retrieve factual records. "
        f"do NOT add words like 'plan', 'strategy', 'improve', 'how to', or any action-oriented "
        f"language. Strip meta-questions about sources or methodology. "
        f"Output only the rewritten query, nothing else.\n\n"
        f"Previous message: {last_user}\n"
        f"Follow-up: {query}\n\n"
        f"Rewritten search query:"
    )
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(temperature=0.0, max_output_tokens=80),
        )
        rewritten = response.text.strip()
        logger.info("Query rewritten for retrieval: '%s' -> '%s'", query[:60], rewritten[:60])
        return rewritten
    except Exception:
        return query


def _build_history_section(history: list[dict]) -> str:
    """Format last N conversation turns for injection into the prompt."""
    if not history:
        return ""
    lines = ["Conversation history (use this to understand what the current query is about):"]
    for turn in history[-4:]:  # max 4 entries = 2 back-and-forth turns
        role = turn.get("role", "")
        content = str(turn.get("content", ""))[:400]  # truncate long answers
        if role == "user":
            lines.append(f"User: {content}")
        elif role == "agent":
            lines.append(f"Agent: {content}")
    return "\n".join(lines) + "\n\n"


_ANALYZE_PLAN_KEYWORDS = {
    "trend", "trends", "growth", "compare", "comparison", "over time",
    "how has", "how have", "draft", "plan", "planning", "brief", "proposal",
    "analyze", "analysis", "attendance", "metrics", "semester", "fall", "spring",
}

# Fields the Atlas vector index accepts as pre-filters (matches metadata.* paths in vector_index)
_VECTOR_FILTER_KEYS = frozenset({"event_name", "semester", "doc_type", "team", "source_type", "date"})

# Maps query keywords → event_name values stored in metadata
_EVENT_KEYWORD_MAP = cfg_dict("event_keyword_map")


def _extract_event_filter(query: str) -> dict:
    """Return {"event_name": <value>} if a known event is mentioned, else {}."""
    q = query.lower()
    for keyword, event_name in _EVENT_KEYWORD_MAP.items():
        if keyword in q:
            return {"event_name": event_name}
    return {}


def _build_retrieval_filters(query: str, request_filters: Optional[dict]) -> Optional[dict]:
    """
    Compose vector search filters from the query + validated request fields.
    Strips non-vector fields like gmail_draft_id that would silently kill results.
    """
    result: dict = {}
    result.update(_extract_event_filter(query))
    if request_filters:
        for k, v in request_filters.items():
            if k in _VECTOR_FILTER_KEYS and v is not None:
                result[k] = v
    return result if result else None


def _estimate_top_k(query: str) -> int:
    """Return top_k=10 for complex/analytical queries, 5 for simple recall."""
    q = query.lower()
    if any(kw in q for kw in _ANALYZE_PLAN_KEYWORDS):
        return 10
    if len(query.split()) >= 12:
        return 10
    return 5


_OUTREACH_EMAIL_PROMPT = """You are writing a short sponsor outreach email on behalf of progsu, the largest student tech org at Georgia State University.

Recipient context: {recipient_context}
Planning doc link (include if not empty): {doc_url}

Planning brief to draw from:
{plan_content}

Output exactly this format, nothing else:
Subject: <subject line>

<email body>

Rules:
- 2 short paragraphs, under 100 words total in the body
- First paragraph: one sentence on what Hacklanta II is and why it matters
- Second paragraph: one sentence on what sponsorship enables, one sentence CTA
- If doc_url is not empty, add exactly this as a third line: "Full planning brief: <url>"
- Sign off: progsu Leadership Team
- Address as "Hi," with no name
- No flattery, no "we are thrilled", no filler. Direct and confident.
- Never use em dashes (--) or en dashes. Use commas or periods instead.
- Plain text only"""

_CLARIFICATION_ANSWER = (
    "That's not enough for me to search the org's records. "
    "Try asking about a specific event, meeting, or decision.\n\n"
    "**Examples:**\n"
    "- \"What were the key challenges at Hacklanta?\"\n"
    "- \"How has our event attendance grown from Fall 2025 to Spring 2026?\"\n"
    "- \"Draft a planning brief for our next major hackathon.\""
)


def _is_meaningful_query(query: str) -> bool:
    """Return False if the query is too short, symbol-only, or lacks enough alphanumeric content."""
    stripped = query.strip()
    # Need at least 5 alphanumeric characters total
    if sum(1 for c in stripped if c.isalnum()) < 5:
        return False
    # Need at least 2 words that contain alphanumeric characters
    words = [w for w in stripped.split() if any(c.isalnum() for c in w)]
    if len(words) < 2:
        return False
    return True


_GROUNDING_PROMPT = """You are a fact-checker. Given a retrieved context and a generated answer, identify any specific factual claims in the answer that are NOT supported by the context.

Context:
{context}

Answer to check:
{answer}

Respond with JSON only:
{{
  "grounded": true | false,
  "unsupported_claims": ["<claim1>", "<claim2>"]
}}

"grounded" is true if every specific factual claim in the answer can be traced to the context. "unsupported_claims" lists any sentences or phrases that cannot."""

_GROUNDING_DISCLAIMER = "\n\n*Note: some details in this response could not be fully verified against the source documents. Treat with caution.*"


async def _check_grounding(query: str, answer: str, context: str, client: genai.Client) -> str:
    """Run a fast grounding check. Appends a disclaimer if unsupported claims are found."""
    prompt = _GROUNDING_PROMPT.format(context=context[:3000], answer=answer[:2000])
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
                max_output_tokens=256,
            ),
        )
        data = json.loads(response.text.strip())
        if not data.get("grounded", True):
            claims = data.get("unsupported_claims", [])
            logger.warning("Grounding check failed — unsupported claims: %s", claims)
            return answer + _GROUNDING_DISCLAIMER
    except Exception as e:
        logger.warning("Grounding check skipped: %s", e)
    return answer


async def run(
    query: str,
    filters: Optional[dict] = None,
    history: Optional[list[dict]] = None,
    client: genai.Client = None,
    access: Optional[Access] = None,
) -> dict:
    """
    Non-streaming pipeline: a thin consumer of run_stream, so there is exactly
    one pipeline implementation. Collects the streamed events and returns the
    final result dict (mode, answer, summary, citations, created_doc_url, and
    any PLAN artifact fields from the done event).
    """
    result: dict = {"mode": "RECALL", "answer": "", "summary": None, "citations": [], "created_doc_url": None}
    tokens: list[str] = []
    async for event in run_stream(query, filters=filters, history=history, client=client, access=access):
        if event.get("type") == "token":
            tokens.append(event.get("content", ""))
        elif event.get("type") == "done":
            result = {k: v for k, v in event.items() if k != "type"}
    if not result.get("answer"):
        result["answer"] = "".join(tokens)
    return result



_LOW_CONFIDENCE_THRESHOLD = 5


async def run_stream(
    query: str,
    filters: Optional[dict] = None,
    history: Optional[list[dict]] = None,
    client: genai.Client = None,
    access: Optional[Access] = None,
):
    """
    Streaming pipeline. Yields SSE event dicts:
      {type: "mode", mode: str}
      {type: "token", content: str}
      {type: "done", mode, answer, citations, created_doc_url, summary}
    access carries the caller's tier capabilities; None falls back to the
    deployment-wide DEMO_MODE behavior.
    """
    if client is None:
        client = _get_client()
    if access is None:
        access = legacy_default()

    if not _is_meaningful_query(query):
        yield {"type": "mode", "mode": "RECALL"}
        yield {"type": "token", "content": _CLARIFICATION_ANSWER}
        yield {"type": "done", "mode": "RECALL", "answer": _CLARIFICATION_ANSWER, "citations": [], "created_doc_url": None, "summary": None}
        return

    # Explicit send-to-email intent: "send this to the sponsor email"
    # Skip if the query also has drafting intent (e.g. "draft a brief and email sponsors")
    # Those belong in the PLAN path, which handles email via wants_email.
    if is_send_to_email_intent(query) and not _PLAN_INTENT_RE.search(query):
        yield {"type": "mode", "mode": "CHAT"}
        # Find the most recent PLAN brief in history (identified by ## headers + length)
        plan_content = None
        for h in reversed(history or []):
            if h.get("role") == "agent":
                c = h.get("content", "")
                if "##" in c and len(c) > 200:
                    plan_content = c
                    break
        # Fallback: longest agent turn
        if not plan_content:
            agent_turns = [h.get("content", "") for h in (history or []) if h.get("role") == "agent"]
            plan_content = max(agent_turns, key=len) if agent_turns else None

        plan_doc_url = (filters or {}).get("plan_doc_url", "")
        if plan_content:
            if not access.can_gmail_send:
                msg = "Email sending is not available at your access level."
                yield {"type": "token", "content": msg}
                yield {"type": "done", "mode": "CHAT", "answer": msg, "citations": [], "created_doc_url": None, "summary": None, "gmail_draft_id": None, "gmail_draft_url": None, "calendar_event_url": None, "calendar_event_id": None, "calendar_event_start_date": None}
                return
            try:
                # Use Gemini to write a proper outreach email
                email_prompt = _OUTREACH_EMAIL_PROMPT.format(
                    recipient_context=query,
                    doc_url=plan_doc_url or "",
                    plan_content=plan_content[:3000],
                )
                email_response = await asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-2.5-flash",
                    contents=email_prompt,
                    config=genai.types.GenerateContentConfig(temperature=0.3, max_output_tokens=2048),
                )
                raw_email = email_response.text.strip()
                # Parse subject from first line
                lines = raw_email.split("\n", 2)
                if lines[0].lower().startswith("subject:"):
                    email_subject = lines[0][8:].strip()
                    email_body = "\n".join(lines[1:]).lstrip("\n")
                else:
                    email_subject = "[progsu] Planning Brief"
                    email_body = raw_email

                draft_result = await asyncio.to_thread(create_gmail_draft, subject=email_subject, body=email_body)
                draft_id = draft_result.get("draft_id")
                await asyncio.to_thread(send_gmail_draft, draft_id)
                msg = f"Done. Email sent to sponsors.\n\n**Subject:** {email_subject}"
            except Exception as e:
                logger.error("Send-to-email failed: %s", e)
                msg = f"Could not send the email: {e}"
        else:
            msg = "I don't have a recent plan to send. Draft a planning brief first, then ask me to send it."
        yield {"type": "token", "content": msg}
        yield {"type": "done", "mode": "CHAT", "answer": msg, "citations": [], "created_doc_url": None, "summary": None, "gmail_draft_id": None, "gmail_draft_url": None, "calendar_event_url": None, "calendar_event_id": None, "calendar_event_start_date": None}
        return

    # Fast CHAT path via regex (no retrieval needed)
    if _is_chat_query(query):
        full = ""
        yield {"type": "mode", "mode": "CHAT"}
        try:
            async for chunk in await client.aio.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=_CHAT_PROMPT.format(query=query),
                config=genai.types.GenerateContentConfig(temperature=0.7, max_output_tokens=512),
            ):
                if chunk.text:
                    full += chunk.text
                    yield {"type": "token", "content": chunk.text}
        except Exception as e:
            logger.error("CHAT stream failed: %s", e)
            msg = "Try asking about Hacklanta, our attendance growth, or planning a hackathon."
            full = msg
            yield {"type": "token", "content": msg}
        yield {"type": "done", "mode": "CHAT", "answer": full, "citations": [], "created_doc_url": None, "summary": None}
        return

    # Financial queries get a canned response for restricted tiers; no retrieval spend
    if not access.financial_access and _is_financial_query(query):
        logger.info("Financial query blocked with canned response (tier: %s)", access.tier)
        yield {"type": "mode", "mode": "RECALL"}
        yield {"type": "token", "content": _FINANCIAL_RESTRICTED_MSG}
        yield {"type": "done", "mode": "RECALL", "answer": _FINANCIAL_RESTRICTED_MSG, "citations": [], "created_doc_url": None, "summary": None}
        return

    # Parallel: classify intent + retrieve
    retrieval_query = await _rewrite_query_for_retrieval(query, history or [], client)
    top_k = _estimate_top_k(retrieval_query)
    retrieval_filters = _build_retrieval_filters(retrieval_query, filters)
    intent, chunks = await asyncio.gather(
        asyncio.to_thread(classify_intent, retrieval_query, client),
        retrieve_context(retrieval_query, filters=retrieval_filters, top_k=top_k, gemini_client=client),
    )
    mode = intent["mode"]

    # Fallback: if event-filtered retrieval returned nothing, retry without filter
    if not chunks and retrieval_filters:
        logger.info("Event-filtered retrieval returned 0 chunks; retrying without filter")
        chunks = await retrieve_context(retrieval_query, filters=None, top_k=top_k, gemini_client=client)

    if mode == "CHAT":
        yield {"type": "mode", "mode": "CHAT"}
        msg = "Ask me about Hacklanta, our attendance growth, or draft a planning doc."
        yield {"type": "token", "content": msg}
        yield {"type": "done", "mode": "CHAT", "answer": msg, "citations": [], "created_doc_url": None, "summary": None}
        return

    yield {"type": "mode", "mode": mode}

    # PLAN creates real Drive docs and calendar events; exec tier and up only
    if mode == "PLAN" and not access.can_plan:
        logger.info("PLAN mode gated (tier: %s)", access.tier)
        yield {"type": "token", "content": _PLAN_GATED_MSG}
        yield {"type": "done", "mode": "PLAN", "answer": _PLAN_GATED_MSG, "citations": [], "created_doc_url": None, "summary": None}
        return

    # Confidence gate
    if chunks:
        best_score = max(c.get("relevance_score", 0) for c in chunks)
        if best_score < _LOW_CONFIDENCE_THRESHOLD:
            msg = "I don't have enough in the org's records to answer that confidently. Try rephrasing, or ask about a specific event, meeting, or decision."
            yield {"type": "token", "content": msg}
            yield {"type": "done", "mode": mode, "answer": msg, "citations": [], "created_doc_url": None, "summary": None}
            return

    # Build prompt
    chunks = _filter_sensitive_chunks(chunks, restrict_financial=not access.financial_access)
    history_section = _build_history_section(history or [])
    if chunks:
        context_block = format_context_for_prompt(chunks)
        prompt = _STREAM_ANSWER_PROMPT.format(
            mode=mode, query=query, context=context_block, history_section=history_section,
            financial_rule=_FINANCIAL_RULE_INTERNAL if access.financial_access else _FINANCIAL_RULE_RESTRICTED,
        )
    else:
        prompt = _STREAM_NO_CONTEXT_PROMPT.format(query=query)

    # Stream answer with gemini-2.5-flash
    # thinking_budget caps how many tokens the model spends reasoning before writing;
    # without it, thinking eats into max_output_tokens and truncates the response.
    full_answer = ""
    max_tokens = 16384 if mode == "PLAN" else 8192
    thinking_budget = 2048 if mode == "PLAN" else 1024
    try:
        async for chunk in await client.aio.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=max_tokens,
                thinking_config=genai.types.ThinkingConfig(thinking_budget=thinking_budget),
            ),
        ):
            if chunk.text:
                full_answer += chunk.text
                yield {"type": "token", "content": chunk.text}
    except Exception as e:
        logger.error("Answer stream failed: %s", e)
        full_answer = "An error occurred while generating a response."
        yield {"type": "token", "content": full_answer}

    # Normalize any absurdly long table separators Gemini may have generated
    full_answer = _normalize_table_separators(full_answer)

    # Grounding check (PLAN only, too expensive per-query). Tokens already
    # streamed, so a failed check appends the disclaimer as one final token
    # event; the done event carries the corrected full answer.
    if mode == "PLAN" and chunks and full_answer and "error" not in full_answer.lower():
        checked = await _check_grounding(query, full_answer, format_context_for_prompt(chunks), client)
        if checked != full_answer:
            yield {"type": "token", "content": _GROUNDING_DISCLAIMER}
            full_answer = checked

    # Build citations from retrieved chunks directly
    raw = [
        {
            "title": c.get("metadata", {}).get("file_title", "Unknown"),
            "date": c.get("metadata", {}).get("date"),
            "file_id": c.get("metadata", {}).get("file_id", ""),
            "relevance_score": c.get("relevance_score", 0),
        }
        for c in chunks
    ]
    citations = _enrich_citations(raw, chunks)

    # PLAN mode: extract summary + create all three artifacts in parallel
    created_doc_url = None
    calendar_event_url = None
    calendar_event_id = None
    calendar_event_start_date = None
    gmail_draft_id = None
    gmail_draft_url = None
    summary = None

    if mode == "PLAN" and full_answer and "error" not in full_answer.lower():
        paras = [p.strip() for p in full_answer.split("\n\n") if p.strip() and not p.startswith("#")]
        summary = paras[0][:200] if paras else full_answer[:200]

        # Action intent comes from the structured classifier, never keyword
        # sniffing (the word "sponsor" alone used to auto-send a real email)
        wants_calendar = intent["wants_calendar"]
        wants_email = intent["wants_email"]

        try:
            created_doc_url = await asyncio.to_thread(create_google_doc, query, full_answer, citations)
        except Exception as e:
            logger.error("Google Doc creation failed: %s", e)

        if wants_calendar:
            if not access.can_calendar:
                logger.info("Calendar event creation skipped (tier: %s)", access.tier)
            else:
                try:
                    heading_match = re.search(r'^#{1,2}\s+(.+)$', full_answer, re.MULTILINE)
                    event_title = f"progsu: {heading_match.group(1).strip()[:60]}" if heading_match else f"progsu: {query[:60].rstrip()}"
                    cal_result = await asyncio.to_thread(
                        create_calendar_event, title=event_title, description=summary, doc_url=created_doc_url
                    )
                    calendar_event_url = cal_result.get("html_link")
                    calendar_event_id = cal_result.get("event_id")
                    calendar_event_start_date = cal_result.get("start_date")
                except Exception as e:
                    logger.error("Calendar event creation failed: %s", e)

        if wants_email and created_doc_url:
            if not access.can_gmail_send:
                logger.info("Gmail draft/send skipped (tier: %s)", access.tier)
            else:
                try:
                    email_prompt = _OUTREACH_EMAIL_PROMPT.format(
                        recipient_context="sponsors",
                        doc_url=created_doc_url,
                        plan_content=full_answer[:3000],
                    )
                    email_response = await asyncio.to_thread(
                        client.models.generate_content,
                        model="gemini-2.5-flash",
                        contents=email_prompt,
                        config=genai.types.GenerateContentConfig(temperature=0.3, max_output_tokens=2048),
                    )
                    raw_email = email_response.text.strip()
                    lines = raw_email.split("\n", 2)
                    if lines[0].lower().startswith("subject:"):
                        email_subject = lines[0][8:].strip()
                        email_body = "\n".join(lines[1:]).lstrip("\n")
                    else:
                        email_subject = "[progsu] Planning Brief"
                        email_body = raw_email
                    draft_result = await asyncio.to_thread(create_gmail_draft, subject=email_subject, body=email_body)
                    draft_id = draft_result.get("draft_id")
                    gmail_draft_url = draft_result.get("draft_url")
                    # Draft only, never auto-send. Sending requires an explicit
                    # confirmation turn ("send it") through the send-intent path,
                    # which is additionally gated to gmail-send capability.
                    logger.info("Gmail draft created (not sent): %s", email_subject)
                except Exception as e:
                    logger.error("Email draft failed: %s", e)

        if (wants_calendar and not access.can_calendar) or (wants_email and created_doc_url and not access.can_gmail_send):
            full_answer += _DEMO_DISABLED_MSG

        logger.info("PLAN artifacts: doc=%s cal=%s email=%s", created_doc_url, calendar_event_url, bool(wants_email))

    # Serialize citations safely
    def _serialize(c: dict) -> dict:
        msgs = c.get("messages")
        if msgs and not isinstance(msgs[0], dict):
            msgs = [m if isinstance(m, dict) else vars(m) for m in msgs]
        return {**c, "messages": msgs}

    yield {
        "type": "done",
        "mode": mode,
        "answer": full_answer,
        "summary": summary,
        "citations": [_serialize(c) for c in citations],
        "created_doc_url": created_doc_url,
        "calendar_event_url": calendar_event_url,
        "calendar_event_id": calendar_event_id,
        "calendar_event_start_date": calendar_event_start_date,
        "gmail_draft_id": gmail_draft_id,
        "gmail_draft_url": gmail_draft_url,
    }
