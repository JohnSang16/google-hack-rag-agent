#!/usr/bin/env python3
"""
Ingestion pipeline orchestrator.

Usage:
    python -m src.ingestion.run_ingestion --priority 1
    python -m src.ingestion.run_ingestion --priority all
    python -m src.ingestion.run_ingestion --priority 1 --skip-gemini-pii
    python -m src.ingestion.run_ingestion --file-id <id> --doc-type event_logistics --event hacklanta
"""

import argparse
import logging
import os
import sys
import time
from typing import Optional

from google import genai
from dotenv import load_dotenv

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.ingestion.chunker import chunk_text
from src.ingestion.drive_reader import GOOGLE_SHEET_MIME, get_drive_service, read_file_as_text
from src.ingestion.embedder import get_embedding
from src.ingestion.noise_filter import filter_chunks
from src.ingestion.pii_filter import filter_pii, strip_pii_regex
from src.ingestion.storer import get_collection, store_chunk

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Aggregate file IDs (never ingest raw — summarize first) ─────────────────

AGGREGATE_FILE_IDS = {
    "1I9Vh8je61pqPp1zgXDZ82DSJ9O-fx70PEecE9xxmw18",  # Combined Attendance
    "1BEr9GATFrBgRJkh-FR9vQiPAnovHZVWK",              # Hacklanta Check in.xlsx
    "1vses3E-EY6PRlW5NdSTDBtXUkUPvSXLlOXviVTyhooI",  # Hacklanta Email/SMS Campaign
    "1GpU7gA6LJKLVzBFmaNEEar_m1R1NXamB_0Y7BAqRSg0",  # Involvement Fair Signups
    "1vkXd1xD-Q8tWhYFLhsTUQkV9i6xIsMNskXxFaGRJYwI",  # Judge Scoring Responses
    "18UCfDtN_8A7Mo5o1eoXxx5IixUF-DB8rmU6PdPQtsgto",  # People's Choice Responses
    "1SfX0WMhVv98e_lXxCDsEAz-FJ0F-WbXyddZv1e0iSJ0",  # Growth Team Interviews
    "1piZbWBvRcm25sArgmnC9IvHZ9RDkNKqTZz6C_rf8UBg",  # Old tech team interviews
    "1YRi0lmXM2zgLtGWDzEG9srndSm8zhcqhbrbaWK7U-Sw",  # t&d interviews
}

# ── File specs by priority ────────────────────────────────────────────────────

PRIORITY_1 = [
    {"file_id": "1YFGL5-laW0CEaTHpR6gydZNV3SzWx0xO7n-IubrxTYc", "file_title": "Hacklanta Master Doc - Spring 26", "doc_type": "event_logistics", "event_name": "hacklanta", "semester": "spring_2026"},
    {"file_id": "1ik1VanYAqzWWDnZC-Nu5mwfK78tmrtPP4TwEqZO3qrk", "file_title": "Hacklanta Run of Show", "doc_type": "event_logistics", "event_name": "hacklanta", "semester": "spring_2026"},
    {"file_id": "1ekbPvjUYMW7oNi8rzWHdoBT1F-DLlKkqLbxcIuuD12Q", "file_title": "FAQs - Hacklanta", "doc_type": "event_logistics", "event_name": "hacklanta", "semester": "spring_2026"},
    {"file_id": "1ttOfvbPcSPQXV19qH3Pw1H9H-BX9p01rHYo_gdcT2k0", "file_title": "post hacklanta growth stuff", "doc_type": "growth", "event_name": "hacklanta", "semester": "spring_2026"},
    {"file_id": "1aS9sc-Vq7LEZTJblleow4sRGTpHPRaU_AM2ihBHbqD4", "file_title": "Hacklanta Winners and End Metrics", "doc_type": "event_logistics", "event_name": "hacklanta", "semester": "spring_2026"},
    {"file_id": "1HXnwa7JRU9sWbitphDzTVtnoYQ1JhWQe5jnuLvOvung", "file_title": "Prizes", "doc_type": "event_logistics", "event_name": "hacklanta", "semester": "spring_2026"},
    {"file_id": "13rAvnRnboJ4Jx0sF53HF6pifQXHGlrJ15fluL54QQC4", "file_title": "Saxby's meeting notes", "doc_type": "meeting_notes", "event_name": "hacklanta", "semester": "spring_2026"},
    {"file_id": "1REX_ezxFW6TzvoVdR-A6ClvFg8QSJfEPZloqf0FiGXU", "file_title": "Hacklanta Receipts Dump", "doc_type": "financial", "event_name": "hacklanta", "semester": "spring_2026"},
    {"file_id": "1A1AZMRaaaAF2mc2RZLzJipgP4P-5-xRFsSUG-8dZJOo", "file_title": "Currency Doc", "doc_type": "financial", "event_name": "hacklanta", "semester": "spring_2026"},
    {"file_id": "1umNbz4FFLimhWT9xsZwkqVSGvlTMJdig1Q8tfYih0Cs", "file_title": "Growth Master Doc", "doc_type": "growth", "event_name": None, "semester": "all"},
    {"file_id": "1G3sGarC2J31ihYH_QqCwB4Q0Dcwr3TYfwuGjVz4DSlQ", "file_title": "FINANCE: 2025-2026 Bookkeeping", "doc_type": "financial", "event_name": None, "semester": "all"},
    {"file_id": "15hXSGRfeYiyTrJ6qY6JE0fQaO9A_BT24M5PPqEyPazo", "file_title": "[NEW] growth team meeting minutes", "doc_type": "meeting_notes", "event_name": None, "semester": "spring_2026"},
    {"file_id": "1-BK0mGR1gHHuKR4Axofuy0WdWReEYf1JDt3sV3-Lxnk", "file_title": "Operations Meeting Notes", "doc_type": "meeting_notes", "event_name": None, "semester": "spring_2026"},
]

