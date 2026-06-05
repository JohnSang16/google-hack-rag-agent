import json
import logging
import os
from typing import Optional

from google import genai
from dotenv import load_dotenv

from src.agent.mode_classifier import classify_mode
from src.agent.tools.retrieve import retrieve_context, format_context_for_prompt
from src.agent.tools.create_doc import create_google_doc

load_dotenv()

logger = logging.getLogger(__name__)

_ANSWER_PROMPT = """You are an AI chief of staff for a student tech organization called progsu.
You have retrieved the following context from the organization's documents.

Mode: {mode}
- RECALL: Answer what happened, what was decided, or what exists. Be specific and cite sources.
- ANALYZE: Synthesize trends across multiple events and time periods. Show patterns and numbers.
- PLAN: Write a comprehensive, structured planning document (markdown with sections).

Retrieved Context:
{context}

User Query: {query}

Instructions:
1. Answer using ONLY the provided context. Do not invent facts not present in the sources.
2. Every specific claim must be attributable to one of the sources above.
3. For PLAN mode: write a full structured document with sections (## headings). Make it actionable.
4. Output ONLY valid JSON with this exact structure (no markdown code fences around it):
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

Include only sources you actually used. Do not include sources you did not draw from."""

_NO_CONTEXT_PROMPT = """You are an AI chief of staff for a student tech organization called progsu.
No relevant context was found in the knowledge base for this query.

User Query: {query}

Respond with exactly this JSON:
{{
  "answer": "I could not find relevant information in the organization's documents for this query. Try rephrasing or ask about a specific event, meeting, or document.",
  "citations": []
}}"""


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def _parse_response(raw: str) -> tuple[str, list[dict]]:
    """Parse Gemini JSON response. Returns (answer, citations)."""
    try:
        # Strip accidental markdown fences
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        return data.get("answer", raw), data.get("citations", [])
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse JSON response, using raw text: %s", e)
        return raw, []


def _enrich_citations(citations: list[dict], chunks: list[dict]) -> list[dict]:
    """Add drive_url to each citation using file_id from retrieved chunks."""
    chunk_map = {
        c.get("metadata", {}).get("file_id"): c.get("metadata", {})
        for c in chunks
    }
    enriched = []
    for cite in citations:
        file_id = cite.get("file_id", "")
        meta = chunk_map.get(file_id, {})
        enriched.append({
            "title": cite.get("title") or meta.get("file_title", "Unknown"),
            "date": cite.get("date") or meta.get("date"),
            "file_id": file_id,
            "drive_url": f"https://drive.google.com/file/d/{file_id}/view" if file_id else None,
            "relevance_score": cite.get("relevance_score", 0),
        })
    return enriched


async def run(
    query: str,
    filters: Optional[dict] = None,
    client: genai.Client = None,
) -> dict:
    """
    Full agent pipeline: classify → retrieve → generate → (create doc if PLAN).
    Returns dict with mode, answer, citations, created_doc_url.
    """
    if client is None:
        client = _get_client()

    # 1. Classify mode
    mode = classify_mode(query, client=client)
    logger.info("Agent mode: %s", mode)

    # 2. Retrieve context
    chunks = await retrieve_context(query, filters=filters, gemini_client=client)

    # 3. Generate answer
    if chunks:
        context_block = format_context_for_prompt(chunks)
        prompt = _ANSWER_PROMPT.format(mode=mode, query=query, context=context_block)
    else:
        prompt = _NO_CONTEXT_PROMPT.format(query=query)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        answer, citations = _parse_response(response.text)
    except Exception as e:
        logger.error("Answer generation failed: %s", e)
        answer = "An error occurred while generating a response."
        citations = []

    citations = _enrich_citations(citations, chunks)

    # 4. PLAN mode: create Google Doc
    created_doc_url = None
    if mode == "PLAN" and answer and "error" not in answer.lower():
        try:
            created_doc_url = create_google_doc(query, answer, citations)
            logger.info("Google Doc created: %s", created_doc_url)
        except Exception as e:
            logger.error("Google Doc creation failed: %s", e)

    return {
        "mode": mode,
        "answer": answer,
        "citations": citations,
        "created_doc_url": created_doc_url,
    }
