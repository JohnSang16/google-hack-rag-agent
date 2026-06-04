import logging
import re

logger = logging.getLogger(__name__)

MAX_TOKENS = 800
OVERLAP_TOKENS = 100
SINGLE_CHUNK_TOKEN_LIMIT = 600
LARGE_DOC_BYTES = 1_000_000   # 1MB
SMALL_DOC_BYTES = 50_000      # 50KB


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _split_into_windows(text: str, max_tokens: int = MAX_TOKENS, overlap: int = OVERLAP_TOKENS) -> list[str]:
    max_chars = max_tokens * 4
    overlap_chars = overlap * 4
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap_chars
    return chunks


def _split_by_heading(text: str, max_tokens: int = MAX_TOKENS, overlap: int = OVERLAP_TOKENS) -> list[str]:
    sections = re.split(r"\n(?=##)", text)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if _estimate_tokens(section) <= max_tokens:
            chunks.append(section)
        else:
            chunks.extend(_split_into_windows(section, max_tokens, overlap))
    return chunks


def _split_by_separator(text: str, separator: str = "---") -> list[str]:
    parts = text.split(separator)
    return [p.strip() for p in parts if p.strip()]


def _split_by_paragraph(text: str, max_tokens: int = MAX_TOKENS) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks = []
    current: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _estimate_tokens(para)
        if current_tokens + para_tokens > max_tokens and current:
            chunks.append("\n\n".join(current))
            current = [para]
            current_tokens = para_tokens
        else:
            current.append(para)
            current_tokens += para_tokens

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _split_meeting_notes(text: str) -> list[str]:
    # Try "---" separator first
    if "---" in text:
        parts = _split_by_separator(text, "---")
        if len(parts) > 1:
            result = []
            for p in parts:
                if _estimate_tokens(p) > MAX_TOKENS:
                    result.extend(_split_by_heading(p))
                else:
                    result.append(p)
            return result

    # Try ## headings
    if re.search(r"\n##", text) or text.startswith("##"):
        return _split_by_heading(text)

    # Fall back to paragraph split
    return _split_by_paragraph(text)


def chunk_text(text: str, doc_type: str) -> list[str]:
    """Split document text into chunks based on doc_type and document size."""
    size_bytes = len(text.encode("utf-8"))

    # Large docs: always heading split with token limit + overlap
    if size_bytes > LARGE_DOC_BYTES:
        logger.debug("Large doc (%d bytes) → heading split with overlap", size_bytes)
        chunks = _split_by_heading(text, max_tokens=MAX_TOKENS, overlap=OVERLAP_TOKENS)
        return [c for c in chunks if c.strip()]

    # doc_type-specific splits take precedence over size heuristics
    if doc_type == "meeting_notes":
        return _split_meeting_notes(text)
    elif doc_type in ("event_logistics", "blueprint"):
        return _split_by_heading(text)

    # Small non-typed docs: single chunk or paragraph split
    if size_bytes < SMALL_DOC_BYTES:
        if _estimate_tokens(text) <= SINGLE_CHUNK_TOKEN_LIMIT:
            return [text.strip()] if text.strip() else []
        logger.debug("Small doc (%d bytes) → paragraph split", size_bytes)
        return _split_by_paragraph(text)

    # Medium docs: paragraph split for remaining types
    # growth, financial, guide, wiki, feedback_aggregate
    return _split_by_paragraph(text)
