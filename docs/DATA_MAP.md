# Data Map — Google Drive Ingestion

Drive root folder: `11eYr6RIieuw4EvCZCzaMBa8ib8llDr9-`

## Labels
- **INGEST** — read, chunk, embed, store directly
- **AGGREGATE** — summarize first (strip PII), then store the summary
- **SKIP** — do not ingest

---

## Priority 1: High-Signal Files (Ingest First)

These are the most important for demo queries. Start here.

| File Title | File ID | Action | Doc Type | Event |
|---|---|---|---|---|
| Hacklanta Master Doc - Spring 26 | 1YFGL5-laW0CEaTHpR6gydZNV3SzWx0xO7n-IubrxTYc | INGEST | event_logistics | hacklanta |
| Hacklanta Run of Show | 1ik1VanYAqzWWDnZC-Nu5mwfK78tmrtPP4TwEqZO3qrk | INGEST | event_logistics | hacklanta |
| FAQs - Hacklanta | 1ekbPvjUYMW7oNi8rzWHdoBT1F-DLlKkqLbxcIuuD12Q | INGEST | event_logistics | hacklanta |
| post hacklanta growth stuff | 1ttOfvbPcSPQXV19qH3Pw1H9H-BX9p01rHYo_gdcT2k0 | INGEST | growth | hacklanta |
| Hacklanta Winners and End Metrics | 1aS9sc-Vq7LEZTJblleow4sRGTpHPRaU_AM2ihBHbqD4 | INGEST | event_logistics | hacklanta |
| Prizes | 1HXnwa7JRU9sWbitphDzTVtnoYQ1JhWQe5jnuLvOvung | INGEST | event_logistics | hacklanta |
| Saxby's meeting notes | 13rAvnRnboJ4Jx0sF53HF6pifQXHGlrJ15fluL54QQC4 | INGEST | meeting_notes | hacklanta |
| Hacklanta Receipts Dump | 1REX_ezxFW6TzvoVdR-A6ClvFg8QSJfEPZloqf0FiGXU | INGEST | financial | hacklanta |
| Currency Doc | 1A1AZMRaaaAF2mc2RZLzJipgP4P-5-xRFsSUG-8dZJOo | INGEST | financial | hacklanta |
| Growth Master Doc | 1umNbz4FFLimhWT9xsZwkqVSGvlTMJdig1Q8tfYih0Cs | INGEST | growth | null |
| FINANCE: 2025-2026 Bookkeeping | 1G3sGarC2J31ihYH_QqCwB4Q0Dcwr3TYfwuGjVz4DSlQ | INGEST | financial | null |
| [NEW] growth team meeting minutes | 15hXSGRfeYiyTrJ6qY6JE0fQaO9A_BT24M5PPqEyPazo | INGEST | meeting_notes | null |
| Operations Meeting Notes | 1-BK0mGR1gHHuKR4Axofuy0WdWReEYf1JDt3sV3-Lxnk | INGEST | meeting_notes | null |

---

## Priority 2: Meeting Notes + Exec Decisions

| File Title | File ID | Action | Doc Type | Semester |
|---|---|---|---|---|
| 2025-2026 Executive Meetings | 176mli2EyyOKFdNqB0mTm3aXPV0HGm-WEMvYM7AYYfqA | INGEST | meeting_notes | fall_2025 |
| Marketing Meetings: Fall 2025 | 17Qspd_JHg_39GhaS3QcjwL-RypqjN6b0mhOTUfSsPSY | INGEST | meeting_notes | fall_2025 |
| Outreach Meetings: Fall 2025 | 1GW-lW3jrCQUoI6ZPUGK2ItcGkXav7oafgJepm0PcVCQ | INGEST | meeting_notes | fall_2025 |
| Startup Meetings: Fall 2025 | 1dXOqi1l6TjOkHP2EkdJOz1uPGJVdObMWkm43EJYB7AI | INGEST | meeting_notes | fall_2025 |
| Tech/Workshop Meetings: Fall 2025 | 1iks_kc9gBLjXMOyXXZJTYngN-C1S8NFH0vIwxl_jnsQ | INGEST | meeting_notes | fall_2025 |
| tech & dev team meeting notes | 1GL22wqFY6W9XpItw3r057CH7lewY47oTz1DSPwuU-eU | INGEST | meeting_notes | spring_2026 |
| Outreach Meeting Notes | 1X4Y4KHqNh54gnDNjK1z8t8pxAWa1WH0072g6VbrCffg | INGEST | meeting_notes | spring_2026 |
| hacklanta full body meeting notes | 1UlzaXQTPyH1QU_fvMlTwC1plVjZa9H5KGqKcryc3fMM | INGEST | meeting_notes | spring_2026 |
| team collaboration meeting minutes | 1-4tg1YFrmsrwY9WpOoMpV532CtMjL9hJ7tmoDCeUei8 | INGEST | meeting_notes | spring_2026 |
| Meetings with Fearless Founder: Jenny Liu | 1f0zlrugtJu5ruLe6d9Tt9eeXvsABDh6AMfeb8k6lARs | INGEST | meeting_notes | fall_2025 |
| ENI Meetings | 1pQgGV998RXKU53YIOw1gZexrUc-xl3odn4Bo9mdiLI4 | INGEST | meeting_notes | fall_2025 |

