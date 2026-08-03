import httpx

from . import config

MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Sonnet: writing detailed, well-organized topic-by-topic notes across a long
# transcript benefits from a more capable model. The cost difference vs. Haiku
# here is a couple cents per episode, trivial next to the ~$0.30-0.50 Whisper
# already costs per episode, so it's worth it for the quality.
MODEL = "claude-sonnet-5"

SUMMARY_PROMPT = """You are taking notes on a podcast episode for someone who listened while \
multitasking and wants detailed notes afterward to help them actually remember what was said, \
similar to notes they'd have taken themselves while listening closely.

Show: {show_name}
Episode: {episode_name}

The transcript below includes sponsor and ad reads mixed in with the real content (things \
like unrelated product pitches). Ignore those completely, they are not part of the actual \
episode and should never appear in your notes.

Break the episode into a small number of broad topics, aim for 3-6 total for a typical \
episode. Group related threads together under one topic rather than giving every minor \
sub-point its own heading. Skip anything that isn't real content: intro banter, personal \
jokes, small talk between hosts, or chit-chat before a topic actually starts.

For each broad topic:

TOPIC: <short, specific topic name>
- 2-3 bullet points capturing only the most important points, arguments, or conclusions,
  specific enough that reading them brings the discussion back to mind
- Exactly one sentence per bullet. Favor brevity over completeness, these are quick-reference
  notes meant to jog your memory, not a full transcript recap
- Include a name, number, or specific detail only when it's actually important to the point

Cover every major topic in the episode, not just the first one.

After all topics, add one final section:

REFERENCES:
- Every specific named source mentioned anywhere in the episode: articles, papers, books,
  studies, reports, other podcasts or episodes, blog posts, etc. Include the title and
  author/publication when mentioned, so it could be looked up later.
- Only include things actually mentioned in the transcript. If nothing concrete was
  referenced, write "None mentioned" rather than inventing something.

Use plain text only, no markdown symbols like # or **, just the TOPIC:/REFERENCES: labels
and dash bullet points shown above, since these notes need to read cleanly in a spreadsheet
cell later.

Transcript:
{transcript}
"""


class SummarizationError(Exception):
    """Raised when Claude fails to summarize a transcript, with a message describing
    what specifically went wrong."""


def summarize_transcript(transcript: str, episode_name: str, show_name: str) -> str:
    """Send a transcript to Claude and return a short summary of the actual episode
    content, with sponsor reads filtered out by the prompt itself."""
    if not config.ANTHROPIC_API_KEY:
        raise SummarizationError("ANTHROPIC_API_KEY isn't set in .env yet")

    prompt = SUMMARY_PROMPT.format(
        show_name=show_name, episode_name=episode_name, transcript=transcript
    )

    try:
        response = httpx.post(
            MESSAGES_URL,
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                # Detailed, multi-topic notes for a dense episode (several news
                # segments plus a full guest interview) can genuinely run long.
                # Both 2000 and 4096 got cut off mid-sentence in testing, so this
                # gives real headroom rather than guessing again one step at a time.
                "max_tokens": 8192,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise SummarizationError(
            f"Claude rejected this request ({e.response.status_code}): {e.response.text[:300]}"
        ) from e
    except httpx.TimeoutException as e:
        raise SummarizationError("Claude took too long to respond") from e
    except httpx.RequestError as e:
        raise SummarizationError(f"Couldn't reach Anthropic's servers: {e}") from e

    data = response.json()

    # Claude's response can include content blocks other than plain text
    # (behavior can vary by model), so we pull out only the text blocks
    # instead of assuming the first block is always the one we want.
    text_blocks = [block["text"] for block in data.get("content", []) if block.get("type") == "text"]
    if not text_blocks:
        raise SummarizationError(f"Claude's response didn't include any text content: {data}")

    text = "\n".join(text_blocks)

    # If Claude was still writing when it hit max_tokens, say so clearly rather
    # than silently handing back notes that stop mid-sentence with no explanation.
    if data.get("stop_reason") == "max_tokens":
        text += "\n\n[Note: these notes were cut off because the response hit the length limit.]"

    return text
