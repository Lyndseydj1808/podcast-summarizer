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

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Path to the Google service account's private key file, and the ID of the
# Google Sheet (from its URL) to write summaries into. The key file lives in
# the backend/ folder alongside .env, so we build its full path here rather
# than relying on whatever folder the app happens to be launched from.
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
GOOGLE_SERVICE_ACCOUNT_PATH = (
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), GOOGLE_SERVICE_ACCOUNT_FILE)
    if GOOGLE_SERVICE_ACCOUNT_FILE
    else None
)
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

# Connection string for the Postgres database (see backend/app/database.py).
DATABASE_URL = os.getenv("DATABASE_URL")
