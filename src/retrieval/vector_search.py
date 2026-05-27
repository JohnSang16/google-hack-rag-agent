"""MongoDB Atlas $vectorSearch with metadata pre-filter."""

import os
import logging
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection

logger = logging.getLogger(__name__)

# Fields supported by the Atlas vector index filter definition
FILTERABLE_FIELDS = {"semester", "event_name", "doc_type", "team", "source_type"}


def get_collection() -> Collection:
    uri = os.environ["MONGODB_URI"]
    db_name = os.environ.get("MONGODB_DB_NAME", "progsu_intelligence")
    collection_name = os.environ.get("MONGODB_COLLECTION", "chunks")
    client = MongoClient(uri)
    return client[db_name][collection_name]


def _build_pre_filter(filters: dict[str, str] | None) -> dict | None:
    """Convert caller-supplied {field: value} into an Atlas MQL pre-filter."""
    if not filters:
        return None

    clauses = []
    for field, value in filters.items():
        if field not in FILTERABLE_FIELDS:
            logger.warning("Ignoring unknown filter field: %s", field)
            continue
        if value:
            clauses.append({f"metadata.{field}": {"$eq": value}})

    if not clauses:
        return None
    return {"$and": clauses} if len(clauses) > 1 else clauses[0]


def vector_search(
    query_embedding: list[float],
    filters: dict[str, str] | None = None,
    top_k: int = 10,
    collection: Collection | None = None,
) -> list[dict[str, Any]]:
    """
    Run Atlas $vectorSearch and return top_k chunks with metadata + score.

    Args:
        query_embedding: 768-dim float list from text-embedding-004.
        filters: optional dict with keys from FILTERABLE_FIELDS.
        top_k: number of results to return (default 10 for reranker input).
        collection: optional pre-built Collection (for testing / dependency injection).

    Returns:
        List of dicts with keys: text, metadata, score.
    """
    col = collection or get_collection()
    pre_filter = _build_pre_filter(filters)

    vector_search_stage: dict[str, Any] = {
        "index": "vector_index",
        "path": "embedding",
        "queryVector": query_embedding,
        "numCandidates": top_k * 10,  # cast wide, then filter down
        "limit": top_k,
    }
    if pre_filter:
        vector_search_stage["filter"] = pre_filter

    pipeline = [
        {"$vectorSearch": vector_search_stage},
        {
            "$project": {
                "_id": 0,
                "text": 1,
                "metadata": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    try:
        results = list(col.aggregate(pipeline))
        logger.info(
            "Vector search returned %d results (filters=%s)",
            len(results),
            filters,
        )
        return results
    except Exception as e:
        logger.error("Vector search failed: %s", e)
        raise
