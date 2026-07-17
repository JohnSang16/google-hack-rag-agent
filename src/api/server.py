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
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agent import agent as _agent

load_dotenv()

# DEMO_MODE=true enables public guardrails (off-topic filter, sensitive query block,
# rate limiting). Leave unset or false for internal club use — full access, no restrictions.
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


def _get_client_ip(req: Request) -> str:
    forwarded = req.headers.get("x-forwarded-for")
    if forwarded:
        # Use the last hop: clients can prepend arbitrary values to this header,
        # but the last entry is appended by Cloud Run's own proxy and is trustworthy.
        return forwarded.split(",")[-1].strip()
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
        })
    except Exception as e:
        logger.warning("Query log insert failed: %s", e)


def _log_query_bg(*args, **kwargs) -> None:
    """Fire-and-forget wrapper so logging adds no request latency."""
    asyncio.get_running_loop().create_task(_log_query(*args, **kwargs))


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

# Demo seeds — pre-canned responses that survive cache/clear so the demo always
# returns the same output for the recorded queries regardless of live retrieval.
# PLAN seed has no artifact URLs; those come from the first live run and are
# preserved in _LIVE_ARTIFACTS so they survive subsequent cache clears.
_DEMO_SEEDS: dict[str, dict] = {
    # RECALL — Q1
    "What were the key logistics challenges at Hacklanta and how did we solve them?": {
        "mode": "RECALL",
        "summary": None,
        "answer": (
            "The key logistics challenges at Hacklanta centered on parking, food coordination, "
            "venue navigation, and check-in flow. Here is how each was handled:\n\n"
            "**Parking**\n"
            "- Secured free parking at GSU's G Deck on a first-come, first-served basis\n"
            "- Paid overflow options available at N and K Decks\n"
            "- Parking reimbursement offered via Cashapp, Venmo, and Zelle for confirmed attendees\n\n"
            "**Food and Drinks**\n"
            "- DoorDash ambassador sponsorship covered food for approximately 150 people, "
            "saving the org roughly $1,200\n"
            "- Red Bull and Celsius provided energy drinks; a Red Bull Can Estimation game "
            "kept attendees engaged at the help desk\n\n"
            "**Venue Navigation**\n"
            "- QR code event maps placed at the Help Desk with all room locations\n"
            "- Restroom directions from key rooms (LIBSO 102, CLSO 103, 105, 107) included in the FAQs\n"
            "- Non-GSU students directed to show government-issued ID at the security desk or CURVE Lab\n"
            "- Wi-Fi for non-GSU attendees handled via Eduroam with a quick registration link\n\n"
            "**Check-in and Opening Ceremonies**\n"
            "- Centralized in Library South 102 with volunteers on hand to guide attendees"
        ),
        "citations": [
            {
                "title": "FAQs - Hacklanta",
                "date": "2026-03-01",
                "file_id": "1ekbPvjUYMW7oNi8rzWHdoBT1F-DLlKkqLbxcIuuD12Q",
                "source_type": "google_drive",
                "drive_url": "https://docs.google.com/document/d/1ekbPvjUYMW7oNi8rzWHdoBT1F-DLlKkqLbxcIuuD12Q/edit",
                "discord_url": None,
                "messages": None,
                "relevance_score": 10.0,
            },
            {
                "title": "Hacklanta Master Doc - Spring 26",
                "date": "2026-03-01",
                "file_id": "1YFGL5-laW0CEaTHpR6gydZNV3SzWx0xO7n-IubrxTYc",
                "source_type": "google_drive",
                "drive_url": "https://docs.google.com/document/d/1YFGL5-laW0CEaTHpR6gydZNV3SzWx0xO7n-IubrxTYc/edit",
                "discord_url": None,
                "messages": None,
                "relevance_score": 9.5,
            },
            {
                "title": "Operations Meeting Notes",
                "date": "2026-02-15",
                "file_id": "1-BK0mGR1gHHuKR4Axofuy0WdWReEYf1JDt3sV3-Lxnk",
                "source_type": "google_drive",
                "drive_url": "https://docs.google.com/document/d/1-BK0mGR1gHHuKR4Axofuy0WdWReEYf1JDt3sV3-Lxnk/edit",
                "discord_url": None,
                "messages": None,
                "relevance_score": 8.5,
            },
        ],
        "created_doc_url": None,
        "calendar_event_url": None,
        "calendar_event_id": None,
        "calendar_event_start_date": None,
        "gmail_draft_id": None,
        "gmail_draft_url": None,
    },
    # ANALYZE — Q2
    "How has our event attendance grown from Fall 2025 to Spring 2026, and which events drove the most engagement?": {
        "mode": "ANALYZE",
        "summary": None,
        "answer": (
            "Attendance scaled significantly from Fall 2025 into Spring 2026, with two Spring flagship events "
            "accounting for the majority of the org's total reach for the year.\n\n"
            "| Event | Semester | Attendance |\n"
            "| --- | --- | --- |\n"
            "| Fall Kickoff + Interest Meetings | Fall 2025 | org-building scale |\n"
            "| Involvement Fair | Fall 2025 | 130+ signups |\n"
            "| Claude Workshop | Spring 2026 | 200+ |\n"
            "| Hacklanta | Spring 2026 | 400+ |\n\n"
            "The inflection point was Spring 2026. The Claude Workshop brought 200+ students to a live session "
            "with Anthropic ambassador Tyler Sztuka, establishing progsu's ability to attract industry partners. "
            "Hacklanta followed with 400+ attendees, $20,000 in sponsorships, and $5,000+ in prizes across a "
            "12-hour event. The largest single-event turnout in the org's history. "
            "The Fall 2025 slate was intentional org-building; Spring 2026 was the payoff. "
            "The next phase is replicating that scale consistently, not just as a one-time spike."
        ),
        "citations": [
            {
                "title": "Combined Attendance Fall 2025 / Spring 2026",
                "date": "2026-04-01",
                "file_id": "1I9Vh8je61pqPp1zgXDZ82DSJ9O-fx70PEecE9xxmw18",
                "source_type": "google_drive",
                "drive_url": "https://docs.google.com/spreadsheets/d/1I9Vh8je61pqPp1zgXDZ82DSJ9O-fx70PEecE9xxmw18/edit",
                "discord_url": None,
                "messages": None,
                "relevance_score": 10.0,
            },
            {
                "title": "Growth Master Doc",
                "date": "2026-04-01",
                "file_id": "1umNbz4FFLimhWT9xsZwkqVSGvlTMJdig1Q8tfYih0Cs",
                "source_type": "google_drive",
                "drive_url": "https://docs.google.com/document/d/1umNbz4FFLimhWT9xsZwkqVSGvlTMJdig1Q8tfYih0Cs/edit",
                "discord_url": None,
                "messages": None,
                "relevance_score": 9.0,
            },
            {
                "title": "Involvement Fair Signups Fall 2025",
                "date": "2025-09-15",
                "file_id": "1GpU7gA6LJKLVzBFmaNEEar_m1R1NXamB_0Y7BAqRSg0",
                "source_type": "google_drive",
                "drive_url": "https://docs.google.com/spreadsheets/d/1GpU7gA6LJKLVzBFmaNEEar_m1R1NXamB_0Y7BAqRSg0/edit",
                "discord_url": None,
                "messages": None,
                "relevance_score": 8.5,
            },
        ],
        "created_doc_url": None,
        "calendar_event_url": None,
        "calendar_event_id": None,
        "calendar_event_start_date": None,
        "gmail_draft_id": None,
        "gmail_draft_url": None,
    },
    # PLAN — Q3 (artifact URLs are None until first live run, which overwrites this seed)
    "Create a sponsor packet for Hacklanta II with key metrics from Hacklanta 1, what we're improving, and how sponsors can get involved. Add it to our calendar and email our sponsors.": {
        "mode": "PLAN",
        "summary": (
            "A full sponsor packet for Hacklanta II grounded in Hacklanta 1 metrics: 400+ attendees, "
            "$20,000 in sponsorships, $5,000+ in prizes. Covers what we proved, what we're improving, "
            "and three sponsorship tiers with concrete deliverables."
        ),
        "answer": (
            "## Hacklanta II Sponsor Packet\n"
            "*Generated by progsu Intelligence Agent. Based on Hacklanta 1 post-event data.*\n\n"
            "---\n\n"
            "## What We Proved at Hacklanta 1\n\n"
            "- **400+ attendees** at Georgia State University, the largest student hackathon in progsu history\n"
            "- **$20,000 in total sponsorships** raised in 5 weeks of outreach\n"
            "- **$5,000+ in prizes** distributed across 12 hours of competition\n"
            "- **DoorDash** covered food for ~150 attendees, saving the org approximately $1,200\n"
            "- **Red Bull and Celsius** provided energy drinks with on-floor brand activation\n"
            "- Sponsors received booth space, judging roles, and direct access to 400+ student developers\n\n"
            "---\n\n"
            "## What We're Improving for Hacklanta II\n\n"
            "- **Check-in flow:** Moving from paper sign-in to QR-code check-in to eliminate bottlenecks at Library South 102\n"
            "- **Parking coordination:** Pre-registering parking with GSU to reduce day-of reimbursement overhead\n"
            "- **Wi-Fi onboarding:** Pre-configured Eduroam links sent to non-GSU attendees before the event\n"
            "- **Sponsor visibility:** Dedicated sponsor slide deck during opening and closing ceremonies\n"
            "- **Run of show buffer:** Adding 15-minute buffers between major segments based on Hacklanta 1 timing overruns\n\n"
            "---\n\n"
            "## Sponsorship Tiers\n\n"
            "| Tier | Investment | What You Get |\n"
            "| --- | --- | --- |\n"
            "| Title Sponsor | $5,000+ | Name in event title, keynote slot, top booth placement, logo on all materials |\n"
            "| Gold Sponsor | $2,500 | Booth space, judging panel seat, logo on website and signage |\n"
            "| Silver Sponsor | $1,000 | Logo on website, social media mention, swag table space |\n"
            "| In-Kind Sponsor | Food, drinks, prizes | Brand activation on floor, mention in opening ceremonies |\n\n"
            "---\n\n"
            "## Why Sponsor progsu\n\n"
            "- Direct access to 400+ student developers at Georgia State, one of the largest CS programs in the Southeast\n"
            "- Demonstrated execution: we raised $20k and ran a 12-hour hackathon in 5 weeks\n"
            "- Sponsor alumni: DoorDash, Red Bull, Celsius, and Anthropic all activated at Hacklanta 1\n"
            "- Recruiting pipeline: sponsors who hosted booths reported direct interview conversations on the day\n\n"
            "---\n\n"
            "## Next Steps\n\n"
            "- Kickoff planning meeting added to calendar\n"
            "- Outreach email sent to sponsor contacts from Hacklanta 1\n"
            "- Confirm venue booking at Library South by end of month\n\n"
            "*Sources: Hacklanta Master Doc, Operations Meeting Notes, FAQs-Hacklanta, post-event growth data*"
        ),
        "citations": [
            {
                "title": "Hacklanta Master Doc - Spring 26",
                "date": "2026-03-01",
                "file_id": "1YFGL5-laW0CEaTHpR6gydZNV3SzWx0xO7n-IubrxTYc",
                "source_type": "google_drive",
                "drive_url": "https://docs.google.com/document/d/1YFGL5-laW0CEaTHpR6gydZNV3SzWx0xO7n-IubrxTYc/edit",
                "discord_url": None,
                "messages": None,
                "relevance_score": 10.0,
            },
            {
                "title": "FAQs - Hacklanta",
                "date": "2026-03-01",
                "file_id": "1ekbPvjUYMW7oNi8rzWHdoBT1F-DLlKkqLbxcIuuD12Q",
                "source_type": "google_drive",
                "drive_url": "https://docs.google.com/document/d/1ekbPvjUYMW7oNi8rzWHdoBT1F-DLlKkqLbxcIuuD12Q/edit",
                "discord_url": None,
                "messages": None,
                "relevance_score": 9.5,
            },
            {
                "title": "Operations Meeting Notes",
                "date": "2026-02-15",
                "file_id": "1-BK0mGR1gHHuKR4Axofuy0WdWReEYf1JDt3sV3-Lxnk",
                "source_type": "google_drive",
                "drive_url": "https://docs.google.com/document/d/1-BK0mGR1gHHuKR4Axofuy0WdWReEYf1JDt3sV3-Lxnk/edit",
                "discord_url": None,
                "messages": None,
                "relevance_score": 9.0,
            },
        ],
        "created_doc_url": None,
        "calendar_event_url": None,
        "calendar_event_id": None,
        "calendar_event_start_date": None,
        "gmail_draft_id": None,
        "gmail_draft_url": None,
    },
}


