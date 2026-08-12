"""
Run this to pick a justified value for k (number of clusters) instead
of the k=4 placeholder in ingest.py.

Loads your most recent day's data from music_pulse.db, builds the same
feature matrix ingest.py uses, computes inertia across a range of k
values, and plots the elbow curve.

Usage:
    python choose_k.py
"""

import sqlite3
import matplotlib.pyplot as plt

import db
import tag_features
import clustering


def load_latest_tags():
    with db.get_connection() as conn:
        # find the most recent snapshot date
        cur = conn.execute("SELECT MAX(snapshot_date) as latest FROM snapshots")
        latest_date = cur.fetchone()["latest"]
        if not latest_date:
            raise RuntimeError("No snapshots found -- run ingest.py at least once first.")

        cur = conn.execute(
            "SELECT DISTINCT track_id FROM snapshots WHERE snapshot_date = ?",
            (latest_date,),
        )
        track_ids = [row["track_id"] for row in cur.fetchall()]

        tags_by_track = db.get_tags_for_tracks(conn, track_ids)

    print(f"Loaded {len(tags_by_track)} tracks from {latest_date}")
    return tags_by_track


def main():
    tags_by_track = load_latest_tags()

    vocabulary = tag_features.build_vocabulary(tags_by_track)
    print(f"Vocabulary ({len(vocabulary)} tags): {vocabulary}")

    track_ids, feature_matrix = tag_features.build_feature_matrix(tags_by_track, vocabulary)

    if len(track_ids) < 3:
        print("Not enough tracked tracks to run this yet.")
        return

    max_k = min(9, len(track_ids))
    results = clustering.find_optimal_k(feature_matrix, k_range=range(2, max_k))

    print("\nk -> inertia (lower = tighter clusters, but always decreases as k grows --")
    print("look for where the drop-off levels off, not just the lowest number):")
    for k, inertia in results:
        print(f"  k={k}: {inertia:.3f}")

    ks = [k for k, _ in results]
    inertias = [i for _, i in results]

    plt.figure(figsize=(7, 5))
    plt.plot(ks, inertias, marker="o")
    plt.xlabel("k (number of clusters)")
    plt.ylabel("Inertia")
    plt.title("Elbow method -- look for where the curve bends and flattens")
    plt.grid(True, alpha=0.3)
    plt.savefig("elbow_plot.png")
    print("\nSaved plot to elbow_plot.png -- open it and look for the elbow point.")
    print("Once you've picked a k, update k = min(4, len(track_ids)) in ingest.py")
    print("to use your chosen number instead of 4.")


if __name__ == "__main__":
    main()