PRIORITY_2 = [
    {"file_id": "176mli2EyyOKFdNqB0mTm3aXPV0HGm-WEMvYM7AYYfqA", "file_title": "2025-2026 Executive Meetings", "doc_type": "meeting_notes", "event_name": None, "semester": "fall_2025"},
    {"file_id": "17Qspd_JHg_39GhaS3QcjwL-RypqjN6b0mhOTUfSsPSY", "file_title": "Marketing Meetings: Fall 2025", "doc_type": "meeting_notes", "event_name": None, "semester": "fall_2025"},
    {"file_id": "1GW-lW3jrCQUoI6ZPUGK2ItcGkXav7oafgJepm0PcVCQ", "file_title": "Outreach Meetings: Fall 2025", "doc_type": "meeting_notes", "event_name": None, "semester": "fall_2025"},
    {"file_id": "1dXOqi1l6TjOkHP2EkdJOz1uPGJVdObMWkm43EJYB7AI", "file_title": "Startup Meetings: Fall 2025", "doc_type": "meeting_notes", "event_name": None, "semester": "fall_2025"},
    {"file_id": "1iks_kc9gBLjXMOyXXZJTYngN-C1S8NFH0vIwxl_jnsQ", "file_title": "Tech/Workshop Meetings: Fall 2025", "doc_type": "meeting_notes", "event_name": None, "semester": "fall_2025"},
    {"file_id": "1GL22wqFY6W9XpItw3r057CH7lewY47oTz1DSPwuU-eU", "file_title": "tech & dev team meeting notes", "doc_type": "meeting_notes", "event_name": None, "semester": "spring_2026"},
    {"file_id": "1X4Y4KHqNh54gnDNjK1z8t8pxAWa1WH0072g6VbrCffg", "file_title": "Outreach Meeting Notes", "doc_type": "meeting_notes", "event_name": None, "semester": "spring_2026"},
    {"file_id": "1UlzaXQTPyH1QU_fvMlTwC1plVjZa9H5KGqKcryc3fMM", "file_title": "hacklanta full body meeting notes", "doc_type": "meeting_notes", "event_name": "hacklanta", "semester": "spring_2026"},
    {"file_id": "1-4tg1YFrmsrwY9WpOoMpV532CtMjL9hJ7tmoDCeUei8", "file_title": "team collaboration meeting minutes", "doc_type": "meeting_notes", "event_name": None, "semester": "spring_2026"},
    {"file_id": "1f0zlrugtJu5ruLe6d9Tt9eeXvsABDh6AMfeb8k6lARs", "file_title": "Meetings with Fearless Founder: Jenny Liu", "doc_type": "meeting_notes", "event_name": None, "semester": "fall_2025"},
    {"file_id": "1pQgGV998RXKU53YIOw1gZexrUc-xl3odn4Bo9mdiLI4", "file_title": "ENI Meetings", "doc_type": "meeting_notes", "event_name": None, "semester": "fall_2025"},
]

