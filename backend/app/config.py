import os

from dotenv import load_dotenv

# Reads the .env file in the backend/ folder and loads it into the environment.
load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")

# playlist-read-private: lets us see the contents of your private "To Summarize" playlist.
# playlist-modify-private / playlist-modify-public: lets us remove an episode once it's processed.
SPOTIFY_SCOPES = "playlist-read-private playlist-modify-private playlist-modify-public"

# The Spotify ID of the playlist you're using as your "episodes to summarize" queue.
# Create a playlist (e.g. named "To Summarize"), then use the /playlists route
# this app provides to find its ID and paste it in here.
SPOTIFY_PLAYLIST_ID = os.getenv("SPOTIFY_PLAYLIST_ID")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Temporary local file for storing your Spotify tokens between requests.
# This is a placeholder until Phase 6, when Postgres takes over.
TOKEN_STORE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tokens.json"
)
