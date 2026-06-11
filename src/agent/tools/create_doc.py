import logging
import os
import re
from datetime import datetime

from dotenv import load_dotenv
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

PLAN_OUTPUT_FOLDER_ID = "1_3u5kxsAC91LQyfBOgkVGqlYlHB4a5ou"
DRIVE_FILE_BASE_URL = "https://docs.google.com/document/d/"
OAUTH_TOKEN_FILE = next(
    (p for p in [
        "/secrets/drive_oauth_token.json",        # Cloud Run secret mount
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "drive_oauth_token.json")),  # local dev
    ] if os.path.exists(p)),
    None,
)


def _get_services():
    if OAUTH_TOKEN_FILE and os.path.exists(OAUTH_TOKEN_FILE):
        logger.debug("Using OAuth user credentials for Drive: %s", OAUTH_TOKEN_FILE)
        creds = Credentials.from_authorized_user_file(OAUTH_TOKEN_FILE, SCOPES)
    else:
        logger.debug("Using service account credentials for Drive")
        creds_path = os.environ.get("GOOGLE_DRIVE_CREDENTIALS", "./service_account.json")
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds), build("docs", "v1", credentials=creds)


def _parse_bold(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Strip **text** markers. Returns (clean_text, [(start, end), ...])."""
    result = ""
    ranges = []
    for i, part in enumerate(text.split("**")):
        if i % 2 == 1:
            start = len(result)
            result += part
            ranges.append((start, len(result)))
        else:
            result += part
    return result, ranges


def _parse_line(line: str) -> tuple[str, str, list[tuple[int, int]]]:
    """Returns (clean_text, para_style, bold_ranges)."""
    # Headings — support up to ####
    if line.startswith("#### "):
        text, bolds = _parse_bold(line[5:])
        return text, "HEADING_3", bolds
    if line.startswith("### "):
        text, bolds = _parse_bold(line[4:])
        return text, "HEADING_3", bolds
    if line.startswith("## "):
        text, bolds = _parse_bold(line[3:])
        return text, "HEADING_2", bolds
    if line.startswith("# "):
        text, bolds = _parse_bold(line[2:])
        return text, "HEADING_1", bolds

    # Unordered bullets — `*` or `-` followed by one or more spaces
    bullet_m = re.match(r"^[\*\-]\s+", line)
    if bullet_m:
        text, bolds = _parse_bold(line[bullet_m.end():])
        prefix = "    •  "
        shifted = [(s + len(prefix), e + len(prefix)) for s, e in bolds]
        return prefix + text, "NORMAL_TEXT", shifted

    # Numbered lists — `1.` or `1)` followed by spaces
    num_m = re.match(r"^(\d+)[.)]\s+", line)
    if num_m:
        num = num_m.group(1)
        text, bolds = _parse_bold(line[num_m.end():])
        prefix = f"    {num}.  "
        shifted = [(s + len(prefix), e + len(prefix)) for s, e in bolds]
        return prefix + text, "NORMAL_TEXT", shifted

    text, bolds = _parse_bold(line)
    return text, "NORMAL_TEXT", bolds


def _build_doc_requests(query: str, answer: str, citations: list[dict]) -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")

    # Replace (Source N) in body with actual citation titles
    body = answer
    for i, c in enumerate(citations, 1):
        title = c.get("title", f"Source {i}")
        body = body.replace(f"(Source {i})", f"({title})")

    # Derive H1 title from first heading in the answer, fall back to query
    h1_match = re.search(r'^#\s+(.+)$', answer, re.MULTILINE)
    doc_title = h1_match.group(1).strip() if h1_match else query[:80].rstrip()

    # Build content segments: {'text', 'style', 'bolds', 'link'}
    segs: list[dict] = []

    # Title + query
    segs.append({"text": doc_title, "style": "HEADING_1", "bolds": [], "link": None})
    segs.append({"text": query, "style": "NORMAL_TEXT", "bolds": [], "link": None})
    segs.append({"text": "", "style": "NORMAL_TEXT", "bolds": [], "link": None})

    # Sources at the top
    segs.append({"text": "Sources", "style": "HEADING_2", "bolds": [], "link": None})
    for c in citations:
        title = c.get("title", "Unknown")
        date = c.get("date") or "n/a"
        url = c.get("drive_url") or ""
        segs.append({
            "text": f"    •  {title} ({date})",
            "style": "NORMAL_TEXT",
            "bolds": [],
            "link": url or None,
            "_title_len": len(title),
        })
    segs.append({"text": "", "style": "NORMAL_TEXT", "bolds": [], "link": None})

    # Main content
    for line in body.split("\n"):
        text, style, bolds = _parse_line(line)
        segs.append({"text": text, "style": style, "bolds": bolds, "link": None})

    # Footer
    segs.append({"text": "", "style": "NORMAL_TEXT", "bolds": [], "link": None})
    segs.append({
        "text": f"Generated by progsu Intelligence Agent · {today}",
        "style": "NORMAL_TEXT",
        "bolds": [],
        "link": None,
    })

    # Build full plain text and calculate positions
    full_text = "\n".join(seg["text"] for seg in segs)

    positions: list[int] = []
    pos = 1
    for seg in segs:
        positions.append(pos)
        pos += len(seg["text"]) + 1  # +1 for \n separator

    # Requests
    requests: list[dict] = [
        {"insertText": {"location": {"index": 1}, "text": full_text}}
    ]

    for seg, lpos in zip(segs, positions):
        text = seg["text"]
        if not text:
            continue

        # Paragraph style
        if seg["style"] != "NORMAL_TEXT":
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": lpos, "endIndex": lpos + len(text) + 1},
                    "paragraphStyle": {"namedStyleType": seg["style"]},
                    "fields": "namedStyleType",
                }
            })

        # Bold ranges
        for bs, be in seg["bolds"]:
            if be > bs:
                requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": lpos + bs, "endIndex": lpos + be},
                        "textStyle": {"bold": True},
                        "fields": "bold",
                    }
                })

        # Hyperlink on source title
        if seg.get("link") and seg.get("_title_len"):
            prefix_len = len("    •  ")
            link_start = lpos + prefix_len
            link_end = link_start + seg["_title_len"]
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": link_start, "endIndex": link_end},
                    "textStyle": {
                        "link": {"url": seg["link"]},
                        "foregroundColor": {
                            "color": {"rgbColor": {"red": 0.07, "green": 0.36, "blue": 0.80}}
                        },
                        "underline": True,
                    },
                    "fields": "link,foregroundColor,underline",
                }
            })

    return requests


def create_google_doc(
    query: str,
    answer: str,
    citations: list[dict],
    folder_id: str = PLAN_OUTPUT_FOLDER_ID,
) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"[progsu Agent] {query[:60].rstrip()}, {today}"

    try:
        drive_service, docs_service = _get_services()

        file_meta = {
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
            "parents": [folder_id],
        }
        file = drive_service.files().create(body=file_meta, fields="id").execute()
        doc_id = file["id"]

        requests = _build_doc_requests(query, answer, citations)
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()

        doc_url = f"{DRIVE_FILE_BASE_URL}{doc_id}/edit"
        logger.info("Created Google Doc: %s (%s)", title, doc_url)
        return doc_url

    except Exception as e:
        raise RuntimeError(f"Google Doc creation failed: {e}") from e
