"""
Eval: mode classification accuracy.

Runs every query in MODE_FIXTURES through classify_mode() and reports accuracy
per mode and overall. Only requires GEMINI_API_KEY (no MongoDB needed).

Run:
    pytest tests/eval/eval_mode_classifier.py -v -s
    python -m tests.eval.eval_mode_classifier
"""

import logging
import os
import sys
from collections import defaultdict

import pytest
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    pytest.skip("GEMINI_API_KEY not set", allow_module_level=True)

from google import genai
from src.agent.mode_classifier import classify_mode
from tests.eval.fixtures import MODE_FIXTURES

logger = logging.getLogger(__name__)

OVERALL_ACCURACY_THRESHOLD = 0.85
PLAN_ACCURACY_THRESHOLD = 0.90


def run() -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)
    results = []
    by_mode: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})

    for fixture in MODE_FIXTURES:
        predicted = classify_mode(fixture.query, client)
        correct = predicted == fixture.expected_mode
        results.append({
            "label": fixture.label,
            "query": fixture.query,
            "expected": fixture.expected_mode,
            "predicted": predicted,
            "correct": correct,
        })
        by_mode[fixture.expected_mode]["total"] += 1
        if correct:
            by_mode[fixture.expected_mode]["correct"] += 1

    total = len(results)
    n_correct = sum(1 for r in results if r["correct"])

    return {
        "total": total,
        "correct": n_correct,
        "accuracy": n_correct / total if total else 0,
        "by_mode": {
            mode: {
                **counts,
                "accuracy": counts["correct"] / counts["total"] if counts["total"] else 0,
            }
            for mode, counts in by_mode.items()
        },
        "failures": [r for r in results if not r["correct"]],
        "results": results,
    }


# --- pytest ---

@pytest.fixture(scope="module")
def classification_report():
    return run()


def test_overall_accuracy(classification_report):
    acc = classification_report["accuracy"]
    assert acc >= OVERALL_ACCURACY_THRESHOLD, (
        f"Overall accuracy {acc:.0%} below {OVERALL_ACCURACY_THRESHOLD:.0%}. "
        f"Failures: {classification_report['failures']}"
    )


def test_chat_accuracy(classification_report):
    chat = classification_report["by_mode"].get("CHAT", {})
    acc = chat.get("accuracy", 0)
    assert acc == 1.0, (
        f"CHAT accuracy {acc:.0%} — all pattern-matched CHAT queries must classify correctly"
    )


def test_plan_accuracy(classification_report):
    plan = classification_report["by_mode"].get("PLAN", {})
    acc = plan.get("accuracy", 0)
    assert acc >= PLAN_ACCURACY_THRESHOLD, (
        f"PLAN accuracy {acc:.0%} below {PLAN_ACCURACY_THRESHOLD:.0%} — "
        "PLAN misclassification skips artifact creation entirely"
    )


def test_no_plan_as_chat(classification_report):
    bad = [
        r for r in classification_report["results"]
        if r["expected"] == "PLAN" and r["predicted"] == "CHAT"
    ]
    assert not bad, f"PLAN queries misclassified as CHAT: {bad}"


# --- standalone ---

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    report = run()
    print("\nMode Classification Eval")
    print(f"Overall accuracy: {report['accuracy']:.0%} ({report['correct']}/{report['total']})")
    print("\nPer-mode:")
    for mode, counts in sorted(report["by_mode"].items()):
        print(f"  {mode}: {counts['accuracy']:.0%} ({counts['correct']}/{counts['total']})")
    if report["failures"]:
        print("\nFailures:")
        for f in report["failures"]:
            print(f"  [{f['label']}] expected={f['expected']} got={f['predicted']} | {f['query'][:80]}")
    sys.exit(0 if report["accuracy"] >= OVERALL_ACCURACY_THRESHOLD else 1)
