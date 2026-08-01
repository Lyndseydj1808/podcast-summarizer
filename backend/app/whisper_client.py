import os
import tempfile

import httpx

from . import config

TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"

# Whisper rejects any file over 25MB. We stay a little under that as a safety margin.
MAX_CHUNK_BYTES = 24 * 1024 * 1024


class TranscriptionError(Exception):
    """Raised when downloading or transcribing an episode fails, with a message
    describing what specifically went wrong, instead of letting a raw network
    exception bubble up as an unhelpful generic error."""


def download_audio(audio_url: str) -> str:
    """Download an episode's audio to a temporary file on disk and return its path.
    Episodes can be large, so we stream to disk rather than holding the whole
    thing in memory."""
    fd, path = tempfile.mkstemp(suffix=".mp3")
    try:
        with os.fdopen(fd, "wb") as f:
            with httpx.stream("GET", audio_url, follow_redirects=True, timeout=120.0) as response:
                response.raise_for_status()
                for data in response.iter_bytes():
                    f.write(data)
    except httpx.HTTPStatusError as e:
        os.remove(path)
        raise TranscriptionError(
            f"The audio host returned an error ({e.response.status_code}) while downloading {audio_url}"
        ) from e
    except httpx.RequestError as e:
        os.remove(path)
        raise TranscriptionError(f"Couldn't reach the audio file at {audio_url}: {e}") from e

    return path


def split_audio(file_path: str) -> list[str]:
    """Split an audio file into pieces small enough for Whisper's 25MB limit.

    This is a simple byte-level split, not an audio-aware one (which would need
    ffmpeg installed separately). That means the exact cut point can land mid-sound
    rather than in a clean gap, occasionally garbling a fraction of a second right
    at each seam. Whisper is built to handle real-world, imperfect audio, so this
    tradeoff is worth it to avoid a whole extra system dependency.
    """
    size = os.path.getsize(file_path)
    if size <= MAX_CHUNK_BYTES:
        return [file_path]

    chunk_paths = []
    with open(file_path, "rb") as f:
        index = 0
        while True:
            data = f.read(MAX_CHUNK_BYTES)
            if not data:
                break
            chunk_path = f"{file_path}.part{index}.mp3"
            with open(chunk_path, "wb") as chunk_file:
                chunk_file.write(data)
            chunk_paths.append(chunk_path)
            index += 1
    return chunk_paths


def transcribe_chunk(file_path: str) -> str:
    """Send one audio file to Whisper and return the transcribed text."""
    if not config.OPENAI_API_KEY:
        raise TranscriptionError("OPENAI_API_KEY isn't set in .env yet")

    try:
        with open(file_path, "rb") as f:
            response = httpx.post(
                TRANSCRIPTION_URL,
                headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                files={"file": (os.path.basename(file_path), f, "audio/mpeg")},
                data={"model": "whisper-1"},
                timeout=300.0,  # transcription can take a while for a long chunk
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        # OpenAI's error responses include a helpful message body, so we surface
        # it (truncated) instead of just the status code.
        raise TranscriptionError(
            f"Whisper rejected this audio ({e.response.status_code}): {e.response.text[:300]}"
        ) from e
    except httpx.TimeoutException as e:
        raise TranscriptionError("Whisper took longer than 5 minutes to respond for this chunk") from e
    except httpx.RequestError as e:
        raise TranscriptionError(f"Couldn't reach OpenAI's servers: {e}") from e

    return response.json()["text"]


def transcribe_episode(audio_url: str) -> str:
    """Download an episode's audio and return its full transcript, splitting into
    chunks first if the file is too large for a single Whisper request."""
    audio_path = download_audio(audio_url)
    chunk_paths = split_audio(audio_path)

    try:
        transcripts = [transcribe_chunk(chunk) for chunk in chunk_paths]
    finally:
        # Always clean up the temp files we created, whether transcription
        # succeeded or blew up partway through.
        for path in set(chunk_paths + [audio_path]):
            if os.path.exists(path):
                os.remove(path)

    return " ".join(transcripts)
