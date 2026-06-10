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

_PROMPT = """Classify this query into exactly one of four modes:

CHAT: The user is making small talk, asking what the system can do, requesting example questions, saying thanks, or asking something not about org history.
  Examples: "hello", "what can you do?", "give me example questions", "thanks", "what are the 3 prompts?", "give me the other prompts to try", "who are you?"

RECALL: The user wants to know what happened, what was decided, or what exists in the org's history.
  Examples: "What were the logistics for Hacklanta?", "What sponsors did we have?", "What was decided in the last exec meeting?"

ANALYZE: The user wants trends, comparisons, or synthesis across multiple events/time periods.
  Examples: "How has our attendance grown?", "What events drove the most engagement?", "Compare Fall 2025 to Spring 2026"

PLAN: The user wants to create something new, draft a document, or plan a future event. This should produce a Google Doc.
  Examples: "Draft a planning brief for...", "Help me plan...", "Create a template for...", "Write a proposal for..."

Query: {query}

Respond with exactly one word: CHAT, RECALL, ANALYZE, or PLAN"""

VALID_MODES = {"CHAT", "RECALL", "ANALYZE", "PLAN"}


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def classify_mode(query: str, client: genai.Client = None) -> str:
    """Classify a query as CHAT, RECALL, ANALYZE, or PLAN. Defaults to RECALL on failure."""
    if _is_chat(query):
        logger.info("Classified query as CHAT (pattern match): %s...", query[:60])
        return "CHAT"

    if client is None:
        client = _get_client()

    prompt = _PROMPT.format(query=query)
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        )
        mode = response.text.strip().upper()
        if mode not in VALID_MODES:
            logger.warning("Unexpected mode '%s', defaulting to RECALL", mode)
            return "RECALL"
        logger.info("Classified query as %s: %s...", mode, query[:60])
        return mode
    except Exception as e:
        logger.error("Mode classification failed, defaulting to RECALL: %s", e)
        return "RECALL"