PRIORITY_3 = [
    {"file_id": "1hwISK9FtiRsefSs3VsxgzLz7qrcllWL8Gf4g4RwKU64", "file_title": "BLUEPRINT: HackJam Series", "doc_type": "blueprint"},
    {"file_id": "1keSd8Gf6anzSLxdHBqvRYV1oEYkLSyQR4LYZWLnUedY", "file_title": "BLUEPRINT: DSA Workshops", "doc_type": "blueprint"},
    {"file_id": "1u5T9fspOQa8jICDSBaWK_aTkmlQHShkoxyu31QgOzx8", "file_title": "BLUEPRINT: Resume/Internship Workshop", "doc_type": "blueprint"},
    {"file_id": "1hjPR3ZhrGj_yjkDwU7CAA4scYGKl-2IJQjHqNjhz1UU", "file_title": "BLUEPRINT: Startup Nights (Innov8)", "doc_type": "blueprint"},
    {"file_id": "1VQhKPn4PuUcU10vNz8k_amEKR9q5JV0PF_kAOpGUZMk", "file_title": "BLUEPRINT: Skills Workshops", "doc_type": "blueprint"},
    {"file_id": "1pcvpAfbU1MyTFIw2XEUDY0SzfCI7CjcqFII1wgAGSHw", "file_title": "BLUEPRINT: Interview Prep Workshops", "doc_type": "blueprint"},
    {"file_id": "1kq9XWid324kNVhxsrVvlwr7zQiI7uFzIj0qkjrDjs38", "file_title": "BLUEPRINT: Shipathon", "doc_type": "blueprint"},
    {"file_id": "1ci9EuRQjeAKMny5dLkkWITkAA7s6G6moqmjMvQpF2Lw", "file_title": "BLUEPRINT: General Meeting", "doc_type": "blueprint"},
    {"file_id": "1KQdLcak0jchIwfE15BdSkDez59IN7dX-", "file_title": "Event Planning Guide.docx", "doc_type": "guide"},
    {"file_id": "1P5_ppIaZ0tOxiVK0RUOOaLAtB_ThQ80s", "file_title": "VP of Operations Guide.docx", "doc_type": "guide"},
    {"file_id": "1QohfCCtXPzfgpj_Poj6J-yQnt9cjwvmR", "file_title": "Logistics Guide.docx", "doc_type": "guide"},
    {"file_id": "1SOtQ0r5mjvn4SMRodAwmZ5SirF0Eyj8K", "file_title": "Finance Guide.docx", "doc_type": "guide"},
    {"file_id": "1wOWGkOyTCCZl9U056bmUHHEDt6Q46xzet712VVcQc2A", "file_title": "Luma Attendance GUIDE", "doc_type": "guide"},
    {"file_id": "168e0SJosQzUtydvNWlPpE9vIJOrYHTWAwX7B8w88zqo", "file_title": "Registering PIN Events GUIDE", "doc_type": "guide"},
]

PRIORITY_4 = [
    {"file_id": "1u94gnTmZpoJdkjUGDWCKL3_WhqI7v5VumlVc1zXkL7I", "file_title": "PROGSU Company Partnership Opportunities", "doc_type": "growth"},
    {"file_id": "1fWSXp0M8gj-finvR3vNFnC0GZABv8SHgGy6bUHsToPw", "file_title": "Growth Team", "doc_type": "growth"},
    {"file_id": "1lf8mq46UNx7SLwQqD5Z6bNUSfFZYjxmWv4zoT-fwc1w", "file_title": "Growth Team Event Procedure Template", "doc_type": "blueprint"},
    {"file_id": "17NYZQHMXGFnoW8MwzU95PQRLZlpjPfc86JEhwA6kUww", "file_title": "Progsu Org Structure", "doc_type": "wiki"},
    {"file_id": "1JUHwQMGKHptHS9E8Yuk78UXnC-FqM9ZSREzHw1f70ro", "file_title": "wiki.progsu", "doc_type": "wiki"},
    {"file_id": "1_8oyqbywfGRzg_sRmzESvWEsbdW4i-kISEpSPZ8GnGc", "file_title": "GENERAL: Roles and Responsibilities 2025", "doc_type": "wiki"},
    {"file_id": "1BOYxgj4pwCdMJ_VURezA9sckOI7sPa38wZRJgYE4hN0", "file_title": "GENERAL: Weekly Sprints + Agenda (Fall 25)", "doc_type": "meeting_notes", "semester": "fall_2025"},
    {"file_id": "1sDxba-qfSQftE9WbMHrQcggPgKbcFTmmjiU_c8GHqU4", "file_title": "2024-2025 Monthly Goals", "doc_type": "growth"},
    {"file_id": "1S-y6Q_Rt9b7T0ynblBBMALSI_8QCrDc3Uay-Hoe00BI", "file_title": "EVENT SCHEDULE FALL 2025", "doc_type": "event_logistics", "semester": "fall_2025"},
    {"file_id": "18_S328NRXW-62-ZMIHE_8LryasOxZOfB8PiNNIJA3Vc", "file_title": "Progsu non profit planning", "doc_type": "growth"},
]

