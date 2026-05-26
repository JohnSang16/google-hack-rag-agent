# PII Rules

## Core Principle

This system does NOT train any model. Data is retrieved at query time and temporarily read by Gemini to generate answers. No training, no persistent data exposure outside MongoDB Atlas.

However, attendee data was collected for org operations, not for AI querying. We remove individual personal data before ingestion.

---

## Always Strip (Regex Pass — Run on Every Document)

```python
import re

PII_PATTERNS = [
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]'),
    (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]'),
    (r'\b\d{9}\b', '[STUDENT_ID]'),
    (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]'),
]

def strip_pii_regex(text: str) -> str:
    for pattern, replacement in PII_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text
```

---

## Files Requiring Full Aggregation (Never Ingest Raw)

These files contain rows of individual attendee data. Do not chunk them — summarize them into a single aggregate chunk instead.

```python
AGGREGATE_FILE_IDS = [
    "1I9Vh8je61pqPp1zgXDZ82DSJ9O-fx70PEecE9xxmw18",  # Combined Attendance
    "1BEr9GATFrBgRJkh-FR9vQiPAnovHZVWK",              # Hacklanta Check in.xlsx
    "1vses3E-EY6PRlW5NdSTDBtXUkUPvSXLlOXviVTyhooI",  # Hacklanta Email/SMS Campaign
    "1GpU7gA6LJKLVzBFmaNEEar_m1R1NXamB_0Y7BAqRSg0",  # Involvement Fair Signups
    "1vkXd1xD-Q8tWhYFLhsTUQkV9i6xIsMNskXxFaGRJYwI",  # Judge Scoring Responses
    "18UCfDtN_8A7Mo5o1eoXxx5IixUF-DB8rmU6PdPQtsgto",  # People's Choice Responses
    "1SfX0WMhVv98e_lXxCDsEAz-FJ0F-WbXyddZv1e0iSJ0",  # Growth_Team_Interviews
    "1piZbWBvRcm25sArgmnC9IvHZ9RDkNKqTZz6C_rf8UBg",  # Old tech team interviews
    "1YRi0lmXM2zgLtGWDzEG9srndSm8zhcqhbrbaWK7U-Sw",  # t&d interviews
]
```

Aggregation prompt for spreadsheet files:
```
The following is raw spreadsheet data from a student organization. 
Summarize it into aggregate statistics only. 
DO NOT include any individual names, email addresses, or personal identifiers.
Include only: total counts, percentage breakdowns by category, average scores, date ranges.
Output as a clean paragraph of stats.

Data:
{raw_csv_text}
```

Aggregation prompt for interview files:
```
The following contains interview notes from a student organization.
Summarize the key themes, insights, and patterns across all interviews.
DO NOT include any interviewee names or personally identifiable information.
Keep team/org-level insights only.

Content:
{interview_text}
```

---

## Safe to Keep

The following types of names are fine to keep — they are public-facing org members:

```python
EXEC_NAMES = [
    "John Sang", "Liam", "Charan", "Natasha", "Jared", 
    "Joey", "Carter", "Tyler", "Aaron", "Ibe", "Temi",
    "Eda", "Ishan", "Phillip"
    # Add more exec names here as needed
]

SPONSOR_NAMES = [
    "Anthropic", "Google", "Amazon", "Cox Enterprises", 
    "Microsoft", "FanDuel", "Mercedes-Benz", "Nexlayer"
]
```

Also safe:
- Event names and dates
- Project/team names from Hacklanta submissions
- Budget line items (not personal account numbers)
- Room numbers and venue names
- Sponsor company names

---

## Verification Check

After ingestion, run this check to confirm no PII leaked into Atlas:

```python
import re

def check_chunk_for_pii(chunk_text: str) -> list[str]:
    """Returns list of PII types found. Should always be empty."""
    found = []
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', chunk_text):
        found.append("EMAIL")
    if re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', chunk_text):
        found.append("PHONE")
    if re.search(r'\b\d{9}\b', chunk_text):
        found.append("STUDENT_ID")
    return found
```

Log a warning if any PII is found in stored chunks. Do not block ingestion — log and flag for manual review.
