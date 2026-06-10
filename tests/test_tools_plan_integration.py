"""
Integration test: full PLAN mode pipeline creates all three artifacts.

Tests the end-to-end flow:
  PLAN query → Google Doc + Calendar event + Gmail draft (all in parallel)

Skips if any required credential or env var is missing.
Run with: pytest tests/test_tools_plan_integration.py -v -s
"""
import asyncio
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
MONGODB_URI = os.getenv("MONGODB_URI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GMAIL_RECIPIENT = os.getenv("GMAIL_DEMO_RECIPIENT")

if not OAUTH_TOKEN_FILE:
    pytest.skip("OAuth token not found", allow_module_level=True)
if not MONGODB_URI:
    pytest.skip("MONGODB_URI not set", allow_module_level=True)
if not GEMINI_API_KEY:
    pytest.skip("GEMINI_API_KEY not set", allow_module_level=True)
if not GMAIL_RECIPIENT:
    pytest.skip("GMAIL_DEMO_RECIPIENT not set", allow_module_level=True)

from src.agent.tools.create_calendar_event import delete_calendar_event
from src.agent.tools.send_gmail import delete_gmail_draft
from src.agent import agent as _agent

PLAN_QUERY = "Draft a planning brief for our next major hackathon based on everything we learned from Hacklanta."


@pytest.fixture(scope="module")
def plan_result():
    """Run the agent once and share the result across all tests in this module."""
    return asyncio.run(_run_plan())


async def _run_plan():
    events = []
    async for event in _agent.run_stream(query=PLAN_QUERY):
        events.append(event)
    done = next((e for e in events if e.get("type") == "done"), None)
    assert done is not None, "run_stream must yield a 'done' event"
    return done


@pytest.fixture(scope="module", autouse=True)
def cleanup_artifacts(plan_result):
    yield
    if plan_result.get("calendar_event_id"):
        try:
            delete_calendar_event(plan_result["calendar_event_id"])
            print(f"Cleaned up calendar event: {plan_result['calendar_event_id']}")
        except Exception as e:
            print(f"Warning: could not delete test calendar event: {e}")
    if plan_result.get("gmail_draft_id"):
        try:
            delete_gmail_draft(plan_result["gmail_draft_id"])
            print(f"Cleaned up Gmail draft: {plan_result['gmail_draft_id']}")
        except Exception as e:
            print(f"Warning: could not delete test draft: {e}")


# --- Mode ---

def test_plan_mode_classified_correctly(plan_result):
    assert plan_result["mode"] == "PLAN", (
        f"Expected mode=PLAN, got {plan_result['mode']!r}"
    )


# --- Google Doc ---

def test_plan_creates_google_doc(plan_result):
    url = plan_result.get("created_doc_url")
    assert url, "PLAN mode must return a created_doc_url"
    assert "docs.google.com" in url, f"Expected a Google Docs URL, got {url!r}"


# --- Calendar event ---

def test_plan_creates_calendar_event(plan_result):
    url = plan_result.get("calendar_event_url")
    assert url, "PLAN mode must return a calendar_event_url"
    assert "calendar.google.com" in url or "google.com/calendar" in url, (
        f"Expected a Google Calendar URL, got {url!r}"
    )


def test_plan_calendar_event_has_id(plan_result):
    event_id = plan_result.get("calendar_event_id")
    assert event_id, "PLAN result must include calendar_event_id for cleanup/management"


def test_plan_calendar_event_date_is_future(plan_result):
    from datetime import datetime
    start_date = plan_result.get("calendar_event_start_date")
    assert start_date, "PLAN result should include calendar_event_start_date"
    parsed = datetime.fromisoformat(start_date[:10])
    assert parsed > datetime.now().replace(hour=0, minute=0, second=0, microsecond=0), (
        "Calendar event should be scheduled in the future"
    )


# --- Gmail draft ---

def test_plan_creates_gmail_draft(plan_result):
    draft_id = plan_result.get("gmail_draft_id")
    assert draft_id, "PLAN mode must return a gmail_draft_id"
    assert len(draft_id) > 0


def test_plan_gmail_draft_has_url(plan_result):
    draft_url = plan_result.get("gmail_draft_url")
    assert draft_url, "PLAN mode must return a gmail_draft_url"
    assert "mail.google.com" in draft_url, f"Expected a Gmail URL, got {draft_url!r}"


# --- Answer quality ---

def test_plan_answer_is_not_empty(plan_result):
    answer = plan_result.get("answer", "")
    assert len(answer) > 200, "PLAN answer should be a substantial document, not a stub"


def test_plan_answer_has_sections(plan_result):
    answer = plan_result.get("answer", "")
    assert "##" in answer, "PLAN answer should have ## section headings"


def test_plan_summary_present(plan_result):
    summary = plan_result.get("summary")
    assert summary, "PLAN result must include a summary for the chat preview"
    assert len(summary) < 600, "Summary should be concise (under 600 chars)"


def test_plan_all_three_artifacts_present(plan_result):
    """Convenience test: verifies all three tools fired successfully."""
    missing = []
    if not plan_result.get("created_doc_url"):
        missing.append("created_doc_url")
    if not plan_result.get("calendar_event_url"):
        missing.append("calendar_event_url")
    if not plan_result.get("gmail_draft_id"):
        missing.append("gmail_draft_id")
    assert not missing, f"Missing artifacts from PLAN mode: {missing}"
