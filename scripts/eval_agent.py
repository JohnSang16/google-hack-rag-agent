#!/usr/bin/env python3
"""
progsu Agent Eval Pipeline

Runs test cases against the live agent API, judges each response on
criteria you define, and prints a scored report.

USAGE:
    python3 scripts/eval_agent.py
    python3 scripts/eval_agent.py --api https://your-cloud-run-url
    python3 scripts/eval_agent.py --case q1 q3
    python3 scripts/eval_agent.py --output results.json

CONFIGURE:
    Edit CRITERIA and TEST_CASES below. Nothing else needs to change.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv
from google import genai

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# CRITERIA — edit these. Each criterion has:
#   description: what the judge looks for
#   weight:      how much it counts toward the weighted score (1.0 = normal)
# ─────────────────────────────────────────────────────────────────────────────

CRITERIA: dict[str, dict] = {
    # ── Retrieval quality ──────────────────────────────────────────────────────
    "topic_relevance": {
        "description": (
            "Does the answer stay on topic and directly address what was asked? "
            "Penalize drift to unrelated content (e.g. brag docs when asked about logistics). "
            "For follow-up queries, penalize if the agent lost the thread from the previous turn."
        ),
        "weight": 2.0,
    },
    "grounded_in_sources": {
        "description": (
            "Are ALL specific claims backed by the retrieved sources shown in citations? "
            "Penalize any invented facts, invented statistics, or details not traceable to a source. "
            "This is the hallucination check: a 0 means the agent fabricated something; "
            "a 10 means every claim has clear evidence in the retrieved context."
        ),
        "weight": 2.5,
    },
    "citation_quality": {
        "description": (
            "Are citations actually useful? Penalize: citing a source but not drawing from it, "
            "zero citations on a factual claim, or citing Discord when the content clearly came "
            "from a Drive doc. A good citation directly supports the specific claim it annotates."
        ),
        "weight": 1.5,
    },
    "uncertainty_handling": {
        "description": (
            "Does the agent admit when it does not know rather than guessing? "
            "If context is missing or thin, the agent should say so explicitly rather than "
            "filling gaps with plausible-sounding invented details. "
            "Penalize confident-sounding answers that outrun the available evidence."
        ),
        "weight": 1.5,
    },
    # ── Response quality ───────────────────────────────────────────────────────
    "no_wrong_attribution": {
        "description": (
            "Does the answer avoid attributing content to wrong people? "
            "Claims should go to teams or roles, not first names of meeting attendees. "
            "Penalize surfacing 'Uyi said' or 'MJ recommended' from meeting notes."
        ),
        "weight": 1.5,
    },
    "appropriate_detail": {
        "description": (
            "Is the detail level right? Summary first, then specifics. Not padded. "
            "Not surface-level. No unnecessary repetition. "
            "Penalize answers that are either too vague to be useful or too long to digest."
        ),
        "weight": 1.0,
    },
    "consolidation": {
        "description": (
            "Are closely related points merged into one bullet rather than split? "
            "Penalize if the same underlying issue appears as multiple separate bullets "
            "(e.g. parking + navigation as two bullets when they are one problem)."
        ),
        "weight": 1.0,
    },
    "naming_conventions": {
        "description": (
            "Does the answer use 'Hacklanta 1' for the Spring 2026 event "
            "and 'Hacklanta II' for future planning? Penalize any other form."
        ),
        "weight": 0.5,
    },
    "tone_and_clarity": {
        "description": (
            "Is the language plain, direct, and conversational? "
            "Could a new member follow it without prior context? "
            "Penalize academic padding, jargon without explanation, or generic filler advice."
        ),
        "weight": 1.0,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# TEST CASES — edit these. Each case has:
#   id:             short identifier used for filtering (--case q1)
#   query:          what gets sent to the agent
#   history:        list of prior turns [{role, content}] — empty for fresh queries
#   mode_expected:  RECALL / ANALYZE / PLAN (or None to skip mode check)
#   notes:          human context for the judge — what should a good answer cover?
# ─────────────────────────────────────────────────────────────────────────────

TEST_CASES: list[dict] = [
    {
        "id": "q1",
        "query": "What were the key logistics challenges at Hacklanta and how did we solve them?",
        "history": [],
        "mode_expected": "RECALL",
        "notes": (
            "Should cover: parking change to G deck, QR code reliability check, check-in flow "
            "for different attendee types, signage, breakfast pickup. "
            "Should call it Hacklanta 1. Should convey real difficulty/stress, not just solutions. "
            "Parking and navigation are one problem, not two. "
            "Should not over-focus on one person (Phillip)."
        ),
    },
    {
        "id": "q2",
        "query": "How has our event attendance grown from Fall 2025 to Spring 2026, and which events drove the most engagement?",
        "history": [],
        "mode_expected": "ANALYZE",
        "notes": (
            "Should return real numbers: 107 (Sept), 183 (Oct), 215 (Nov), 157 (Feb 2026). "
            "Should include a markdown table. "
            "Should cite Combined Attendance aggregate as source. "
            "Should identify HackJam/Workshop series and November as peaks."
        ),
    },
    {
        "id": "q3",
        "query": "Draft a planning brief for our next major hackathon based on everything we learned from Hacklanta.",
        "history": [],
        "mode_expected": "PLAN",
        "notes": (
            "Should produce a structured doc with ## sections. "
            "Every recommendation should be grounded in Hacklanta 1 specifics, not generic advice. "
            "Should reference real outcomes: 400+ attendees, parking issues, check-in flow, sponsorship. "
            "Should create a Google Doc (created_doc_url should not be null)."
        ),
    },
    {
        "id": "q1_followup",
        "query": "go more in depth and give me something actionable for next time",
        "history": [
            {
                "role": "user",
                "content": "What were the key logistics challenges at Hacklanta and how did we solve them?",
            },
            {
                "role": "agent",
                "content": (
                    "At Hacklanta 1, we faced several key logistics challenges, primarily around "
                    "parking and venue navigation, check-in technology reliability, and managing "
                    "different attendee flows."
                ),
            },
        ],
        "mode_expected": "PLAN",
        "notes": (
            "This is a follow-up. The agent should understand it's still about Hacklanta 1 logistics "
            "and NOT drift to brag docs, content quality, or soft skills. "
            "Should produce actionable Hacklanta II planning recommendations specific to logistics."
        ),
    },
    {
        "id": "q_discord",
        "query": "What was the team coordinating on Discord leading up to Hacklanta?",
        "history": [],
        "mode_expected": "RECALL",
        "notes": (
            "Should pull from Discord #hacklanta or #operations channels. "
            "Should cite Discord source with a real discord_url. "
            "Should describe real coordination items, not generic team activity."
        ),
    },
    {
        "id": "q_hallucination",
        "query": "What were the exact dollar amounts paid to each individual vendor at Hacklanta and their contact emails?",
        "history": [],
        "mode_expected": "RECALL",
        "notes": (
            "This is a hallucination trap. The org data does NOT contain per-vendor payment "
            "breakdowns or vendor email addresses (PII stripped). "
            "A good agent should say it does not have that level of detail rather than "
            "inventing figures or emails. Score uncertainty_handling a 10 if it admits "
            "the gap; score it 0 if it invents specific numbers or contact details."
        ),
    },
    {
        "id": "q_out_of_scope",
        "query": "What is the best way to raise a Series A for a student startup?",
        "history": [],
        "mode_expected": "RECALL",
        "notes": (
            "Completely out of scope for the progsu knowledge base. "
            "A good agent should say it does not have relevant org data on this topic "
            "rather than giving generic startup advice. "
            "Penalize any answer that invents progsu-specific startup fundraising history."
        ),
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# PASSING THRESHOLD — responses below this weighted score are flagged as FAIL
# ─────────────────────────────────────────────────────────────────────────────

PASS_THRESHOLD = 7.0

# ─────────────────────────────────────────────────────────────────────────────
# JUDGE PROMPT — modify if you want to change how the judge reasons
# ─────────────────────────────────────────────────────────────────────────────

JUDGE_PROMPT = """You are evaluating a response from an AI knowledge-base agent for progsu, a student tech org at GSU.

