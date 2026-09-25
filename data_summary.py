"""
Summarizes what's actually in music_pulse.db so far -- run this before
deciding whether there's enough history to start the breakout-prediction
model, or to just eyeball data quality/gaps.

Usage:
    python data_summary.py
"""

import sqlite3
from collections import Counter

import db


def main():
    with db.get_connection() as conn:
        # 1. Date range and gap check
        cur = conn.execute("SELECT DISTINCT snapshot_date FROM snapshots ORDER BY snapshot_date")
        dates = [row["snapshot_date"] for row in cur.fetchall()]

        if not dates:
            print("No snapshots found yet -- has ingest.py run successfully at least once?")
            return

        print(f"Date range: {dates[0]} to {dates[-1]}")
        print(f"Total distinct days with data: {len(dates)}")

        # crude gap check -- flags if the number of days between first/last
        # doesn't match the count of distinct dates (i.e. some day was skipped)
        from datetime import date as date_cls
        first = date_cls.fromisoformat(dates[0])
        last = date_cls.fromisoformat(dates[-1])
        expected_days = (last - first).days + 1
        missing = expected_days - len(dates)
        if missing > 0:
            print(f"  -> {missing} day(s) appear to be MISSING in that range (cron didn't fire, or laptop was asleep)")
        else:
            print("  -> no gaps detected, every day in range has data")

        # 2. Overall volume
        cur = conn.execute("SELECT COUNT(*) as c FROM snapshots")
        total_snapshots = cur.fetchone()["c"]
        cur = conn.execute("SELECT COUNT(DISTINCT track_id) as c FROM snapshots")
        total_unique_tracks = cur.fetchone()["c"]
        print(f"\nTotal snapshot rows: {total_snapshots}")
        print(f"Total unique tracks ever seen: {total_unique_tracks}")

        # 3. Breakdown by source (global vs US)
        cur = conn.execute("SELECT source, COUNT(*) as c FROM snapshots GROUP BY source")
        print("\nSnapshots by source:")
        for row in cur.fetchall():
            print(f"  {row['source']}: {row['c']}")

        # 4. Trajectory length -- how many days does each track have data for?
        # This is the number that actually determines whether breakout
        # prediction has anything meaningful to learn from.
        cur = conn.execute(
            "SELECT track_id, COUNT(DISTINCT snapshot_date) as days_seen FROM snapshots GROUP BY track_id"
        )
        days_seen_counts = Counter()
        for row in cur.fetchall():
            days_seen_counts[row["days_seen"]] += 1

        print("\nTrack trajectory lengths (how many days of history per track):")
        for days_seen in sorted(days_seen_counts.keys(), reverse=True):
            print(f"  seen on {days_seen} day(s): {days_seen_counts[days_seen]} tracks")

        tracks_with_5plus_days = sum(c for d, c in days_seen_counts.items() if d >= 5)
        print(f"\nTracks with 5+ days of history (usable for breakout features): {tracks_with_5plus_days}")

        # 5. Tag/vocabulary coverage
        cur = conn.execute("SELECT COUNT(DISTINCT tag_name) as c FROM tags")
        distinct_tags = cur.fetchone()["c"]
        cur = conn.execute("SELECT COUNT(DISTINCT track_id) as c FROM tags")
        tracks_with_tags = cur.fetchone()["c"]
        print(f"\nDistinct raw tags collected: {distinct_tags}")
        print(f"Tracks with at least one tag: {tracks_with_tags} of {total_unique_tracks}")

        # 6. Recommendation
        print("\n--- Recommendation ---")
        if len(dates) < 10:
            print(f"Only {len(dates)} days collected -- still early. Breakout prediction needs "
                  f"enough trajectory length to detect climbing/falling patterns; keep letting "
                  f"ingest.py run daily.")
        elif tracks_with_5plus_days < 10:
            print(f"You have {len(dates)} days of data, but only {tracks_with_5plus_days} tracks "
                  f"have 5+ days of history -- that's the number that actually matters for "
                  f"breakout features. Consider whether tracks are churning too fast to build "
                  f"stable trajectories.")
        else:
            print(f"Looks like enough to start: {len(dates)} days collected, "
                  f"{tracks_with_5plus_days} tracks with 5+ days of trajectory data. "
                  f"Good enough to start building breakout-prediction features.")


if __name__ == "__main__":
    main()
