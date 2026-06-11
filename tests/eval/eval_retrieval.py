"""
Eval: retrieval quality.

For each fixture with expected_sources, runs the full retrieval pipeline
(embed query → vector search → rerank) and measures:
  - top_source_hit: at least one expected source appears in the top-3 chunks
  - precision_at_3: fraction of top-3 chunks that match an expected source
  - mean_relevance_score: average reranker relevance_score of returned chunks

Requires GEMINI_API_KEY and MONGODB_URI.

Run:
    pytest tests/eval/eval_retrieval.py -v -s
    python -m tests.eval.eval_retrieval
"""

import asyncio
import logging
import os
import sys

import pytest
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI")

if not GEMINI_API_KEY:
    pytest.skip("GEMINI_API_KEY not set", allow_module_level=True)
if not MONGODB_URI:
    pytest.skip("MONGODB_URI not set", allow_module_level=True)

from google import genai
from src.retrieval.retriever import retrieve
from tests.eval.fixtures import RETRIEVAL_FIXTURES

logger = logging.getLogger(__name__)

HIT_RATE_THRESHOLD = 0.75
PRECISION_AT_3_THRESHOLD = 0.50
MIN_RELEVANCE_SCORE = 6.0


def _source_matches(chunk: dict, expected: list[str]) -> bool:
    title = chunk.get("metadata", {}).get("file_title", "").lower()
    return any(e.lower() in title for e in expected)


async def run() -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)
    results = []

    for fixture in RETRIEVAL_FIXTURES:
        chunks = await retrieve(query=fixture.query, gemini_client=client)
        returned_titles = [c.get("metadata", {}).get("file_title", "?") for c in chunks]

        hit = any(_source_matches(c, fixture.expected_sources) for c in chunks)
        precision = (
            sum(1 for c in chunks if _source_matches(c, fixture.expected_sources)) / len(chunks)
            if chunks else 0
        )
        mean_score = (
            sum(c.get("relevance_score", 0) for c in chunks) / len(chunks)
            if chunks else 0
        )

        results.append({
            "label": fixture.label,
            "query": fixture.query,
            "expected_sources": fixture.expected_sources,
            "returned_sources": returned_titles,
            "top_source_hit": hit,
            "precision_at_3": precision,
            "mean_relevance_score": mean_score,
            "n_chunks": len(chunks),
        })
        logger.info(
            "[%s] hit=%s precision=%.0f%% score=%.1f returned=%s",
            fixture.label, hit, precision * 100, mean_score, returned_titles,
        )

    n = len(results)
    return {
        "n_queries": n,
        "hit_rate": sum(1 for r in results if r["top_source_hit"]) / n if n else 0,
        "mean_precision_at_3": sum(r["precision_at_3"] for r in results) / n if n else 0,
        "mean_relevance_score": sum(r["mean_relevance_score"] for r in results) / n if n else 0,
        "results": results,
        "misses": [r for r in results if not r["top_source_hit"]],
    }


# --- pytest ---

@pytest.fixture(scope="module")
def retrieval_report():
    return asyncio.run(run())


def test_top_source_hit_rate(retrieval_report):
    rate = retrieval_report["hit_rate"]
    assert rate >= HIT_RATE_THRESHOLD, (
        f"Top-source hit rate {rate:.0%} below {HIT_RATE_THRESHOLD:.0%}. "
        f"Misses: {retrieval_report['misses']}"
    )


def test_mean_precision_at_3(retrieval_report):
    prec = retrieval_report["mean_precision_at_3"]
    assert prec >= PRECISION_AT_3_THRESHOLD, (
        f"Mean precision@3 {prec:.0%} below {PRECISION_AT_3_THRESHOLD:.0%}"
    )


def test_mean_relevance_score(retrieval_report):
    score = retrieval_report["mean_relevance_score"]
    assert score >= MIN_RELEVANCE_SCORE, (
        f"Mean relevance score {score:.1f}/10 below minimum {MIN_RELEVANCE_SCORE}"
    )


def test_demo_query_1_hits(retrieval_report):
    r = next((r for r in retrieval_report["results"] if r["label"] == "demo query 1"), None)
    assert r and r["top_source_hit"], (
        f"Demo query 1 (Hacklanta logistics) missed. Got: {r['returned_sources'] if r else 'not run'}"
    )


def test_demo_query_2_hits(retrieval_report):
    r = next((r for r in retrieval_report["results"] if r["label"] == "demo query 2"), None)
    assert r and r["top_source_hit"], (
        f"Demo query 2 (attendance growth) missed. Got: {r['returned_sources'] if r else 'not run'}"
    )


def test_demo_query_3_hits(retrieval_report):
    r = next((r for r in retrieval_report["results"] if r["label"] == "demo query 3"), None)
    assert r and r["top_source_hit"], (
        f"Demo query 3 (hackathon planning brief) missed. Got: {r['returned_sources'] if r else 'not run'}"
    )


# --- standalone ---

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    report = asyncio.run(run())
    print("\nRetrieval Eval")
    n_hits = sum(1 for r in report["results"] if r["top_source_hit"])
    print(f"Top-source hit rate:   {report['hit_rate']:.0%} ({n_hits}/{report['n_queries']})")
    print(f"Mean precision@3:      {report['mean_precision_at_3']:.0%}")
    print(f"Mean relevance score:  {report['mean_relevance_score']:.1f}/10")
    print("\nPer-query:")
    for r in report["results"]:
        status = "HIT" if r["top_source_hit"] else "MISS"
        print(f"  [{status}] {r['label']}: precision={r['precision_at_3']:.0%} score={r['mean_relevance_score']:.1f}")
        print(f"         returned: {r['returned_sources']}")
    sys.exit(0 if report["hit_rate"] >= HIT_RATE_THRESHOLD else 1)
