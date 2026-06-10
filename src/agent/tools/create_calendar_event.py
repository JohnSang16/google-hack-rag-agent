import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
]

OAUTH_TOKEN_FILE = next(
    (p for p in [
        "/secrets/drive_oauth_token.json",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "drive_oauth_token.json")),
    ] if os.path.exists(p)),
    None,
)

CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
DEFAULT_DAYS_AHEAD = 14


def _get_service():
    if not OAUTH_TOKEN_FILE:
        raise RuntimeError("OAuth token not found for Calendar API")
    creds = Credentials.from_authorized_user_file(OAUTH_TOKEN_FILE, SCOPES)
    return build("calendar", "v3", credentials=creds)


def _parse_date(date_str: Optional[str]) -> datetime:
    """Parse a date string into a datetime. Falls back to DEFAULT_DAYS_AHEAD on bad/missing input."""
    if date_str:
        for fmt in ["%Y-%m-%d", "%B %d, %Y", "%m/%d/%Y", "%b %d, %Y"]:
            try:
                return datetime.strptime(date_str[:len(fmt)].strip(), fmt)
            except ValueError:
                continue
    return datetime.now() + timedelta(days=DEFAULT_DAYS_AHEAD)


def create_calendar_event(
    title: str,
    description: str,
    suggested_date_str: Optional[str] = None,
    doc_url: Optional[str] = None,
    calendar_id: Optional[str] = None,
) -> dict:
    """
    Create an all-day Google Calendar event.

    Returns dict with: event_id, html_link, start_date, title, description.
    """
    cal_id = calendar_id or CALENDAR_ID
    event_date = _parse_date(suggested_date_str)

    full_description = description
    if doc_url:
        full_description += f"\n\nPlanning Brief: {doc_url}"

    event_body = {
        "summary": title,
        "description": full_description,
        "start": {"date": event_date.strftime("%Y-%m-%d"), "timeZone": "America/New_York"},
        "end":   {"date": event_date.strftime("%Y-%m-%d"), "timeZone": "America/New_York"},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email",  "minutes": 24 * 60},
                {"method": "popup",  "minutes": 30},
            ],
        },
    }

    try:
        service = _get_service()
        event = service.events().insert(calendarId=cal_id, body=event_body).execute()
        logger.info("Created Calendar event: %s (%s)", title, event["htmlLink"])
        return {
            "event_id":    event["id"],
            "html_link":   event["htmlLink"],
            "start_date":  event["start"]["date"],
            "title":       event["summary"],
            "description": event.get("description", ""),
        }
    except Exception as e:
        raise RuntimeError(f"Calendar event creation failed: {e}") from e


def delete_calendar_event(event_id: str, calendar_id: Optional[str] = None) -> None:
    """Delete a Calendar event by ID. Used for test cleanup."""
    cal_id = calendar_id or CALENDAR_ID
    try:
        service = _get_service()
        service.events().delete(calendarId=cal_id, eventId=event_id).execute()
        logger.info("Deleted Calendar event: %s", event_id)
    except Exception as e:
        logger.warning("Could not delete Calendar event %s: %s", event_id, e)
