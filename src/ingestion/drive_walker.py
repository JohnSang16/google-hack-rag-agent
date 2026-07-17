"""Recursive Drive folder walk with change detection.

Replaces the hardcoded PRIORITY_1-5 file lists: walks the org's root folder,
skips files whose modifiedTime hasn't changed since ingestion_state, and
classifies metadata from the known specs first (files from the original manual
lists keep their curated doc_type/event/semester), falling back to folder-path
heuristics for files added since.
"""
import logging
from typing import Optional

from src.org_config import cfg_dict, cfg_list

logger = logging.getLogger(__name__)

_INGESTABLE_MIMES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
}
_SPREADSHEET_MIMES = {
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_FOLDER_MIME = "application/vnd.google-apps.folder"

_SKIP_NAME_SUBSTRINGS = ("copy of", "resume", "deprecated")


def _known_specs() -> dict:
    """file_id -> curated spec from the original manual priority lists."""
    from src.ingestion.run_ingestion import (
        AGGREGATE_SPECS, PRIORITY_1, PRIORITY_2, PRIORITY_3, PRIORITY_4, PRIORITY_5,
    )
    specs = {}
    for lst in (PRIORITY_1, PRIORITY_2, PRIORITY_3, PRIORITY_4, PRIORITY_5, AGGREGATE_SPECS):
        for spec in lst:
            specs[spec["file_id"]] = spec
    return specs


def _classify_from_path(name: str, path: str) -> dict:
    """Heuristic metadata for files not in the curated lists."""
    p = f"{path}/{name}".lower()
    doc_type = "wiki"
    if "meeting" in p or "minutes" in p:
        doc_type = "meeting_notes"
    elif "blueprint" in p:
        doc_type = "blueprint"
    elif "guide" in p:
        doc_type = "guide"
    elif "finance" in p or "bookkeeping" in p or "budget" in p:
        doc_type = "financial"
    elif "growth" in p or "marketing" in p:
        doc_type = "growth"
    elif "event" in p or "kickoff" in p or "workshop" in p:
        doc_type = "event_logistics"

    event_name = None
    for keyword, event in cfg_dict("event_keyword_map").items():
        if keyword in p:
            event_name = event
            break

    semester = "all"
    for year in ("2025", "2026", "2027"):
        if f"fall {year}" in p or f"fall_{year}" in p or f"fall{year}" in p:
            semester = f"fall_{year}"
        elif f"spring {year}" in p or f"spring_{year}" in p or f"spring{year}" in p:
            semester = f"spring_{year}"

    return {"doc_type": doc_type, "event_name": event_name, "semester": semester}


def spec_for_file(file_meta: dict, path: str, known: dict) -> dict:
    """Build the ingestion spec for one walked file. Files from the curated
    lists keep their hand-assigned metadata. Unknown spreadsheets default to
    the aggregate-summary path: roster-style sheets (sign-ins, attendance)
    are full of names and emails, and the aggregate path stores only
    Gemini-summarized stats, never raw rows."""
    file_id = file_meta["id"]
    if file_id in known:
        return dict(known[file_id])
    spec = {"file_id": file_id, "file_title": file_meta["name"], **_classify_from_path(file_meta["name"], path)}
    if file_meta["mimeType"] in _SPREADSHEET_MIMES:
        spec["agg_type"] = "spreadsheet"
        spec["doc_type"] = "feedback_aggregate"
    return spec


def walk_drive_folder(service, root_folder_id: str) -> list[dict]:
    """Return ingestable file specs for the whole tree under root_folder_id:
    [{file_id, file_title, mime_type, modified_time, doc_type, event_name,
      semester, agg_type?}]."""
    known = _known_specs()
    results: list[dict] = []
    stack = [(root_folder_id, "")]

    while stack:
        folder_id, path = stack.pop()
        page_token = None
        while True:
            resp = service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id,name,mimeType,modifiedTime)",
                pageSize=200,
                pageToken=page_token,
            ).execute()
            for f in resp.get("files", []):
                name = f["name"]
                if f["mimeType"] == _FOLDER_MIME:
                    if not any(s in name.lower() for s in _SKIP_NAME_SUBSTRINGS):
                        stack.append((f["id"], f"{path}/{name}"))
                    continue
                if f["mimeType"] not in _INGESTABLE_MIMES:
                    continue
                if any(s in name.lower() for s in _SKIP_NAME_SUBSTRINGS):
                    continue
                spec = spec_for_file(f, path, known)
                results.append({
                    **spec,
                    "mime_type": f["mimeType"],
                    "modified_time": f.get("modifiedTime", ""),
                    "drive_path": path,
                })
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    logger.info("Drive walk: %d ingestable files under root", len(results))
    return results


def sweep_deleted_files(collection, state_coll, walked_file_ids: set) -> int:
    """Purge chunks for Drive files that vanished from the walk (deleted,
    trashed, or moved out of the root). Without this, a deleted doc stays
    searchable forever."""
    deleted_chunks = 0
    gone = state_coll.find({
        "source_type": "google_drive",
        "source_id": {"$nin": list(walked_file_ids)},
    })
    for state in gone:
        source_id = state["source_id"]
        n = collection.delete_many({"metadata.file_id": source_id}).deleted_count
        state_coll.delete_one({"source_id": source_id})
        logger.info("Swept deleted Drive source %s (%d chunks purged)", state.get("file_title", source_id), n)
        deleted_chunks += n
    return deleted_chunks


def delete_orphaned_chunks(collection, file_id: str, new_chunk_count: int, old_chunk_count: Optional[int]) -> int:
    """A shrunken re-ingest leaves stale tail chunks retrievable forever unless
    the orphaned index range is deleted."""
    if old_chunk_count is None or new_chunk_count >= old_chunk_count:
        return 0
    result = collection.delete_many({
        "metadata.file_id": file_id,
        "metadata.chunk_index": {"$gte": new_chunk_count},
    })
    if result.deleted_count:
        logger.info("Deleted %d orphaned chunks for %s", result.deleted_count, file_id)
    return result.deleted_count
