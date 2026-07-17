import json
import logging
import os

from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_RERANK_BATCH_PROMPT = """You are scoring how relevant retrieved document chunks are to a user's query.

Query: {query}

Score each chunk from 0-10 where:
10 = Directly and specifically answers the query with concrete details
7-9 = Highly relevant, contains most of what the query needs
4-6 = Somewhat relevant, tangentially related
1-3 = Barely relevant or only shares keywords
0 = Not relevant at all

Chunks to score:

{chunks_block}

Respond with ONLY a JSON array of integers, one score per chunk in order. Example for 3 chunks: [8, 3, 7]"""

MIN_SCORE = 6
MIN_RESULTS = 2
MAX_CHUNK_CHARS = 800

# Score assigned to every chunk when the reranker call fails or returns a
# malformed response. Must stay below the agent's confidence gate (5) even
# after the +1.5 authority boost, so a reranker outage degrades to
# "not enough info" instead of ungated generation.
FAILURE_SCORE = 3

# Authoritative sources: one source of truth per topic area.
# Chunks from these files get a +1.5 score boost after reranking.
# The ids live in org_config.json (private, gitignored), not in source.
from src.org_config import cfg_list

_AUTHORITATIVE_FILE_IDS = frozenset(cfg_list("authoritative_file_ids"))
_AUTHORITY_BOOST = 1.5


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def _build_chunks_block(chunks: list[dict]) -> str:
    lines = []
    for i, chunk in enumerate(chunks):
        meta = chunk.get("metadata", {})
        title = meta.get("file_title", "Unknown")
        date = meta.get("date") or "n/a"
        text = chunk.get("text", "")[:MAX_CHUNK_CHARS]
        lines.append(f"[{i}] Source: {title} ({date})\n{text}")
    return "\n\n".join(lines)


def _batch_score(query: str, chunks: list[dict], client: genai.Client) -> list[int]:
    """Score all chunks in a single Gemini call. Returns list of ints same length as chunks."""
    prompt = _RERANK_BATCH_PROMPT.format(
        query=query,
        chunks_block=_build_chunks_block(chunks),
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        raw = response.text.strip()
        scores = json.loads(raw)
        if isinstance(scores, list) and len(scores) == len(chunks):
            return [min(max(int(s), 0), 10) for s in scores]
        logger.warning("Unexpected reranker response shape, defaulting scores to %d", FAILURE_SCORE)
        return [FAILURE_SCORE] * len(chunks)
    except Exception as e:
        logger.warning("Batch reranker failed, defaulting all scores to %d: %s", FAILURE_SCORE, e)
        return [FAILURE_SCORE] * len(chunks)


def rerank(query: str, chunks: list[dict], client: genai.Client = None) -> list[dict]:
    """
    Score all chunks against the query in one Gemini call, return top results.
    Keeps chunks scoring >= MIN_SCORE. If fewer than MIN_RESULTS qualify, returns top MIN_RESULTS.
    Each returned dict gains a 'relevance_score' key.
    """
    if not chunks:
        return []

    if client is None:
        client = _get_client()

    scores = _batch_score(query, chunks, client)

    scored = []
    for chunk, score in zip(chunks, scores):
        file_id = chunk.get("metadata", {}).get("file_id", "")
        boost = _AUTHORITY_BOOST if file_id in _AUTHORITATIVE_FILE_IDS else 0
        final_score = min(score + boost, 10)
        scored.append({**chunk, "relevance_score": final_score})
    scored.sort(key=lambda c: c["relevance_score"], reverse=True)

    for c in scored:
        logger.debug(
            "Chunk '%s' score: %d",
            c.get("metadata", {}).get("file_title", "?"),
            c["relevance_score"],
        )

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
