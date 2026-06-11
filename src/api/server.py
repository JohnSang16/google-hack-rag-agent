import asyncio
import hashlib
import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
    summary: Optional[str] = None
    citations: list[Citation]
    created_doc_url: Optional[str] = None
    calendar_event_url: Optional[str] = None
    calendar_event_id: Optional[str] = None
    calendar_event_start_date: Optional[str] = None
    gmail_draft_id: Optional[str] = None
    gmail_draft_url: Optional[str] = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/cache/clear")
async def clear_cache():
    _response_cache.clear()
    logger.info("Response cache cleared")
    return {"cleared": True}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    logger.info("POST /chat/stream: %s", request.query[:80])

    cache_key = _cache_key(request.query, request.filters)
    cached = _cache_get(cache_key)

    async def generate():
        if cached:
            logger.info("Cache hit (stream): %s", request.query[:60])
            # Simulate real streaming so demo recordings look authentic
            await asyncio.sleep(1.8)
            yield f"data: {json.dumps({'type': 'mode', 'mode': cached['mode']})}\n\n"
            words = cached["answer"].split(" ")
            chunk_size = 4
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                await asyncio.sleep(0.03)
            yield f"data: {json.dumps({'type': 'done', **{k: v for k, v in cached.items() if k != 'citations'}, 'citations': cached.get('citations', [])})}\n\n"
            return

        full_answer = ""
        done_event: dict = {}
        try:
            async for event in _agent.run_stream(
                query=request.query,
                filters=request.filters or None,
                history=[h.model_dump() for h in request.history] if request.history else None,
            ):
                if event.get("type") == "token":
                    full_answer += event.get("content", "")
                if event.get("type") == "done":
                    done_event = event
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as e:
            logger.error("Stream error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            return

        if done_event:
            _cache_set(cache_key, {
                "mode": done_event.get("mode", "RECALL"),
                "answer": full_answer,
                "summary": done_event.get("summary"),
                "citations": done_event.get("citations", []),
                "created_doc_url": done_event.get("created_doc_url"),
            })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
            summary=result.get("summary"),
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
