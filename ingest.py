"""
Daily pipeline: pull trending tracks from Last.fm, store a rank snapshot,
fetch/store tags, then run mood clustering on the current snapshot.

Run this once a day (cron, Task Scheduler, or a simple loop) to build up
history for the breakout-prediction model down the line.

Usage:
    export LASTFM_API_KEY=your_key_here
    python ingest.py
"""

import time
from datetime import date

import db
import lastfm_client
import tag_features
import clustering

TRACK_LIMIT = 50           # how many trending tracks to pull each run
RATE_LIMIT_DELAY = 0.25    # seconds between Last.fm calls, be a good API citizen


def run_ingestion():
    today = date.today().isoformat()
    db.init_db()

    print(f"[{today}] Pulling global top tracks...")
    top_tracks = lastfm_client.get_global_top_tracks(limit=TRACK_LIMIT)
    print(f"  -> got {len(top_tracks)} tracks")

    with db.get_connection() as conn:
        track_id_map = {}

        # 1. Store rank snapshot for each track
        for t in top_tracks:
            track_id = db.upsert_track(conn, t["artist"], t["title"])
            db.insert_snapshot(
                conn, track_id, today,
                rank=t["rank"], playcount=t["playcount"],
                listeners=t["listeners"], source="lastfm_global",
            )
            track_id_map[track_id] = t

        # 2. Fetch and store tags for each track
        print("Fetching tags for each track...")
        for track_id, t in track_id_map.items():
            tags = lastfm_client.get_track_top_tags(t["artist"], t["title"])
            db.replace_track_tags(conn, track_id, tags, today)
            time.sleep(RATE_LIMIT_DELAY)
        print("  -> tags fetched")

        # 3. Build feature matrix and cluster
        print("Running mood clustering...")
        tags_by_track = db.get_tags_for_tracks(conn, list(track_id_map.keys()))
        track_ids, feature_matrix = tag_features.build_feature_matrix(tags_by_track)

        if len(track_ids) < 3:
            print("  -> not enough tagged tracks to cluster yet, skipping")
            return

        # NOTE: k=4 is a starting guess. Run clustering.find_optimal_k()
        # separately (e.g. in a notebook) against a real day's data to
        # pick a better value, then hardcode it here.
        k = min(4, len(track_ids))
        labels, centers = clustering.cluster_tracks(feature_matrix, k)
        cluster_names = clustering.describe_clusters(centers)

        for track_id, cluster_id in zip(track_ids, labels):
            db.insert_cluster_assignment(
                conn, track_id, today, int(cluster_id), cluster_names[cluster_id]
            )

        print(f"  -> clustered into {k} groups: {list(cluster_names.values())}")

    print(f"[{today}] Done.")


if __name__ == "__main__":
    run_ingestion()
