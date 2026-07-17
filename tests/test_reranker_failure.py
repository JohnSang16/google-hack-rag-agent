"""
Pins the reranker-failure vs confidence-gate interaction.

The agent's confidence gate rejects generation when the best relevance_score
is below 5. When the reranker call fails, every chunk gets FAILURE_SCORE.
That default must stay below the gate even after the +1.5 authority boost,
otherwise a reranker outage silently bypasses the gate and every raw vector
hit passes through ungated.
"""
from unittest.mock import MagicMock

from src.retrieval import reranker
from src.retrieval.reranker import (
    FAILURE_SCORE,
    _AUTHORITY_BOOST,
    _batch_score,
    rerank,
)

_GATE_THRESHOLD = 5  # mirrors _LOW_CONFIDENCE_THRESHOLD in src/agent/agent.py


def _chunks(n, file_id=""):
    return [
        {"text": f"chunk {i}", "metadata": {"file_title": f"doc {i}", "file_id": file_id}}
        for i in range(n)
    ]


def _failing_client():
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError("gemini down")
    return client


def _malformed_client():
    client = MagicMock()
    response = MagicMock()
    response.text = '{"not": "a list"}'
    client.models.generate_content.return_value = response
    return client


def test_failure_score_stays_below_gate():
    assert FAILURE_SCORE < _GATE_THRESHOLD


def test_failure_score_plus_authority_boost_stays_below_gate():
    assert FAILURE_SCORE + _AUTHORITY_BOOST < _GATE_THRESHOLD


def test_batch_score_returns_failure_score_on_exception():
    chunks = _chunks(3)
    scores = _batch_score("query", chunks, _failing_client())
    assert scores == [FAILURE_SCORE] * 3


def test_batch_score_returns_failure_score_on_malformed_response():
    chunks = _chunks(3)
    scores = _batch_score("query", chunks, _malformed_client())
    assert scores == [FAILURE_SCORE] * 3


def test_rerank_on_failure_yields_scores_below_gate():
    chunks = _chunks(4)
    results = rerank("query", chunks, client=_failing_client())
    assert results, "rerank still returns fallback chunks"
    assert all(c["relevance_score"] < _GATE_THRESHOLD for c in results)


def test_rerank_on_failure_with_authoritative_chunk_stays_below_gate():
    authoritative_id = next(iter(reranker._AUTHORITATIVE_FILE_IDS))
    chunks = _chunks(2) + _chunks(1, file_id=authoritative_id)
    results = rerank("query", chunks, client=_failing_client())
    assert all(c["relevance_score"] < _GATE_THRESHOLD for c in results)
