"""Shared financial-content signals.

Used as a cheap trigger in two places: at ingestion to decide which chunks are
worth an LLM access-classification call, and at query time as the backstop
filter for legacy chunks ingested before access_level tagging existed.
Deliberately blunt; the precise judgment lives in
src/ingestion/access_classifier.py.
"""
import re

FINANCIAL_KEYWORDS = (
    "budget", "expense", "cost", "invoice", "receipt", "bookkeeping",
    "sponsor amount", "dollars", "payment", "reimbursement",
)

DOLLAR_RE = re.compile(r"\$\s?\d")


def has_financial_signals(text: str) -> bool:
    lower = text.lower()
    if DOLLAR_RE.search(lower):
        return True
    return any(k in lower for k in FINANCIAL_KEYWORDS)
