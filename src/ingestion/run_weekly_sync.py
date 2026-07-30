"""Weekly knowledge refresh: Drive delta then Discord delta.

Usage:
    python -m src.ingestion.run_weekly_sync            # full sync
    python -m src.ingestion.run_weekly_sync --dry-run  # report what would sync, no Gemini spend
    python -m src.ingestion.run_weekly_sync --skip-drive / --skip-discord

Designed to run as a scheduled Cloud Run Job (Cloud Scheduler, weekly). Run
summaries go to the sync_runs collection because job containers don't keep
local disk between runs. Only successfully processed sources get marked
synced, so failures retry automatically next run.

Drive: walks the root folder, re-ingests only files whose modifiedTime
changed, and deletes orphaned tail chunks when a file shrinks.

Discord: fetches a rolling window (default 14 days, 2x the weekly cadence)
per channel through the bot token. Date-keyed chunks make the overlap
idempotent: re-processed days re-upsert the same key with refreshed text, so
edits and reactions inside the window self-correct with no separate rescan
job. A text-hash check per chunk skips the Gemini noise-filter and embedding
calls for unchanged days.
"""
import argparse
import hashlib
import logging
import os
import time

from dotenv import load_dotenv
from google import genai

from src.org_config import load_org_config
from src.ingestion.access_classifier import classify_chunk_access
from src.ingestion.discord_fetcher import DEFAULT_WINDOW_DAYS, fetch_messages_window, list_text_channels
from src.ingestion.discord_reader import LEGACY_CHUNK_KEY_CEILING, chunks_from_messages, date_chunk_key
from src.ingestion.drive_reader import get_drive_service
from src.ingestion.drive_walker import delete_orphaned_chunks, sweep_deleted_files, walk_drive_folder
from src.ingestion.embedder import get_embedding
from src.ingestion.noise_filter import is_useful_chunk
from src.ingestion.pii_filter import strip_pii_regex
from src.ingestion.run_discord_ingestion import _doc_type_for_channel, _semester_for_date, _should_skip_channel
from src.ingestion.run_ingestion import ingest_file
from src.ingestion.storer import get_collection, store_chunk
from src.ingestion.sync_state import get_source_state, get_state_collection, mark_synced, record_run

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _gemini_client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _window_floor_key(window_days: int) -> int:
    """Smallest date_chunk_key inside the fetch window; chunks at or above this
    key that a run does not re-produce correspond to deleted conversations."""
    from datetime import datetime, timedelta, timezone
    start = datetime.now(timezone.utc) - timedelta(days=window_days)
    return date_chunk_key(start.strftime("%Y-%m-%d"), 0)


def _post_webhook_summary(summary: dict) -> None:
    """One-line run report to a Discord channel webhook, so a failing sync is
    noticed instead of silently going stale. No-op unless DISCORD_SYNC_WEBHOOK_URL
    is set."""
    url = os.environ.get("DISCORD_SYNC_WEBHOOK_URL", "")
    if not url:
        return
    d, dc = summary.get("drive", {}), summary.get("discord", {})
    errors = d.get("errors", 0) + dc.get("errors", 0)
    icon = "⚠️" if errors else "✅"
    content = (
        f"{icon} Weekly knowledge sync: Drive {d.get('synced', 0)} synced / {d.get('skipped', 0)} unchanged / "
        f"{d.get('swept', 0)} removed. Discord {dc.get('stored', 0)} chunks stored / {dc.get('hash_skipped', 0)} unchanged / "
        f"{dc.get('swept', 0)} removed. {errors} errors. {summary.get('duration_s', '?')}s."
    )
    try:
        import httpx
        httpx.post(url, json={"content": content}, timeout=10)
    except Exception as e:
        logger.warning("Sync webhook post failed: %s", e)


