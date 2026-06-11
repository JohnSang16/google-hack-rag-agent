import base64
import logging
import os
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
]

OAUTH_TOKEN_FILE = next(
    (p for p in [
        "/secrets/drive_oauth_token.json",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "drive_oauth_token.json")),
    ] if os.path.exists(p)),
    None,
)

DEFAULT_RECIPIENT = os.getenv("GMAIL_DEMO_RECIPIENT", "")

# Detects explicit "send [plan/this/brief] to [someone]" intent
_SEND_TO_RE = re.compile(
    r'\b(send|email|forward)\b.{0,60}\bto\b.{1,50}\b(sponsor|team|exec|club|email|member|lead|everyone|them)',
    re.IGNORECASE,
)
_SEND_TARGET_RE = re.compile(
    r'\b(send|email|forward)\b.{0,30}\b(sponsor|exec\s+team|club\s+members)',
    re.IGNORECASE,
)


def is_send_to_email_intent(query: str) -> bool:
    """Return True if the user is explicitly asking to send a plan/brief to someone."""
    q = query.strip()
    return bool(_SEND_TO_RE.search(q) or _SEND_TARGET_RE.search(q))


def _get_service():
    if not OAUTH_TOKEN_FILE:
        raise RuntimeError("OAuth token not found for Gmail API")
    creds = Credentials.from_authorized_user_file(OAUTH_TOKEN_FILE, SCOPES)
    return build("gmail", "v1", credentials=creds)


def _make_html(body: str) -> str:
    """Convert plain text body to HTML with clickable links."""
    escaped = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    linked = re.sub(r'(https?://[^\s]+)', r'<a href="\1">\1</a>', escaped)
    return f"<html><body style='font-family:sans-serif;line-height:1.6'>{linked.replace(chr(10), '<br>')}</body></html>"


def create_gmail_draft(
    subject: str,
    body: str,
    to: Optional[str] = None,
) -> dict:
    """
    Create a Gmail draft.

    Returns dict with: draft_id, draft_url, subject, to.
    """
    recipient = to or DEFAULT_RECIPIENT
    if not recipient:
        raise ValueError("No recipient specified and GMAIL_DEMO_RECIPIENT not set in environment")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["To"] = recipient
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(_make_html(body), "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    try:
        service = _get_service()
        draft = service.users().drafts().create(
            userId="me",
            body={"message": {"raw": raw}},
        ).execute()
        draft_id = draft["id"]
        draft_url = f"https://mail.google.com/mail/u/0/#drafts/{draft_id}"
        logger.info("Created Gmail draft: %s → %s", subject, draft_id)
        return {
            "draft_id":  draft_id,
            "draft_url": draft_url,
            "subject":   subject,
            "to":        recipient,
        }
    except Exception as e:
        raise RuntimeError(f"Gmail draft creation failed: {e}") from e


def send_gmail_draft(draft_id: str) -> str:
    """Send an existing Gmail draft by ID. Returns message_id."""
    try:
        service = _get_service()
        result = service.users().drafts().send(
            userId="me",
            body={"id": draft_id},
        ).execute()
        message_id = result.get("id", "")
        logger.info("Sent Gmail draft %s → message %s", draft_id, message_id)
        return message_id
    except Exception as e:
        raise RuntimeError(f"Gmail send failed: {e}") from e


def delete_gmail_draft(draft_id: str) -> None:
    """Delete a Gmail draft by ID. Used for test cleanup."""
    try:
        service = _get_service()
        service.users().drafts().delete(userId="me", id=draft_id).execute()
        logger.info("Deleted Gmail draft: %s", draft_id)
    except Exception as e:
        logger.warning("Could not delete Gmail draft %s: %s", draft_id, e)


def build_plan_email_body(query: str, summary: str, doc_url: Optional[str], event_url: Optional[str]) -> str:
    """Build the email body for a PLAN mode draft."""
    lines = [
        "Hi team,",
        "",
        "The progsu Intelligence Agent has prepared a planning brief for:",
        f'"{query}"',
        "",
        "Summary:",
        summary,
        "",
    ]
    if doc_url:
        lines += [f"Full Planning Brief: {doc_url}", ""]
    if event_url:
        lines += [f"Kickoff Event (Calendar): {event_url}", ""]
    lines += [
        "This brief was generated from progsu's org knowledge base.",
        "Feel free to reply with questions or edits.",
        "",
        "progsu Intelligence Agent",
    ]
    return "\n".join(lines)
