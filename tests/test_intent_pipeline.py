"""
Pins Section 3: the structured intent classifier and the unified pipeline.

- classify_intent failure can never trigger an action (flags all false)
- CHAT regex fast path costs no Gemini call
- run() is a pure consumer of run_stream and returns the done event's payload
"""
import asyncio
import json
from unittest.mock import MagicMock

import pytest

from src.agent import agent
from src.agent.mode_classifier import _FALLBACK_INTENT, classify_intent, classify_mode


def _client_returning(text):
    client = MagicMock()
    response = MagicMock()
    response.text = text
    client.models.generate_content.return_value = response
    return client


def _failing_client():
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError("gemini down")
    return client


def test_intent_parses_structured_response():
    payload = {"mode": "PLAN", "wants_calendar": True, "wants_email": False, "send_now": False}
    intent = classify_intent("draft a brief and schedule it", _client_returning(json.dumps(payload)))
    assert intent == payload


def test_intent_failure_degrades_to_recall_with_no_actions():
    intent = classify_intent("draft a brief on our sponsor strategy", _failing_client())
    assert intent == _FALLBACK_INTENT
    assert not intent["wants_email"] and not intent["send_now"]


def test_intent_invalid_mode_degrades_safely():
    payload = {"mode": "DESTROY", "wants_calendar": True, "wants_email": True, "send_now": True}
    intent = classify_intent("q", _client_returning(json.dumps(payload)))
    assert intent == _FALLBACK_INTENT


def test_chat_fast_path_skips_gemini():
    client = _failing_client()
    intent = classify_intent("hello there, what can you do", client)
    assert intent["mode"] == "CHAT"
    client.models.generate_content.assert_not_called()


def test_classify_mode_wraps_intent():
    payload = {"mode": "ANALYZE", "wants_calendar": False, "wants_email": False, "send_now": False}
    assert classify_mode("how has attendance grown", _client_returning(json.dumps(payload))) == "ANALYZE"


def test_run_consumes_run_stream(monkeypatch):
    async def fake_stream(query, filters=None, history=None, client=None, access=None):
        yield {"type": "mode", "mode": "RECALL"}
        yield {"type": "token", "content": "Hello "}
        yield {"type": "token", "content": "world"}
        yield {"type": "done", "mode": "RECALL", "answer": "Hello world",
               "citations": [{"title": "t"}], "created_doc_url": None, "summary": None}

    monkeypatch.setattr(agent, "run_stream", fake_stream)
    result = asyncio.run(agent.run("test query", client=MagicMock()))
    assert result["mode"] == "RECALL"
    assert result["answer"] == "Hello world"
    assert result["citations"] == [{"title": "t"}]


def test_run_falls_back_to_tokens_without_done_event(monkeypatch):
    async def fake_stream(query, filters=None, history=None, client=None, access=None):
        yield {"type": "mode", "mode": "RECALL"}
        yield {"type": "token", "content": "partial answer"}

    monkeypatch.setattr(agent, "run_stream", fake_stream)
    result = asyncio.run(agent.run("test query", client=MagicMock()))
    assert result["answer"] == "partial answer"