def sync_drive(dry_run: bool = False) -> dict:
    root = os.environ.get("DRIVE_ROOT_FOLDER_ID") or load_org_config().get("drive_root_folder_id", "")
    vp_root = os.environ.get("VP_ONLY_FOLDER_ID") or load_org_config().get("vp_only_folder_id", "")
    if not root:
        logger.warning("No drive_root_folder_id configured, skipping Drive sync")
        return {"skipped": 0, "synced": 0, "errors": 0, "unconfigured": True}

    service = get_drive_service()
    collection = get_collection()
    state_coll = get_state_collection()
    client = None if dry_run else _gemini_client()

    stats = {"skipped": 0, "synced": 0, "errors": 0, "swept": 0, "would_sync": []}
    walked = walk_drive_folder(service, root)
    if vp_root:
        # exec-only tier: every chunk from this tree is gated regardless of
        # content, same drop-for-restricted-tiers path as financial chunks
        walked += walk_drive_folder(service, vp_root, forced_access_level="exec")
    if not dry_run:
        stats["swept"] = sweep_deleted_files(collection, state_coll, {s["file_id"] for s in walked})
    for spec in walked:
        file_id = spec["file_id"]
        state = get_source_state(file_id, state_coll)
        if state and state.get("modified_time") == spec["modified_time"]:
            stats["skipped"] += 1
            continue
        if dry_run:
            stats["would_sync"].append(spec["file_title"])
            continue
        try:
            summary = ingest_file(spec, service, client, collection)
            delete_orphaned_chunks(
                collection, file_id, summary.get("chunks_stored", 0),
                state.get("chunk_count") if state else None,
            )
            mark_synced(
                file_id, "google_drive", state_coll=state_coll,
                modified_time=spec["modified_time"],
                chunk_count=summary.get("chunks_stored", 0),
                file_title=spec.get("file_title"),
            )
            stats["synced"] += 1
        except Exception as e:
            logger.error("Drive sync failed for %s: %s", spec.get("file_title", file_id), e)
            mark_synced(file_id, "google_drive", status=f"error: {e}"[:200], state_coll=state_coll)
            stats["errors"] += 1
    return stats


