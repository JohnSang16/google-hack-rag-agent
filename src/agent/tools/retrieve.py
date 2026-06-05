import logging
from typing import Optional

from google import genai

from src.retrieval.retriever import retrieve as _retrieve

logger = logging.getLogger(__name__)


async def retrieve_context(
    query: str,
    filters: Optional[dict] = None,
    gemini_client: genai.Client = None,
) -> list[dict]:
    """
    Agent tool: retrieve relevant chunks from Atlas for a query.
    Returns list of dicts with text, metadata, score, relevance_score.
    """
    try:
        results = await _retrieve(query, filters=filters, gemini_client=gemini_client)
        logger.info("retrieve_context: %d chunks returned for '%s...'", len(results), query[:50])
        return results
    except Exception as e:
        logger.error("retrieve_context failed: %s", e)
        return []


def format_context_for_prompt(chunks: list[dict]) -> str:
    """Format retrieved chunks into a readable block for the agent prompt."""
    if not chunks:
        return "No relevant context found."

    lines = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        title = meta.get("file_title", "Unknown")
        date = meta.get("date") or "n/a"
        score = chunk.get("relevance_score", "?")
        text = chunk.get("text", "").strip()
        lines.append(f"[Source {i}: {title} | date: {date} | relevance: {score}/10]\n{text}")

    return "\n\n---\n\n".join(lines)
