import os
import tempfile

import httpx
from pydub import AudioSegment

from . import config

TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"

# Whisper rejects any file over 25MB. We stay a little under that as a safety margin.
MAX_CHUNK_BYTES = 24 * 1024 * 1024

# When a file needs splitting, cut it into fixed-length pieces (rather than a
# fixed byte size) and re-export each one at a modest, known bitrate. That
# combination keeps every chunk comfortably under Whisper's limit no matter
# how the original file was encoded.
CHUNK_DURATION_MS = 20 * 60 * 1000  # 20 minutes
CHUNK_EXPORT_BITRATE = "128k"

# Podcast hosts don't always serve audio from a URL ending in .mp3 even when
# the file isn't actually an MP3. We use the real Content-Type header to pick
# the right extension, since ffmpeg leans on it to identify the format.
CONTENT_TYPE_TO_EXTENSION = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/x-m4a": "m4a",
    "audio/mp4": "m4a",
    "audio/aac": "aac",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
}


class TranscriptionError(Exception):
    """Raised when downloading or transcribing an episode fails, with a message
    describing what specifically went wrong, instead of letting a raw network
    exception bubble up as an unhelpful generic error."""


def download_audio(audio_url: str) -> str:
    """Download an episode's audio to a temporary file on disk and return its path.
    Episodes can be large, so we stream to disk rather than holding the whole
    thing in memory."""
    path = None
    try:
        with httpx.stream("GET", audio_url, follow_redirects=True, timeout=120.0) as response:
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            extension = CONTENT_TYPE_TO_EXTENSION.get(content_type, "mp3")

            fd, path = tempfile.mkstemp(suffix=f".{extension}")
            with os.fdopen(fd, "wb") as f:
                for data in response.iter_bytes():
                    f.write(data)
    except httpx.HTTPStatusError as e:
        raise TranscriptionError(
            f"The audio host returned an error ({e.response.status_code}) while downloading {audio_url}"
        ) from e
    except httpx.RequestError as e:
        if path and os.path.exists(path):
            os.remove(path)
        raise TranscriptionError(f"Couldn't reach the audio file at {audio_url}: {e}") from e

    return path


def split_audio(file_path: str) -> list[str]:
    """Split an audio file into pieces small enough for Whisper's 25MB limit.

    Files under the limit are sent as-is. Larger files are decoded with ffmpeg
    (via pydub) and cut by time rather than by raw byte position, then each
    piece is re-exported as a clean mp3. A raw byte-level split only produces
    valid audio for simple, frame-based formats like MP3, container formats
    like M4A aren't playable anymore once sliced mid-file.
    """
    if os.path.getsize(file_path) <= MAX_CHUNK_BYTES:
        return [file_path]

    audio = AudioSegment.from_file(file_path)

    chunk_paths = []
    for index, start_ms in enumerate(range(0, len(audio), CHUNK_DURATION_MS)):
        chunk = audio[start_ms : start_ms + CHUNK_DURATION_MS]
        chunk_path = f"{file_path}.part{index}.mp3"
        chunk.export(chunk_path, format="mp3", bitrate=CHUNK_EXPORT_BITRATE)
        chunk_paths.append(chunk_path)

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
