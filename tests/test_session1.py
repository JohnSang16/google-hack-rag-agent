"""
Session 1 validation: MongoDB Atlas vector search loop on dummy data.

Inserts 5 test chunks (3 hacklanta, 2 other_event), waits for Atlas index sync,
then verifies unfiltered search, metadata pre-filter, and schema correctness.
All test documents are cleaned up after the module runs.
"""
import asyncio
import os
import random
import time

import pytest
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("MONGODB_URI"):
    pytest.skip("MONGODB_URI not set in .env — skipping Session 1 tests", allow_module_level=True)

from src.ingestion.storer import get_collection, store_chunks_bulk
from src.retrieval.vector_search import vector_search

TEST_PREFIX = "test_session1_"
ATLAS_SYNC_WAIT = 10  # seconds for M0 free tier to index new documents


def _unit_vec(seed: int) -> list:
    """Deterministic normalized 768-dim vector."""
    rng = random.Random(seed)
    v = [rng.gauss(0, 1) for _ in range(768)]
    norm = sum(x * x for x in v) ** 0.5
    return [x / norm for x in v]


def _make_chunk(idx: int, event: str) -> dict:
    return {
        "text": f"Test chunk {idx} for event {event}. Contains meeting notes and action items.",
        "embedding": _unit_vec(idx),
        "metadata": {
            "source_type": "google_drive",
            "doc_type": "meeting_notes",
            "semester": "fall_2025",
            "event_name": event,
            "date": "2025-10-01",
            "team": "exec",
            "file_id": f"{TEST_PREFIX}{event}_{idx}",
            "file_title": f"Test Doc {idx}",
            "chunk_index": 0,
        },
    }


@pytest.fixture(scope="module", autouse=True)
def seed_and_cleanup():
    chunks = [
        _make_chunk(0, "hacklanta"),
        _make_chunk(1, "hacklanta"),
        _make_chunk(2, "hacklanta"),
        _make_chunk(3, "other_event"),
        _make_chunk(4, "other_event"),
    ]
    col = get_collection()
    store_chunks_bulk(chunks, collection=col)
    print(f"\nSeeded 5 test chunks. Waiting {ATLAS_SYNC_WAIT}s for Atlas index sync...")
    time.sleep(ATLAS_SYNC_WAIT)
    yield
    deleted = col.delete_many(
        {"metadata.file_id": {"$regex": f"^{TEST_PREFIX}"}}
    ).deleted_count
    print(f"Cleaned up {deleted} test chunks.")


def test_unfiltered_search_returns_results():
    results = asyncio.run(vector_search(_unit_vec(0), top_k=5))
    assert len(results) > 0, "Expected at least one result from unfiltered search"
    for r in results:
        assert "text" in r
        assert "metadata" in r
        assert "score" in r
        assert isinstance(r["score"], float)


def test_result_schema_complete():
    results = asyncio.run(vector_search(_unit_vec(0), top_k=3))
    assert results, "Expected at least one result"
    meta = results[0]["metadata"]
    required = ["source_type", "doc_type", "semester", "file_id", "file_title", "chunk_index"]
    for field in required:
        assert field in meta, f"Missing required metadata field: {field}"


def test_prefilter_hacklanta_only():
    results = asyncio.run(
        vector_search(_unit_vec(0), top_k=10, filters={"event_name": "hacklanta"})
    )
    assert len(results) > 0, "Expected results when filtering by event_name=hacklanta"
    for r in results:
        assert r["metadata"]["event_name"] == "hacklanta", (
            f"Pre-filter leak: expected 'hacklanta', got {r['metadata']['event_name']!r}"
        )


def test_prefilter_other_event():
    results = asyncio.run(
        vector_search(_unit_vec(3), top_k=10, filters={"event_name": "other_event"})
    )
    assert len(results) > 0, "Expected results when filtering by event_name=other_event"
    for r in results:
        assert r["metadata"]["event_name"] == "other_event", (
            f"Pre-filter leak: expected 'other_event', got {r['metadata']['event_name']!r}"
        )


def test_multi_filter_semester_and_event():
    results = asyncio.run(
        vector_search(
            _unit_vec(0),
            top_k=10,
            filters={"event_name": "hacklanta", "semester": "fall_2025"},
        )
    )
    for r in results:
        assert r["metadata"]["event_name"] == "hacklanta"
        assert r["metadata"]["semester"] == "fall_2025"
