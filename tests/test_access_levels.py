"""
Pins ingestion-time access classification and its query-time enforcement.

The fix this protects: "the venue cost us a lot of stress" must reach members
(tagged member at ingestion despite matching the keyword "cost"), while real
figures stay exec-only, served redacted when a redaction exists.
"""
import json
from unittest.mock import MagicMock

from src.financial_signals import has_financial_signals
from src.ingestion.access_classifier import ACCESS_EXEC, ACCESS_MEMBER, classify_chunk_access
from src.agent.agent import _filter_sensitive_chunks


def _client_returning(payload):
    client = MagicMock()
    response = MagicMock()
    response.text = json.dumps(payload)
    client.models.generate_content.return_value = response
    return client


# --- Trigger: no signals means no LLM call, zero cost ---

def test_clean_chunk_skips_llm_entirely():
    client = MagicMock()
    verdict = classify_chunk_access("we planned the venue walkthrough for friday", client)
    assert verdict == {"level": ACCESS_MEMBER, "redacted": None}
    client.models.generate_content.assert_not_called()


def test_known_financial_doc_skips_llm():
    client = MagicMock()
    verdict = classify_chunk_access("row of bookkeeping data $500", client, known_financial=True)
    assert verdict == {"level": ACCESS_EXEC, "redacted": None}
    client.models.generate_content.assert_not_called()


# --- Judge: figurative money words get cleared, real figures restricted ---

def test_figurative_cost_judged_member():
    client = _client_returning({"financial": False, "redacted": None})
    verdict = classify_chunk_access("the venue cost us a lot of stress", client)
    assert verdict["level"] == ACCESS_MEMBER


def test_real_figures_judged_exec_with_redaction():
    client = _client_returning({"financial": True, "redacted": "sponsorship came in at [amount]"})
    verdict = classify_chunk_access("sponsorship came in at $20,000", client)
    assert verdict == {"level": ACCESS_EXEC, "redacted": "sponsorship came in at [amount]"}


def test_judge_failure_restricts_not_leaks():
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError("down")
    verdict = classify_chunk_access("budget details $500", client)
    assert verdict["level"] == ACCESS_EXEC


# --- Query-time enforcement ---

def _chunk(text, access_level=None, redacted=None):
    c = {"text": text, "metadata": {"file_title": "t", "doc_type": "meeting_notes"}}
    if access_level:
        c["metadata"]["access_level"] = access_level
    if redacted:
        c["redacted_text"] = redacted
    return c


def test_member_tagged_chunk_passes_despite_keyword():
    chunks = [_chunk("the venue cost us a lot of stress", access_level="member")]
    assert _filter_sensitive_chunks(chunks, restrict_financial=True) == chunks


def test_exec_tagged_chunk_served_redacted():
    chunks = [_chunk("sponsorship came in at $20,000", access_level="exec",
                     redacted="sponsorship came in at [amount]")]
    out = _filter_sensitive_chunks(chunks, restrict_financial=True)
    assert len(out) == 1
    assert out[0]["text"] == "sponsorship came in at [amount]"


def test_exec_tagged_chunk_without_redaction_dropped():
    chunks = [_chunk("raw bookkeeping row $500", access_level="exec")]
    assert _filter_sensitive_chunks(chunks, restrict_financial=True) == []


def test_untagged_legacy_chunk_falls_back_to_keyword_scan():
    financial = _chunk("so that saves us like $1200")
    clean = _chunk("parking was at the G Deck")
    out = _filter_sensitive_chunks([financial, clean], restrict_financial=True)
    assert out == [clean]


def test_unrestricted_tier_gets_full_text():
    chunks = [_chunk("sponsorship came in at $20,000", access_level="exec",
                     redacted="sponsorship came in at [amount]")]
    out = _filter_sensitive_chunks(chunks, restrict_financial=False)
    assert out[0]["text"] == "sponsorship came in at $20,000"


def test_signals_trigger_matches_expected_cases():
    assert has_financial_signals("the budget was tight")
    assert has_financial_signals("saves us like $1200")
    assert not has_financial_signals("we met at the library")
