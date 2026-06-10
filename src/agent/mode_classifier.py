import logging
import os

from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_PROMPT = """Classify this query into exactly one of three modes:

RECALL: The user wants to know what happened, what was decided, or what exists.
  Examples: "What were the logistics for Hacklanta?", "What sponsors did we have?", "What was decided in the last exec meeting?"

ANALYZE: The user wants trends, comparisons, or synthesis across multiple events/time periods.
  Examples: "How has our attendance grown?", "What events drove the most engagement?", "Compare Fall 2025 to Spring 2026"

PLAN: The user wants to create something new, draft a document, or plan a future event. This should produce a Google Doc.
  Examples: "Draft a planning brief for...", "Help me plan...", "Create a template for...", "Write a proposal for..."

Query: {query}

Respond with exactly one word: RECALL, ANALYZE, or PLAN"""

VALID_MODES = {"RECALL", "ANALYZE", "PLAN"}


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def classify_mode(query: str, client: genai.Client = None) -> str:
    """Classify a query as RECALL, ANALYZE, or PLAN. Defaults to RECALL on failure."""
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
