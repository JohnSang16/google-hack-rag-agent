import asyncio
import hashlib
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.access import Access, TIER_ANONYMOUS
from src.org_config import cfg_dict
from src.agent import agent as _agent
from src.api.auth import auth_configured, get_access, router as auth_router

load_dotenv()

# DEMO_MODE=true enables public guardrails (off-topic filter, sensitive query block,
# rate limiting). Leave unset/false with no Discord auth configured and the
# restricted anonymous tier applies (see access.legacy_default); the old
# "internal club use, full access, no restrictions" behavior now requires
# LEGACY_FULL_ACCESS=true as well.
_DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"

# --- Demo guardrails (only active when DEMO_MODE=true) ---
_RATE_LIMIT_WINDOW = 60   # seconds
_RATE_LIMIT_MAX = 10      # requests per IP per window
_MAX_QUERY_LEN = 400

# Hard daily cap across all IPs — acts as a billing circuit breaker.
# Set DAILY_REQUEST_CAP in env to override. 0 = disabled.
_DAILY_CAP = int(os.environ.get("DAILY_REQUEST_CAP", "300"))
_daily_counter: dict[str, int] = {}

_rate_tracker: dict[str, list[float]] = defaultdict(list)

_BLOCKED_PATTERNS = [
    "ignore previous", "ignore all instructions", "forget your instructions",
    "override", "jailbreak", "dan mode", "act as", "pretend you are",
    "system prompt", "sql injection", "drop table", "<script", "prompt injection",
]


_TRUSTED_PROXY_HOPS = int(os.environ.get("TRUSTED_PROXY_HOPS", "1"))


def _get_client_ip(req: Request) -> str:
    forwarded = req.headers.get("x-forwarded-for")
    if forwarded:
        # Clients can prepend arbitrary values to this header. Only the last
        # TRUSTED_PROXY_HOPS entries are appended by infrastructure we trust —
        # default 1 hop assumes Cloud Run's own proxy is the only thing in
        # front of this service. If this deployment sits behind an additional
        # trusted proxy/CDN, set TRUSTED_PROXY_HOPS to match, or this will
        # read a client-controlled value as the "real" IP.
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            return hops[max(0, len(hops) - _TRUSTED_PROXY_HOPS)]
    return req.client.host if req.client else "unknown"


def _check_rate_limit(ip: str) -> bool:
    now = time.time()
    window_start = now - _RATE_LIMIT_WINDOW
    _rate_tracker[ip] = [t for t in _rate_tracker[ip] if t > window_start]
    if len(_rate_tracker[ip]) >= _RATE_LIMIT_MAX:
        return False
    _rate_tracker[ip].append(now)
    return True


def _check_daily_cap() -> bool:
    """Return False if the global daily request cap has been reached. Does not count the request."""
    if _DAILY_CAP <= 0:
        return True
    today = time.strftime("%Y-%m-%d")
    return _daily_counter.get(today, 0) < _DAILY_CAP


def _count_daily_request() -> None:
    """Count one request against the daily cap. Call only after all other guards pass,
    so rate-limited or blocked requests don't burn the daily budget."""
    today = time.strftime("%Y-%m-%d")
    # Evict stale dates so the dict doesn't grow unbounded across days
    for k in list(_daily_counter):
        if k != today:
            del _daily_counter[k]
    _daily_counter[today] = _daily_counter.get(today, 0) + 1



def _check_query(query: str) -> Optional[str]:
    if len(query) > _MAX_QUERY_LEN:
        return f"Query too long. Demo limit is {_MAX_QUERY_LEN} characters."
    q = query.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern in q:
            return "That query isn't supported in the demo."
    return None


# --- Query logging (query_logs collection on the existing Atlas cluster) ---
_query_log_collection = None


def _get_query_log_collection():
    global _query_log_collection
    if _query_log_collection is None:
        uri = os.environ.get("MONGODB_URI")
        if not uri:
            return None
        import motor.motor_asyncio
        db_name = os.getenv("MONGODB_DB_NAME", "progsu_intelligence")
        client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        _query_log_collection = client[db_name]["query_logs"]
    return _query_log_collection


