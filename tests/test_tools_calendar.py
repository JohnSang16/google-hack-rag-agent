"""
TDD tests for create_calendar_event tool.

These tests are RED until src/agent/tools/create_calendar_event.py is implemented
and the OAuth token has calendar.events scope.

Skips automatically if:
- GOOGLE_CREDENTIALS_MISSING: OAuth token not present or lacks Calendar scope
- Run with: pytest tests/test_tools_calendar.py -v
"""
import os
import pytest
from datetime import datetime, timedelta
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
    pytest.skip("OAuth token not found — skipping Calendar tests", allow_module_level=True)

from src.agent.tools.create_calendar_event import create_calendar_event, delete_calendar_event

TEST_TITLE_PREFIX = "[TEST progsu agent]"


@pytest.fixture(autouse=True)
def cleanup_test_events():
    """Collect event IDs created during a test and delete them after."""
    created: list[str] = []
    yield created
    for event_id in created:
        try:
            delete_calendar_event(event_id)
        except Exception as e:
            print(f"Warning: could not delete test event {event_id}: {e}")


# --- Unit-level: return shape ---

def test_create_calendar_event_returns_html_link(cleanup_test_events):
    result = create_calendar_event(
        title=f"{TEST_TITLE_PREFIX} Kickoff Meeting",
        description="Test event created by progsu agent test suite.",
        suggested_date_str=None,
        doc_url=None,
    )
    assert isinstance(result, dict), "Expected a dict with event_id and html_link"
    assert "event_id" in result, "Result must include 'event_id' for cleanup/send"
    assert "html_link" in result, "Result must include 'html_link' for frontend display"
    assert result["html_link"].startswith("https://"), "html_link must be a URL"
    cleanup_test_events.append(result["event_id"])


def test_create_calendar_event_default_date_is_future(cleanup_test_events):
    """When suggested_date_str is None, event should be ~14 days from now."""
    result = create_calendar_event(
        title=f"{TEST_TITLE_PREFIX} Future Date Test",
        description="Testing default date logic.",
    )
    cleanup_test_events.append(result["event_id"])
    event_date = result.get("start_date")
    assert event_date is not None, "Result should include start_date for verification"
    parsed = datetime.fromisoformat(event_date[:10])
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    assert parsed > today, "Default event date must be in the future"
    assert parsed <= today + timedelta(days=30), "Default date should be within 30 days"


def test_create_calendar_event_respects_suggested_date(cleanup_test_events):
    """Explicit date string should be used as the event date."""
    target = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    result = create_calendar_event(
        title=f"{TEST_TITLE_PREFIX} Explicit Date Test",
        description="Testing explicit date.",
        suggested_date_str=target,
    )
    cleanup_test_events.append(result["event_id"])
    assert result["start_date"][:10] == target, (
        f"Expected event on {target}, got {result['start_date'][:10]}"
    )


def test_create_calendar_event_includes_doc_link_in_description(cleanup_test_events):
    """doc_url should appear somewhere in the event description."""
    doc_url = "https://docs.google.com/document/d/fake_test_id/edit"
    result = create_calendar_event(
        title=f"{TEST_TITLE_PREFIX} Doc Link Test",
        description="See the planning brief for details.",
        doc_url=doc_url,
    )
    cleanup_test_events.append(result["event_id"])
    desc = result.get("description", "")
    assert doc_url in desc, f"Expected doc_url in event description, got: {desc!r}"


def test_create_calendar_event_title_appears_in_result(cleanup_test_events):
    title = f"{TEST_TITLE_PREFIX} Title Verification"
    result = create_calendar_event(title=title, description="Check title.")
    cleanup_test_events.append(result["event_id"])
    assert title in result.get("title", ""), "Event title should be echoed in result"


def test_delete_calendar_event_removes_event(cleanup_test_events):
    """delete_calendar_event should not raise on a valid event ID."""
    result = create_calendar_event(
        title=f"{TEST_TITLE_PREFIX} Delete Me",
        description="This event should be deleted by the test.",
    )
    event_id = result["event_id"]
    delete_calendar_event(event_id)
    # If we get here without exception, deletion succeeded.
    # Do NOT add to cleanup_test_events since it's already deleted.


def test_create_calendar_event_bad_date_falls_back_gracefully(cleanup_test_events):
    """Unparseable date string should fall back to default, not raise."""
    result = create_calendar_event(
        title=f"{TEST_TITLE_PREFIX} Bad Date Fallback",
        description="Testing bad date input.",
        suggested_date_str="not-a-real-date",
    )
    cleanup_test_events.append(result["event_id"])
    assert "event_id" in result, "Should still create an event even with bad date input"
