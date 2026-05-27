"""Upserts document chunks with embeddings into MongoDB Atlas."""

import os
import logging
from typing import Any

from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError

logger = logging.getLogger(__name__)


def get_collection() -> Collection:
    uri = os.environ["MONGODB_URI"]
    db_name = os.environ.get("MONGODB_DB_NAME", "progsu_intelligence")
    collection_name = os.environ.get("MONGODB_COLLECTION", "chunks")
    client = MongoClient(uri)
    return client[db_name][collection_name]


def store_chunk(chunk: dict[str, Any], collection: Collection | None = None) -> str:
    """Insert or update a single chunk. Returns the inserted/matched _id as string."""
    col = collection or get_collection()

    # Build a stable filter key from file_id + chunk_index so reruns are idempotent
    file_id = chunk["metadata"]["file_id"]
    chunk_index = chunk["metadata"]["chunk_index"]
    filter_doc = {
        "metadata.file_id": file_id,
        "metadata.chunk_index": chunk_index,
    }

    result = col.update_one(filter_doc, {"$set": chunk}, upsert=True)

    if result.upserted_id is not None:
        logger.info("Inserted new chunk: file_id=%s chunk_index=%d", file_id, chunk_index)
        return str(result.upserted_id)

    logger.info("Updated existing chunk: file_id=%s chunk_index=%d", file_id, chunk_index)
    matched = col.find_one(filter_doc, {"_id": 1})
    return str(matched["_id"])


def store_chunks(chunks: list[dict[str, Any]], collection: Collection | None = None) -> int:
    """Bulk upsert a list of chunks. Returns count of chunks stored."""
    if not chunks:
        return 0

    col = collection or get_collection()

    ops = [
        UpdateOne(
            {
                "metadata.file_id": c["metadata"]["file_id"],
                "metadata.chunk_index": c["metadata"]["chunk_index"],
            },
            {"$set": c},
            upsert=True,
        )
        for c in chunks
    ]

    try:
        result = col.bulk_write(ops, ordered=False)
        stored = result.upserted_count + result.modified_count
        logger.info(
            "Bulk upsert: %d inserted, %d modified, %d total",
            result.upserted_count,
            result.modified_count,
            stored,
        )
        return stored
    except BulkWriteError as e:
        logger.error("Bulk write error: %s", e.details)
        raise
