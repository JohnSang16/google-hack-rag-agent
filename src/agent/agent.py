import asyncio
import json
import logging
import re
import os
from typing import Optional

from google import genai
from dotenv import load_dotenv

from src.agent.mode_classifier import classify_mode
from src.agent.tools.retrieve import retrieve_context, format_context_for_prompt
from src.agent.tools.create_doc import create_google_doc

load_dotenv()

logger = logging.getLogger(__name__)

_ANSWER_PROMPT = """You are the institutional memory of progsu, a student tech org at Georgia State University. You have deep knowledge of every event, meeting, decision, financial detail, and team dynamic in the org's history. You think and speak like a senior member who has been here since day one — knowledgeable, direct, and genuinely invested in the org's success.

Mode: {mode}

Response rules — apply to every answer:
- Open with 1-2 sentences that directly answer the question. No preamble, no "great question."
- Then unpack the detail using bullets or short paragraphs. Summary before depth, always.
- Keep language plain and conversational. A new member should be able to follow it.
- Never pad. If 3 bullets cover it, don't write 3 paragraphs.
- Consolidate closely related points into one bullet. Do not split the same underlying issue into multiple bullets just because the details differ slightly. For example, parking location and parking navigation are one problem, not two.
- Do not let one person's name or role dominate a response. Represent the collective team picture.
- When referencing feedback, assignments, or decisions found in meeting notes, attribute them to the team or role (e.g., "the operations team flagged", "per the tech meeting") rather than by first names of meeting attendees. First names in meeting notes are usually attendees, not decision-makers — do not surface them as the source of authority.
- The first Hacklanta event (Spring 2026) is Hacklanta 1. Any future hackathon being planned is Hacklanta II. Use these names consistently.

Mode-specific output:
- RECALL: Be specific and concrete. What happened, what was decided, what the outcome was. For questions about challenges or problems, describe the actual difficulty and stress involved — make the pain point feel real before explaining how it was addressed.
- ANALYZE: Lead with the pattern or trend in 1-2 sentences. Follow with a markdown table of the key data points. Close with a 2-3 sentence narrative on what it means for the org.
- PLAN: Write a full structured document with ## section headings. Every section must be actionable, not theoretical. Ground every recommendation in what actually worked or failed in Hacklanta 1 or other real org history — make it clear this plan is built on real experience.

{history_section}Retrieved context:
{context}

User query: {query}

Output ONLY valid JSON with this exact structure (no markdown code fences):
{{
  "answer": "<your complete response in markdown>",
  "citations": [
    {{
      "title": "<file_title from source>",
      "date": "<date or null>",
      "file_id": "<file_id from source metadata>",
      "relevance_score": <number 0-10>
    }}
  ]
}}

Use only facts present in the retrieved context. Every specific claim must be attributable to a source. Include only sources you actually drew from."""

_NO_CONTEXT_PROMPT = """You are the institutional memory of progsu, a student tech org at Georgia State University. You know the org's full history — events, meetings, decisions, people, and finances.

Nothing relevant came up in the knowledge base for this query.

User query: {query}

Respond with exactly this JSON:
{{
  "answer": "I don't have anything on that in the org's records. Try asking about a specific event, meeting, or decision — I know Hacklanta, the Claude Workshop, our attendance growth, exec meetings, sponsorship strategy, and more.",
  "citations": []
}}"""

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


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def _parse_response(raw: str) -> tuple[str, list[dict]]:
    """Parse Gemini JSON response. Returns (answer, citations)."""
    text = raw.strip()
    # Strip markdown fences
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    # First try clean parse
    try:
        data = json.loads(text)
        return data.get("answer", raw), data.get("citations", [])
    except json.JSONDecodeError:
        pass

    # Truncated JSON — extract "answer" value with regex and try to salvage citations
    try:
        answer_match = re.search(r'"answer"\s*:\s*"(.*?)(?:"\s*,\s*"citations"|"\s*})', text, re.DOTALL)
        if answer_match:
            answer = answer_match.group(1).encode().decode("unicode_escape", errors="ignore")
        else:
            # Last resort: everything after "answer": "
            answer_match2 = re.search(r'"answer"\s*:\s*"(.+)', text, re.DOTALL)
            answer = answer_match2.group(1).rstrip('"}').strip() if answer_match2 else raw

        citations_match = re.search(r'"citations"\s*:\s*(\[.*?\])', text, re.DOTALL)
        citations: list[dict] = []
        if citations_match:
            try:
                citations = json.loads(citations_match.group(1))
            except json.JSONDecodeError:
                pass

        logger.warning("Recovered from malformed JSON: answer=%d chars, citations=%d", len(answer), len(citations))
        return answer, citations
    except Exception as e:
        logger.warning("Failed to parse JSON response, using raw text: %s", e)
        return raw, []


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


