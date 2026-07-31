import base64
import json
import os
import time
from urllib.parse import urlencode

import httpx

from . import config

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"


def get_authorize_url() -> str:
    """Build the URL that sends the user to Spotify's own login/approval screen."""
    params = {
        "client_id": config.SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": config.SPOTIFY_REDIRECT_URI,
        "scope": config.SPOTIFY_SCOPES,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _basic_auth_header() -> dict:
    """Spotify wants the client ID + secret combined and base64-encoded for token requests."""
    raw = f"{config.SPOTIFY_CLIENT_ID}:{config.SPOTIFY_CLIENT_SECRET}"
    encoded = base64.b64encode(raw.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def exchange_code_for_tokens(code: str) -> dict:
    """Trade the one-time code Spotify gave us for a real access token + refresh token."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.SPOTIFY_REDIRECT_URI,
    }
    response = httpx.post(TOKEN_URL, data=data, headers=_basic_auth_header())
    response.raise_for_status()
    tokens = response.json()
    tokens["obtained_at"] = time.time()
    _save_tokens(tokens)
    return tokens


def refresh_access_token(refresh_token: str) -> dict:
    """Access tokens expire after about an hour. Use the refresh token to get a new
    one without sending the user through the login screen again."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    response = httpx.post(TOKEN_URL, data=data, headers=_basic_auth_header())
    response.raise_for_status()
    tokens = response.json()
    tokens["obtained_at"] = time.time()
    # Spotify doesn't always send back a new refresh_token; keep the old one if so.
    if "refresh_token" not in tokens:
        tokens["refresh_token"] = refresh_token
    _save_tokens(tokens)
    return tokens


def _save_tokens(tokens: dict) -> None:
    with open(config.TOKEN_STORE_PATH, "w") as f:
        json.dump(tokens, f)


def _load_tokens() -> dict | None:
    if not os.path.exists(config.TOKEN_STORE_PATH):
        return None
    with open(config.TOKEN_STORE_PATH) as f:
        return json.load(f)


def get_valid_access_token() -> str:
    """Return a usable access token, refreshing it first if it has expired."""
    tokens = _load_tokens()
    if tokens is None:
        raise RuntimeError("No Spotify tokens found yet. Visit /login first.")

    expires_in = tokens.get("expires_in", 3600)
    obtained_at = tokens.get("obtained_at", 0)
    # Refresh a little early (60 second buffer) to avoid edge-case timing failures.
    if time.time() > obtained_at + expires_in - 60:
        tokens = refresh_access_token(tokens["refresh_token"])

    return tokens["access_token"]


def list_playlists() -> list[dict]:
    """Helper for finding your playlist's ID: lists your playlists by name.
    Visit /playlists after creating your 'To Summarize' playlist to find it here."""
    access_token = get_valid_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.get(f"{API_BASE}/me/playlists", headers=headers, params={"limit": 50})
    response.raise_for_status()
    data = response.json()
    return [{"id": p["id"], "name": p["name"]} for p in data["items"]]


def get_queue_episodes() -> list[dict]:
    """Fetch every episode currently sitting in your 'To Summarize' playlist.
    This is our queue of 'episodes waiting to be summarized,' built from a playlist
    you add to on purpose, instead of Spotify's saved-episodes library (which turned
    out to also fill up from downloads and followed shows, not just deliberate saves).

    Playlist items don't reliably include the show name, so this fetches each
    episode's full details directly from Spotify rather than trusting whatever
    the playlist happened to embed."""
    if not config.SPOTIFY_PLAYLIST_ID:
        raise RuntimeError("SPOTIFY_PLAYLIST_ID isn't set in .env yet. Visit /playlists to find it.")

    access_token = get_valid_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    # Step 1: collect the episode IDs currently in the playlist.
    episode_ids = []
    added_at_by_id = {}
    url = f"{API_BASE}/playlists/{config.SPOTIFY_PLAYLIST_ID}/items"
    params = {"limit": 50}

    while url:
        response = httpx.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        for entry in data["items"]:
            item = entry.get("item")
            # Skip anything that isn't a podcast episode (e.g. a song someone added
            # by mistake) or an item Spotify can no longer resolve.
            if not item or item.get("type") != "episode":
                continue
            episode_ids.append(item["id"])
            added_at_by_id[item["id"]] = entry.get("added_at")

        url = data.get("next")
        params = None  # the 'next' URL already has query params baked in

    # Step 2: hydrate each episode with its full details, including the show name.
    episodes = []
    for episode_id in episode_ids:
        response = httpx.get(f"{API_BASE}/episodes/{episode_id}", headers=headers)
        response.raise_for_status()
        ep = response.json()

        show_name = (ep.get("show") or {}).get("name")  # None if genuinely unavailable
        episodes.append(
            {
                "id": ep["id"],
                "uri": ep["uri"],
                "name": ep["name"],
                "description": ep.get("description", ""),
                "show_name": show_name,
                "duration_ms": ep.get("duration_ms"),
                "added_at": added_at_by_id.get(episode_id),
            }
        )

    return episodes


def remove_from_queue(episode_uri: str) -> None:
    """Remove an episode from the 'To Summarize' playlist. Our 'mark as done' signal."""
    if not config.SPOTIFY_PLAYLIST_ID:
        raise RuntimeError("SPOTIFY_PLAYLIST_ID isn't set in .env yet. Visit /playlists to find it.")

    access_token = get_valid_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    response = httpx.request(
        "DELETE",
        f"{API_BASE}/playlists/{config.SPOTIFY_PLAYLIST_ID}/items",
        headers=headers,
        json={"items": [{"uri": episode_uri}]},
    )
    response.raise_for_status()
