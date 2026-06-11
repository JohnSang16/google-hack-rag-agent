"""
Eval orchestrator: run all three eval suites and write a JSON + text report.

Usage:
    python -m tests.eval.run_eval
    python -m tests.eval.run_eval --output path/to/report.json

Suites:
    1. Mode classification accuracy  (needs GEMINI_API_KEY)
    2. Retrieval quality             (needs GEMINI_API_KEY + MONGODB_URI)
    3. Answer quality, Gemini judge  (needs GEMINI_API_KEY + MONGODB_URI + OAuth token)

Any suite missing its credentials is skipped cleanly.
Report is written to tests/eval/reports/latest.json by default.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent / "reports"

THRESHOLDS = {
    "mode_accuracy":                    0.85,
    "retrieval_hit_rate":               0.75,
    "retrieval_precision_at_3":         0.50,
    "retrieval_mean_relevance":         6.0,
    "answer_faithfulness":              4.0,
    "answer_relevance":                 4.0,
    "answer_hallucination_free_rate":   0.67,
}


def _has_credentials() -> dict[str, bool]:
    oauth = next(
        (p for p in ["/secrets/drive_oauth_token.json", os.path.abspath("drive_oauth_token.json")]
         if os.path.exists(p)),
        None,
    )
    return {
        "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
        "MONGODB_URI":    bool(os.getenv("MONGODB_URI")),
        "OAUTH_TOKEN":    bool(oauth),
    }


def _run_mode_eval() -> dict | None:
    if not os.getenv("GEMINI_API_KEY"):
        logger.warning("Skipping mode eval: GEMINI_API_KEY not set")
        return None
    from tests.eval.eval_mode_classifier import run
    return run()


def _run_retrieval_eval() -> dict | None:
    if not os.getenv("GEMINI_API_KEY") or not os.getenv("MONGODB_URI"):
        logger.warning("Skipping retrieval eval: GEMINI_API_KEY or MONGODB_URI not set")
        return None
    from tests.eval.eval_retrieval import run
    return asyncio.run(run())


def _run_answer_eval() -> dict | None:
    if not os.getenv("GEMINI_API_KEY") or not os.getenv("MONGODB_URI"):
        logger.warning("Skipping answer quality eval: GEMINI_API_KEY or MONGODB_URI not set")
        return None
    from tests.eval.eval_answer_quality import run
    return asyncio.run(run())


def _status(value: float | None, threshold: float) -> str:
    if value is None:
        return "SKIP"
    return "PASS" if value >= threshold else "FAIL"


def main(output_path: str | None = None) -> int:
    creds = _has_credentials()
    logger.info("Credentials available: %s", creds)

    print("\n=====  progsu Intelligence Agent  |  Eval Report  =====\n")

    mode_report       = _run_mode_eval()
    retrieval_report  = _run_retrieval_eval()
    answer_report     = _run_answer_eval()

    scores = {
        "mode_accuracy":                    mode_report["accuracy"]                 if mode_report      else None,
        "retrieval_hit_rate":               retrieval_report["hit_rate"]            if retrieval_report else None,
        "retrieval_precision_at_3":         retrieval_report["mean_precision_at_3"] if retrieval_report else None,
        "retrieval_mean_relevance":         retrieval_report["mean_relevance_score"]if retrieval_report else None,
        "answer_faithfulness":              answer_report["mean_faithfulness"]      if answer_report    else None,
        "answer_relevance":                 answer_report["mean_relevance"]         if answer_report    else None,
        "answer_hallucination_free_rate":   answer_report["hallucination_free_rate"]if answer_report    else None,
    }

    rows = [
        ("Mode classification accuracy",   "mode_accuracy",                  "%"),
        ("Retrieval top-source hit rate",   "retrieval_hit_rate",             "%"),
        ("Retrieval precision@3",           "retrieval_precision_at_3",       "%"),
        ("Retrieval mean relevance score",  "retrieval_mean_relevance",       "/10"),
        ("Answer faithfulness (judge)",     "answer_faithfulness",            "/5"),
        ("Answer relevance (judge)",        "answer_relevance",               "/5"),
        ("Answer hallucination-free rate",  "answer_hallucination_free_rate", "%"),
    ]

    print(f"{'Metric':<42} {'Score':>9}  {'Threshold':>10}  Status")
    print("-" * 72)

    any_fail = False
    for label, key, unit in rows:
        value     = scores[key]
        threshold = THRESHOLDS[key]
        st        = _status(value, threshold)
        if st == "FAIL":
            any_fail = True

        if value is None:
            score_str = "SKIP"
            thr_str   = ""
        elif unit == "%":
            score_str = f"{value:.0%}"
            thr_str   = f"{threshold:.0%}"
        elif unit == "/10":
            score_str = f"{value:.1f}/10"
            thr_str   = f"{threshold:.1f}/10"
        else:
            score_str = f"{value:.1f}/5"
            thr_str   = f"{threshold:.1f}/5"

        print(f"{label:<42} {score_str:>9}  {thr_str:>10}  {st}")

    print()

    if mode_report and mode_report.get("failures"):
        print("Mode classification failures:")
        for f in mode_report["failures"]:
            print(f"  [{f['label']}] expected={f['expected']} got={f['predicted']} | {f['query'][:70]}")
        print()

    if retrieval_report and retrieval_report.get("misses"):
        print("Retrieval misses:")
        for r in retrieval_report["misses"]:
            print(f"  [{r['label']}] expected={r['expected_sources']}")
            print(f"              got={r['returned_sources']}")
        print()

    summary = {
        "run_at":      datetime.now(timezone.utc).isoformat(),
        "credentials": creds,
        "scores":      scores,
        "thresholds":  THRESHOLDS,
        "details": {
            "mode":           mode_report,
            "retrieval":      retrieval_report,
            "answer_quality": answer_report,
        },
    }

    out = Path(output_path) if output_path else REPORTS_DIR / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    print(f"Report saved: {out}")
    print(f"Result: {'ALL PASS' if not any_fail else 'SOME FAILURES'}\n")
    return 1 if any_fail else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full progsu eval suite")
    parser.add_argument("--output", help="JSON report output path")
    args = parser.parse_args()
    sys.exit(main(args.output))
