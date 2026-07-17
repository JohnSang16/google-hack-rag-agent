import logging
import os
import re

from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_CHAT_PATTERNS = [
    r'\b(hi|hello|hey|sup|yo)\b',
    r'\b(thanks|thank you|thx|ty)\b',
    r'\bwho are you\b',
    r'\bwhat (can|do|are) you\b',
    r'\bhow do(es)? (this|it) work\b',
    r'\b(give|show|list|tell) me (the )?(example|sample|demo|3|three|those|the)? ?(prompts?|questions?)\b',
    r'\b(example|demo|sample) (prompts?|questions?)\b',
    r'\bprompts? (to try|from earlier|again|you mentioned)\b',
    r'\bi forgot\b',
    r'\bremind me\b',
    r'\bwhat (were|are) the (3|three|example|demo|default)\b',
    r'\bwhat (else )?can i ask\b',
]

_CHAT_RE = re.compile('|'.join(_CHAT_PATTERNS), re.IGNORECASE)


def _is_chat(query: str) -> bool:
    return bool(_CHAT_RE.search(query))

VALID_MODES = {"CHAT", "RECALL", "ANALYZE", "PLAN"}


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def classify_mode(query: str, client: genai.Client = None) -> str:
    """Classify a query as CHAT, RECALL, ANALYZE, or PLAN. Defaults to RECALL on failure."""
    return classify_intent(query, client)["mode"]


# One structured call replaces the six independent keyword/regex mechanisms
# that used to decide mode and action intent and disagreed at the edges
# (worst case: the word "sponsor" alone used to auto-send a real email).
_INTENT_PROMPT = """Classify this query about a student tech org's knowledge base.

Fields:
- mode: exactly one of
  CHAT: small talk, questions about what the system can do, example question requests, thanks.
  RECALL: what happened, what was decided, what exists in the org's history.
  ANALYZE: trends, comparisons, synthesis across events or time periods.
  PLAN: create something new, draft a document, plan a future event (produces a Google Doc).
- wants_calendar: true ONLY if the user explicitly asks to schedule something or add it to a calendar.
- wants_email: true ONLY if the user explicitly asks to email or send the result to someone. Merely mentioning sponsors, emails, or outreach as a TOPIC is not email intent ("what is our sponsor strategy" is false; "email the brief to our sponsors" is true).
- send_now: true ONLY if the user explicitly says to send immediately rather than draft or prepare.

Query: {query}"""

_INTENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "mode": {"type": "STRING", "enum": ["CHAT", "RECALL", "ANALYZE", "PLAN"]},
        "wants_calendar": {"type": "BOOLEAN"},
        "wants_email": {"type": "BOOLEAN"},
        "send_now": {"type": "BOOLEAN"},
    },
    "required": ["mode", "wants_calendar", "wants_email", "send_now"],
}

_FALLBACK_INTENT = {"mode": "RECALL", "wants_calendar": False, "wants_email": False, "send_now": False}


def classify_intent(query: str, client: genai.Client = None) -> dict:
    """One structured Gemini call returning {mode, wants_calendar, wants_email, send_now}.

    Failure degrades to RECALL with all action flags false, so a classifier
    outage can never trigger an action, only a plain retrieval answer.
    """
    if _is_chat(query):
        logger.info("Classified query as CHAT (pattern match): %s...", query[:60])
        return {**_FALLBACK_INTENT, "mode": "CHAT"}

    if client is None:
        client = _get_client()

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=_INTENT_PROMPT.format(query=query),
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_INTENT_SCHEMA,
                temperature=0.0,
            ),
        )
        import json
        intent = json.loads(response.text)
        if intent.get("mode") not in VALID_MODES:
            logger.warning("Unexpected mode '%s', defaulting to RECALL", intent.get("mode"))
            return dict(_FALLBACK_INTENT)
        result = {**_FALLBACK_INTENT, **{k: intent[k] for k in _FALLBACK_INTENT if k in intent}}
        logger.info("Intent: %s (cal=%s email=%s now=%s): %s...",
                    result["mode"], result["wants_calendar"], result["wants_email"],
                    result["send_now"], query[:60])
        return result
    except Exception as e:
        logger.error("Intent classification failed, defaulting to RECALL: %s", e)
        return dict(_FALLBACK_INTENT)
