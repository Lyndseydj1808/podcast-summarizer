from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from .database import Base


class SpotifyToken(Base):
    """Holds the current Spotify access/refresh tokens. This app only ever
    connects one Spotify account, so in practice this table only ever has
    one row, which gets overwritten each time the token refreshes."""

    __tablename__ = "spotify_tokens"

    id = Column(Integer, primary_key=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    expires_in = Column(Integer, nullable=False)
    obtained_at = Column(Float, nullable=False)


class ProcessedEpisode(Base):
    """A permanent record of every episode this app has summarized, replacing
    'no longer in the playlist' as the only signal that something is done."""

    __tablename__ = "processed_episodes"

    id = Column(Integer, primary_key=True)
    spotify_episode_id = Column(String, unique=True, nullable=False)
    show_name = Column(String, nullable=True)
    episode_name = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
