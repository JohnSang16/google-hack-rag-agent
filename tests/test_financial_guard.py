"""
Pins the content-level financial data guard.

A doc_type filter alone is not enough: dollar figures mentioned casually in
Discord or meeting-note chunks (never tagged financial) must also be caught.
Live-verified leak this guards against: "How much did Hacklanta cost in total?"
answered with a real figure cited from an untagged Discord chunk.
"""
from src.agent.agent import (
    _ANSWER_PROMPT,
    _FINANCIAL_RULE_INTERNAL,
    _FINANCIAL_RULE_RESTRICTED,
    _STREAM_ANSWER_PROMPT,
    _is_financial_chunk,
    _is_financial_query,
)


def _chunk(text, doc_type="meeting_notes"):
    return {"text": text, "metadata": {"doc_type": doc_type, "file_title": "t"}}


def test_financial_doc_type_is_flagged():
    assert _is_financial_chunk(_chunk("nothing sensitive here", doc_type="financial"))


def test_casual_dollar_amount_in_untagged_chunk_is_flagged():
    assert _is_financial_chunk(_chunk("so that saves us like $1200"))


def test_financial_keyword_in_untagged_chunk_is_flagged():
    assert _is_financial_chunk(_chunk("see the bookkeeping doc for details"))


def test_ordinary_chunk_passes():
    assert not _is_financial_chunk(_chunk("parking was at the G Deck, first come first served"))


def test_financial_query_detected():
    assert _is_financial_query("How much did Hacklanta cost in total?")
    assert _is_financial_query("what was the sponsorship budget")
    assert _is_financial_query("how much money did we raise")


def test_ordinary_query_passes():
    assert not _is_financial_query("What were the key logistics challenges at Hacklanta and how did we solve them?")
    assert not _is_financial_query("How has our event attendance grown from Fall 2025 to Spring 2026, and which events drove the most engagement?")
    assert not _is_financial_query("Draft a planning brief for our next major hackathon based on everything we learned from Hacklanta.")


def test_answer_prompts_format_with_financial_rule():
    for template in (_ANSWER_PROMPT, _STREAM_ANSWER_PROMPT):
        for rule in (_FINANCIAL_RULE_RESTRICTED, _FINANCIAL_RULE_INTERNAL):
            rendered = template.format(
                mode="RECALL",
                query="q",
                context="ctx",
                history_section="",
                financial_rule=rule,
            )
            assert rule in rendered
