"""Fetch Discord messages via the bot token REST API.

Replaces the manual DiscordChatExporter step. Polling REST (not a gateway
listener) matches the ephemeral scheduled-job model: a live connection cannot
replay what it missed while down, a scheduled poll always can.

Messages are converted to the same dict shape DiscordChatExporter's JSON
produces ({id, timestamp, content, author: {isBot, name, nickname}}) so the
existing discord_reader grouping/cleaning functions work unchanged.
"""
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

_API = "https://discord.com/api/v10"
_DISCORD_EPOCH_MS = 1420070400000
_TEXT_CHANNEL_TYPES = {0, 5}  # guild text + announcement

DEFAULT_WINDOW_DAYS = 14


def _bot_headers() -> dict:
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN is not set")
    return {"Authorization": f"Bot {token}"}


def snowflake_for_time(dt: datetime) -> int:
    """Discord snowflake ids embed a timestamp; a synthetic snowflake for a
    moment in time lets `after=` pagination start at that moment."""
    unix_ms = int(dt.timestamp() * 1000)
    return (unix_ms - _DISCORD_EPOCH_MS) << 22


def window_start_snowflake(days: int = DEFAULT_WINDOW_DAYS) -> int:
    return snowflake_for_time(datetime.now(timezone.utc) - timedelta(days=days))


def _get_with_rate_limit(http: httpx.Client, url: str, params: dict) -> httpx.Response:
    for _ in range(5):
        resp = http.get(url, headers=_bot_headers(), params=params)
        if resp.status_code == 429:
            wait = float(resp.json().get("retry_after", 1.0))
            logger.warning("Discord rate limited, sleeping %.1fs", wait)
            time.sleep(wait)
            continue
        return resp
    resp.raise_for_status()
    return resp


def list_text_channels(guild_id: str) -> list[dict]:
    """Return [{id, name}] for all text channels the bot can see."""
    with httpx.Client(timeout=15) as http:
        resp = _get_with_rate_limit(http, f"{_API}/guilds/{guild_id}/channels", {})
        resp.raise_for_status()
        return [
            {"id": c["id"], "name": c["name"]}
            for c in resp.json()
            if c.get("type") in _TEXT_CHANNEL_TYPES
        ]


def _to_exporter_shape(msg: dict) -> dict:
    author = msg.get("author", {})
    return {
        "id": msg.get("id", ""),
        "timestamp": msg.get("timestamp", ""),
        "content": msg.get("content", ""),
        "author": {
            "isBot": author.get("bot", False),
            "name": author.get("username", ""),
            "nickname": author.get("global_name") or author.get("username", ""),
        },
    }


def fetch_messages_window(channel_id: str, days: int = DEFAULT_WINDOW_DAYS) -> list[dict]:
    """Fetch all messages in the rolling window, oldest first, in exporter
    dict shape. Re-fetching a window that overlaps the previous run silently
    corrects edits and reactions on already-ingested days, because date-keyed
    chunks just re-upsert. Returns [] for channels the bot cannot read (403)."""
    after = window_start_snowflake(days)
    messages: list[dict] = []
    with httpx.Client(timeout=20) as http:
        while True:
            resp = _get_with_rate_limit(
                http,
                f"{_API}/channels/{channel_id}/messages",
                {"after": str(after), "limit": 100},
            )
            if resp.status_code == 403:
                logger.info("No read access to channel %s, skipping", channel_id)
                return []
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            # Discord returns newest-first within a batch; sort and advance
            batch.sort(key=lambda m: int(m["id"]))
            messages.extend(_to_exporter_shape(m) for m in batch)
            after = int(batch[-1]["id"])
            if len(batch) < 100:
                break
    logger.info("Fetched %d messages from channel %s (%dd window)", len(messages), channel_id, days)
    return messages
