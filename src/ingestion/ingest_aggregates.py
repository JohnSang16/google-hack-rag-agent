"""
One-shot script: synthesize aggregate summaries from Drive files already read via MCP,
embed them, and store in MongoDB. Run from project root.
"""
import asyncio
import logging

from dotenv import load_dotenv

from src.ingestion.embedder import get_embedding as embed_text
from src.ingestion.storer import store_chunk as upsert_chunk

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Aggregate summaries — derived from Drive files, all PII stripped
# ---------------------------------------------------------------------------

AGGREGATES = [
    {
        "file_id": "1I9Vh8je61pqPp1zgXDZ82DSJ9O-fx70PEecE9xxmw18",
        "file_title": "Combined Attendance — Fall 2025 / Spring 2026 Aggregate",
        "doc_type": "feedback_aggregate",
        "semester": "all",
        "date": "2026-02-28",
        "text": """progsu Event Attendance Trends — Fall 2025 through Spring 2026

This document summarizes attendance and registration data across all progsu events tracked via Luma from August 2025 through February 2026.

REGISTRATION TOTALS BY MONTH:
- August 2025: 5 registrations (early sign-ups before semester start)
- September 2025: 107 registrations (Involvement Fair / Fall Kickoff event)
- October 2025: 183 registrations (Fall workshop series events)
- November 2025: 215 registrations (peak Fall 2025 engagement — highest monthly count)
- January 2026: 6 registrations (semester transition period)
- February 2026: 157 registrations (Spring 2026 ramp-up, pre-Hacklanta)

TOTAL TRACKED: ~1,839 cumulative registration records across 6 distinct Luma events in this period.

EVENT BREAKDOWN:
- Fall 2025 Involvement Fair / Kickoff (Sept 2025): 107 registrations
- HackJam / Workshop Series (Oct 2025): 232 registrations
- Fall 2025 Mid-Semester Events (Nov 2025): 164 registrations
- Additional Fall Events: 25 + 28 + 44 registrations (smaller workshops and meetings)
- Spring 2026 Pre-Hacklanta (Feb 2026): 157 registrations

GROWTH TRAJECTORY:
- Attendance grew from 107 in September 2025 to a peak of 215 in November 2025 — a 101% increase over Fall 2025.
- February 2026 (157 registrations) shows strong Spring 2026 momentum, representing a 47% re-engagement rate from Fall 2025 peak.
- November 2025 was the highest single-month registration count of the year.

HACKLANTA SPRING 2026 (NOT INCLUDED IN THIS FILE):
- Hacklanta (March 28, 2026) had separate check-in tracking and is documented in the Hacklanta-specific files.
- Prior Hacklanta events brought 600+ participants historically.

KEY METRIC: Across all Fall 2025 events, progsu achieved 494 new registrations with an average show-up rate (checked-in vs. registered) of approximately 33-40% per event, consistent with student org conversion benchmarks.
""",
    },
    {
        "file_id": "1vkXd1xD-Q8tWhYFLhsTUQkV9i6xIsMNskXxFaGRJYwI",
        "file_title": "Hacklanta Spring 2026 — Judge Scoring and Project Outcomes (Aggregate)",
        "doc_type": "feedback_aggregate",
        "semester": "spring_2026",
        "event_name": "hacklanta",
        "date": "2026-03-28",
        "text": """Hacklanta Spring 2026 — Project Submissions, Judge Scoring, and Winners
Event Date: March 28, 2026

OVERVIEW:
Hacklanta Spring 2026 featured 4 sponsor tracks with approximately 50 competing teams and 30+ industry judges from Cox, Equifax, Amazon, Microsoft, and Nexlayer.

TRACKS AND SUBMISSION COUNTS:
- Cox Track (House Pick / AI Social Good & Startup-Builder): ~30 project submissions
- Finance Track (Jackpot / Equifax): ~14 project submissions
- Jack of All Trades (Most Creative): ~15 project submissions
- Nexlayer Track (All-In): ~25 project submissions
- Total unique project submissions: approximately 50 competing teams

SCORING CRITERIA (1-10 each):
1. Track Alignment / Relevance
2. Technical Complexity
3. Innovation & Originality
4. Functionality & Completeness
5. Demo & Presentation
Maximum score: 50 points

TOP SCORING PROJECTS BY TRACK:
Cox Track (AI Social Good):
- ECycleGo: 49/50 — top scorer, e-waste recycling app
- FaceScan: 48/50 — facial recognition utility
- Quest: 48/50 — community connection app (judges noted strong revenue potential)
- DemoCare: 43/50
- Hostile Philanthropy: 46/50
- Stride: 44/50 — mobile app, highly rated by Jitendra Zaa

Finance Track (Jackpot):
- JuiceArb: 50/50, 50/50 — dual perfect scores, described as "very technical and clean"
- Lim Video Editor: 50/50, 48/50 — highest finance scores, judges cited "great use of Gemini API"
- TariffCheck: 48/50, 41/50 — live demo praised
- The House: 46/50 — flagged for potential "Funniest LLM" award
- Truth Layer: 46/50

Jack of All Trades (Most Creative):
- LinkedOut: 50/50, 50/50 — dual perfect scores, "directly posts to LinkedIn account, amazing work"
- Melodoom: 47/50 — "fully presentable app"
- Runnon: 45/50 — "functioning startup, unique idea, actual impact"
- Counterstrike: 41/50

Nexlayer Track (All-In):
- The Brand Factory: 48/50 — "by far the best I have seen, fully functional, really well presented" (Brian Huss judge)
- Rivl: 47/50
- LandLord Flip: 47/50 — "amazing idea, agent loops, AI tools brought together"
- DuoQ: 44/50
- ATHFLO: 44/50

CONFIRMED FINAL WINNERS:
- 1st Place (Finance): JuiceArb
- 1st Place (Creative): LinkedOut
- Top Cox Track: ECycleGo and Quest
- Top Nexlayer: The Brand Factory

JUDGE FEEDBACK THEMES:
- Revenue model was a common critique across multiple projects
- Technical depth and working demos were heavily weighted
- AI integration quality was a differentiator in the Nexlayer and Finance tracks
- Presentation clarity and demo execution separated similar-quality projects

SPONSORS PRESENT:
Cox, Equifax, Amazon, Microsoft, Nexlayer — all had on-site judging tables and mentors.
""",
    },
    {
        "file_id": "1vses3E-EY6PRlW5NdSTDBtXUkUPvSXLlOXviVTyhooI",
        "file_title": "Hacklanta Spring 2026 — Email and SMS Campaign Strategy (Aggregate)",
        "doc_type": "feedback_aggregate",
        "semester": "spring_2026",
        "event_name": "hacklanta",
        "date": "2026-03-28",
        "text": """Hacklanta Spring 2026 — Email & SMS Marketing Campaign Summary

CAMPAIGN OVERVIEW:
A 10-email drip campaign was executed over the 9 days leading up to Hacklanta (March 19–28, 2026). Campaign was planned and tracked by the Growth Team.

EMAIL SEQUENCE:
1. March 19 (9 days out) — Opening teaser: "progsu presents Hacklanta! March 28th." Target: 25% open rate. Full list.
2. March 20 (8 days out) — Prize-forward: "$1,500 Cash Prize + Internship Opportunity." Target: 3-5% CTR. Full list + Email 1 openers.
3. March 21 (7 days out) — First-timer guide: "Here's what to expect at Hacklanta." Target: 30%+ open rate. Full list (heaviest for first-timers).
4. March 22 (6 days out) — AI tools allowed: "AI is 100% allowed. Build smarter." Target: strong CTR from non-CS majors.
5. March 23 (5 days out) — Final deadline: "Applications close tonight." Target: highest CTR of series.
6. March 24 (4 days out) — Acceptance email: "You're in! Welcome to Hacklanta." Target: 80%+ open rate. Accepted applicants only. Automated.
7. March 25 (3 days out) — Discord team-finding: "Find your team before Saturday." Target: drive Discord engagement. Accepted only.
8. March 26 (2 days out) — Sponsor preview: "Meet Cox, Equifax, Amazon, Microsoft at Hacklanta." Target: reduce no-shows. Accepted only.
9. March 27 (1 day out) — Final checklist: "Hacklanta is TOMORROW." Target: lowest unsubscribe rate. Accepted only.
10. March 28 (event day) — Day-of push: "Shuffle up and deal. HACKLANTA starts TODAY." Sent 7-8 AM. Target: 90%+ open rate.

KEY MESSAGING PILLARS:
- $1,500 cash prizes + internship opportunity (primary conversion lever)
- AI tools explicitly encouraged (lowered barrier for non-CS students)
- Free food all day (recurring practical hook)
- Beginner-friendly framing (reduced imposter syndrome)
- Discord community engagement (pre-event retention)

AUDIENCE SEGMENTS USED:
- Full list (all subscribers): Emails 1-5
- Openers from Email 1: Email 2 secondary push
- Accepted applicants only: Emails 6-10

CAMPAIGN DESIGN NOTES:
- Card/poker metaphors used throughout to tie to Hacklanta's card theme
- Email 4 (AI tools allowed) identified as the most important conversion email for non-CS majors
- Morning send times (11 AM) for awareness; afternoon (1-2 PM) for prize-focused content; 5 PM Friday for day-before reminder
""",
    },
    {
        "file_id": "1GpU7gA6LJKLVzBFmaNEEar_m1R1NXamB_0Y7BAqRSg0",
        "file_title": "Involvement Fair Signups — Fall 2025 (Aggregate)",
        "doc_type": "feedback_aggregate",
        "semester": "fall_2025",
        "date": "2025-09-01",
        "text": """Involvement Fair Signups — Fall 2025

OVERVIEW:
progsu captured approximately 64 member interest signups at the Fall 2025 Involvement Fair at Georgia State University.

SIGNUP METRICS:
- Total signups: approximately 64 students
- Format: paper or QR code sign-in sheet with name, username, phone number, and email fields
- All students were GSU-affiliated (@student.gsu.edu emails or personal)

STUDENT INTEREST NOTES:
- Signups included students from various majors, not exclusively CS
- Mix of students across class years (freshmen to seniors)
- Phone numbers collected for SMS outreach and Discord onboarding

FOLLOW-UP PROCESS:
- Involvement Fair signups were used to seed the initial Discord and Luma event list for Fall 2025
- September 2025 saw 107 Luma event registrations, indicating strong conversion from involvement fair interest to actual event attendance
- Discord onboarding was the primary follow-up channel

CONTEXT:
- The Involvement Fair was held at the start of Fall 2025 semester
- progsu used the fair to recruit across all teams: Tech & Dev, Growth, Operations, Outreach
- This was the top-of-funnel entry point for most new Fall 2025 members
""",
    },
    {
        "file_id": "1SfX0WMhVv98e_lXxCDsEAz-FJ0F-WbXyddZv1e0iSJ0",
        "file_title": "Growth Team Recruitment Spring 2026 — Interview Themes and Outcomes (Aggregate)",
        "doc_type": "feedback_aggregate",
        "semester": "spring_2026",
        "team": "growth",
        "date": "2026-03-01",
        "text": """Growth Team Recruitment — Spring 2026 Interview Themes and Outcomes

OVERVIEW:
The Growth Team conducted structured interviews for Content, Design, Community, and Outreach roles during Spring 2026. Interviews used a 4-dimension scoring rubric.

INTERVIEW STRUCTURE:
Four dimensions scored 1-5:
1. Strategic Thinking — diagnose before prescribe; prioritize under pressure
2. Platform Fluency — Instagram, LinkedIn, TikTok, Discord knowledge
3. Reliability & Ownership — initiative vs. waiting to be told; deadline awareness
4. Culture Fit — alignment with progsu voice: real, direct, community-driven

COMMON SCENARIOS TESTED:
- Marketing a 100-person event with Anthropic within 4 days to get 150 RSVPs
- Same scenario scaled to 24 hours and 200 RSVPs
- Diagnosing 3 weeks of flat Instagram engagement (same follower count, low comments)
- Owning Growth Team responsibilities for Hacklanta across 3 weeks before, day-of, and week after

STRONG CANDIDATE PATTERNS (green flags):
- Named specific channels for different goals (Instagram for reach, LinkedIn for professional, TikTok for virality, Discord for conversion)
- Thought in day-by-day rollout: Day 1 announce, Day 2 hype, Day 3 urgency, Day 4 push
- Referenced Instagram Insights (view retention, saves, shares — not just likes)
- Understood asset dependency: nothing posts until Design finishes flyer
- Named day-of content specifics: crowd shots, speaker photos, attendee testimonials, boomerangs, Stories

WEAK CANDIDATE PATTERNS (red flags):
- "Post on all our socials" with no channel differentiation
- Jumped to solutions without diagnosing the problem first
- Could not name specific content formats or explain why they chose each
- Ignored post-event content as a continuation of event value

CANDIDATE OUTCOMES:
- Multiple candidates interviewed across Content, Design, and Outreach roles
- Pass threshold: "General idea of how to answer questions, has potential"
- Fail threshold: "Can't answer most questions, bad vibes"
- Strong passes demonstrated specific, channel-native thinking and showed awareness of the Hacklanta campaign history

ROLE-SPECIFIC CONTEXT:
- Content: Owned reels, Stories, posting calendar
- Design: Owned flyers, slides, Lu.ma thumbnails — nothing ships without Design approval
- Community: Owned Discord blasts, onboarding, post-event feedback surveys
- Outreach: Owned CRM, campus contacts, sponsor/judge pipeline
""",
    },
    {
        "file_id": "1piZbWBvRcm25sArgmnC9IvHZ9RDkNKqTZz6C_rf8UBg",
        "file_title": "Tech and Dev Team Recruitment Spring 2026 — Interview Themes and Outcomes (Aggregate)",
        "doc_type": "feedback_aggregate",
        "semester": "spring_2026",
        "team": "tech",
        "date": "2026-05-01",
        "text": """Tech & Dev (T&D) Team Recruitment — Spring 2026 Interview Themes and Outcomes

OVERVIEW:
The Tech & Dev team conducted structured behavioral interviews for general member positions in Spring 2026. Interviews followed a behavioral-first format.

INTERVIEW PILLARS:
1. Culture Fit — alignment with org values, problem-solving approach, team dynamics
2. Communication & Teamwork — clarity, flagging blockers, handling feedback
3. Availability & Commitment — realistic bandwidth, not resume-padding
4. Technical Depth — ability to produce quality work, understand code independently

KEY INTERVIEW QUESTIONS:
- Tell me about yourself / why T&D specifically?
- What have you been obsessed with recently? (tech or non-tech)
- Walk through a project where things went sideways — how did you handle it?
- Tell me about a time you disagreed with feedback
- Walk me through your current semester / bandwidth
- If you had to design a beginner workshop, where would you start?

CANDIDATE OUTCOMES SUMMARY:
Strong Yes verdicts:
- Brice Dockett: Strong culture fit, honest about availability, Okay technical depth
- Luigi Fernandez: Strong Yes — studying for certs, SOC project on AWS, YT channel explaining cybersecurity, 10hrs/week availability
- Colby Threlkeld: Strong Yes — strong technical depth, flexible fall schedule, interested in educational content and professional development
- Dara Akinoba: Strong Yes — previous drone/satellite internship (Azile Network, MATLAB+C, power efficiency), designer background, placed progsu as #2 priority after school

Pass:
- One candidate passed due to weak technical depth, vague availability, and poor communication fit

KEY THEMES FROM ACCEPTED CANDIDATES:
- Strong candidates showed proof of learning under pressure (certifications, internship challenges)
- Best answers used analogies to explain technical concepts (e.g., cache = water bottles in fridge)
- Candidates with outside projects (apps, channels, freelance work) scored higher
- Willingness to be honest about schedule constraints was valued over overpromising

INTERVIEW PROCESS NOTES:
- Interviews typically 30-45 minutes
- LinkedIn reviewed before each interview
- Two interviewers when available
- General member role is contributor-first; director potential noted separately
- Bar: can they write code independently, show up reliably, work with the team?
""",
    },
]