---

## Priority 3: Blueprints + SOPs (Event Playbooks)

| File Title | File ID | Action | Doc Type |
|---|---|---|---|
| BLUEPRINT: HackJam Series | 1hwISK9FtiRsefSs3VsxgzLz7qrcllWL8Gf4g4RwKU64 | INGEST | blueprint |
| BLUEPRINT: DSA Workshops | 1keSd8Gf6anzSLxdHBqvRYV1oEYkLSyQR4LYZWLnUedY | INGEST | blueprint |
| BLUEPRINT: Resume/Internship Workshop | 1u5T9fspOQa8jICDSBaWK_aTkmlQHShkoxyu31QgOzx8 | INGEST | blueprint |
| BLUEPRINT: Startup Nights (Innov8) | 1hjPR3ZhrGj_yjkDwU7CAA4scYGKl-2IJQjHqNjhz1UU | INGEST | blueprint |
| BLUEPRINT: Skills Workshops | 1VQhKPn4PuUcU10vNz8k_amEKR9q5JV0PF_kAOpGUZMk | INGEST | blueprint |
| BLUEPRINT: Interview Prep Workshops | 1pcvpAfbU1MyTFIw2XEUDY0SzfCI7CjcqFII1wgAGSHw | INGEST | blueprint |
| BLUEPRINT: Shipathon | 1kq9XWid324kNVhxsrVvlwr7zQiI7uFzIj0qkjrDjs38 | INGEST | blueprint |
| BLUEPRINT: General Meeting | 1ci9EuRQjeAKMny5dLkkWITkAA7s6G6moqmjMvQpF2Lw | INGEST | blueprint |
| Event Planning Guide.docx | 1KQdLcak0jchIwfE15BdSkDez59IN7dX- | INGEST | guide |
| VP of Operations Guide.docx | 1P5_ppIaZ0tOxiVK0RUOOaLAtB_ThQ80s | INGEST | guide |
| Logistics Guide.docx | 1QohfCCtXPzfgpj_Poj6J-yQnt9cjwvmR | INGEST | guide |
| Finance Guide.docx | 1SOtQ0r5mjvn4SMRodAwmZ5SirF0Eyj8K | INGEST | guide |
| Luma Attendance GUIDE | 1wOWGkOyTCCZl9U056bmUHHEDt6Q46xzet712VVcQc2A | INGEST | guide |
| Registering PIN Events GUIDE | 168e0SJosQzUtydvNWlPpE9vIJOrYHTWAwX7B8w88zqo | INGEST | guide |

---

## Priority 4: Growth + Org Strategy

| File Title | File ID | Action | Doc Type |
|---|---|---|---|
| PROGSU Company Partnership Opportunities | 1u94gnTmZpoJdkjUGDWCKL3_WhqI7v5VumlVc1zXkL7I | INGEST | growth |
| Growth Team | 1fWSXp0M8gj-finvR3vNFnC0GZABv8SHgGy6bUHsToPw | INGEST | growth |
| Growth Team Event Procedure Template | 1lf8mq46UNx7SLwQqD5Z6bNUSfFZYjxmWv4zoT-fwc1w | INGEST | blueprint |
| Progsu Org Structure | 17NYZQHMXGFnoW8MwzU95PQRLZlpjPfc86JEhwA6kUww | INGEST | wiki |
| wiki.progsu | 1JUHwQMGKHptHS9E8Yuk78UXnC-FqM9ZSREzHw1f70ro | INGEST | wiki |
| GENERAL: Roles and Responsibilities 2025 | 1_8oyqbywfGRzg_sRmzESvWEsbdW4i-kISEpSPZ8GnGc | INGEST | wiki |
| GENERAL: Weekly Sprints + Agenda (Fall 25) | 1BOYxgj4pwCdMJ_VURezA9sckOI7sPa38wZRJgYE4hN0 | INGEST | meeting_notes |
| 2024-2025 Monthly Goals | 1sDxba-qfSQftE9WbMHrQcggPgKbcFTmmjiU_c8GHqU4 | INGEST | growth |
| EVENT SCHEDULE FALL 2025 | 1S-y6Q_Rt9b7T0ynblBBMALSI_8QCrDc3Uay-Hoe00BI | INGEST | event_logistics |
| Progsu non profit planning | 18_S328NRXW-62-ZMIHE_8LryasOxZOfB8PiNNIJA3Vc | INGEST | growth |

