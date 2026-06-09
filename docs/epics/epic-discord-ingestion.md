# Epic: Discord Ingestion
**Session:** 6.5 (add-on to Session 6)
**Status:** IN PROGRESS
**Goal:** Ingest high-signal Discord channels into Atlas so the agent can answer
questions about decisions, feedback, and org communications alongside Drive docs.

---

## Context

progsu's Discord server contains a year of org history that doesn't exist anywhere
in Google Drive — realtime decisions, member feedback, event debrief discussions,
and informal knowledge that never made it into a doc. Adding it makes Query 2
(attendance/engagement trends) significantly richer and gives the agent access to
the full picture, not just the formal documents.

Privacy approach: PII filter strips names before storage. Only org-facing channels
are ingested (no DMs, no social/meme channels). After the hackathon, post a notice
in the server if deploying for real use.

---

## Export Tool: DiscordChatExporter CLI

### Why this tool
- Exports any channel you have access to as clean JSON
- Batch-exports multiple channels in one command
- Completely offline — no third-party service sees your data
- As server owner you can access all channels

### One-time setup (human)

**Step 1 — Get your Discord token**
1. Open Discord in a browser (discord.com, not the app)
2. Open DevTools → Network tab
3. Send any message or click any channel
4. Find any request, look at request headers → find `Authorization`
5. Copy that value — it's your token (starts with your user ID)

**Step 2 — Install DiscordChatExporter CLI**
```bash
brew install dotnet
dotnet tool install -g Tyrrrz.DiscordChatExporter.Cli
```
OR download the binary from: https://github.com/Tyrrrz/DiscordChatExporter/releases
(pick `DiscordChatExporter.Cli.osx-arm64.zip` for Mac M-series)

**Step 3 — Export channels**
```bash
# Export all channels in your server to JSON
discordchatexporter-cli exportguild \
  --token YOUR_TOKEN \
  --guild YOUR_SERVER_ID \
  --format Json \
  --output discord_export/

# OR export specific channels by ID
discordchatexporter-cli exportchannel \
  --token YOUR_TOKEN \
  --channel CHANNEL_ID \
  --format Json \
  --output discord_export/
```

**Where to find server/channel IDs:**
Enable Developer Mode in Discord (Settings → Advanced → Developer Mode),
then right-click any server or channel → Copy ID.

**Drop the exported JSON files into:** `discord_export/` in the project root.
That directory is gitignored — files never get committed.

---

## High-Value Channels to Export

Export these, skip the rest:

| Channel | Why |
|---|---|
| #announcements | Key org decisions, event launches |
| #general | Member feedback, discussion summaries |
| #exec / #leadership | Strategic decisions, planning |
| #hacklanta (any event channels) | Event-specific decisions and debrief |
| #growth / #marketing | Campaign decisions, metrics shared |
| #operations | Logistics decisions |
| #feedback / #debrief | Post-event learnings |

**Skip:** #memes, #off-topic, #bot-commands, #introductions, DMs

---

## Ingestion Pipeline

**File:** `src/ingestion/discord_reader.py`
**Approach:**
- Parse DiscordChatExporter JSON format
- Group messages into chunks by: date (daily summaries) OR thread/topic
- Strip PII: author names replaced with roles (exec/member/unknown)
- Run through existing noise filter (Gemini YES/NO)
- Embed with text-embedding-004
- Store with `source_type: "discord"`, channel name as `file_title`

**Run command (after exporting):**
```bash
python3 -m src.ingestion.run_discord_ingestion --input discord_export/
```

---

## Tasks

- [x] Write epic
- [ ] Human: export channels using DiscordChatExporter CLI
- [ ] Human: drop JSON files into `discord_export/` folder
- [ ] Write `src/ingestion/discord_reader.py`
- [ ] Write `src/ingestion/run_discord_ingestion.py`
- [ ] Test on one channel export
- [ ] Ingest all target channels
- [ ] Re-run all 3 demo queries — verify Discord data surfaces in results
- [ ] Deploy updated backend to Cloud Run

---

## Definition of Done
At least one Discord source appears in citations for Query 1 or Query 2.
All 3 demo queries still return correct results after Discord data is added.
