"""
Ingest Discord channel exports into MongoDB Atlas.

Usage:
    python3 -m src.ingestion.run_discord_ingestion --input discord_export/

Expects the discord_export/ directory to contain JSON files exported by
DiscordChatExporter CLI (--format Json). Each file = one channel.
"""
import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from src.ingestion.discord_reader import read_discord_export_dir
from src.ingestion.embedder import get_embedding
from src.ingestion.noise_filter import is_useful_chunk
from src.ingestion.pii_filter import strip_pii_regex
from src.ingestion.storer import store_chunk

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Map channel names to doc_type metadata.
# ORDER MATTERS: more specific keys must come before substrings they contain.
# e.g. "hacklanta" before "general" so "hacklanta-general" maps to event_logistics.
# Channels to skip entirely — social, media, bots, admin noise
SKIP_CHANNEL_SUBSTRINGS: tuple[str, ...] = (
    "off-topic",
    "meme",
    "bot-test",
    "bot-command",
    "tech-bot",
    "admin-bot",
    "admin-info",
    "food",
    "pics-and-media",
    "receipts",
    "crab-fits",
    "nasharoni",
    "commands",
    "welcome",
    "socials",
    "rules-dot-md",
    "join-log",
    "trial",
    "spiels",
    "graphics",
    "test",
)


def _should_skip_channel(channel: str) -> bool:
    c = channel.lower()
    return any(skip in c for skip in SKIP_CHANNEL_SUBSTRINGS)


CHANNEL_DOC_TYPES: dict[str, str] = {
    "hacklanta": "event_logistics",
    "announcements": "wiki",
    "exec": "meeting_notes",
    "leadership": "meeting_notes",
    "operations": "meeting_notes",
    "growth": "growth",
    "marketing": "growth",
    "feedback": "feedback_aggregate",
    "debrief": "feedback_aggregate",
    "general": "meeting_notes",
}


def _doc_type_for_channel(channel: str) -> str:
    channel_lower = channel.lower()
    for key, doc_type in CHANNEL_DOC_TYPES.items():
        if key in channel_lower:
            return doc_type
    return "meeting_notes"


def _semester_for_date(date: str) -> str:
    if not date or date == "unknown":
        return "all"
    try:
        year, month = int(date[:4]), int(date[5:7])
        if month >= 8:
            return "fall_2025" if year == 2025 else "all"
        elif month <= 5:
            return "spring_2026" if year == 2026 else "all"
    except Exception:
        pass
    return "all"


def main(export_dir: Path, skip_noise_filter: bool = False) -> None:
    if not export_dir.exists():
        logger.error("Export directory not found: %s", export_dir)
        return

    json_files = list(export_dir.glob("*.json"))
    if not json_files:
        logger.error("No JSON files found in %s", export_dir)
        return

    logger.info("Found %d channel export(s) in %s", len(json_files), export_dir)

    total_chunks = 0
    total_stored = 0
    total_noise_filtered = 0

    for json_path, chunk in read_discord_export_dir(export_dir):
        text = chunk["text"]
        channel = chunk["channel"]
        date = chunk["date"]
        chunk_index = chunk["chunk_index"]
        discord_url = chunk.get("discord_url")
        display_messages = chunk.get("messages", [])

        if _should_skip_channel(channel):
            continue

        # PII strip (regex only — fast, no Gemini call)
        text = strip_pii_regex(text)

        total_chunks += 1

        # Noise filter
        if not skip_noise_filter:
            try:
                if not is_useful_chunk(text):
                    total_noise_filtered += 1
                    continue
            except Exception as e:
                logger.warning("Noise filter error for %s chunk %d: %s", channel, chunk_index, e)

        # Embed
        try:
            embedding = get_embedding(text)
        except Exception as e:
            logger.error("Embedding failed for %s chunk %d: %s", channel, chunk_index, e)
            continue

        # Store
        metadata = {
            "source_type": "discord",
            "doc_type": _doc_type_for_channel(channel),
            "semester": _semester_for_date(date),
            "event_name": "hacklanta" if "hacklanta" in channel.lower() else None,
            "date": date,
            "team": None,
            "file_id": f"discord_{channel}",
            "file_title": f"Discord #{channel}",
            "chunk_index": chunk_index,
            "source_heading": f"{channel}, {date}",
            "discord_url": discord_url,
            "messages": display_messages,
        }

        try:
            store_chunk(text=text, embedding=embedding, metadata=metadata)
            total_stored += 1
            logger.info("Stored #%s %s chunk %d", channel, date, chunk_index)
        except Exception as e:
            logger.error("Store failed for %s chunk %d: %s", channel, chunk_index, e)

    noise_rate = (total_noise_filtered / total_chunks * 100) if total_chunks else 0
    logger.info(
        "Done. %d total chunks | %d stored | %d noise-filtered (%.0f%%)",
        total_chunks,
        total_stored,
        total_noise_filtered,
        noise_rate,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Discord exports into MongoDB Atlas")
    parser.add_argument("--input", default="discord_export", help="Directory containing JSON exports")
    parser.add_argument("--skip-noise-filter", action="store_true", help="Skip Gemini noise filter (faster)")
    args = parser.parse_args()
    main(Path(args.input), skip_noise_filter=args.skip_noise_filter)
