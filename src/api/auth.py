"""Discord OAuth login and tier resolution.

Flow: /auth/login redirects to Discord's authorize page (identify scope only).
Discord redirects back to /auth/callback, which exchanges the code, looks up
the user's roles in the progsu server via the bot token, maps roles to a tier,
and redirects to the frontend with a signed bearer token in the URL fragment.
The frontend stores it and sends `Authorization: Bearer <token>` on every
request; get_access() verifies it and re-resolves the tier through a 1-hour
role cache so role changes take effect without re-login.

Required env vars (auth is disabled and everything falls back to legacy
DEMO_MODE behavior until all of these are set):
  DISCORD_CLIENT_ID / DISCORD_CLIENT_SECRET   OAuth application
  DISCORD_BOT_TOKEN                            guild member role lookup
  DISCORD_GUILD_ID                             the progsu server id
  SESSION_SECRET                               HMAC key for bearer tokens
Optional:
  DISCORD_EXEC_ROLE_IDS    comma-separated role ids mapped to exec
  DISCORD_ADMIN_ROLE_IDS   comma-separated role ids mapped to admin
  DISCORD_ADMIN_USER_IDS   comma-separated user ids always admin (bootstrap)
  DISCORD_REDIRECT_URI     defaults to <request base>/auth/callback
  FRONTEND_URL             post-login redirect target
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from src.access import (
    TIER_ADMIN,
    TIER_ANONYMOUS,
    TIER_EXEC,
    TIER_MEMBER,
    Access,
    access_for_tier,
    legacy_default,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth")

_DISCORD_API = "https://discord.com/api/v10"
_TOKEN_TTL = 7 * 24 * 3600
_STATE_TTL = 600
_ROLE_CACHE_TTL = 3600

# user_id -> (tier, username, expires_at)
_role_cache: dict = {}


def _cfg(name: str) -> str:
    return os.environ.get(name, "")


def auth_configured() -> bool:
    return all(_cfg(n) for n in (
        "DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET",
        "DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID", "SESSION_SECRET",
    ))


def _csv_env(name: str) -> set:
    return {v.strip() for v in _cfg(name).split(",") if v.strip()}


# --- Signed bearer tokens (stdlib HMAC, no extra crypto deps) ---

def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def sign_token(payload: dict, secret: str, ttl: int = _TOKEN_TTL) -> str:
    body = dict(payload)
    body["exp"] = int(time.time()) + ttl
    raw = json.dumps(body, separators=(",", ":")).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).digest()
    return f"{_b64e(raw)}.{_b64e(sig)}"


def verify_token(token: str, secret: str) -> Optional[dict]:
    try:
        raw_b64, sig_b64 = token.split(".", 1)
        raw = _b64d(raw_b64)
        expected = hmac.new(secret.encode(), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64d(sig_b64)):
            return None
        payload = json.loads(raw)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# --- Role to tier mapping ---

def tier_from_roles(roles: list, user_id: str) -> str:
    """Map a guild member's role ids to a tier. Being in the guild at all
    makes you at least a member."""
    # TODO(permission-overrides): check an Atlas access_overrides collection
    # here so individual members can be granted temporary exec/admin access
    # without a Discord role change. See src/access.py module docstring.
    if user_id in _csv_env("DISCORD_ADMIN_USER_IDS"):
        return TIER_ADMIN
    role_set = set(roles or [])
    if role_set & _csv_env("DISCORD_ADMIN_ROLE_IDS"):
        return TIER_ADMIN
    if role_set & _csv_env("DISCORD_EXEC_ROLE_IDS"):
        return TIER_EXEC
    return TIER_MEMBER


async def _lookup_tier(user_id: str) -> Optional[str]:
    """Fetch guild membership via the bot token. Returns a tier, or None if
    Discord is unreachable (caller falls back to the tier baked in the token)."""
    url = f"{_DISCORD_API}/guilds/{_cfg('DISCORD_GUILD_ID')}/members/{user_id}"
    headers = {"Authorization": f"Bot {_cfg('DISCORD_BOT_TOKEN')}"}
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(url, headers=headers)
        if resp.status_code == 404:
            return TIER_ANONYMOUS  # not in the server (anymore)
        resp.raise_for_status()
        return tier_from_roles(resp.json().get("roles", []), user_id)
    except Exception as e:
        logger.warning("Discord role lookup failed for %s: %s", user_id, e)
        return None


async def resolve_tier(user_id: str, fallback: str = TIER_ANONYMOUS) -> str:
    now = time.time()
    cached = _role_cache.get(user_id)
    if cached and cached[2] > now:
        return cached[0]
    tier = await _lookup_tier(user_id)
    if tier is None:
        # Discord unreachable at the cache-refresh boundary. Fall back to the
        # last known (now-stale) cache entry rather than the bearer token's
        # baked-in tier: the token can be valid for up to 7 days, so trusting
        # it here would let a demoted/kicked admin keep elevated access far
        # longer than the intended ~1-hour revocation window. A stale cache
        # entry is bounded by how recently the last successful check ran.
        if cached:
            return cached[0]
        return fallback
    _role_cache[user_id] = (tier, None, now + _ROLE_CACHE_TTL)
    return tier


# --- FastAPI dependency ---

async def get_access(request: Request) -> Access:
    if not auth_configured():
        return legacy_default()
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return access_for_tier(TIER_ANONYMOUS)
    payload = verify_token(auth_header[7:], _cfg("SESSION_SECRET"))
    if not payload or not payload.get("uid"):
        return access_for_tier(TIER_ANONYMOUS)
    tier = await resolve_tier(payload["uid"], fallback=payload.get("tier", TIER_ANONYMOUS))
    return access_for_tier(tier, user_id=payload["uid"], username=payload.get("name"))


# --- Endpoints ---

def _redirect_uri(request: Request) -> str:
    return _cfg("DISCORD_REDIRECT_URI") or str(request.url_for("auth_callback"))


@router.get("/login")
async def auth_login(request: Request):
    if not auth_configured():
        raise HTTPException(status_code=501, detail="Discord auth is not configured on this deployment.")
    state = sign_token({"n": secrets.token_urlsafe(8)}, _cfg("SESSION_SECRET"), ttl=_STATE_TTL)
    params = httpx.QueryParams({
        "client_id": _cfg("DISCORD_CLIENT_ID"),
        "redirect_uri": _redirect_uri(request),
        "response_type": "code",
        "scope": "identify",
        "state": state,
        "prompt": "none",
    })
    return RedirectResponse(f"{_DISCORD_API}/oauth2/authorize?{params}")


@router.get("/callback", name="auth_callback")
async def auth_callback(request: Request, code: str = "", state: str = ""):
    if not auth_configured():
        raise HTTPException(status_code=501, detail="Discord auth is not configured on this deployment.")
    if not code or not verify_token(state, _cfg("SESSION_SECRET")):
        raise HTTPException(status_code=400, detail="Invalid login attempt. Please try again.")

    try:
        async with httpx.AsyncClient(timeout=15) as http:
            token_resp = await http.post(
                f"{_DISCORD_API}/oauth2/token",
                data={
                    "client_id": _cfg("DISCORD_CLIENT_ID"),
                    "client_secret": _cfg("DISCORD_CLIENT_SECRET"),
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _redirect_uri(request),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_resp.raise_for_status()
            user_resp = await http.get(
                f"{_DISCORD_API}/users/@me",
                headers={"Authorization": f"Bearer {token_resp.json()['access_token']}"},
            )
            user_resp.raise_for_status()
            user = user_resp.json()
    except Exception as e:
        logger.error("Discord OAuth exchange failed: %s", e)
        raise HTTPException(status_code=502, detail="Login with Discord failed. Please try again.")

    user_id = user["id"]
    username = user.get("global_name") or user.get("username", "")
    tier = await resolve_tier(user_id)
    _role_cache[user_id] = (tier, username, time.time() + _ROLE_CACHE_TTL)
    token = sign_token({"uid": user_id, "name": username, "tier": tier}, _cfg("SESSION_SECRET"))
    logger.info("Login: %s resolved to tier %s", username, tier)

    frontend = _cfg("FRONTEND_URL").rstrip("/")
    return RedirectResponse(f"{frontend}/#token={token}" if frontend else f"/#token={token}")


@router.get("/me")
async def auth_me(access: Access = Depends(get_access)):
    return {**access.as_dict(), "auth_configured": auth_configured()}