def sync_discord(window_days: int = DEFAULT_WINDOW_DAYS, dry_run: bool = False) -> dict:
    guild_id = os.environ.get("DISCORD_GUILD_ID", "")
    if not guild_id or not os.environ.get("DISCORD_BOT_TOKEN"):
        logger.warning("Discord bot credentials not configured, skipping Discord sync")
        return {"channels": 0, "stored": 0, "hash_skipped": 0, "errors": 0, "unconfigured": True}

    collection = get_collection()
    state_coll = get_state_collection()
    client = None if dry_run else _gemini_client()
    stats = {"channels": 0, "stored": 0, "hash_skipped": 0, "noise_filtered": 0, "swept": 0, "errors": 0, "would_sync": []}
    window_floor = _window_floor_key(window_days)

    for channel in list_text_channels(guild_id):
        name = channel["name"]
        channel_id = channel["id"]
        if _should_skip_channel(name):
            continue
        stats["channels"] += 1
        # State keys on the channel ID: stable through renames, unlike the name
        source_id = f"discord_channel_{channel_id}"
        display_file_id = f"discord_{name}"
        try:
            messages = fetch_messages_window(channel_id, window_days)
            chunks = list(chunks_from_messages("progsu", name, guild_id, channel_id, messages))
            if dry_run:
                if chunks:
                    stats["would_sync"].append(f"#{name}: {len(chunks)} chunks from {len(messages)} messages")
                continue

            # Fall back to the pre-rename name-keyed state doc so its hashes carry over
            state = get_source_state(source_id, state_coll) or get_source_state(display_file_id, state_coll) or {}
            hashes: dict = dict(state.get("chunk_hashes", {}))

            # One-time purge of pre-sync sequential chunk keys, which would
            # otherwise duplicate date-keyed upserts for the same days
            if not state.get("legacy_purged"):
                purged = collection.delete_many({
                    "metadata.file_id": display_file_id,
                    "metadata.chunk_index": {"$lt": LEGACY_CHUNK_KEY_CEILING},
                }).deleted_count
                if purged:
                    logger.info("Purged %d legacy sequential-key chunks for #%s", purged, name)

            # If the channel was renamed, re-label existing chunks to the current name
            collection.update_many(
                {"metadata.channel_id": channel_id, "metadata.file_id": {"$ne": display_file_id}},
                {"$set": {"metadata.file_id": display_file_id, "metadata.file_title": f"Discord #{name}"}},
            )

            produced_keys = []
            for chunk in chunks:
                text = strip_pii_regex(chunk["text"])
                key = str(chunk["chunk_index"])
                produced_keys.append(chunk["chunk_index"])
                digest = hashlib.sha256(text.encode()).hexdigest()
                if hashes.get(key) == digest:
                    stats["hash_skipped"] += 1
                    continue
                if not is_useful_chunk(text):
                    stats["noise_filtered"] += 1
                    hashes[key] = digest  # remember the verdict, skip next run too
                    continue
                access = classify_chunk_access(text, client)
                doc = {
                    "text": text,
                    "embedding": get_embedding(text),
                    "redacted_text": access["redacted"],
                    "metadata": {
                        "source_type": "discord",
                        "doc_type": _doc_type_for_channel(name),
                        "semester": _semester_for_date(chunk["date"]),
                        "event_name": next((e for k, e in load_org_config().get("event_keyword_map", {}).items() if k in name.lower()), None),
                        "date": chunk["date"],
                        "team": None,
                        "file_id": display_file_id,
                        "file_title": f"Discord #{name}",
                        "channel_id": channel_id,
                        "access_level": access["level"],
                        "chunk_index": chunk["chunk_index"],
                        "source_heading": f"{name}, {chunk['date']}",
                        "discord_url": chunk.get("discord_url"),
                        "messages": chunk.get("messages", []),
                    },
                }
                # Upsert keyed by channel ID + chunk key, rename-proof
                collection.update_one(
                    {"metadata.channel_id": channel_id, "metadata.chunk_index": chunk["chunk_index"]},
                    {"$set": doc},
                    upsert=True,
                )
                hashes[key] = digest
                stats["stored"] += 1

            # Sweep: any stored chunk inside the window this run did NOT
            # re-produce means its day's messages were deleted; purge it so
            # deleted conversations stop being retrievable
            swept = collection.delete_many({
                "metadata.channel_id": channel_id,
                "metadata.chunk_index": {"$gte": window_floor, "$nin": produced_keys},
            }).deleted_count
            if swept:
                stats["swept"] += swept
                logger.info("Swept %d deleted-day chunks from #%s", swept, name)
                hashes = {k: v for k, v in hashes.items() if int(k) < window_floor or int(k) in produced_keys}

            mark_synced(
                source_id, "discord", state_coll=state_coll,
                last_message_id=messages[-1]["id"] if messages else state.get("last_message_id"),
                chunk_hashes=hashes,
                channel_name=name,
                legacy_purged=True,
            )
        except Exception as e:
            logger.error("Discord sync failed for #%s: %s", name, e)
            mark_synced(source_id, "discord", status=f"error: {e}"[:200], state_coll=state_coll)
            stats["errors"] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly Drive + Discord knowledge refresh")
    parser.add_argument("--dry-run", action="store_true", help="Report what would sync; no Gemini spend, no writes")
    parser.add_argument("--skip-drive", action="store_true")
    parser.add_argument("--skip-discord", action="store_true")
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    args = parser.parse_args()

    started = time.monotonic()
    drive_stats = {} if args.skip_drive else sync_drive(dry_run=args.dry_run)
    discord_stats = {} if args.skip_discord else sync_discord(window_days=args.window_days, dry_run=args.dry_run)
    duration = round(time.monotonic() - started, 1)

    summary = {"drive": drive_stats, "discord": discord_stats, "duration_s": duration, "dry_run": args.dry_run}
    logger.info("Weekly sync complete in %.1fs: drive=%s discord=%s", duration,
                {k: v for k, v in drive_stats.items() if k != "would_sync"},
                {k: v for k, v in discord_stats.items() if k != "would_sync"})
    for line in drive_stats.get("would_sync", []):
        logger.info("[dry-run] Drive would sync: %s", line)
    for line in discord_stats.get("would_sync", []):
        logger.info("[dry-run] Discord would sync: %s", line)
    if not args.dry_run:
        record_run(summary)
        _post_webhook_summary(summary)


if __name__ == "__main__":
    main()
