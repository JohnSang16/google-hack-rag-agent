"""
Session 1 smoke test: insert 5 dummy chunks, query returns correct one,
and metadata pre-filter (event_name=hacklanta) works.

Run: python tests/test_session1.py
Requires: MONGODB_URI set in environment (or .env file loaded before running).
"""

import os
import sys
import random
import time
import logging

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from src.ingestion.storer import store_chunks, get_collection
from src.retrieval.vector_search import vector_search

DIMS = 768


def random_embedding(seed: int | None = None) -> list[float]:
    rng = random.Random(seed)
    vec = [rng.gauss(0, 1) for _ in range(DIMS)]
    norm = sum(x**2 for x in vec) ** 0.5
    return [x / norm for x in vec]


# Five dummy chunks. Chunks 0-3 are about random topics; chunk 4 is "hacklanta".
DUMMY_CHUNKS = [
    {
        "text": "Fall 2025 general meeting: discussed project ideas for the semester.",
        "embedding": random_embedding(0),
        "metadata": {
            "source_type": "google_drive",
            "doc_type": "meeting_notes",
            "semester": "fall_2025",
            "event_name": None,
            "date": "2025-09-05",
            "team": "exec",
            "file_id": "dummy_file_001",
            "file_title": "Fall 2025 Exec Meeting Notes",
            "chunk_index": 0,
        },
    },
    {
        "text": "Spring 2026 budget review: allocated $500 for workshop supplies.",
        "embedding": random_embedding(1),
        "metadata": {
            "source_type": "google_drive",
            "doc_type": "financial",
            "semester": "spring_2026",
            "event_name": None,
            "date": "2026-01-15",
            "team": "exec",
            "file_id": "dummy_file_002",
            "file_title": "Spring 2026 Budget",
            "chunk_index": 0,
        },
    },
    {
        "text": "Growth team brainstorm: ideas for recruiting 50 new members next semester.",
        "embedding": random_embedding(2),
        "metadata": {
            "source_type": "google_drive",
            "doc_type": "growth",
            "semester": "fall_2025",
            "event_name": None,
            "date": "2025-10-01",
            "team": "growth",
            "file_id": "dummy_file_003",
            "file_title": "Growth Brainstorm Oct 2025",
            "chunk_index": 0,
        },
    },
    {
        "text": "Tech team guide: setting up the club Discord server and channel permissions.",
        "embedding": random_embedding(3),
        "metadata": {
            "source_type": "discord",
            "doc_type": "guide",
            "semester": "fall_2025",
            "event_name": None,
            "date": "2025-08-20",
            "team": "tech",
            "file_id": "dummy_file_004",
            "file_title": "Discord Setup Guide",
            "chunk_index": 0,
        },
    },
    {
        "text": (
            "Hacklanta 2025: 120 attendees, venue was Georgia Tech Klaus building. "
            "Sponsors included TechCorp and CloudCo. Main logistics challenge was catering "
            "running out early  -  resolved by ordering 30% more next time."
        ),
        "embedding": random_embedding(42),  # distinct seed → distinct vector
        "metadata": {
            "source_type": "google_drive",
            "doc_type": "event_logistics",
            "semester": "fall_2025",
            "event_name": "hacklanta",
            "date": "2025-11-10",
            "team": "operations",
            "file_id": "dummy_file_005",
            "file_title": "Hacklanta Master Logistics",
            "chunk_index": 0,
        },
    },
]


def run():
    col = get_collection()

    # Clean up any leftover dummy data from previous runs
    dummy_ids = [c["metadata"]["file_id"] for c in DUMMY_CHUNKS]
    col.delete_many({"metadata.file_id": {"$in": dummy_ids}})
    print(f"Cleaned up previous dummy data for {len(dummy_ids)} file IDs")

    # --- Insert ---
    stored = store_chunks(DUMMY_CHUNKS, collection=col)
    print(f"Stored {stored} chunks")
    assert stored == len(DUMMY_CHUNKS), f"Expected {len(DUMMY_CHUNKS)} stored, got {stored}"

    # Atlas index is near-real-time but give it a moment in CI
    print("Waiting 3s for Atlas index to catch up...")
    time.sleep(3)

    # --- Test 1: unfiltered query using hacklanta embedding → should rank it first ---
    hacklanta_vec = DUMMY_CHUNKS[4]["embedding"]
    results = vector_search(hacklanta_vec, top_k=5, collection=col)
    assert results, "No results returned from vector search"
    top = results[0]
    assert top["metadata"]["event_name"] == "hacklanta", (
        f"Expected hacklanta as top result, got: {top['metadata']}"
    )
    print(f"Test 1 PASSED: top result is '{top['metadata']['file_title']}' (score={top['score']:.4f})")

    # --- Test 2: pre-filter by event_name=hacklanta → should return only that chunk ---
    filtered = vector_search(
        hacklanta_vec,
        filters={"event_name": "hacklanta"},
        top_k=10,
        collection=col,
    )
    assert all(r["metadata"]["event_name"] == "hacklanta" for r in filtered), (
        f"Pre-filter leak: got non-hacklanta results: {[r['metadata'] for r in filtered]}"
    )
    assert len(filtered) == 1, f"Expected 1 result with pre-filter, got {len(filtered)}"
    print(f"Test 2 PASSED: pre-filter returned {len(filtered)} result(s), all event_name=hacklanta")

    # --- Test 3: pre-filter by team=growth → should return only growth chunk ---
    growth_vec = DUMMY_CHUNKS[2]["embedding"]
    growth_results = vector_search(
        growth_vec,
        filters={"team": "growth"},
        top_k=10,
        collection=col,
    )
    assert all(r["metadata"]["team"] == "growth" for r in growth_results), (
        f"Pre-filter leak: {[r['metadata'] for r in growth_results]}"
    )
    print(f"Test 3 PASSED: team=growth filter returned {len(growth_results)} result(s)")

    # Cleanup
    col.delete_many({"metadata.file_id": {"$in": dummy_ids}})
    print("Cleaned up dummy data")
    print("\nAll Session 1 tests PASSED.")


if __name__ == "__main__":
    # Load .env if present
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    run()
