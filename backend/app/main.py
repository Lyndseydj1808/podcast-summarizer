from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse

from . import claude_client, rss_client, sheets_client, spotify_client, whisper_client

app = FastAPI(title="Podcast Summarizer")


@app.get("/")
def root():
    return {"status": "running"}


@app.get("/login")
def login():
    """Send the user to Spotify's own login/approval screen."""
    return RedirectResponse(spotify_client.get_authorize_url())


@app.get("/callback")
def callback(code: str):
    """Spotify redirects back here with a one-time code after the user approves access."""
    spotify_client.exchange_code_for_tokens(code)
    return {"status": "connected", "message": "Spotify account linked. You can close this tab."}


@app.get("/playlists")
def playlists():
    """Helper route: lists your playlists so you can find the ID of your
    'To Summarize' playlist and paste it into .env as SPOTIFY_PLAYLIST_ID."""
    return spotify_client.list_playlists()


@app.get("/episodes/queue")
def episode_queue():
    """The episodes currently sitting in your 'To Summarize' playlist, waiting to be processed."""
    return spotify_client.get_queue_episodes()


@app.post("/episodes/{episode_id}/complete")
def complete_episode(episode_id: str):
    """Mark an episode as done by removing it from the 'To Summarize' playlist."""
    spotify_client.remove_from_queue(f"spotify:episode:{episode_id}")
    return {"status": "removed", "episode_id": episode_id}


@app.get("/episodes/{episode_id}/resolve")
def resolve_episode(episode_id: str):
    """Given an episode from your queue, find its RSS feed and pull out the
    audio link (and transcript link, if the feed happens to publish one)."""
    episodes = spotify_client.get_queue_episodes()
    episode = next((e for e in episodes if e["id"] == episode_id), None)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found in your queue")
    if not episode.get("show_name"):
        raise HTTPException(status_code=422, detail={
            "message": "Spotify didn't return a show name for this episode, can't search for its feed",
            "episode_name": episode["name"],
        })

    feed_result = rss_client.find_feed_url(episode["show_name"])
    if not feed_result:
        raise HTTPException(status_code=404, detail={
            "message": "No podcasts found in Apple's directory matching this show name",
            "show_name": episode["show_name"],
        })
    if not feed_result["confident"]:
        raise HTTPException(status_code=404, detail={
            "message": "Couldn't confidently find this show's RSS feed",
            "show_name_searched": episode["show_name"],
            "closest_show_found": feed_result["matched_show_name"],
            "confidence": feed_result["confidence"],
            "other_candidates": feed_result["candidates"],
        })

    feed_url = feed_result["feed_url"]
    feed_episodes = rss_client.get_feed_episodes(feed_url)
    if not feed_episodes:
        raise HTTPException(status_code=404, detail={
            "message": "Found a feed, but it had no episodes in it",
            "feed_url": feed_url,
        })

    match = rss_client.match_episode(episode, feed_episodes)
    if not match["confident"]:
        raise HTTPException(status_code=404, detail={
            "message": "Couldn't confidently match this episode in the RSS feed",
            "spotify_episode_name": episode["name"],
            "feed_url": feed_url,
            "feed_episode_count": len(feed_episodes),
            "closest_title_found": match["title"],
            "confidence": match["match_confidence"],
        })

    return {
        "episode_name": episode["name"],
        "show_name": episode["show_name"],
        "feed_url": feed_url,
        "matched_title": match["title"],
        "match_confidence": match["match_confidence"],
        "audio_url": match["audio_url"],
        "transcript_url": match["transcript_url"],
    }


@app.get("/episodes/{episode_id}/transcript")
def get_transcript(episode_id: str):
    """Full pipeline so far: resolve the episode to its audio (Phase 2), then
    download and transcribe it (Phase 3). This can take a while for a long episode."""
    resolved = resolve_episode(episode_id)
    try:
        transcript = whisper_client.transcribe_episode(resolved["audio_url"])
    except whisper_client.TranscriptionError as e:
        # 502: we tried to talk to an outside service (the audio host or OpenAI)
        # and it failed, this wasn't a problem with the request itself.
        raise HTTPException(status_code=502, detail=str(e))
    return {
        "episode_name": resolved["episode_name"],
        "show_name": resolved["show_name"],
        "transcript": transcript,
    }


@app.get("/episodes/{episode_id}/summary")
def get_summary(episode_id: str):
    """Full pipeline so far: resolve (Phase 2), transcribe (Phase 3), summarize (Phase 4)."""
    transcript_result = get_transcript(episode_id)
    try:
        summary = claude_client.summarize_transcript(
            transcript_result["transcript"],
            transcript_result["episode_name"],
            transcript_result["show_name"],
        )
    except claude_client.SummarizationError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {
        "episode_name": transcript_result["episode_name"],
        "show_name": transcript_result["show_name"],
        "summary": summary,
    }


@app.post("/episodes/{episode_id}/process")
def process_episode(episode_id: str):
    """The full pipeline: resolve (Phase 2), transcribe (Phase 3), summarize (Phase 4),
    write to the Google Sheet (Phase 5), and mark the episode done by removing it
    from the playlist."""
    summary_result = get_summary(episode_id)

    try:
        sheets_client.append_summary_row(
            show_name=summary_result["show_name"],
            episode_name=summary_result["episode_name"],
            summary=summary_result["summary"],
        )
    except sheets_client.SheetsError as e:
        raise HTTPException(status_code=502, detail=str(e))

    spotify_client.remove_from_queue(f"spotify:episode:{episode_id}")

    return {
        "status": "done",
        "episode_name": summary_result["episode_name"],
        "show_name": summary_result["show_name"],
    }
