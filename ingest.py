"""
Daily pipeline: pull trending tracks from Last.fm (global + US charts),
store rank snapshots, fetch/store tags, then run genre clustering on
the combined set of tracks seen today.

Run this once a day (cron, Task Scheduler, or a simple loop) to build up
history for the breakout-prediction model down the line.

Usage:
    export LASTFM_API_KEY=94d7749a39b0002f0d7c887840801d3a
    python ingest.py
"""

from curses import echo
import time
from datetime import date

import db
import lastfm_client
import tag_features
import clustering

TRACK_LIMIT = 50           # how many trending tracks to pull per chart, per run
RATE_LIMIT_DELAY = 0.25    # seconds between Last.fm calls, be a good API citizen

# Charts to pull each run: (source label, fetch function)
CHARTS = [
    ("lastfm_global", lambda: lastfm_client.get_global_top_tracks(limit=TRACK_LIMIT)),
    ("lastfm_us", lambda: lastfm_client.get_top_tracks_by_country("United States", limit=TRACK_LIMIT)),
]


def run_ingestion():
    today = date.today().isoformat()
    db.init_db()

    with db.get_connection() as conn:
        track_id_map = {}  # deduped across charts -- same track can appear in both

        # 1. Pull each chart and store a rank snapshot per source
        for source, fetch_fn in CHARTS:
            print(f"[{today}] Pulling {source} top tracks...")
            top_tracks = fetch_fn()
            print(f"  -> got {len(top_tracks)} tracks")

            for t in top_tracks:
                track_id = db.upsert_track(conn, t["artist"], t["title"])
                db.insert_snapshot(
                    conn, track_id, today,
                    rank=t["rank"], playcount=t["playcount"],
                    listeners=t["listeners"], source=source,
                )
                track_id_map[track_id] = t  # dedupes automatically by track_id
            time.sleep(RATE_LIMIT_DELAY)

        print(f"Combined unique tracks across charts: {len(track_id_map)}")

        # 2. Fetch and store tags for each unique track (only once, even if
        #    it appeared in both charts)
        print("Fetching tags for each track...")
        for track_id, t in track_id_map.items():
            tags = lastfm_client.get_track_top_tags(t["artist"], t["title"])
            db.replace_track_tags(conn, track_id, tags, today)
            time.sleep(RATE_LIMIT_DELAY)
        print("  -> tags fetched")

        # 3. Build a data-driven vocabulary, feature matrix, and cluster
        print("Building tag vocabulary from today's data...")
        tags_by_track = db.get_tags_for_tracks(conn, list(track_id_map.keys()))
        vocabulary = tag_features.build_vocabulary(tags_by_track)
        print(f"  -> vocabulary ({len(vocabulary)} tags): {vocabulary[:10]}"
              f"{'...' if len(vocabulary) > 10 else ''}")

        track_ids, feature_matrix = tag_features.build_feature_matrix(tags_by_track, vocabulary)

        if len(track_ids) < 3 or len(vocabulary) < 2:
            print("  -> not enough tag signal to cluster yet, skipping")
            return

        print("Running clustering...")
        # k=4: chosen via choose_k.py's elbow method against real data.
        # The inertia curve didn't show a sharp elbow at current data
        # volume/vocabulary size (roughly linear decline, ~0.8-1.3 drop
        # per step from k=2 to k=8) -- so k=4 was picked for
        # interpretability (small enough to name each cluster
        # meaningfully) rather than a clear mathematical inflection
        # point. Worth re-running choose_k.py once more history has
        # accumulated to see if a clearer elbow emerges.
        k = min(4, len(track_ids))
        labels, centers = clustering.cluster_tracks(feature_matrix, k)
        cluster_names = clustering.describe_clusters(centers, vocabulary)

        for track_id, cluster_id in zip(track_ids, labels):
            db.insert_cluster_assignment(
                conn, track_id, today, int(cluster_id), cluster_names[cluster_id]
            )

        print(f"  -> clustered into {k} groups: {list(cluster_names.values())}")

    print(f"[{today}] Done.")


if __name__ == "__main__":
    run_ingestion()




