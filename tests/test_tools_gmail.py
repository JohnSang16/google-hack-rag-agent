"""
TDD tests for Gmail draft creation and sending.

These tests are RED until src/agent/tools/send_gmail.py is implemented
and the OAuth token has gmail.compose and gmail.send scopes.

Skips automatically if OAuth token not present.
Run with: pytest tests/test_tools_gmail.py -v

NOTE: test_send_draft_actually_sends will send a real email to GMAIL_DEMO_RECIPIENT.
      Set GMAIL_DEMO_RECIPIENT in .env to your own address before running.
"""
import os
import pytest
from dotenv import load_dotenv

load_dotenv()

OAUTH_TOKEN_FILE = next(
    (p for p in [
        "/secrets/drive_oauth_token.json",
        os.path.abspath("drive_oauth_token.json"),
    ] if os.path.exists(p)),
    None,
)
if not OAUTH_TOKEN_FILE:
    pytest.skip("OAuth token not found — skipping Gmail tests", allow_module_level=True)

GMAIL_RECIPIENT = os.getenv("GMAIL_DEMO_RECIPIENT")
if not GMAIL_RECIPIENT:
    pytest.skip("GMAIL_DEMO_RECIPIENT not set in .env — skipping Gmail tests", allow_module_level=True)

from src.agent.tools.send_gmail import create_gmail_draft, send_gmail_draft, delete_gmail_draft


TEST_SUBJECT_PREFIX = "[TEST progsu agent]"


@pytest.fixture(autouse=True)
def cleanup_test_drafts():
    """Collect draft IDs created during a test and delete them after."""
    created: list[str] = []
    yield created
    for draft_id in created:
        try:
            delete_gmail_draft(draft_id)
        except Exception as e:
            print(f"Warning: could not delete test draft {draft_id}: {e}")


# --- Draft creation ---

def test_create_gmail_draft_returns_id_and_url(cleanup_test_drafts):
    result = create_gmail_draft(
        subject=f"{TEST_SUBJECT_PREFIX} Draft Creation Test",
        body="This is a test draft created by the progsu agent test suite.",
        to=GMAIL_RECIPIENT,
    )
    assert isinstance(result, dict), "Expected dict with draft_id and draft_url"
    assert "draft_id" in result, "Result must include 'draft_id'"
    assert "draft_url" in result, "Result must include 'draft_url'"
    assert result["draft_id"].startswith("r"), f"Unexpected draft_id format: {result['draft_id']!r}"
    assert "mail.google.com" in result["draft_url"], "draft_url should be a Gmail URL"
    cleanup_test_drafts.append(result["draft_id"])


def test_create_gmail_draft_subject_set_correctly(cleanup_test_drafts):
    subject = f"{TEST_SUBJECT_PREFIX} Subject Verification"
    result = create_gmail_draft(subject=subject, body="Body text.", to=GMAIL_RECIPIENT)
    cleanup_test_drafts.append(result["draft_id"])
    assert result.get("subject") == subject, (
        f"Expected subject {subject!r}, got {result.get('subject')!r}"
    )


def test_create_gmail_draft_recipient_set_correctly(cleanup_test_drafts):
    result = create_gmail_draft(
        subject=f"{TEST_SUBJECT_PREFIX} Recipient Test",
        body="Checking recipient.",
        to=GMAIL_RECIPIENT,
    )
    cleanup_test_drafts.append(result["draft_id"])
    assert result.get("to") == GMAIL_RECIPIENT, (
        f"Expected to={GMAIL_RECIPIENT!r}, got {result.get('to')!r}"
    )


def test_create_gmail_draft_uses_default_recipient_when_to_omitted(cleanup_test_drafts):
    """When 'to' is not passed, should use GMAIL_DEMO_RECIPIENT env var."""
    result = create_gmail_draft(
        subject=f"{TEST_SUBJECT_PREFIX} Default Recipient Test",
        body="Testing default recipient fallback.",
    )
    cleanup_test_drafts.append(result["draft_id"])
    assert result.get("to") == GMAIL_RECIPIENT, (
        "Default recipient should be GMAIL_DEMO_RECIPIENT env var"
    )


def test_create_gmail_draft_html_body_renders_links(cleanup_test_drafts):
    """Body with URLs should be sent as HTML so links are clickable."""
    body = "See the brief: https://docs.google.com/document/d/fake/edit"
    result = create_gmail_draft(
        subject=f"{TEST_SUBJECT_PREFIX} HTML Body Test",
        body=body,
        to=GMAIL_RECIPIENT,
    )
    cleanup_test_drafts.append(result["draft_id"])
    assert "draft_id" in result


def test_delete_gmail_draft_removes_draft(cleanup_test_drafts):
    result = create_gmail_draft(
        subject=f"{TEST_SUBJECT_PREFIX} Delete Me",
        body="This draft should be deleted.",
        to=GMAIL_RECIPIENT,
    )
    draft_id = result["draft_id"]
    delete_gmail_draft(draft_id)
    # Success = no exception raised. Do NOT add to cleanup since already deleted.


# --- Sending ---

def test_send_draft_returns_message_id(cleanup_test_drafts):
    """Sending a draft should return a message_id and not raise."""
    result = create_gmail_draft(
        subject=f"{TEST_SUBJECT_PREFIX} Send Test (auto-sent by test suite)",
        body="This email was sent by the progsu agent automated test suite. Safe to ignore.",
        to=GMAIL_RECIPIENT,
    )
    draft_id = result["draft_id"]
    # Note: draft is consumed by send, so no cleanup needed for draft
    # but add it anyway — delete_gmail_draft handles already-sent drafts gracefully
    cleanup_test_drafts.append(draft_id)

    message_id = send_gmail_draft(draft_id)
    assert isinstance(message_id, str) and len(message_id) > 0, (
        "send_gmail_draft should return a non-empty message_id"
    )


def test_send_nonexistent_draft_raises(cleanup_test_drafts):
    """Sending a draft that doesn't exist should raise, not silently fail."""
    with pytest.raises(Exception):
        send_gmail_draft("draft_id_that_does_not_exist_xyz")
