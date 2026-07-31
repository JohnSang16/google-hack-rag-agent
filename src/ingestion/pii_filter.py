import logging
import os
import re

from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

EXEC_NAMES = [
    "John Sang", "Liam", "Charan", "Natasha", "Jared",
    "Joey", "Carter", "Tyler", "Aaron", "Ibe", "Temi",
    "Eda", "Ishan", "Phillip",
]

SPONSOR_NAMES = [
    "Anthropic", "Google", "Amazon", "Cox Enterprises",
    "Microsoft", "FanDuel", "Mercedes-Benz", "Nexlayer",
]

PII_PATTERNS = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL]"),
    (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]"),
    (r"\b\d{9}\b", "[STUDENT_ID]"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),
]

# Chunks larger than this skip the Gemini name-removal pass
GEMINI_PII_CHAR_LIMIT = 8_000


def strip_pii_regex(text: str) -> str:
    for pattern, replacement in PII_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def _strip_names_gemini(text: str, client: genai.Client) -> str:
    safe_names = ", ".join(EXEC_NAMES + SPONSOR_NAMES)
    prompt = f"""You are a PII redaction assistant. Remove any personal information from the text below.

KEEP these names exactly as-is (public org members and sponsors): {safe_names}

REPLACE any other full person names not in the list above with [REDACTED].
Do not remove or change anything else. Return only the cleaned text with no explanation.

Text:
{text}"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        # Near-empty input (e.g. a 1-char doc) can come back with
        # finish_reason=STOP but zero output tokens, so response.text is None
        # despite no error being raised.
        return response.text if response.text is not None else text
    except Exception as e:
        logger.warning("Gemini PII strip failed, keeping regex result: %s", e)
        return text


def filter_pii(text: str, use_gemini: bool = True, client: genai.Client = None) -> str:
    """
    Full PII filter: regex pass first, then optional Gemini name-removal pass.
    Gemini pass is skipped automatically if text exceeds GEMINI_PII_CHAR_LIMIT.
    """
    text = strip_pii_regex(text)

    if use_gemini:
        if len(text) > GEMINI_PII_CHAR_LIMIT:
            logger.debug("Skipping Gemini PII pass (text too large: %d chars)", len(text))
        else:
            if client is None:
                client = _get_client()
            text = _strip_names_gemini(text, client)

    return text
