"""
Unit tests for explicit send-to-email intent detection.

Pure unit tests, no API calls, no env var requirements.
Rewritten 2026-07-17: the original file tested is_send_email_intent (a
two-word "send it" detector) which no longer exists; the current function
is is_send_to_email_intent, which requires an explicit email/recipient
phrasing before the PLAN email path activates.
"""
import pytest

from src.agent.tools.send_gmail import is_send_to_email_intent


# --- Should trigger the send-to-email path ---

@pytest.mark.parametrize("query", [
    "send this to the sponsors",
    "email the brief to the exec team",
    "forward this to club members",
    "send the plan to everyone",
    "send an email to the team",
    "email sponsors the sponsor packet",
    "send the email",
    "email this brief",
])
def test_send_intent_detected(query: str):
    assert is_send_to_email_intent(query), f"Expected True for: {repr(query)}"


# --- Should NOT trigger ---

@pytest.mark.parametrize("query", [
    "What were the key logistics challenges at Hacklanta?",
    "How has our attendance grown?",
    "what is our sponsorship strategy",
    "who is on the exec team",
    "send it",
    "",
    "   ",
])
def test_send_intent_not_detected(query: str):
    assert not is_send_to_email_intent(query), f"Expected False for: {repr(query)}"