---

## Priority 5: Spring 2026 Events

| File Title | File ID | Action | Event |
|---|---|---|---|
| Resume Workshop Event Master/Checklist | 1IEkw4lnb7hl3btJMlyD0RTFNHgDtdwP3oyrtNM9G0Uo | INGEST | resume_workshop |
| Networking Workshop Event Master/Checklist | 1HmTJVzWhOYDGsVXYQtdxqWA15-n5MzT9rDL5CVosv2g | INGEST | networking_workshop |
| Judge/Mentor Packet - Hacklanta Spring 26 | 1kGx2SPb-9JpsFAss3bWfGI4SSkyaXlLEK6Yz_kphWlg | INGEST | hacklanta |
| FINANCE: 2026-2027 Bookkeeping | 1_T2VOddzhsabMDnnywRVmXXWNwo-Pe3geFiTVtJJ1Bg | INGEST | null |
| HackJam Curriculum and Date Planning | 1nKFvUskZxk7EFEqUHM0jMoUA1vUpDQjslOMNyJwDNfo | INGEST | hackjam |
| DSA Curriculum and TimeLine | 1UTow1GNbNbGWbkQ3a9GHZFxRJvlV4Y5Lr7Qx4IZHoyk | INGEST | dsa_workshop |

---

## Aggregate Files (Run Through Summarizer Before Storing)

These contain PII rows. Summarize to aggregate stats only before ingesting.

| File Title | File ID | What to Extract |
|---|---|---|
| Combined Attendance | 1I9Vh8je61pqPp1zgXDZ82DSJ9O-fx70PEecE9xxmw18 | Per-event counts, major/year breakdowns as % |
| Hacklanta Check in.xlsx | 1BEr9GATFrBgRJkh-FR9vQiPAnovHZVWK | Total count, major breakdown %, year % |
| Hacklanta Email/SMS Campaign | 1vses3E-EY6PRlW5NdSTDBtXUkUPvSXLlOXviVTyhooI | Sent count, open rate, click rate |
| Involvement Fair Signups | 1GpU7gA6LJKLVzBFmaNEEar_m1R1NXamB_0Y7BAqRSg0 | Total count, interest breakdown |
| Official Hacklanta Judge Scoring (Responses) | 1vkXd1xD-Q8tWhYFLhsTUQkV9i6xIsMNskXxFaGRJYwI | Per-project avg scores, score distribution |
| $100 People's Choice Award (Responses) | 18UCfDtN_8A7Mo5o1eoXxx5IixUF-DB8rmU6PdPQtsgto | Vote counts per project |
| Growth_Team_Interviews | 1SfX0WMhVv98e_lXxCDsEAz-FJ0F-WbXyddZv1e0iSJ0 | Themes + anonymized insights |
| (old) tech team interviews | 1piZbWBvRcm25sArgmnC9IvHZ9RDkNKqTZz6C_rf8UBg | Themes only |
| t&d interviews | 1YRi0lmXM2zgLtGWDzEG9srndSm8zhcqhbrbaWK7U-Sw | Themes + insights |

---

## Special Case: Progsu Master Doc (22MB — Tab Export Required)

File ID: `1CckqpcWenCg_FvOB2J-X6blUUIH0JSnlMEUTmUQMEiM`

Cannot be exported as one file. Use Google Docs API to export each tab individually.
High-value tabs to prioritize:
- `t.s9nk0rrx742x` — Events + Finished Events (Claude Workshop run of show, Hacklanta tab)
- Carousel tab — Claude Code carousel content (MCPs, skills, subagents)
- Outreach tab — sponsor strategy, one-pager links

## Skip List

Do not ingest any of:
- All video folders and media files (.psd, .jpg, .png, .mkv, .mp4)
- Individual member resumes (Vaishnavi, Axon, Dropbox, Netflix resume docs)
- receipts folder (scanned images)
- Resume file responses folder
- Deprecated / Ignore This for Now folders
- Fall 2026 folder (empty)
- judges sheet (individual judge contact data)
- Script for interview today
- Any file with title starting "Copy of" (duplicates)
