import logging
import os
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection

load_dotenv()

logger = logging.getLogger(__name__)


def get_collection() -> Collection:
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise ValueError("MONGODB_URI environment variable is not set")
    db_name = os.getenv("MONGODB_DB_NAME", "progsu_intelligence")
    collection_name = os.getenv("MONGODB_COLLECTION", "chunks")
    client = MongoClient(uri)
    return client[db_name][collection_name]


def store_chunk(
    text: str,
    embedding: list,
    metadata: dict,
    collection: Optional[Collection] = None,
) -> str:
    """Upsert a single chunk by file_id + chunk_index. Returns the document _id as string."""
    if collection is None:
        collection = get_collection()

    doc = {"text": text, "embedding": embedding, "metadata": metadata}
    file_id = metadata["file_id"]
    chunk_index = metadata["chunk_index"]

    result = collection.update_one(
        {"metadata.file_id": file_id, "metadata.chunk_index": chunk_index},
        {"$set": doc},
        upsert=True,
    )

    if result.upserted_id:
        _id = str(result.upserted_id)
    else:
        _id = str(
            collection.find_one(
                {"metadata.file_id": file_id, "metadata.chunk_index": chunk_index},
                {"_id": 1},
            )["_id"]
        )

    logger.info("Stored chunk %s[%d] → %s", file_id, chunk_index, _id)
    return _id


def store_chunks_bulk(
    chunks: list,
    collection: Optional[Collection] = None,
) -> int:
    """Bulk upsert a list of chunk dicts. Returns count of upserted + modified docs."""
    if collection is None:
        collection = get_collection()

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

    result = collection.bulk_write(ops, ordered=False)
    total = result.upserted_count + result.modified_count
    logger.info(
        "Bulk upsert complete: %d upserted, %d modified, %d matched",
        result.upserted_count,
        result.modified_count,
        result.matched_count,
    )
    return total