PRIORITY_5 = [
    {"file_id": "1IEkw4lnb7hl3btJMlyD0RTFNHgDtdwP3oyrtNM9G0Uo", "file_title": "Resume Workshop Event Master/Checklist", "doc_type": "event_logistics", "event_name": "resume_workshop", "semester": "spring_2026"},
    {"file_id": "1HmTJVzWhOYDGsVXYQtdxqWA15-n5MzT9rDL5CVosv2g", "file_title": "Networking Workshop Event Master/Checklist", "doc_type": "event_logistics", "event_name": "networking_workshop", "semester": "spring_2026"},
    {"file_id": "1kGx2SPb-9JpsFAss3bWfGI4SSkyaXlLEK6Yz_kphWlg", "file_title": "Judge/Mentor Packet - Hacklanta Spring 26", "doc_type": "event_logistics", "event_name": "hacklanta", "semester": "spring_2026"},
    {"file_id": "1_T2VOddzhsabMDnnywRVmXXWNwo-Pe3geFiTVtJJ1Bg", "file_title": "FINANCE: 2026-2027 Bookkeeping", "doc_type": "financial"},
    {"file_id": "1nKFvUskZxk7EFEqUHM0jMoUA1vUpDQjslOMNyJwDNfo", "file_title": "HackJam Curriculum and Date Planning", "doc_type": "event_logistics", "event_name": "hackjam"},
    {"file_id": "1UTow1GNbNbGWbkQ3a9GHZFxRJvlV4Y5Lr7Qx4IZHoyk", "file_title": "DSA Curriculum and TimeLine", "doc_type": "event_logistics", "event_name": "dsa_workshop"},
]

AGGREGATE_SPECS = [
    {"file_id": "1I9Vh8je61pqPp1zgXDZ82DSJ9O-fx70PEecE9xxmw18", "file_title": "Combined Attendance", "doc_type": "feedback_aggregate", "event_name": None, "semester": "all", "agg_type": "spreadsheet"},
    {"file_id": "1BEr9GATFrBgRJkh-FR9vQiPAnovHZVWK", "file_title": "Hacklanta Check in", "doc_type": "feedback_aggregate", "event_name": "hacklanta", "semester": "spring_2026", "agg_type": "spreadsheet"},
    {"file_id": "1vses3E-EY6PRlW5NdSTDBtXUkUPvSXLlOXviVTyhooI", "file_title": "Hacklanta Email/SMS Campaign", "doc_type": "feedback_aggregate", "event_name": "hacklanta", "semester": "spring_2026", "agg_type": "spreadsheet"},
    {"file_id": "1GpU7gA6LJKLVzBFmaNEEar_m1R1NXamB_0Y7BAqRSg0", "file_title": "Involvement Fair Signups", "doc_type": "feedback_aggregate", "event_name": None, "semester": "fall_2025", "agg_type": "spreadsheet"},
    {"file_id": "1vkXd1xD-Q8tWhYFLhsTUQkV9i6xIsMNskXxFaGRJYwI", "file_title": "Official Hacklanta Judge Scoring", "doc_type": "feedback_aggregate", "event_name": "hacklanta", "semester": "spring_2026", "agg_type": "spreadsheet"},
    {"file_id": "18UCfDtN_8A7Mo5o1eoXxx5IixUF-DB8rmU6PdPQtsgto", "file_title": "People's Choice Award Responses", "doc_type": "feedback_aggregate", "event_name": "hacklanta", "semester": "spring_2026", "agg_type": "spreadsheet"},
    {"file_id": "1SfX0WMhVv98e_lXxCDsEAz-FJ0F-WbXyddZv1e0iSJ0", "file_title": "Growth Team Interviews", "doc_type": "feedback_aggregate", "event_name": None, "semester": "all", "agg_type": "interview"},
    {"file_id": "1piZbWBvRcm25sArgmnC9IvHZ9RDkNKqTZz6C_rf8UBg", "file_title": "Old tech team interviews", "doc_type": "feedback_aggregate", "event_name": None, "semester": "all", "agg_type": "interview"},
    {"file_id": "1YRi0lmXM2zgLtGWDzEG9srndSm8zhcqhbrbaWK7U-Sw", "file_title": "t&d interviews", "doc_type": "feedback_aggregate", "event_name": None, "semester": "all", "agg_type": "interview"},
]

