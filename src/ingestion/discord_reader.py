"""
Parse DiscordChatExporter JSON exports into text chunks suitable for ingestion.

Input: JSON file produced by DiscordChatExporter CLI (--format Json)
Output: list of dicts with {text, channel, date, chunk_index, guild_id, channel_id,
        first_message_id, discord_url, messages}

Chunking strategy: group messages by calendar day, produce one chunk per day
that has >= MIN_MESSAGES meaningful messages. Skip days with only bot/system noise.
"""
import json
import re
from pathlib import Path
from typing import Iterator, Optional

MIN_MESSAGES_PER_CHUNK = 3
MAX_CHUNK_CHARS = 3000

# Exec first names safe to display per PII_RULES.md
EXEC_FIRST_NAMES = frozenset({
    "john", "liam", "charan", "natasha", "jared",
    "joey", "carter", "tyler", "aaron", "ibe", "temi",
    "eda", "ishan", "phillip",
})

BOT_INDICATORS = {"MEE6", "Carl-bot", "Dyno", "ProBot", "Ticket Tool", "Captcha.bot"}


def _is_bot_message(msg: dict) -> bool:
    author = msg.get("author", {})
    if author.get("isBot"):
        return True
    if author.get("name", "") in BOT_INDICATORS:
        return True
    return False


def _clean_content(content: str) -> str:
    content = re.sub(r"<@!?\d+>", "@member", content)
    content = re.sub(r"<@&\d+>", "@role", content)
    content = re.sub(r"<#\d+>", "#channel", content)
    content = re.sub(r"<a?:\w+:\d+>", "", content)
    content = re.sub(r"https?://\S+", "[link]", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def _extract_display_author(msg: dict) -> str:
    """Return exec first name if recognized, else '@member'."""
    author = msg.get("author", {})
    nickname = author.get("nickname") or author.get("name") or ""
    first = nickname.split()[0].lower() if nickname else ""
    if first in EXEC_FIRST_NAMES:
        return nickname.split()[0]
    return "@member"


def _format_message(msg: dict) -> str:
    """Format a message as a text line for the chunk body (no author name)."""
    content = _clean_content(msg.get("content", ""))
    if not content:
        return ""
    ts = msg.get("timestamp", "")
    hour = ts[11:16] if len(ts) >= 16 else ""
    return f"[{hour}] {content}" if hour else content


def _format_message_for_display(msg: dict) -> Optional[dict]:
    """Format a message for UI display with author attribution."""
    content = _clean_content(msg.get("content", ""))
    if not content:
        return None
    ts = msg.get("timestamp", "")
    hour = ts[11:16] if len(ts) >= 16 else ""
    return {"time": hour, "author": _extract_display_author(msg), "content": content}


def _parse_date(ts: str) -> str:
    try:
        return ts[:10]
    except Exception:
        return "unknown"


def _build_chunk(
    guild: str,
    channel: str,
    date: str,
    msgs: list[dict],
    guild_id: str,
    channel_id: str,
    chunk_index: int,
) -> dict:
    lines = [_format_message(m) for m in msgs]
    text = f"Discord channel #{channel} ({guild}), {date}\n" + "\n".join(line for line in lines if line)

    first_message_id = msgs[0].get("id", "") if msgs else ""
    discord_url = (
        f"https://discord.com/channels/{guild_id}/{channel_id}/{first_message_id}"
        if guild_id and channel_id and first_message_id
        else None
    )

    display_messages = [m for m in (_format_message_for_display(msg) for msg in msgs) if m]

    return {
        "text": text,
        "channel": channel,
        "date": date,
        "chunk_index": chunk_index,
        "guild_id": guild_id,
        "channel_id": channel_id,
        "first_message_id": first_message_id,
        "discord_url": discord_url,
        "messages": display_messages,
    }


def read_discord_export(json_path: Path) -> Iterator[dict]:
    """
    Parse a DiscordChatExporter JSON file and yield daily chunk dicts.

    Each yielded dict:
      text             - chunk text for embedding (no author names)
      channel          - channel name
      date             - YYYY-MM-DD
      chunk_index      - position within this channel's chunks
      guild_id         - Discord server ID
      channel_id       - Discord channel ID
      first_message_id - ID of the first message in this chunk (for deep link)
      discord_url      - discord.com deep link to the first message
      messages         - list of {time, author, content} for UI display
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    channel_name = data.get("channel", {}).get("name", json_path.stem)
    guild_name = data.get("guild", {}).get("name", "progsu")
    guild_id = data.get("guild", {}).get("id", "")
    channel_id = data.get("channel", {}).get("id", "")
    raw_messages = data.get("messages", [])

    # Group non-bot, non-empty messages by calendar day
    by_date: dict[str, list[dict]] = {}
    for msg in raw_messages:
        if _is_bot_message(msg):
            continue
        date = _parse_date(msg.get("timestamp", ""))
        if _format_message(msg):
            by_date.setdefault(date, []).append(msg)

    chunk_index = 0
    for date in sorted(by_date.keys()):
        day_messages = by_date[date]
        if len(day_messages) < MIN_MESSAGES_PER_CHUNK:
            continue

        current_msgs: list[dict] = []
        current_len = 0
        for msg in day_messages:
            line = _format_message(msg)
            if current_len + len(line) > MAX_CHUNK_CHARS and current_msgs:
                if len(current_msgs) >= MIN_MESSAGES_PER_CHUNK:
                    yield _build_chunk(guild_name, channel_name, date, current_msgs, guild_id, channel_id, chunk_index)
                    chunk_index += 1
                current_msgs = []
                current_len = 0
            current_msgs.append(msg)
            current_len += len(line) + 1

        if len(current_msgs) >= MIN_MESSAGES_PER_CHUNK:
            yield _build_chunk(guild_name, channel_name, date, current_msgs, guild_id, channel_id, chunk_index)
            chunk_index += 1


def read_discord_export_dir(export_dir: Path) -> Iterator[tuple[Path, dict]]:
    """Yield (json_path, chunk) for all JSON files in a directory."""
    for json_path in sorted(export_dir.glob("*.json")):
        for chunk in read_discord_export(json_path):
            yield json_path, chunk