async def _rewrite_query_for_retrieval(query: str, history: list[dict], client: genai.Client) -> str:
    """Rewrite a vague follow-up query into a self-contained search query using conversation history."""
    if not history or len(query.split()) > 12:
        return query
    last_user = next((h["content"] for h in reversed(history) if h["role"] == "user"), "")
    if not last_user:
        return query
    prompt = (
        f"Given this conversation, rewrite the follow-up as a single self-contained search query "
        f"for a document retrieval system. Output only the rewritten query, nothing else.\n\n"
        f"Previous message: {last_user}\n"
        f"Follow-up: {query}\n\n"
        f"Rewritten search query:"
    )
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
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


def _estimate_top_k(query: str) -> int:
    """Return top_k=10 for complex/analytical queries, 5 for simple recall."""
    q = query.lower()
    if any(kw in q for kw in _ANALYZE_PLAN_KEYWORDS):
        return 10
    if len(query.split()) >= 12:
        return 10
    return 5


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
            model="gemini-2.0-flash",
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
) -> dict:
    """
    Full agent pipeline: classify → retrieve → generate → (create doc if PLAN).
    Returns dict with mode, answer, citations, created_doc_url.
    """
    if client is None:
        client = _get_client()

    if not _is_meaningful_query(query):
        return {
            "mode": "RECALL",
            "answer": _CLARIFICATION_ANSWER,
            "citations": [],
            "created_doc_url": None,
        }

    # 1. Classify mode first — determines whether we need retrieval at all
    mode = await asyncio.to_thread(classify_mode, query, client)
    logger.info("Agent mode: %s", mode)

    # CHAT mode: skip retrieval entirely, respond conversationally
    if mode == "CHAT":
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.0-flash",
                contents=_CHAT_PROMPT.format(query=query),
                config=genai.types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=512,
                ),
            )
            answer = response.text.strip()
        except Exception as e:
            logger.error("CHAT response failed: %s", e)
            answer = "Try asking: \"What were the key logistics challenges at Hacklanta?\", \"How has our attendance grown?\", or \"Draft a planning brief for our next hackathon.\""
        return {"mode": "CHAT", "answer": answer, "citations": [], "created_doc_url": None}

    # 2+3. Rewrite retrieval query and retrieve
    retrieval_query = await _rewrite_query_for_retrieval(query, history or [], client)
    top_k = _estimate_top_k(query)
    chunks = await retrieve_context(retrieval_query, filters=filters, top_k=top_k, gemini_client=client)

    # Confidence gate: if best chunk score is too low, don't hallucinate
    _LOW_CONFIDENCE_THRESHOLD = 5
    if chunks:
        best_score = max(c.get("relevance_score", 0) for c in chunks)
        if best_score < _LOW_CONFIDENCE_THRESHOLD:
            logger.info("Low confidence retrieval (best score %s), returning humble response", best_score)
            return {
                "mode": mode,
                "answer": "I don't have enough in the org's records to answer that confidently. Try rephrasing, or ask about a specific event, meeting, or decision I might know about.",
                "citations": [],
                "created_doc_url": None,
            }

    # 4. Generate answer
    history_section = _build_history_section(history or [])
    if chunks:
        context_block = format_context_for_prompt(chunks)
        prompt = _ANSWER_PROMPT.format(
            mode=mode, query=query, context=context_block, history_section=history_section
        )
    else:
        prompt = _NO_CONTEXT_PROMPT.format(query=query)

    try:
        max_tokens = 8192 if mode == "PLAN" else 2048
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
                max_output_tokens=max_tokens,
            ),
        )
        answer, citations = _parse_response(response.text)
    except Exception as e:
        logger.error("Answer generation failed: %s", e)
        answer = "An error occurred while generating a response."
        citations = []

    citations = _enrich_citations(citations, chunks)

    # 5. Grounding check: verify answer doesn't contain claims outside the context
    if chunks and answer and "error" not in answer.lower():
        answer = await _check_grounding(query, answer, format_context_for_prompt(chunks), client)

    # 6. PLAN mode: create Google Doc
    created_doc_url = None
    if mode == "PLAN" and answer and "error" not in answer.lower():
        try:
            created_doc_url = await asyncio.to_thread(create_google_doc, query, answer, citations)
            logger.info("Google Doc created: %s", created_doc_url)
        except Exception as e:
            logger.error("Google Doc creation failed: %s", e)

    return {
        "mode": mode,
        "answer": answer,
        "citations": citations,
        "created_doc_url": created_doc_url,
    }
