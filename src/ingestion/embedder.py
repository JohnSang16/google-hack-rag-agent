import logging
import os
import time

from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMS = 768
RATE_LIMIT_DELAY = 0.1


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def get_embedding(
    text: str,
    task_type: str = "retrieval_document",
    model_name: str = EMBEDDING_MODEL,
) -> list[float]:
    """Return a 768-dim embedding for a single text chunk."""
    client = _get_client()
    try:
        result = client.models.embed_content(
            model=model_name,
            contents=text,
            config=genai.types.EmbedContentConfig(task_type=task_type),
        )
        embedding = result.embeddings[0].values
        if len(embedding) != EMBEDDING_DIMS:
            raise ValueError(f"Expected {EMBEDDING_DIMS} dims, got {len(embedding)}")
        return list(embedding)
    except Exception as e:
        raise RuntimeError(f"Embedding failed: {e}") from e


def get_embeddings_batch(
    texts: list[str],
    task_type: str = "retrieval_document",
    model_name: str = EMBEDDING_MODEL,
    delay: float = RATE_LIMIT_DELAY,
) -> list[list[float]]:
    """Return embeddings for a list of texts with rate limiting."""
    client = _get_client()
    embeddings = []
    for i, text in enumerate(texts):
        try:
            result = client.models.embed_content(
                model=model_name,
                contents=text,
                config=genai.types.EmbedContentConfig(task_type=task_type),
            )
            embeddings.append(list(result.embeddings[0].values))
        except Exception as e:
            logger.error("Embedding failed for chunk %d: %s", i, e)
            raise
        if i < len(texts) - 1:
            time.sleep(delay)

    logger.info("Embedded %d chunks with %s", len(embeddings), model_name)
    return embeddings
