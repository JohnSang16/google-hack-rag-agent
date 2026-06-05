import asyncio
import logging
import os
from typing import Optional

from google import genai
from dotenv import load_dotenv

from src.retrieval.vector_search import vector_search, _get_collection
from src.retrieval.reranker import rerank

load_dotenv()

logger = logging.getLogger(__name__)

TOP_K = 10


def _get_gemini_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def _embed_query(query: str, client: genai.Client) -> list[float]:
    """Embed a query using retrieval_query task type."""
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=query,
        config=genai.types.EmbedContentConfig(
            task_type="retrieval_query",
            output_dimensionality=768,
        ),
    )
    return list(result.embeddings[0].values)


async def retrieve(
    query: str,
    filters: Optional[dict] = None,
    top_k: int = TOP_K,
    collection=None,
    gemini_client: genai.Client = None,
) -> list[dict]:
    """
    Full retrieval pipeline: embed query → vector search → rerank → return top-3.

    filters keys: event_name, semester, doc_type, team, source_type
    Returns list of chunk dicts with keys: text, metadata, score, relevance_score
    """
    if gemini_client is None:
        gemini_client = _get_gemini_client()

    if collection is None:
        collection = _get_collection()

    # 1. Embed query (sync SDK call — run in thread)
    try:
        query_embedding = await asyncio.to_thread(_embed_query, query, gemini_client)
    except Exception as e:
        raise RuntimeError(f"Query embedding failed: {e}") from e

    # 2. Vector search
    candidates = await vector_search(
        query_embedding=query_embedding,
        top_k=top_k,
        filters=filters,
        collection=collection,
    )

    if not candidates:
        logger.warning("Vector search returned 0 results for query: %s", query[:80])
        return []

    # 3. Rerank (sync, makes up to 10 sequential Gemini calls — run in thread)
    results = await asyncio.to_thread(rerank, query, candidates, gemini_client)

    logger.info(
        "retrieve: query='%s...' filters=%s → %d candidates → %d final",
        query[:50],
        filters,
        len(candidates),
        len(results),
    )
    return results
