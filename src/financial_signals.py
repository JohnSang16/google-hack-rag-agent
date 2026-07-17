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
    "sponsor amount", "dollars", "dollar", "payment", "reimbursement",
    "usd", "cad", "eur", "gbp",
)

# $, €, £, ¥ followed by a digit.
CURRENCY_SYMBOL_RE = re.compile(r"[$€£¥]\s?\d")
# Thousands-separated amounts (1,200 / 12,000.50) — a shape plain small
# integers (dates, counts) don't have, so it stays cheap without a keyword.
THOUSANDS_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b")


def has_financial_signals(text: str) -> bool:
    lower = text.lower()
    if CURRENCY_SYMBOL_RE.search(lower) or THOUSANDS_RE.search(lower):
        return True
    return any(k in lower for k in FINANCIAL_KEYWORDS)