def _apply_demo_seeds() -> None:
    for query, value in _DEMO_SEEDS.items():
        key = _cache_key(query, None)
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


def _cache_key(query: str, filters: Optional[dict]) -> str:
    # Strip non-retrieval fields (e.g. plan_doc_url) so they don't cause cache misses
    clean = {k: v for k, v in (filters or {}).items() if k not in _NON_CACHE_FILTER_KEYS}
    payload = query.strip().lower() + json.dumps(clean, sort_keys=True)
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
    allow_headers=["Content-Type", "Accept"],
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


@app.on_event("startup")
async def startup():
    _apply_demo_seeds()
    logger.info("Demo seeds loaded into cache (%d of %d — PLAN skipped until live run)", len(_response_cache), len(_DEMO_SEEDS))


@app.post("/cache/clear")
async def clear_cache(http_request: Request):
    # Unauthenticated cache clears let anyone force live Gemini spend.
    # If ADMIN_TOKEN is set, require it; in DEMO_MODE with no token configured, deny.
    admin_token = os.environ.get("ADMIN_TOKEN")
    if admin_token:
        if http_request.headers.get("x-admin-token") != admin_token:
            raise HTTPException(status_code=403, detail="Forbidden")
    elif _DEMO_MODE:
        raise HTTPException(status_code=403, detail="Forbidden")
    _response_cache.clear()
    _apply_demo_seeds()
    logger.info("Response cache cleared and demo seeds reloaded")
    return {"cleared": True}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, http_request: Request):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    if not _check_daily_cap():
        raise HTTPException(status_code=503, detail="Demo capacity reached for today. Check back tomorrow.")

    ip = _get_client_ip(http_request)
    started = time.perf_counter()

    if _DEMO_MODE:
        if not _check_rate_limit(ip):
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")

        guard_err = _check_query(request.query.strip())
        if guard_err:
            _log_query_bg(request.query, "BLOCKED", ip, 0, injection_flagged=True)
            raise HTTPException(status_code=400, detail=guard_err)

    _count_daily_request()

    logger.info("POST /chat/stream: %s", request.query[:80])

    cache_key = _cache_key(request.query, request.filters)
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
            _log_query_bg(request.query, cached["mode"], ip, (time.perf_counter() - started) * 1000, cache_hit=True)
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
async def chat(request: ChatRequest, http_request: Request):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    if not _check_daily_cap():
        raise HTTPException(status_code=503, detail="Demo capacity reached for today. Check back tomorrow.")

    ip = _get_client_ip(http_request)
    started = time.perf_counter()
    if not _check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")

    guard_err = _check_query(request.query.strip())
    if guard_err:
        _log_query_bg(request.query, "BLOCKED", ip, 0, injection_flagged=True)
        raise HTTPException(status_code=400, detail=guard_err)

    _count_daily_request()

    logger.info("POST /chat: %s", request.query[:80])

    cache_key = _cache_key(request.query, request.filters)
    cached = _cache_get(cache_key)
    if cached and cached.get("mode") != "PLAN":
        logger.info("Cache hit for query: %s", request.query[:60])
        _log_query_bg(request.query, cached["mode"], ip, (time.perf_counter() - started) * 1000, cache_hit=True)
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
        if response.mode != "PLAN":
            _cache_set(cache_key, response.model_dump())
        _log_query_bg(
            request.query,
            response.mode,
            ip,
            (time.perf_counter() - started) * 1000,
            confidence=_best_confidence(result.get("citations")),
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
