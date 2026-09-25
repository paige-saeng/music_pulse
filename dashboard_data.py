"""
Data-loading functions for the dashboard -- deliberately kept separate
from any Streamlit UI code so this logic can be tested directly with
plain function calls and assertions, not just by eyeballing a rendered
page.

dashboard.py imports these and wraps them with Streamlit display calls.
"""

import pandas as pd

import db


def get_available_dates():
    """All distinct snapshot dates, most recent first."""
    with db.get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT DISTINCT snapshot_date FROM snapshots ORDER BY snapshot_date DESC", conn
        )
    return df["snapshot_date"].tolist()


def get_top_tracks_for_date(snapshot_date, source=None, limit=50):
    """Top tracks for a given date, optionally filtered to one source
    (lastfm_global / lastfm_us). Returns rank, artist, title, source."""
    query = """
        SELECT s.rank, t.artist, t.title, s.source
        FROM snapshots s
        JOIN tracks t ON s.track_id = t.track_id
        WHERE s.snapshot_date = ?
    """
    params = [snapshot_date]
    if source:
        query += " AND s.source = ?"
        params.append(source)
    query += " ORDER BY s.rank ASC LIMIT ?"
    params.append(limit)

    with db.get_connection() as conn:
        df = pd.read_sql_query(query, conn, params=params)
    return df


def get_cluster_summary_for_date(run_date):
    """Cluster sizes and labels for a given date, plus which tracks are
    in each cluster."""
    query = """
        SELECT c.cluster_id, c.cluster_label, t.artist, t.title
        FROM clusters c
        JOIN tracks t ON c.track_id = t.track_id
        WHERE c.run_date = ?
        ORDER BY c.cluster_id
    """
    with db.get_connection() as conn:
        df = pd.read_sql_query(query, conn, params=[run_date])

    if df.empty:
        return pd.DataFrame(columns=["cluster_id", "cluster_label", "track_count"]), df

    summary = (
        df.groupby(["cluster_id", "cluster_label"])
        .size()
        .reset_index(name="track_count")
        .sort_values("track_count", ascending=False)
    )
    return summary, df


def search_tracks(query_text, limit=20):
    """Search tracks by artist or title substring, for a track-picker UI."""
    like_pattern = f"%{query_text}%"
    query = """
        SELECT DISTINCT track_id, artist, title
        FROM tracks
        WHERE artist LIKE ? OR title LIKE ?
        LIMIT ?
    """
    with db.get_connection() as conn:
        df = pd.read_sql_query(query, conn, params=[like_pattern, like_pattern, limit])
    return df


def get_track_history(track_id):
    """Full rank history for one track across all dates/sources --
    used to plot an individual track's trajectory over time.

    track_id is explicitly cast to a native Python int: pandas returns
    numpy.int64 from query results, and sqlite3's parameter binding
    silently matches ZERO rows (no error raised) when given a
    numpy.int64 instead of a plain int -- a real bug caught in testing,
    not a hypothetical."""
    track_id = int(track_id)
    query = """
        SELECT snapshot_date, rank, source
        FROM snapshots
        WHERE track_id = ?
        ORDER BY snapshot_date ASC
    """
    with db.get_connection() as conn:
        df = pd.read_sql_query(query, conn, params=[track_id])
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    return df


def get_headline_insights(selected_date):
    """Compute the day's actual story: biggest riser, dominant genre
    cluster, and cross-chart overlap -- the things a person actually
    wants to know first, not pipeline meta-stats.

    Returns a dict; any value can be None if there isn't enough data
    (e.g. no previous date to compare against for 'biggest riser').
    """
    with db.get_connection() as conn:
        dates_df = pd.read_sql_query(
            "SELECT DISTINCT snapshot_date FROM snapshots WHERE snapshot_date <= ? ORDER BY snapshot_date DESC LIMIT 2",
            conn, params=[selected_date]
        )
    insights = {"biggest_riser": None, "dominant_cluster": None, "both_charts_count": None}

    # --- Biggest riser: compare today's ranks to the most recent prior date ---
    if len(dates_df) == 2:
        prev_date = dates_df["snapshot_date"].iloc[1]
        with db.get_connection() as conn:
            today_ranks = pd.read_sql_query(
                "SELECT track_id, MIN(rank) as rank FROM snapshots WHERE snapshot_date = ? GROUP BY track_id",
                conn, params=[selected_date]
            )
            prev_ranks = pd.read_sql_query(
                "SELECT track_id, MIN(rank) as rank FROM snapshots WHERE snapshot_date = ? GROUP BY track_id",
                conn, params=[prev_date]
            )
        merged = today_ranks.merge(prev_ranks, on="track_id", suffixes=("_today", "_prev"))
        if not merged.empty:
            merged["improvement"] = merged["rank_prev"] - merged["rank_today"]
            best = merged.sort_values("improvement", ascending=False).iloc[0]
            if best["improvement"] > 0:
                with db.get_connection() as conn:
                    track_info = pd.read_sql_query(
                        "SELECT artist, title FROM tracks WHERE track_id = ?",
                        conn, params=[int(best["track_id"])]
                    )
                if not track_info.empty:
                    insights["biggest_riser"] = {
                        "artist": track_info["artist"].iloc[0],
                        "title": track_info["title"].iloc[0],
                        "from_rank": int(best["rank_prev"]),
                        "to_rank": int(best["rank_today"]),
                    }

    # --- Dominant genre cluster today ---
    summary, _ = get_cluster_summary_for_date(selected_date)
    if not summary.empty:
        top_cluster = summary.iloc[0]
        insights["dominant_cluster"] = {
            "label": top_cluster["cluster_label"],
            "count": int(top_cluster["track_count"]),
            "total": int(summary["track_count"].sum()),
        }

    # --- Cross-chart overlap: how many tracks are in both global and US today ---
    with db.get_connection() as conn:
        overlap_df = pd.read_sql_query(
            """SELECT track_id, COUNT(DISTINCT source) as n_sources
               FROM snapshots WHERE snapshot_date = ? GROUP BY track_id""",
            conn, params=[selected_date]
        )
    if not overlap_df.empty:
        insights["both_charts_count"] = int((overlap_df["n_sources"] >= 2).sum())

    return insights


def get_overall_stats():
    """High-level pipeline stats for a summary header."""
    with db.get_connection() as conn:
        dates_df = pd.read_sql_query("SELECT DISTINCT snapshot_date FROM snapshots", conn)
        tracks_df = pd.read_sql_query("SELECT COUNT(DISTINCT track_id) as c FROM snapshots", conn)
        snapshots_df = pd.read_sql_query("SELECT COUNT(*) as c FROM snapshots", conn)

    return {
        "total_days": len(dates_df),
        "total_unique_tracks": int(tracks_df["c"].iloc[0]) if not tracks_df.empty else 0,
        "total_snapshots": int(snapshots_df["c"].iloc[0]) if not snapshots_df.empty else 0,
        "date_range": (
            (dates_df["snapshot_date"].min(), dates_df["snapshot_date"].max())
            if not dates_df.empty else (None, None)
        ),
    }
