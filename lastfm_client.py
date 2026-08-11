"""
Thin wrapper around the Last.fm API (read-only chart methods).

Get a free API key at: https://www.last.fm/api/account/create
Only the API key is needed for these read methods -- no secret required.
"""

import os
import requests

BASE_URL = "https://ws.audioscrobbler.com/2.0/"
API_KEY = os.environ.get("LASTFM_API_KEY")  # set this in your environment


def _get(params):
    params.update({"api_key": API_KEY, "format": "json"})
    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_global_top_tracks(limit=50):
    """Last.fm's global top tracks chart."""
    data = _get({"method": "chart.gettoptracks", "limit": limit})
    tracks = data.get("tracks", {}).get("track", [])
    return _parse_tracks(tracks)


def get_top_tracks_by_tag(tag, limit=50):
    """Top tracks for a specific genre/tag, e.g. 'pop', 'hip-hop', 'indie'."""
    data = _get({"method": "tag.gettoptracks", "tag": tag, "limit": limit})
    tracks = data.get("tracks", {}).get("track", [])
    return _parse_tracks(tracks)


def get_track_top_tags(artist, track):
    """Fetch user-applied tags for a single track, ordered by tag count.

    Returns a list like [{"name": "chill", "count": 42}, ...].
    Falls back to an empty list if the track isn't found or has no tags --
    this happens fairly often for less-tagged tracks, so callers should
    handle an empty result gracefully rather than treating it as an error.
    """
    data = _get({"method": "track.gettoptags", "artist": artist, "track": track,
                 "autocorrect": 1})
    toptags = data.get("toptags", {})
    raw_tags = toptags.get("tag", [])
    if isinstance(raw_tags, dict):  # API returns a dict instead of list when there's only one tag
        raw_tags = [raw_tags]

    tags = []
    for t in raw_tags:
        try:
            count = int(t.get("count", 0))
        except (TypeError, ValueError):
            count = 0
        tags.append({"name": t.get("name", ""), "count": count})
    return tags


def _parse_tracks(raw_tracks):
    """Normalize Last.fm's response shape into a simple list of dicts."""
    parsed = []
    for i, t in enumerate(raw_tracks, start=1):
        parsed.append({
            "rank": i,
            "artist": t.get("artist", {}).get("name", "Unknown"),
            "title": t.get("name", "Unknown"),
            "playcount": int(t.get("playcount", 0)) if t.get("playcount") else None,
            "listeners": int(t.get("listeners", 0)) if t.get("listeners") else None,
        })
    return parsed
