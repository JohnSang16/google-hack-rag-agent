"""ingestion_state and sync_runs collections on the existing Atlas cluster.

ingestion_state: one doc per source, keyed by source_id
  Drive file:      {source_id: <file_id>, source_type: "google_drive",
                    modified_time, chunk_count, last_synced, last_sync_status}
  Discord channel: {source_id: "discord_<channel>", source_type: "discord",
                    last_message_id, chunk_hashes: {str(chunk_key): sha256},
                    last_synced, last_sync_status}

sync_runs: one doc per weekly run with per-source counts, so run history
survives Cloud Run Jobs' ephemeral disks (the old local-JSON metrics pattern
does not).

On partial failure only successfully processed sources get marked synced, so
failures retry automatically on the next scheduled run instead of being
silently skipped forever.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
logger = logging.getLogger(__name__)

_client: Optional[MongoClient] = None


def _db():
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI")
        if not uri:
            raise ValueError("MONGODB_URI environment variable is not set")
        _client = MongoClient(uri)
    return _client[os.getenv("MONGODB_DB_NAME", "progsu_intelligence")]


def get_state_collection():
    return _db()["ingestion_state"]


def get_sync_runs_collection():
    return _db()["sync_runs"]


def get_source_state(source_id: str, state_coll=None) -> Optional[dict]:
    if state_coll is None:
        state_coll = get_state_collection()
    return state_coll.find_one({"source_id": source_id})


def mark_synced(source_id: str, source_type: str, status: str = "ok", state_coll=None, **fields) -> None:
    if state_coll is None:
        state_coll = get_state_collection()
    state_coll.update_one(
        {"source_id": source_id},
        {"$set": {
            "source_id": source_id,
            "source_type": source_type,
            "last_synced": datetime.now(timezone.utc),
            "last_sync_status": status,
            **fields,
        }},
        upsert=True,
    )


def record_run(summary: dict, runs_coll=None) -> None:
    if runs_coll is None:
        runs_coll = get_sync_runs_collection()
    runs_coll.insert_one({"ts": datetime.now(timezone.utc), **summary})
    logger.info("Sync run recorded: %s", {k: v for k, v in summary.items() if k != "details"})
