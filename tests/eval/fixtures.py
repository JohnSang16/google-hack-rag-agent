"""
Labeled test fixtures for all eval dimensions.

Each fixture defines a query, expected mode, and (for retrieval tests)
substrings that should appear in at least one of the top-3 chunk file_titles.
"""

from dataclasses import dataclass, field


@dataclass
class QueryFixture:
    query: str
    expected_mode: str
    # Substrings matched against file_title in returned chunks.
    expected_sources: list[str] = field(default_factory=list)
    label: str = ""


MODE_FIXTURES: list[QueryFixture] = [
    # CHAT — resolved by pattern match, no Gemini call needed
    QueryFixture("hello", "CHAT", label="greeting"),
    QueryFixture("hi there", "CHAT", label="greeting variant"),
    QueryFixture("what can you do?", "CHAT", label="capability discovery"),
    QueryFixture("give me example questions", "CHAT", label="example prompt request"),
    QueryFixture("thanks", "CHAT", label="thanks"),
    QueryFixture("who are you?", "CHAT", label="identity question"),
    QueryFixture("what are the 3 prompts?", "CHAT", label="demo prompt request"),
    # RECALL
    QueryFixture(
        "What were the key logistics challenges at Hacklanta and how did we solve them?",
        "RECALL",
        expected_sources=["FAQs", "Hacklanta", "Operations Meeting"],
        label="demo query 1",
    ),
    QueryFixture(
        "What sponsors did we have for Hacklanta?",
        "RECALL",
        expected_sources=["Hacklanta", "FAQs"],
        label="sponsor recall",
    ),
    QueryFixture(
        "What was decided at the last exec meeting?",
        "RECALL",
        label="exec meeting recall",
    ),
    QueryFixture(
        "Who organized the Claude Workshop?",
        "RECALL",
        label="event ownership recall",
    ),
    QueryFixture(
        "What were the attendance numbers for the involvement fair?",
        "RECALL",
        expected_sources=["Involvement Fair", "Attendance"],
        label="involvement fair attendance",
    ),
    # ANALYZE
    QueryFixture(
        "How has event attendance grown from Fall 2025 to Spring 2026, and which events drove the most engagement?",
        "ANALYZE",
        expected_sources=["Attendance", "Involvement Fair"],
        label="demo query 2",
    ),
    QueryFixture(
        "Compare attendance between Fall 2025 and Spring 2026",
        "ANALYZE",
        label="attendance comparison",
    ),
    QueryFixture(
        "How has our membership grown over the year?",
        "ANALYZE",
        label="membership growth trend",
    ),
    # PLAN
    QueryFixture(
        "Draft a planning brief for our next major hackathon based on everything we learned from Hacklanta.",
        "PLAN",
        expected_sources=["Hacklanta", "Operations Meeting"],
        label="demo query 3",
    ),
    QueryFixture(
        "Help me plan our next big event",
        "PLAN",
        label="generic plan request",
    ),
    QueryFixture(
        "Create a sponsor outreach template for our next hackathon",
        "PLAN",
        label="sponsor template plan",
    ),
]

# Fixtures that have expected_sources — used for retrieval eval
RETRIEVAL_FIXTURES = [f for f in MODE_FIXTURES if f.expected_sources]

# The three live demo queries — used for end-to-end answer quality eval
DEMO_FIXTURES = [
    f for f in MODE_FIXTURES
    if f.label in {"demo query 1", "demo query 2", "demo query 3"}
]