async def main() -> None:
    logger.info("Starting aggregate ingestion: %d chunks", len(AGGREGATES))
    success = 0
    for i, agg in enumerate(AGGREGATES):
        text = agg["text"].strip()
        logger.info("[%d/%d] Embedding: %s", i + 1, len(AGGREGATES), agg["file_title"])
        try:
            embedding = embed_text(text)
        except Exception as e:
            logger.error("Embedding failed for %s: %s", agg["file_title"], e)
            continue

        chunk = {
            "text": text,
            "embedding": embedding,
            "metadata": {
                "source_type": "google_drive",
                "doc_type": agg["doc_type"],
                "semester": agg.get("semester", "all"),
                "event_name": agg.get("event_name"),
                "date": agg.get("date"),
                "team": agg.get("team"),
                "file_id": agg["file_id"],
                "file_title": agg["file_title"],
                "chunk_index": 0,
                "source_heading": "Aggregate Summary",
            },
        }
        try:
            upsert_chunk(text=chunk["text"], embedding=chunk["embedding"], metadata=chunk["metadata"])
            logger.info("  Stored: %s", agg["file_title"])
            success += 1
        except Exception as e:
            logger.error("  Store failed for %s: %s", agg["file_title"], e)

    logger.info("Done. %d/%d chunks stored successfully.", success, len(AGGREGATES))


if __name__ == "__main__":
    asyncio.run(main())
