from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from . import spotify_client

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
