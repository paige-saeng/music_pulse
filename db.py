"""
SQLite storage for the music trend pipeline.

Schema:
- tracks: one row per unique track (artist + title), stable across snapshots
- snapshots: one row per (track, date) -- the daily rank/popularity reading
- tags: one row per (track, tag) -- raw Last.fm tag data with counts
- clusters: one row per (track, run_date) -- which mood cluster it landed in
"""

import sqlite3
from contextlib import contextmanager

DB_PATH = "music_pulse.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    track_id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist TEXT NOT NULL,
    title TEXT NOT NULL,
    UNIQUE(artist, title)
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    snapshot_date TEXT NOT NULL,   -- ISO date, e.g. 2026-08-10
    rank INTEGER,
    playcount INTEGER,
    listeners INTEGER,
    source TEXT NOT NULL,          -- e.g. 'lastfm_global', 'lastfm_tag:pop'
    FOREIGN KEY (track_id) REFERENCES tracks(track_id),
    UNIQUE(track_id, snapshot_date, source)
);

CREATE TABLE IF NOT EXISTS tags (
    track_id INTEGER NOT NULL,
    tag_name TEXT NOT NULL,
    tag_count INTEGER,             -- raw count from Last.fm (relative weight, not absolute)
    fetched_date TEXT,
    PRIMARY KEY (track_id, tag_name),
    FOREIGN KEY (track_id) REFERENCES tracks(track_id)
);

CREATE TABLE IF NOT EXISTS clusters (
    track_id INTEGER NOT NULL,
    run_date TEXT NOT NULL,
    cluster_id INTEGER,
    cluster_label TEXT,
    PRIMARY KEY (track_id, run_date),
    FOREIGN KEY (track_id) REFERENCES tracks(track_id)
);
"""


@contextmanager
def get_connection(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path=DB_PATH):
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)


def upsert_track(conn, artist, title):
    """Insert a track if new, return its track_id either way."""
    cur = conn.execute(
        "SELECT track_id FROM tracks WHERE artist = ? AND title = ?",
        (artist, title),
    )
    row = cur.fetchone()
    if row:
        return row["track_id"]

    cur = conn.execute(
        "INSERT INTO tracks (artist, title) VALUES (?, ?)",
        (artist, title),
    )
    return cur.lastrowid


def insert_snapshot(conn, track_id, snapshot_date, rank, playcount, listeners, source):
    conn.execute(
        """INSERT OR REPLACE INTO snapshots
           (track_id, snapshot_date, rank, playcount, listeners, source)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (track_id, snapshot_date, rank, playcount, listeners, source),
    )


def replace_track_tags(conn, track_id, tag_list, fetched_date):
    """Store this track's tags, replacing any previously stored set.

    tag_list: list of dicts like [{"name": "chill", "count": 42}, ...]
    """
    conn.execute("DELETE FROM tags WHERE track_id = ?", (track_id,))
    for tag in tag_list:
        conn.execute(
            """INSERT OR REPLACE INTO tags (track_id, tag_name, tag_count, fetched_date)
               VALUES (?, ?, ?, ?)""",
            (track_id, tag["name"].lower().strip(), tag.get("count", 0), fetched_date),
        )


def get_tags_for_tracks(conn, track_ids):
    """Fetch all stored tags for a set of track_ids, grouped by track_id."""
    if not track_ids:
        return {}
    placeholders = ",".join("?" for _ in track_ids)
    cur = conn.execute(
        f"SELECT track_id, tag_name, tag_count FROM tags WHERE track_id IN ({placeholders})",
        track_ids,
    )
    result = {}
    for row in cur.fetchall():
        result.setdefault(row["track_id"], []).append(
            {"name": row["tag_name"], "count": row["tag_count"]}
        )
    return result


def insert_cluster_assignment(conn, track_id, run_date, cluster_id, cluster_label):
    conn.execute(
        """INSERT OR REPLACE INTO clusters (track_id, run_date, cluster_id, cluster_label)
           VALUES (?, ?, ?, ?)""",
        (track_id, run_date, cluster_id, cluster_label),
    )