async def _log_query(
    query: str,
    mode: str,
    ip: str,
    response_ms: float,
    confidence: Optional[float] = None,
    injection_flagged: bool = False,
    cache_hit: bool = False,
    user_id: Optional[str] = None,
    tier: Optional[str] = None,
) -> None:
    """Insert one usage record. Best-effort: failures are logged and swallowed
    so logging can never break a request."""
    coll = _get_query_log_collection()
    if coll is None:
        return
    try:
        await coll.insert_one({
            "ts": datetime.now(timezone.utc),
            "mode": mode,
            "query_preview": query[:120],
            "response_ms": round(response_ms),
            "confidence": confidence,
            "injection_flagged": injection_flagged,
            "cache_hit": cache_hit,
            "ip_hash": hashlib.sha256(ip.encode()).hexdigest()[:16],
            "user_id": user_id,
            "tier": tier,
        })
    except Exception as e:
        logger.warning("Query log insert failed: %s", e)


_background_tasks: set = set()


def _log_query_bg(*args, **kwargs) -> None:
    """Fire-and-forget wrapper so logging adds no request latency.

    asyncio only holds a weak reference to a task once nothing else refers to
    it, so an unheld task can be garbage-collected mid-flight. Keep a strong
    reference until it finishes.
    """
    task = asyncio.get_running_loop().create_task(_log_query(*args, **kwargs))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def _best_confidence(citations) -> Optional[float]:
    scores = [c.get("relevance_score") for c in (citations or []) if isinstance(c, dict) and c.get("relevance_score") is not None]
    return max(scores) if scores else None


# --- Response cache ---
_response_cache: dict[str, dict] = {}
_CACHE_MAX_SIZE = 100

# Artifact URLs from live PLAN runs — persists across cache/clears so buttons
# don't disappear when the frontend reloads and calls /cache/clear.
_LIVE_ARTIFACTS: dict[str, dict] = {}

_ARTIFACT_FIELDS = (
    "created_doc_url", "calendar_event_url", "calendar_event_id",
    "calendar_event_start_date", "gmail_draft_id", "gmail_draft_url",
)

# Demo seeds: pre-canned responses that survive cache/clear so the demo always
# returns the same output for the recorded queries regardless of live retrieval.
# The seed content is org-specific and lives in org_config.json (private).
# PLAN seeds get artifact URLs from the first live run via _LIVE_ARTIFACTS.
_DEMO_SEEDS: dict = cfg_dict("demo_seeds")


def _apply_demo_seeds() -> None:
    for query, value in _DEMO_SEEDS.items():
        key = _cache_key(query, None, TIER_ANONYMOUS)
        entry = {**value}
        live = _LIVE_ARTIFACTS.get(query, {})
        # Merge in any live artifact URLs preserved from a previous real run
        if live:
            entry.update(live)
        elif value.get("mode") == "PLAN":
            # No live artifacts yet — skip the PLAN seed so the next call goes
            # live and creates real Drive/Calendar/Gmail artifacts.
            continue
        _response_cache[key] = entry


_NON_CACHE_FILTER_KEYS = frozenset({"plan_doc_url"})


def _cache_key(query: str, filters: Optional[dict], tier: str = TIER_ANONYMOUS) -> str:
    # Strip non-retrieval fields (e.g. plan_doc_url) so they don't cause cache misses.
    # Tier is part of the key so an exec-tier answer (may include financial figures)
    # is never replayed to a lower-tier request for the same query text.
    clean = {k: v for k, v in (filters or {}).items() if k not in _NON_CACHE_FILTER_KEYS}
    payload = tier + "|" + query.strip().lower() + json.dumps(clean, sort_keys=True)
    return hashlib.md5(payload.encode()).hexdigest()


def _cache_get(key: str) -> Optional[dict]:
    return _response_cache.get(key)


def _cache_set(key: str, value: dict) -> None:
    if len(_response_cache) >= _CACHE_MAX_SIZE:
        _response_cache.pop(next(iter(_response_cache)))
    _response_cache[key] = value

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="progsu Intelligence Agent", version="1.0.0")
app.include_router(auth_router)

