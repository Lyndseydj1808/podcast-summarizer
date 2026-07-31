from difflib import SequenceMatcher

import feedparser
import httpx

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"

# Below this similarity score (0.0 to 1.0), we don't trust the match enough to use it.
MATCH_CONFIDENCE_THRESHOLD = 0.6


def _normalize(title: str) -> str:
    """Lowercase and strip punctuation so 'The A.I. Trade!' and 'the ai trade' can
    be compared fairly."""
    return "".join(c.lower() for c in title if c.isalnum() or c.isspace()).strip()


def find_feed_url(show_name: str) -> dict | None:
    """Look up a podcast show's RSS feed address using Apple's free podcast directory.
    This works regardless of where you actually listen, iTunes just indexes the feed.

    Always returns the closest candidate found (with a 'confident' flag), rather than
    silently returning a bad match when none of the results are actually the right show."""
    response = httpx.get(
        ITUNES_SEARCH_URL,
        params={"term": show_name, "media": "podcast", "entity": "podcast", "limit": 5},
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        return None

    target = _normalize(show_name)
    scored = [
        (SequenceMatcher(None, target, _normalize(r.get("collectionName", ""))).ratio(), r)
        for r in results
    ]
    best_score, best = max(scored, key=lambda pair: pair[0])

    return {
        "feed_url": best.get("feedUrl"),
        "matched_show_name": best.get("collectionName"),
        "confidence": round(best_score, 2),
        "confident": best_score >= MATCH_CONFIDENCE_THRESHOLD,
        "candidates": [r.get("collectionName") for r in results],
    }


def get_feed_episodes(feed_url: str) -> list[dict]:
    """Download and parse a show's RSS feed into a simple list of episodes."""
    parsed = feedparser.parse(feed_url)

    episodes = []
    for entry in parsed.entries:
        audio_url = None
        for enclosure in entry.get("enclosures", []):
            if enclosure.get("href"):
                audio_url = enclosure["href"]
                break

        episodes.append(
            {
                "title": entry.get("title", ""),
                "audio_url": audio_url,
                # Best-effort: only a minority of feeds publish this (Podcasting 2.0's
                # <podcast:transcript> tag). None just means "not available."
                "transcript_url": entry.get("podcast_transcript", {}).get("url")
                if entry.get("podcast_transcript")
                else None,
                "published": entry.get("published"),
            }
        )

    return episodes


def match_episode(spotify_episode: dict, feed_episodes: list[dict]) -> dict | None:
    """Find whichever RSS entry's title best matches a given Spotify episode's title.
    Always returns the closest candidate (with a 'confident' flag) rather than hiding
    a weak match, so callers can see *why* a match was rejected instead of guessing."""
    if not feed_episodes:
        return None

    target = _normalize(spotify_episode["name"])

    best_match = None
    best_score = 0.0
    for episode in feed_episodes:
        score = SequenceMatcher(None, target, _normalize(episode["title"])).ratio()
        if score > best_score:
            best_score = score
            best_match = episode

    return {
        **best_match,
        "match_confidence": round(best_score, 2),
        "confident": best_score >= MATCH_CONFIDENCE_THRESHOLD,
    }
