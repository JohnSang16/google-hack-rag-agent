import logging
import os
import time

from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """You are evaluating whether a text chunk from a student tech organization contains useful organizational intelligence.

Score YES if the chunk contains ANY of:
- A decision that was made
- An action item or task assigned to someone
- An event detail (date, attendance count, logistics, outcome)
- A growth or attendance metric
- A sponsorship or partnership detail
- A lesson learned or retrospective insight
- A strategic plan or goal
- A process or how-to instruction
- Financial information (budget, spending, revenue)

Score NO if the chunk contains ONLY:
- Meme references, emoji spam, or reaction-only messages
- Duplicate content already present in the same document
- Filler or placeholder text ("TBD", "coming soon", empty template fields)
- Pure logistics with no context (a room number alone, a time alone)
- Template section headers with no filled content

Respond with exactly one word: YES or NO

Chunk:
{chunk_text}"""

MIN_CHUNK_CHARS = 80
MAX_CHARS_TO_SCORE = 2_000
RATE_LIMIT_DELAY = 0.15


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def is_useful_chunk(chunk_text: str, client: genai.Client = None) -> bool:
    """Returns True if the chunk passes the noise filter (Gemini scores it YES)."""
    if len(chunk_text.strip()) < MIN_CHUNK_CHARS:
        return False

    if client is None:
        client = _get_client()

    prompt = _PROMPT_TEMPLATE.format(chunk_text=chunk_text[:MAX_CHARS_TO_SCORE])
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        )
        return response.text.strip().upper().startswith("YES")
    except Exception as e:
        logger.warning("Noise filter call failed, defaulting to YES: %s", e)
        return True


def filter_chunks(
    chunks: list[str],
    client: genai.Client = None,
    rate_limit_delay: float = RATE_LIMIT_DELAY,
) -> tuple[list[str], dict]:
    """
    Filter a list of chunks through the noise filter.
    Returns (kept_chunks, stats_dict).
    """
    if client is None:
        client = _get_client()

    kept = []
    dropped = 0

    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            dropped += 1
            continue
        if is_useful_chunk(chunk, client=client):
            kept.append(chunk)
        else:
            dropped += 1
            logger.debug("Dropped chunk %d (noise filter)", i)
        if i < len(chunks) - 1:
            time.sleep(rate_limit_delay)

    total = len(chunks)
    pass_rate = len(kept) / total if total else 0.0
    stats = {"total": total, "kept": len(kept), "dropped": dropped, "pass_rate": pass_rate}
    logger.info(
        "Noise filter: %d/%d kept (%.0f%% pass rate)", len(kept), total, pass_rate * 100
    )
    return kept, stats