# ALLOWED_ORIGINS env var is a comma-separated list of allowed frontend origins.
# Default "*" works for local dev; set to your actual frontend URL in production.
# Example: ALLOWED_ORIGINS=https://progsu.vercel.app,https://progsu.example.com
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "*")
_allowed_origins: list[str] = (
    ["*"] if _raw_origins.strip() == "*"
    else [o.strip() for o in _raw_origins.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept", "Authorization"],
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


@app.get("/admin/stats")
async def admin_stats(access: Access = Depends(get_access)):
    """Recent query log records plus simple counts. Admin tier only."""
    if not access.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    coll = _get_query_log_collection()
    if coll is None:
        return {"records": [], "total": 0}
    records = []
    async for doc in coll.find({}, {"_id": 0}).sort("ts", -1).limit(50):
        doc["ts"] = doc["ts"].isoformat() if doc.get("ts") else None
        records.append(doc)
    total = await coll.count_documents({})
    return {"records": records, "total": total}


@app.on_event("startup")
async def startup():
    if not auth_configured() and not _DEMO_MODE:
        if os.environ.get("LEGACY_FULL_ACCESS", "false").lower() == "true":
            logger.warning(
                "Startup: Discord auth is NOT configured and LEGACY_FULL_ACCESS=true — "
                "every request gets unguarded, unrated, financial-data-included access."
            )
        else:
            logger.warning(
                "Startup: Discord auth is NOT configured, DEMO_MODE is off, and "
                "LEGACY_FULL_ACCESS is not set — falling back to the restricted "
                "anonymous tier for all requests. Set the Discord auth env vars, "
                "DEMO_MODE=true, or LEGACY_FULL_ACCESS=true to change this."
            )
    _apply_demo_seeds()
    logger.info("Demo seeds loaded into cache (%d of %d — PLAN skipped until live run)", len(_response_cache), len(_DEMO_SEEDS))
    # TTL index: query log rows self-delete after 90 days so the M0 tier
    # storage cap can never fill up from logging.
    coll = _get_query_log_collection()
    if coll is not None:
        try:
            await coll.create_index("ts", expireAfterSeconds=90 * 24 * 3600)
        except Exception as e:
            logger.warning("query_logs TTL index creation failed: %s", e)


@app.post("/cache/clear")
async def clear_cache(http_request: Request, access: Access = Depends(get_access)):
    # Unauthenticated cache clears let anyone force live Gemini spend. Deny by
    # default — there's no configuration where an anonymous caller should be
    # able to hit this. Accept either the shared ADMIN_TOKEN header (legacy /
    # no-auth deployments) or an authenticated admin-tier caller.
    admin_token = os.environ.get("ADMIN_TOKEN")
    token_ok = bool(admin_token) and http_request.headers.get("x-admin-token") == admin_token
    if not (token_ok or access.is_admin):
        raise HTTPException(status_code=403, detail="Forbidden")
    _response_cache.clear()
    _apply_demo_seeds()
    logger.info("Response cache cleared and demo seeds reloaded")
    return {"cleared": True}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, http_request: Request, access: Access = Depends(get_access)):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    if not _check_daily_cap():
        raise HTTPException(status_code=503, detail="Demo capacity reached for today. Check back tomorrow.")

    ip = _get_client_ip(http_request)
    rate_key = access.user_id or ip
    started = time.perf_counter()

    if access.guarded:
        if not _check_rate_limit(rate_key):
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")

        guard_err = _check_query(request.query.strip())
        if guard_err:
            _log_query_bg(request.query, "BLOCKED", rate_key, 0, injection_flagged=True)
            raise HTTPException(status_code=400, detail=guard_err)

    _count_daily_request()

    logger.info("POST /chat/stream: %s", request.query[:80])

    cache_key = _cache_key(request.query, request.filters, access.tier)
    cached = _cache_get(cache_key)

    # Per-mode cache replay config — spinner_delay matches demo script slot timing,
    # chunk config controls how fast the answer streams in after the spinner clears.
    _CACHE_CONFIG = {
        "CHAT":    {"spinner_delay": 0.5,  "chunk_delay": 0.02, "chunk_size": 6},
        "RECALL":  {"spinner_delay": 1.8,  "chunk_delay": 0.03, "chunk_size": 4},
        "ANALYZE": {"spinner_delay": 8.0,  "chunk_delay": 0.06, "chunk_size": 3},
        "PLAN":    {"spinner_delay": 10.0, "chunk_delay": 0.07, "chunk_size": 3},
    }

    async def generate():
        if cached and cached.get("mode") != "PLAN":
            logger.info("Cache hit (stream): %s", request.query[:60])
            _log_query_bg(request.query, cached["mode"], ip, (time.perf_counter() - started) * 1000, cache_hit=True, user_id=access.user_id, tier=access.tier)
            mode = cached["mode"]
            cfg = _CACHE_CONFIG.get(mode, _CACHE_CONFIG["RECALL"])
            # Send mode immediately so the frontend can switch to scripted spinner messages.
            yield f"data: {json.dumps({'type': 'mode', 'mode': mode})}\n\n"
            # Hold for the scripted spinner duration before streaming the answer.
            await asyncio.sleep(cfg["spinner_delay"])
            words = cached["answer"].split(" ")
            chunk_size = cfg["chunk_size"]
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                await asyncio.sleep(cfg["chunk_delay"])
            yield f"data: {json.dumps({'type': 'done', **{k: v for k, v in cached.items() if k != 'citations'}, 'citations': cached.get('citations', [])})}\n\n"
            return

        full_answer = ""
        done_event: dict = {}
        try:
            async for event in _agent.run_stream(
                query=request.query,
                filters=request.filters or None,
                history=[h.model_dump() for h in request.history] if request.history else None,
                access=access,
            ):
                if event.get("type") == "token":
                    full_answer += event.get("content", "")
                if event.get("type") == "done":
                    done_event = event
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as e:
            # Log detail server-side only; str(e) can leak connection strings or key fragments
            logger.error("Stream error: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Something went wrong generating this response. Please try again.'})}\n\n"
            return

        if done_event:
            _log_query_bg(
                request.query,
                done_event.get("mode", "RECALL"),
                ip,
                (time.perf_counter() - started) * 1000,
                confidence=_best_confidence(done_event.get("citations")),
                user_id=access.user_id,
                tier=access.tier,
            )
            entry = {
                "mode": done_event.get("mode", "RECALL"),
                "answer": full_answer,
                "summary": done_event.get("summary"),
                "citations": done_event.get("citations", []),
                "created_doc_url": done_event.get("created_doc_url"),
                "calendar_event_url": done_event.get("calendar_event_url"),
                "calendar_event_id": done_event.get("calendar_event_id"),
                "calendar_event_start_date": done_event.get("calendar_event_start_date"),
                "gmail_draft_id": done_event.get("gmail_draft_id"),
                "gmail_draft_url": done_event.get("gmail_draft_url"),
            }
            if entry.get("mode") != "PLAN":
                _cache_set(cache_key, entry)
            # Persist any real artifact URLs so they survive future cache/clears
            artifacts = {f: entry[f] for f in _ARTIFACT_FIELDS if entry.get(f)}
            if artifacts and request.query.strip() in _DEMO_SEEDS:
                _LIVE_ARTIFACTS[request.query.strip()] = artifacts
                logger.info("Live artifacts saved for demo query: %s", request.query[:60])

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request, access: Access = Depends(get_access)):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    if not _check_daily_cap():
        raise HTTPException(status_code=503, detail="Demo capacity reached for today. Check back tomorrow.")

    ip = _get_client_ip(http_request)
    rate_key = access.user_id or ip
    started = time.perf_counter()
    if access.guarded:
        if not _check_rate_limit(rate_key):
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")

        guard_err = _check_query(request.query.strip())
        if guard_err:
            _log_query_bg(request.query, "BLOCKED", rate_key, 0, injection_flagged=True)
            raise HTTPException(status_code=400, detail=guard_err)

    _count_daily_request()

    logger.info("POST /chat: %s", request.query[:80])

    cache_key = _cache_key(request.query, request.filters, access.tier)
    cached = _cache_get(cache_key)
    if cached and cached.get("mode") != "PLAN":
        logger.info("Cache hit for query: %s", request.query[:60])
        _log_query_bg(request.query, cached["mode"], ip, (time.perf_counter() - started) * 1000, cache_hit=True, user_id=access.user_id, tier=access.tier)
        return ChatResponse(**cached)

    try:
        result = await _agent.run(
            query=request.query,
            filters=request.filters or None,
            history=[h.model_dump() for h in request.history] if request.history else None,
            access=access,
        )
        response = ChatResponse(
            mode=result["mode"],
            answer=result["answer"],
            summary=result.get("summary"),
            citations=[Citation(**c) for c in result["citations"]],
            created_doc_url=result.get("created_doc_url"),
        )
        if response.mode != "PLAN":
            _cache_set(cache_key, response.model_dump())
        _log_query_bg(
            request.query,
            response.mode,
            ip,
            (time.perf_counter() - started) * 1000,
            confidence=_best_confidence(result.get("citations")),
            user_id=access.user_id,
            tier=access.tier,
        )
        return response
    except Exception as e:
        logger.error("Agent error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Something went wrong generating this response. Please try again.")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("API_PORT", 8000))
    host = os.environ.get("API_HOST", "0.0.0.0")
    uvicorn.run("src.api.server:app", host=host, port=port, reload=True)
