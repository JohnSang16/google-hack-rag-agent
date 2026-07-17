"""Ingestion-time access classification for chunks.

Fixes the blunt query-time keyword filter: "the venue cost us a lot of stress"
matches the keyword "cost" but contains nothing sensitive. At ingestion the
chunk is judged once, with context, and the verdict rides along as metadata:

  access_level "member"  safe for every tier (default)
  access_level "exec"    real financial data; restricted tiers get the
                         redacted rendition, or nothing if none exists

Cost control: the LLM is only consulted when the cheap keyword/regex trigger
fires. Chunks with no money-ish signals are trivially "member" at zero cost.
"""
import json
import logging

from google import genai

from src.financial_signals import has_financial_signals

logger = logging.getLogger(__name__)

ACCESS_MEMBER = "member"
ACCESS_EXEC = "exec"

_JUDGE_PROMPT = """You are classifying a text chunk from a student org's knowledge base.

Does this chunk contain REAL financial data: specific dollar amounts, budgets,
sponsorship figures, payment or reimbursement details, or bookkeeping records?

Casual mentions are NOT financial data: "cost us a lot of stress", "paid off",
"at what cost", or money words used figuratively.

If financial is true, also produce "redacted": the exact same text with only the
specific figures and amounts replaced by [amount], keeping every other word
verbatim. If financial is false, redacted must be null.

Chunk:
{text}"""

_JUDGE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "financial": {"type": "BOOLEAN"},
        "redacted": {"type": "STRING", "nullable": True},
    },
    "required": ["financial"],
}


def classify_chunk_access(text: str, client: genai.Client, known_financial: bool = False) -> dict:
    """Return {"level": "member"|"exec", "redacted": str|None}.

    known_financial short-circuits for chunks from doc_type=financial sources
    (the whole doc is financial by definition; no LLM call, no redaction since
    a bookkeeping row minus its numbers carries no value).
    Failure degrades to restricting the chunk (exec, no redaction): when in
    doubt, over-restrict rather than leak.
    """
    if known_financial:
        return {"level": ACCESS_EXEC, "redacted": None}
    if not has_financial_signals(text):
        return {"level": ACCESS_MEMBER, "redacted": None}
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=_JUDGE_PROMPT.format(text=text[:6000]),
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_JUDGE_SCHEMA,
                temperature=0.0,
            ),
        )
        verdict = json.loads(response.text)
        if not verdict.get("financial"):
            return {"level": ACCESS_MEMBER, "redacted": None}
        return {"level": ACCESS_EXEC, "redacted": verdict.get("redacted") or None}
    except Exception as e:
        logger.warning("Access classification failed, restricting chunk: %s", e)
        return {"level": ACCESS_EXEC, "redacted": None}
