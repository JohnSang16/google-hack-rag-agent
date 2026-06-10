import hashlib
import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agent import agent as _agent

_response_cache: dict[str, dict] = {}
_CACHE_MAX_SIZE = 100


def _cache_key(query: str, filters: Optional[dict]) -> str:
    payload = query.strip().lower() + json.dumps(filters or {}, sort_keys=True)
    return hashlib.md5(payload.encode()).hexdigest()


def _cache_get(key: str) -> Optional[dict]:
    return _response_cache.get(key)


def _cache_set(key: str, value: dict) -> None:
    if len(_response_cache) >= _CACHE_MAX_SIZE:
        _response_cache.pop(next(iter(_response_cache)))
    _response_cache[key] = value

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="progsu Intelligence Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class HistoryItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    query: str
    filters: Optional[dict] = None
    history: Optional[list[HistoryItem]] = None


class DiscordMessage(BaseModel):
    time: str
    author: str
    content: str


class Citation(BaseModel):
    title: str
    date: Optional[str] = None
    file_id: str
    source_type: str = "google_drive"
    drive_url: Optional[str] = None
    discord_url: Optional[str] = None
    messages: Optional[list[DiscordMessage]] = None
    relevance_score: float


class ChatResponse(BaseModel):
    mode: str
    answer: str
    citations: list[Citation]
    created_doc_url: Optional[str] = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    logger.info("POST /chat: %s", request.query[:80])

    cache_key = _cache_key(request.query, request.filters)
    cached = _cache_get(cache_key)
    if cached:
        logger.info("Cache hit for query: %s", request.query[:60])
        return ChatResponse(**cached)

    try:
        result = await _agent.run(
            query=request.query,
            filters=request.filters or None,
            history=[h.model_dump() for h in request.history] if request.history else None,
        )
        response = ChatResponse(
            mode=result["mode"],
            answer=result["answer"],
            citations=[Citation(**c) for c in result["citations"]],
            created_doc_url=result.get("created_doc_url"),
        )
        _cache_set(cache_key, response.model_dump())
        return response
    except Exception as e:
        logger.error("Agent error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("API_PORT", 8000))
    host = os.environ.get("API_HOST", "0.0.0.0")
    uvicorn.run("src.api.server:app", host=host, port=port, reload=True)
