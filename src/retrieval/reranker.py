import logging
import os
import time

from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_RERANK_PROMPT = """You are scoring how relevant a retrieved document chunk is to a user's query.

Query: {query}

Chunk: {chunk_text}
Source: {file_title} ({date})

Score this chunk from 1-10 where:
10 = Directly and specifically answers the query with concrete details
7-9 = Highly relevant, contains most of what the query needs
4-6 = Somewhat relevant, tangentially related
1-3 = Barely relevant or only shares keywords
0 = Not relevant at all

Respond with only a number 1-10."""

MIN_SCORE = 6
MIN_RESULTS = 2
MAX_CHUNK_CHARS = 2_000
RATE_LIMIT_DELAY = 0.15


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def _score_chunk(query: str, chunk: dict, client: genai.Client) -> int:
    """Score a single chunk against a query. Returns 0-10."""
    text = chunk.get("text", "")[:MAX_CHUNK_CHARS]
    file_title = chunk.get("metadata", {}).get("file_title", "Unknown")
    date = chunk.get("metadata", {}).get("date") or "n/a"

    prompt = _RERANK_PROMPT.format(
        query=query, chunk_text=text, file_title=file_title, date=date
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        raw = response.text.strip()
        score = int("".join(c for c in raw if c.isdigit())[:2])
        return min(max(score, 0), 10)
    except Exception as e:
        logger.warning("Reranker scoring failed, defaulting to 5: %s", e)
        return 5


def rerank(query: str, chunks: list[dict], client: genai.Client = None) -> list[dict]:
    """
    Score each chunk against the query and return the top results.
    Keeps chunks scoring >= 6. If fewer than MIN_RESULTS qualify, returns top MIN_RESULTS.
    Each returned dict gains a 'relevance_score' key.
    """
    if not chunks:
        return []

    if client is None:
        client = _get_client()

    scored = []
    for i, chunk in enumerate(chunks):
        score = _score_chunk(query, chunk, client)
        scored.append({**chunk, "relevance_score": score})
        logger.debug(
            "Chunk %d '%s' score: %d",
            i,
            chunk.get("metadata", {}).get("file_title", "?"),
            score,
        )
        if i < len(chunks) - 1:
            time.sleep(RATE_LIMIT_DELAY)

    scored.sort(key=lambda c: c["relevance_score"], reverse=True)

    qualified = [c for c in scored if c["relevance_score"] >= MIN_SCORE]
    if len(qualified) >= MIN_RESULTS:
        result = qualified[:3]
    else:
        result = scored[:max(MIN_RESULTS, len(qualified))][:3]

    logger.info(
        "Reranker: %d → %d chunks (scores: %s)",
        len(chunks),
        len(result),
        [c["relevance_score"] for c in result],
    )
    return result
