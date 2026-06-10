"""
TDD tests for send-email intent detection.

Pure unit tests — no API calls, no env var requirements.
Run with: pytest tests/test_send_intent.py -v
"""
import pytest

from src.agent.tools.send_gmail import is_send_email_intent


# --- Should trigger send ---

@pytest.mark.parametrize("query", [
    "send the email",
    "send it",
    "go ahead and send",
    "send the draft",
    "ok send it",
    "looks good, send the email",
    "send that email",
    "send it now",
    "yes send",
    "please send the email",
    "Send the email",
    "SEND IT",
])
def test_send_intent_detected(query: str):
    assert is_send_email_intent(query), f"Expected True for: {repr(query)}"


# --- Should NOT trigger send ---

@pytest.mark.parametrize("query", [
    "What were the key logistics challenges at Hacklanta?",
    "Draft a planning brief for our next hackathon",
    "How has our attendance grown?",
    "send me the attendance data",        # 'send me' is a request, not a send command
    "can you send a recap to the team",   # 'send a recap' — could go either way, but safer to exclude
    "what should I send to sponsors",
    "I'll send the email later",          # future tense, not a command
    "",
    "   ",
])
def test_send_intent_not_detected(query: str):
    assert not is_send_email_intent(query), f"Expected False for: {repr(query)}"
