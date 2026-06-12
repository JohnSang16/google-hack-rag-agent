"""
Delete financial data chunks from MongoDB Atlas.

Run dry-run first to preview what will be deleted:
    python scripts/delete_financial_chunks.py

Then confirm and delete:
    python scripts/delete_financial_chunks.py --confirm
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()


def get_collection():
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("ERROR: MONGODB_URI not set. Check your .env file.")
        sys.exit(1)
    db_name = os.getenv("MONGODB_DB_NAME", "progsu_intelligence")
    collection_name = os.getenv("MONGODB_COLLECTION", "chunks")
    client = MongoClient(uri)
    return client[db_name][collection_name]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete. Without this flag, runs as dry-run only.",
    )
    args = parser.parse_args()

    collection = get_collection()
    query = {"metadata.doc_type": "financial"}

    chunks = list(collection.find(query, {"_id": 1, "metadata.source_name": 1, "metadata.file_id": 1, "text": 1}))
    count = len(chunks)

    if count == 0:
        print("No financial chunks found. Nothing to delete.")
        return

    print(f"\nFound {count} financial chunk(s):\n")
    seen_files = {}
    for c in chunks:
        fid = c.get("metadata", {}).get("file_id", "unknown")
        name = c.get("metadata", {}).get("source_name", "unnamed")
        seen_files[fid] = name

    for fid, name in seen_files.items():
        file_chunks = [c for c in chunks if c.get("metadata", {}).get("file_id") == fid]
        print(f"  {name} ({fid}) — {len(file_chunks)} chunk(s)")
        for c in file_chunks[:2]:
            preview = c.get("text", "")[:120].replace("\n", " ")
            print(f"    preview: {preview}...")
        if len(file_chunks) > 2:
            print(f"    ... and {len(file_chunks) - 2} more chunk(s)")

    if not args.confirm:
        print(f"\nDRY RUN — {count} chunk(s) would be deleted from {len(seen_files)} file(s).")
        print("Re-run with --confirm to actually delete.")
        return

    result = collection.delete_many(query)
    print(f"\nDeleted {result.deleted_count} financial chunk(s) from Atlas.")
    print("Financial data is no longer queryable on the live deployment.")
    print("Re-ingest after judging ends (July 13) for the full club deployment.")


if __name__ == "__main__":
    main()
