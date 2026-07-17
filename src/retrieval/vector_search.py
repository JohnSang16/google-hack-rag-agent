import logging
import os
from typing import Optional

import motor.motor_asyncio
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _get_collection():
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise ValueError("MONGODB_URI environment variable is not set")
    db_name = os.getenv("MONGODB_DB_NAME", "progsu_intelligence")
    collection_name = os.getenv("MONGODB_COLLECTION", "chunks")
    client = motor.motor_asyncio.AsyncIOMotorClient(uri)
    return client[db_name][collection_name]


async def vector_search(
    query_embedding: list,
    top_k: int = 10,
    filters: Optional[dict] = None,
    collection=None,
) -> list:
    """
    Run $vectorSearch against the Atlas vector_index with optional metadata pre-filter.

    filters keys match metadata field names: event_name, semester, doc_type, team,
    source_type, date. None values are ignored.

    Returns up to top_k dicts with keys: _id, text, metadata, score.
    """
    if collection is None:
        collection = _get_collection()

    search_stage: dict = {
        "index": "vector_index",
        "path": "embedding",
        "queryVector": query_embedding,
        "numCandidates": max(top_k * 10, 100),
        "limit": top_k,
    }

    if filters:
        clauses = [
            {"metadata." + k: {"$eq": v}}
            for k, v in filters.items()
            if v is not None
        ]
        if clauses:
            search_stage["filter"] = {"$and": clauses} if len(clauses) > 1 else clauses[0]

    pipeline = [
        {"$vectorSearch": search_stage},
        {
            "$project": {
                "_id": 1,
                "text": 1,
                "redacted_text": 1,
                "metadata": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    results = []
    async for doc in collection.aggregate(pipeline):
        doc["_id"] = str(doc["_id"])
        results.append(doc)

    logger.info(
        "vector_search: returned %d results (top_k=%d, filters=%s)",
        len(results),
        top_k,
        filters,
    )
    return results
