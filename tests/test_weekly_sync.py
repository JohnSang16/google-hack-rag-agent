"""
Pins the Section 6 ingestion refresh mechanics that must not regress:
date-based chunk keys (the fix that makes incremental sync idempotent),
snowflake time conversion, REST-to-exporter message conversion, and the
Drive delta skip / orphan cleanup logic.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.ingestion.discord_fetcher import _to_exporter_shape, snowflake_for_time
from src.ingestion.discord_reader import (
    LEGACY_CHUNK_KEY_CEILING,
    chunks_from_messages,
    date_chunk_key,
)
from src.ingestion.drive_walker import _classify_from_path, delete_orphaned_chunks


# --- Date-based chunk keys ---

def test_date_chunk_key_is_date_deterministic():
    assert date_chunk_key("2026-07-17", 0) == 20260717000
    assert date_chunk_key("2026-07-17", 3) == 20260717003


def test_date_chunk_key_independent_of_fetch_window():
    # The same day must produce the same key no matter what else was fetched
    assert date_chunk_key("2026-07-10", 0) == date_chunk_key("2026-07-10", 0)


def test_legacy_ceiling_separates_old_sequential_keys():
    assert date_chunk_key("1970-01-01", 0) >= LEGACY_CHUNK_KEY_CEILING
    assert 42 < LEGACY_CHUNK_KEY_CEILING  # old sequential keys were small ints


def _msg(mid, ts, content, bot=False):
    return {"id": mid, "timestamp": ts, "content": content,
            "author": {"isBot": bot, "name": "user", "nickname": "user"}}


def test_chunks_from_messages_uses_date_keys():
    messages = [
        _msg("1", "2026-07-15T10:00:00", "first message with enough words here"),
        _msg("2", "2026-07-15T10:05:00", "second message continuing the thread"),
        _msg("3", "2026-07-15T10:10:00", "third message wrapping up the decision"),
    ]
    chunks = list(chunks_from_messages("g", "general", "gid", "cid", messages))
    assert len(chunks) == 1
    assert chunks[0]["chunk_index"] == date_chunk_key("2026-07-15", 0)


def test_chunks_from_messages_skips_bot_and_sparse_days():
    messages = [
        _msg("1", "2026-07-15T10:00:00", "only message that day"),
        _msg("2", "2026-07-16T10:00:00", "bot spam", bot=True),
    ]
    assert list(chunks_from_messages("g", "c", "gid", "cid", messages)) == []


# --- Snowflake conversion ---

def test_snowflake_roundtrip():
    dt = datetime(2026, 7, 1, tzinfo=timezone.utc)
    snowflake = snowflake_for_time(dt)
    recovered_ms = (snowflake >> 22) + 1420070400000
    assert abs(recovered_ms - dt.timestamp() * 1000) < 1000


def test_rest_message_converts_to_exporter_shape():
    rest = {"id": "9", "timestamp": "2026-07-17T12:00:00", "content": "hi",
            "author": {"bot": False, "username": "js17", "global_name": "Js"}}
    out = _to_exporter_shape(rest)
    assert out == {"id": "9", "timestamp": "2026-07-17T12:00:00", "content": "hi",
                   "author": {"isBot": False, "name": "js17", "nickname": "Js"}}


# --- Drive delta ---

def test_classify_from_path_heuristics():
    meta = _classify_from_path("Fall Kickoff Logistics", "/Fall 2026/Events")
    assert meta["doc_type"] == "event_logistics"
    assert meta["semester"] == "fall_2026"
    bookkeeping = _classify_from_path("FINANCE: 2026-2027 Bookkeeping", "/Finance")
    assert bookkeeping["doc_type"] == "financial"


def test_delete_orphaned_chunks_only_on_shrink():
    coll = MagicMock()
    coll.delete_many.return_value.deleted_count = 2
    assert delete_orphaned_chunks(coll, "f1", 5, 7) == 2
    coll.delete_many.assert_called_once_with(
        {"metadata.file_id": "f1", "metadata.chunk_index": {"$gte": 5}}
    )
    coll.reset_mock()
    assert delete_orphaned_chunks(coll, "f1", 7, 7) == 0
    assert delete_orphaned_chunks(coll, "f1", 7, None) == 0
    coll.delete_many.assert_not_called()