Query asked:
{query}

{history_section}Agent response:
{answer}

Sources cited:
{citations}

---

Score this response on each criterion from 0 to 10:

{criteria_block}

Hallucination detection rules:
- A claim is hallucinated if it cannot be traced to the retrieved context shown above.
- Invented statistics, made-up dates, and plausible-but-absent details all count as hallucinations.
- Fluent, confident-sounding language does NOT make a claim grounded — only source evidence does.
- If the agent said "I don't have enough information" when context was thin, reward that as good uncertainty handling.
- If the agent invented details to fill a gap, penalize grounded_in_sources AND uncertainty_handling.

Other grading notes:
- The first Hacklanta event (Spring 2026) should be called "Hacklanta 1". Future events = "Hacklanta II".
- Attribution should go to teams or roles, not first names of meeting attendees.
- Follow-up queries should stay on the topic established in the conversation history.

Evaluator context (what a good answer should cover):
{notes}

Respond with ONLY valid JSON — no markdown fences:
{
  "scores": {
    "criterion_name": <0-10>,
    ...
  },
  "feedback": {
    "criterion_name": "one sentence on why you gave this score",
    ...
  },
  "overall_notes": "2-3 sentences on the response quality and the most important improvement"
}"""


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE — nothing below here needs editing for normal use
# ─────────────────────────────────────────────────────────────────────────────

def _build_criteria_block() -> str:
    lines = []
    for name, cfg in CRITERIA.items():
        lines.append(f"  {name} (weight {cfg['weight']}): {cfg['description']}")
    return "\n".join(lines)


def _weighted_score(scores: dict[str, float]) -> float:
    total_weight = sum(CRITERIA[k]["weight"] for k in scores if k in CRITERIA)
    if total_weight == 0:
        return 0.0
    weighted_sum = sum(
        scores[k] * CRITERIA[k]["weight"] for k in scores if k in CRITERIA
    )
    return round(weighted_sum / total_weight, 1)


def call_agent(api_base: str, case: dict) -> Optional[dict]:
    url = f"{api_base.rstrip('/')}/chat"
    payload = {"query": case["query"]}
    if case.get("history"):
        payload["history"] = case["history"]
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  ERROR calling agent: {e}")
        return None


def judge_response(result: dict, case: dict, gemini_client: genai.Client) -> Optional[dict]:
    history_section = ""
    if case.get("history"):
        lines = ["Conversation history (context for this query):"]
        for turn in case["history"]:
            role = turn["role"].capitalize()
            lines.append(f"  {role}: {turn['content'][:300]}")
        history_section = "\n".join(lines) + "\n\n"

    citations_text = "\n".join(
        f"  - {c.get('title', '?')} ({c.get('date', 'n/a')}) — relevance {c.get('relevance_score', '?')}/10"
        for c in result.get("citations", [])
    ) or "  (none)"

    prompt = (
        JUDGE_PROMPT
        .replace("{query}", case["query"])
        .replace("{history_section}", history_section)
        .replace("{answer}", result.get("answer", "")[:1200])
        .replace("{citations}", citations_text)
        .replace("{criteria_block}", _build_criteria_block())
        .replace("{notes}", case.get("notes", "No additional context provided."))
    )

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
                max_output_tokens=4096,
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"  ERROR from judge: {e}")
        return None


def print_report(results: list[dict]) -> None:
    width = 80
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("=" * width)
    print(f"progsu Agent Eval Report — {now}")
    print("=" * width)

    for r in results:
        case = r["case"]
        result = r.get("result")
        evaluation = r.get("evaluation")

        print(f"\nTEST CASE: {case['id']}  —  \"{case['query'][:65]}\"")

        if result is None:
            print("  STATUS: AGENT CALL FAILED")
            print("-" * width)
            continue

        mode_got = result.get("mode", "?")
        mode_exp = case.get("mode_expected")
        mode_ok = "✓" if not mode_exp or mode_got == mode_exp else "✗"
        expected_str = f" (expected: {mode_exp})" if mode_exp else ""
        print(f"  Mode: {mode_got}{expected_str} {mode_ok}")
        print(f"  Citations: {len(result.get('citations', []))}")
        if result.get("created_doc_url"):
            print(f"  Google Doc: {result['created_doc_url']}")
        print(f"  Latency: {r.get('latency_s', '?'):.1f}s")

        if evaluation is None:
            print("  STATUS: JUDGE CALL FAILED")
            print("-" * width)
            continue

        scores = evaluation.get("scores", {})
        feedback = evaluation.get("feedback", {})
        weighted = _weighted_score(scores)
        passed = weighted >= PASS_THRESHOLD
        status = "PASS" if passed else "FAIL"

        print()
        print("  SCORES:")
        for criterion, cfg in CRITERIA.items():
            score = scores.get(criterion, "?")
            fb = feedback.get(criterion, "")
            bar = "█" * int(score) + "░" * (10 - int(score)) if isinstance(score, (int, float)) else ""
            print(f"    {criterion:<28} {str(score):>3}/10  {bar}  {fb}")

        print()
        print(f"  WEIGHTED SCORE: {weighted}/10  [{status}]  (threshold: {PASS_THRESHOLD})")
        print()
        notes = evaluation.get("overall_notes", "")
        if notes:
            # Word-wrap at 74 chars
            words = notes.split()
            line = "  JUDGE: "
            for word in words:
                if len(line) + len(word) + 1 > 78:
                    print(line)
                    line = "          " + word
                else:
                    line += (" " if line.strip() else "") + word
            print(line)
        print("-" * width)

    print("\nSUMMARY")
    total = len(results)
    passed_n = sum(1 for r in results if (r.get("weighted_score") or 0) >= PASS_THRESHOLD)
    for r in results:
        ws = r.get("weighted_score")
        status = "PASS" if ws and ws >= PASS_THRESHOLD else "FAIL"
        flag = "  ← flagged" if status == "FAIL" else ""
        ws_str = f"{ws}/10" if ws is not None else "error"
        print(f"  {r['case']['id']:<20} {ws_str:<10} {status}{flag}")
    overall = sum(r.get("weighted_score", 0) for r in results if r.get("weighted_score")) / max(total, 1)
    print(f"\n  Overall average: {overall:.1f}/10 — {passed_n}/{total} passed")
    print("=" * width)


def main():
    parser = argparse.ArgumentParser(description="progsu agent eval pipeline")
    parser.add_argument("--api", default="http://localhost:8000", help="Agent API base URL")
    parser.add_argument("--case", nargs="*", help="Run only these case IDs (e.g. --case q1 q3)")
    parser.add_argument("--output", help="Write full results to this JSON file")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)
    gemini_client = genai.Client(api_key=api_key)

    cases = TEST_CASES
    if args.case:
        cases = [c for c in TEST_CASES if c["id"] in args.case]
        if not cases:
            print(f"No matching cases for: {args.case}")
            sys.exit(1)

    print(f"Running {len(cases)} test case(s) against {args.api}\n")

    all_results = []
    for case in cases:
        print(f"Running: {case['id']} ...", end="", flush=True)
        t0 = time.time()
        result = call_agent(args.api, case)
        latency = round(time.time() - t0, 1)
        print(f" {latency}s — judging ...", end="", flush=True)

        evaluation = None
        weighted = None
        if result:
            evaluation = judge_response(result, case, gemini_client)
            if evaluation:
                weighted = _weighted_score(evaluation.get("scores", {}))

        print(f" {weighted}/10" if weighted else " judge failed")

        all_results.append({
            "case": case,
            "result": result,
            "evaluation": evaluation,
            "weighted_score": weighted,
            "latency_s": latency,
        })

    print()
    print_report(all_results)

    if args.output:
        with open(args.output, "w") as f:
            # Serialize without the full agent answer to keep it readable
            slim = [
                {
                    "id": r["case"]["id"],
                    "query": r["case"]["query"],
                    "mode": r["result"]["mode"] if r.get("result") else None,
                    "latency_s": r["latency_s"],
                    "weighted_score": r["weighted_score"],
                    "scores": r["evaluation"]["scores"] if r.get("evaluation") else None,
                    "feedback": r["evaluation"]["feedback"] if r.get("evaluation") else None,
                    "overall_notes": r["evaluation"]["overall_notes"] if r.get("evaluation") else None,
                }
                for r in all_results
            ]
            json.dump(slim, f, indent=2)
        print(f"\nResults written to {args.output}")


if __name__ == "__main__":
    main()
