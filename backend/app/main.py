import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import claude_client, models, rss_client, sheets_client, spotify_client, whisper_client
from .database import SessionLocal, get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POLL_INTERVAL_MINUTES = 15

# Episodes get added to the playlist deliberately, one at a time, so the queue
# should never realistically hold more than a handful at once. If it ever
# does, that's more likely a bug or a Spotify glitch than intentional, and
# since Whisper/Claude cost real money per episode, auto-processing shouldn't
# blindly plow through an abnormally large queue. Skip the run and flag it
# for a human to check instead.
MAX_QUEUE_SIZE_TO_AUTO_PROCESS = 10


def _auto_process_queue() -> None:
    """Runs on a schedule: check the 'To Summarize' playlist for anything new
    and process it automatically, the same way the manual /process route does.
    One episode failing (bad audio, no RSS match, etc.) shouldn't stop the
    rest of the queue from being tried, so each one gets its own try/except."""
    try:
        episodes = spotify_client.get_queue_episodes()
    except Exception as e:
        logger.error(f"Auto-processing: couldn't fetch the playlist queue: {e}")
        return

    if len(episodes) > MAX_QUEUE_SIZE_TO_AUTO_PROCESS:
        logger.error(
            f"Auto-processing: playlist has {len(episodes)} episodes queued, "
            f"more than the safety limit of {MAX_QUEUE_SIZE_TO_AUTO_PROCESS}. "
            "Skipping this run entirely, check the playlist manually before processing."
        )
        return

    for episode in episodes:
        db = SessionLocal()
        try:
            process_episode(episode["id"], db)
            logger.info(f"Auto-processed: {episode['name']}")
        except HTTPException as e:
            logger.warning(f"Skipped '{episode['name']}': {e.detail}")
        except Exception as e:
            logger.error(f"Unexpected error auto-processing '{episode['name']}': {e}")
        finally:
            db.close()


scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts.
    scheduler.add_job(_auto_process_queue, "interval", minutes=POLL_INTERVAL_MINUTES)
    scheduler.start()
    yield
    # Runs once when the server shuts down.
    scheduler.shutdown()


app = FastAPI(title="Podcast Summarizer", lifespan=lifespan)


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
def process_episode(episode_id: str, db: Session = Depends(get_db)):
    """The full pipeline: resolve (Phase 2), transcribe (Phase 3), summarize (Phase 4),
    write to the Google Sheet (Phase 5), record it in Postgres, and mark the episode
    done by removing it from the playlist (Phase 6)."""
    summary_result = get_summary(episode_id)

    try:
        sheets_client.append_summary_row(
            show_name=summary_result["show_name"],
            episode_name=summary_result["episode_name"],
            summary=summary_result["summary"],
        )
    except sheets_client.SheetsError as e:
        raise HTTPException(status_code=502, detail=str(e))

    try:
        db.add(
            models.ProcessedEpisode(
                spotify_episode_id=episode_id,
                show_name=summary_result["show_name"],
                episode_name=summary_result["episode_name"],
            )
        )
        db.commit()
    except IntegrityError:
        # spotify_episode_id is unique, this fires if we've already recorded this one.
        db.rollback()
        raise HTTPException(status_code=409, detail="This episode was already processed")

    spotify_client.remove_from_queue(f"spotify:episode:{episode_id}")

    return {
        "status": "done",
        "episode_name": summary_result["episode_name"],
        "show_name": summary_result["show_name"],
    }


@app.get("/episodes/processed")
def list_processed_episodes(db: Session = Depends(get_db)):
    """Your processing history, pulled straight from Postgres, most recent first."""
    records = (
        db.query(models.ProcessedEpisode)
        .order_by(models.ProcessedEpisode.processed_at.desc())
        .all()
    )
    return [
        {
            "episode_name": r.episode_name,
            "show_name": r.show_name,
            "processed_at": r.processed_at,
        }
        for r in records
    ]