# ── Aggregation helpers ───────────────────────────────────────────────────────

_SPREADSHEET_AGG_PROMPT = """The following is raw spreadsheet data from a student organization.
Summarize it into aggregate statistics only.
DO NOT include any individual names, email addresses, or personal identifiers.
Include only: total counts, percentage breakdowns by category, average scores, date ranges.
Output as a clean paragraph of stats.

Data:
{raw_csv_text}"""

_INTERVIEW_AGG_PROMPT = """The following contains interview notes from a student organization.
Summarize the key themes, insights, and patterns across all interviews.
DO NOT include any interviewee names or personally identifiable information.
Keep team/org-level insights only.

Content:
{interview_text}"""


def _aggregate_with_gemini(raw_text: str, agg_type: str, client: genai.Client) -> str:
    if agg_type == "spreadsheet":
        prompt = _SPREADSHEET_AGG_PROMPT.format(raw_csv_text=raw_text[:12_000])
    else:
        prompt = _INTERVIEW_AGG_PROMPT.format(interview_text=raw_text[:12_000])
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        raise RuntimeError(f"Aggregation Gemini call failed: {e}") from e


# ── Single-file ingestion ─────────────────────────────────────────────────────

def ingest_file(
    spec: dict,
    service,
    gemini_client: genai.Client,
    collection,
    skip_gemini_pii: bool = False,
) -> dict:
    file_id = spec["file_id"]
    file_title = spec.get("file_title", file_id)
    doc_type = spec.get("doc_type", "wiki")
    event_name = spec.get("event_name")
    semester = spec.get("semester", "all")
    team = spec.get("team")
    agg_type = spec.get("agg_type")

    logger.info("=== Ingesting: %s ===", file_title)

    # Read from Drive
    text, fetched_title, mime_type = read_file_as_text(file_id, service=service)
    file_title = file_title or fetched_title

    # AGGREGATE path
    if file_id in AGGREGATE_FILE_IDS or agg_type:
        resolved_agg_type = agg_type or ("spreadsheet" if GOOGLE_SHEET_MIME in mime_type else "interview")
        summary = _aggregate_with_gemini(text, resolved_agg_type, gemini_client)
        embedding = get_embedding(summary)
        metadata = {
            "source_type": "google_drive",
            "doc_type": doc_type,
            "semester": semester,
            "event_name": event_name,
            "date": None,
            "team": team,
            "file_id": file_id,
            "file_title": file_title,
            "chunk_index": 0,
        }
        store_chunk(summary, embedding, metadata, collection=collection)
        logger.info("Aggregate stored: 1 summary chunk for '%s'", file_title)
        return {"file_id": file_id, "file_title": file_title, "chunks_stored": 1, "noise_pass_rate": 1.0}

    # INGEST path
    # 1. PII regex strip on full doc
    text = strip_pii_regex(text)

    # 2. Chunk
    chunks = chunk_text(text, doc_type)
    logger.info("Chunked '%s' → %d chunks", file_title, len(chunks))

    if not chunks:
        logger.warning("No chunks produced for '%s', skipping", file_title)
        return {"file_id": file_id, "file_title": file_title, "chunks_stored": 0, "noise_pass_rate": 0.0}

    # 3. Gemini PII strip per chunk (skipped for large docs or when flag set)
    if not skip_gemini_pii:
        cleaned_chunks = []
        for i, chunk in enumerate(chunks):
            cleaned = filter_pii(chunk, use_gemini=True, client=gemini_client)
            cleaned_chunks.append(cleaned)
            if i < len(chunks) - 1:
                time.sleep(0.1)
        chunks = cleaned_chunks

    # 4. Noise filter
    kept_chunks, noise_stats = filter_chunks(chunks, client=gemini_client)

    if not kept_chunks:
        logger.warning("All chunks filtered out for '%s'", file_title)
        return {"file_id": file_id, "file_title": file_title, "chunks_stored": 0, "noise_pass_rate": 0.0}

    # 5. Embed + store
    stored = 0
    for i, chunk in enumerate(kept_chunks):
        embedding = get_embedding(chunk)
        metadata = {
            "source_type": "google_drive",
            "doc_type": doc_type,
            "semester": semester,
            "event_name": event_name,
            "date": None,
            "team": team,
            "file_id": file_id,
            "file_title": file_title,
            "chunk_index": i,
        }
        store_chunk(chunk, embedding, metadata, collection=collection)
        stored += 1
        if i < len(kept_chunks) - 1:
            time.sleep(0.05)

    logger.info(
        "Stored %d chunks for '%s' (noise pass rate: %.0f%%)",
        stored, file_title, noise_stats["pass_rate"] * 100,
    )
    return {
        "file_id": file_id,
        "file_title": file_title,
        "total_chunks": len(chunks),
        "chunks_stored": stored,
        "noise_pass_rate": noise_stats["pass_rate"],
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Drive ingestion pipeline")
    parser.add_argument(
        "--priority",
        choices=["1", "2", "3", "4", "5", "all", "aggregate"],
        default="1",
        help="Which priority bucket to ingest (default: 1)",
    )
    parser.add_argument("--file-id", help="Ingest a single file by ID")
    parser.add_argument("--doc-type", default="wiki", help="doc_type for single file")
    parser.add_argument("--event", help="event_name for single file")
    parser.add_argument("--semester", default="all", help="semester for single file")
    parser.add_argument(
        "--skip-gemini-pii",
        action="store_true",
        help="Skip per-chunk Gemini PII pass (faster, regex-only)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is not set — aborting")
        sys.exit(1)

    gemini_client = genai.Client(api_key=api_key)
    service = get_drive_service()
    collection = get_collection()

    # Build spec list
    if args.file_id:
        specs = [{"file_id": args.file_id, "doc_type": args.doc_type, "event_name": args.event, "semester": args.semester}]
    elif args.priority == "all":
        specs = PRIORITY_1 + PRIORITY_2 + PRIORITY_3 + PRIORITY_4 + PRIORITY_5 + AGGREGATE_SPECS
    elif args.priority == "aggregate":
        specs = AGGREGATE_SPECS
    else:
        specs = {
            "1": PRIORITY_1,
            "2": PRIORITY_2,
            "3": PRIORITY_3,
            "4": PRIORITY_4,
            "5": PRIORITY_5,
        }[args.priority]

    logger.info("Starting ingestion: %d files (priority=%s)", len(specs), args.priority)

    results = []
    errors = []
    for spec in specs:
        try:
            result = ingest_file(
                spec,
                service=service,
                gemini_client=gemini_client,
                collection=collection,
                skip_gemini_pii=args.skip_gemini_pii,
            )
            results.append(result)
        except Exception as e:
            logger.error("FAILED: %s — %s", spec.get("file_title", spec["file_id"]), e)
            errors.append({"file_id": spec["file_id"], "error": str(e)})

    # Summary
    total_chunks = sum(r.get("chunks_stored", 0) for r in results)
    avg_pass_rate = (
        sum(r.get("noise_pass_rate", 0) for r in results) / len(results) if results else 0
    )
    logger.info("=== Ingestion Complete ===")
    logger.info("Files processed: %d | Errors: %d", len(results), len(errors))
    logger.info("Total chunks stored: %d", total_chunks)
    logger.info("Average noise filter pass rate: %.0f%%", avg_pass_rate * 100)
    if errors:
        logger.warning("Failed files: %s", [e["file_id"] for e in errors])


if __name__ == "__main__":
    main()
