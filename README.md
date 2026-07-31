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
- [ ] RSS feed matching and audio retrieval
- [ ] Whisper-based transcription pipeline
- [ ] AI-generated summaries (Claude API)
- [ ] Google Sheets storage
- [ ] Postgres-backed persistence
- [ ] React + TypeScript frontend
- [ ] Dockerized deployment

## How it works

1. I add an episode to a dedicated "To Summarize" playlist in Spotify.
2. The backend finds the episode's RSS feed and retrieves its audio.
3. The audio is transcribed via the Whisper API.
4. The transcript is summarized using Claude.
5. The summary is written to a Google Sheet, and the episode is removed from the
   playlist to mark it as done.

## Tech stack

- **Backend:** Python, FastAPI
- **Database:** PostgreSQL (planned)
- **Frontend:** React, TypeScript (planned)
- **Transcription:** OpenAI Whisper API
- **Summarization:** Anthropic Claude API
- **Storage:** Google Sheets API
- **Deployment:** Docker (planned)

## Local setup

```
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env           # then fill in your own API credentials
uvicorn app.main:app --reload --port 8000
```

Visit `http://127.0.0.1:8000/login` to connect a Spotify account, then
`http://127.0.0.1:8000/playlists` to find the ID of your "To Summarize" playlist.
