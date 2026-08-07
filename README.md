# Podcast Summarizer

An app that connects to Spotify, transcribes and summarizes podcast episodes I've
queued up to listen to, and logs the summaries to a Google Sheet.

## Why I'm building this

I'm a career-changer learning software development through LaunchCode. This project
is deliberately built with Python, FastAPI, PostgreSQL, React, TypeScript, and Docker,
a stack chosen to match the technologies used at companies I'm targeting in my job
search, so I can show real, working familiarity with these tools rather than just
listing them on a resume.

## Status: actively in development

- [x] Spotify OAuth integration
- [x] Playlist-based episode queue (episodes added to a "To Summarize" playlist get
      picked up automatically; removing one marks it as processed)
- [x] RSS feed matching and audio retrieval
- [x] Whisper-based transcription pipeline
- [x] AI-generated summaries (Claude API)
- [x] Google Sheets storage
- [x] Postgres-backed persistence (tokens + a permanent processed-episodes record)
- [x] Automatic playlist polling (checks every 15 minutes, no manual trigger needed)
- [ ] React + TypeScript frontend
- [ ] Dockerized deployment

## How it works

1. I add an episode to a dedicated "To Summarize" playlist in Spotify.
2. A background job checks that playlist every 15 minutes for anything new
   (a safety cap skips processing entirely if the queue ever looks abnormally
   large, to avoid runaway API costs from a malfunction).
3. The backend finds the episode's RSS feed and retrieves its audio.
4. The audio is transcribed via the Whisper API (chunked and re-encoded with
   ffmpeg for episodes too large for a single request).
5. The transcript is summarized using Claude.
6. The summary is written to a Google Sheet, a permanent record is saved to
   Postgres, and the episode is removed from the playlist to mark it as done.

## Tech stack

- **Backend:** Python, FastAPI
- **Database:** PostgreSQL, SQLAlchemy
- **Frontend:** React, TypeScript (planned)
- **Transcription:** OpenAI Whisper API
- **Summarization:** Anthropic Claude API
- **Storage:** Google Sheets API
- **Scheduling:** APScheduler (background playlist polling)
- **Deployment:** Docker (planned)

## Local setup

Requires PostgreSQL and ffmpeg installed locally (used for audio chunking).

```
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env           # then fill in your own API credentials + DATABASE_URL
uvicorn app.main:app --reload --port 8000
```

Visit `http://127.0.0.1:8000/login` to connect a Spotify account, then
`http://127.0.0.1:8000/playlists` to find the ID of your "To Summarize" playlist.
