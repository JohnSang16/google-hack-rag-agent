"""
Eval: answer quality via Gemini-as-judge.

Runs the three demo queries end-to-end through run_stream() and scores each answer:
  - faithfulness (1-5): answer uses only facts from retrieved context
  - relevance (1-5): answer directly addresses the query
  - no_hallucination (bool): no invented numbers, names, or statistics

Requires GEMINI_API_KEY and MONGODB_URI. PLAN mode also needs the OAuth token.

Run:
    pytest tests/eval/eval_answer_quality.py -v -s
    python -m tests.eval.eval_answer_quality
"""

import asyncio
import json
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
from src.agent import agent as _agent
from tests.eval.fixtures import DEMO_FIXTURES

logger = logging.getLogger(__name__)

FAITHFULNESS_THRESHOLD = 4.0
RELEVANCE_THRESHOLD = 4.0
HALLUCINATION_FREE_THRESHOLD = 0.67

_JUDGE_PROMPT = """You are evaluating an AI answer produced by a RAG system for a student org knowledge base.

Query: {query}
Expected mode: {mode}

Answer:
{answer}

Score on three dimensions and respond ONLY with valid JSON, no extra text:

{{
  "faithfulness": <integer 1-5>,
  "relevance": <integer 1-5>,
  "no_hallucination": <true|false>,
  "reasoning": "<1-2 sentence explanation>"
}}

faithfulness — does the answer avoid unsupported claims?
  5 = every claim is grounded in a real org knowledge base, no invented facts
  3 = mostly grounded, one or two unverifiable claims
  1 = invents statistics, names, or events not in the knowledge base

relevance — does the answer address the query?
  5 = directly and completely answers the question
  3 = partially answers, misses key aspects
  1 = off-topic or misses the point

no_hallucination: true only if there are NO invented dollar amounts, attendance figures,
sponsor names, or other specifics that appear to be fabricated rather than retrieved."""


async def run() -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)
    results = []

    for fixture in DEMO_FIXTURES:
        events = []
        async for event in _agent.run_stream(query=fixture.query):
            events.append(event)

        done = next((e for e in events if e.get("type") == "done"), None)
        if not done:
            results.append({
                "label": fixture.label,
                "query": fixture.query,
                "error": "no done event received",
                "faithfulness": 0,
                "relevance": 0,
                "no_hallucination": False,
            })
            continue

        answer = done.get("answer", "")
        prompt = _JUDGE_PROMPT.format(
            query=fixture.query,
            mode=fixture.expected_mode,
            answer=answer[:3000],
        )

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            scores = json.loads(response.text.strip())
        except Exception as e:
            logger.error("Judge call failed for %s: %s", fixture.label, e)
            scores = {
                "faithfulness": 0,
                "relevance": 0,
                "no_hallucination": False,
                "reasoning": str(e),
            }

        results.append({
            "label": fixture.label,
            "query": fixture.query,
            "mode": done.get("mode"),
            "answer_length": len(answer),
            "n_citations": len(done.get("citations", [])),
            **scores,
        })
        logger.info(
            "[%s] faithfulness=%s/5 relevance=%s/5 clean=%s | %s",
            fixture.label,
            scores.get("faithfulness"),
            scores.get("relevance"),
            scores.get("no_hallucination"),
            scores.get("reasoning", "")[:80],
        )

    n = len(results)
    return {
        "n_queries": n,
        "mean_faithfulness": sum(r.get("faithfulness", 0) for r in results) / n if n else 0,
        "mean_relevance": sum(r.get("relevance", 0) for r in results) / n if n else 0,
        "hallucination_free_rate": (
            sum(1 for r in results if r.get("no_hallucination")) / n if n else 0
        ),
        "results": results,
    }


# --- pytest ---

@pytest.fixture(scope="module")
def answer_quality_report():
    return asyncio.run(run())


def test_mean_faithfulness(answer_quality_report):
    score = answer_quality_report["mean_faithfulness"]
    assert score >= FAITHFULNESS_THRESHOLD, (
        f"Mean faithfulness {score:.1f}/5 below {FAITHFULNESS_THRESHOLD}. "
        f"Details: {answer_quality_report['results']}"
    )


def test_mean_relevance(answer_quality_report):
    score = answer_quality_report["mean_relevance"]
    assert score >= RELEVANCE_THRESHOLD, (
        f"Mean relevance {score:.1f}/5 below {RELEVANCE_THRESHOLD}"
    )


def test_hallucination_free_rate(answer_quality_report):
    rate = answer_quality_report["hallucination_free_rate"]
    assert rate >= HALLUCINATION_FREE_THRESHOLD, (
        f"Hallucination-free rate {rate:.0%} — at least 2/3 demo queries must be clean"
    )


def test_all_answers_have_citations(answer_quality_report):
    for r in answer_quality_report["results"]:
        if r.get("mode") in ("RECALL", "ANALYZE", "PLAN"):
            assert r.get("n_citations", 0) > 0, (
                f"[{r['label']}] mode={r.get('mode')} returned 0 citations"
            )


# --- standalone ---

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    report = asyncio.run(run())
    print("\nAnswer Quality Eval (Gemini-as-judge)")
    print(f"Mean faithfulness:      {report['mean_faithfulness']:.1f}/5")
    print(f"Mean relevance:         {report['mean_relevance']:.1f}/5")
    print(f"Hallucination-free:     {report['hallucination_free_rate']:.0%}")
    print("\nPer-query:")
    for r in report["results"]:
        if "error" in r:
            print(f"  [{r['label']}] ERROR: {r['error']}")
        else:
            print(
                f"  [{r['label']}] faith={r.get('faithfulness')}/5 "
                f"rel={r.get('relevance')}/5 clean={r.get('no_hallucination')} "
                f"| {r.get('reasoning', '')[:100]}"
            )
    sys.exit(0 if report["mean_faithfulness"] >= FAITHFULNESS_THRESHOLD else 1)
