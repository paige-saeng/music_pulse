"""
Feature engineering for the breakout-prediction model.

Builds one row per (track_id, as_of_date) from actual accumulated
snapshot history: rank-trajectory features describing what was known
UP TO that date, plus (where enough future data exists) a label for
whether the track reached the top-N threshold within a lookahead
window.

Design note -- this matters given real data: history has gaps (missed
cron days -- data_summary.py found 18 of 36 calendar days missing in
the first month). All lookback/lookahead logic works off actual
calendar dates present in the data, with a tolerance window, rather
than assuming a fixed day-index or that "yesterday's snapshot" exists.
Rows where a lookback/lookahead value can't be found within tolerance
just get NaN / an unlabeled row, rather than crashing or silently
using wrong data.

Usage:
    python breakout_features.py
"""

import pandas as pd
import numpy as np
from datetime import timedelta

import db

TOP_N_THRESHOLD = 20      # "breakout" = reaching this rank or better
LOOKAHEAD_DAYS = 5        # ...within this many days
LOOKAHEAD_TOLERANCE = 1   # allow +/- this many days when finding the "future" snapshot
MIN_TRACK_DAYS = 3        # skip tracks with fewer distinct days of history than this -- not enough to compute trends from


def load_daily_ranks():
    """One row per (track_id, date): the best (lowest) rank seen that day
    across all sources (global/US combined), plus how many sources it
    appeared in that day (a track charting in both is a meaningfully
    different signal than charting in just one)."""
    with db.get_connection() as conn:
        raw = pd.read_sql_query(
            "SELECT track_id, snapshot_date, rank, source FROM snapshots", conn
        )
    raw["snapshot_date"] = pd.to_datetime(raw["snapshot_date"])

    daily = raw.groupby(["track_id", "snapshot_date"]).agg(
        rank=("rank", "min"),
        n_sources=("source", "nunique"),
    ).reset_index()

    return daily.sort_values(["track_id", "snapshot_date"])


def _closest_rank(track_df, target_date, direction, tolerance_days):
    """Find the rank at the closest available date to target_date, in the
    given direction ('before' or 'after'), within tolerance_days.
    Returns None if nothing close enough exists -- callers must handle
    this (NaN feature / unlabeled row), never assume a value exists."""
    if direction == "before":
        window_start = target_date - timedelta(days=tolerance_days)
        candidates = track_df[(track_df["snapshot_date"] <= target_date) &
                               (track_df["snapshot_date"] >= window_start)]
    else:  # "after"
        window_end = target_date + timedelta(days=tolerance_days)
        candidates = track_df[(track_df["snapshot_date"] >= target_date) &
                               (track_df["snapshot_date"] <= window_end)]

    if candidates.empty:
        return None
    closest_idx = (candidates["snapshot_date"] - target_date).abs().idxmin()
    return candidates.loc[closest_idx, "rank"]


def build_feature_table():
    daily = load_daily_ranks()
    rows = []

    for track_id, track_df in daily.groupby("track_id"):
        track_df = track_df.sort_values("snapshot_date").reset_index(drop=True)
        if track_df["snapshot_date"].nunique() < MIN_TRACK_DAYS:
            continue

        for _, row in track_df.iterrows():
            as_of = row["snapshot_date"]
            current_rank = row["rank"]

            rank_1d = _closest_rank(track_df, as_of - timedelta(days=1), "before", tolerance_days=1)
            rank_3d = _closest_rank(track_df, as_of - timedelta(days=3), "before", tolerance_days=1)
            rank_7d = _closest_rank(track_df, as_of - timedelta(days=7), "before", tolerance_days=2)

            # velocity: rank points improved per day (positive = climbing,
            # since a LOWER rank number is better)
            velocity_1d = (rank_1d - current_rank) if rank_1d is not None else np.nan
            velocity_3d = ((rank_3d - current_rank) / 3) if rank_3d is not None else np.nan
            velocity_7d = ((rank_7d - current_rank) / 7) if rank_7d is not None else np.nan

            acceleration = (
                velocity_3d - velocity_7d
                if not (np.isnan(velocity_3d) or np.isnan(velocity_7d))
                else np.nan
            )

            # volatility: how much has rank bounced around over the
            # trailing ~2 weeks of REAL available history (not a fixed
            # count of rows, since gaps mean that's not a fixed time span)
            window_start = as_of - timedelta(days=14)
            trailing = track_df[(track_df["snapshot_date"] >= window_start) &
                                 (track_df["snapshot_date"] <= as_of)]
            volatility_14d = trailing["rank"].std() if len(trailing) >= 3 else np.nan

            days_tracked_so_far = track_df[track_df["snapshot_date"] <= as_of]["snapshot_date"].nunique()

            # label: does the track reach the threshold within the
            # lookahead window? None (not 0) if we simply don't have
            # future data yet -- these rows get excluded from training,
            # never treated as a negative example by default.
            future_date = as_of + timedelta(days=LOOKAHEAD_DAYS)
            future_rank = _closest_rank(track_df, future_date, "after", tolerance_days=LOOKAHEAD_TOLERANCE)
            label = None if future_rank is None else int(future_rank <= TOP_N_THRESHOLD)

            rows.append({
                "track_id": track_id,
                "as_of_date": as_of,
                "current_rank": current_rank,
                "rank_1d_ago": rank_1d,
                "rank_3d_ago": rank_3d,
                "rank_7d_ago": rank_7d,
                "velocity_1d": velocity_1d,
                "velocity_3d": velocity_3d,
                "velocity_7d": velocity_7d,
                "acceleration": acceleration,
                "volatility_14d": volatility_14d,
                "days_tracked_so_far": days_tracked_so_far,
                "n_sources_today": row["n_sources"],
                "label": label,
            })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    features = build_feature_table()
    labeled = features.dropna(subset=["label"])

    print(f"Total feature rows (all as-of-dates, all tracks): {len(features)}")
    print(f"Labeled rows (usable for training right now): {len(labeled)}")
    if len(labeled) > 0:
        print(f"Label distribution:\n{labeled['label'].value_counts().to_string()}")
    else:
        print("No labeled rows yet -- need LOOKAHEAD_DAYS more days of history "
              "past your earliest as_of_date before any row can be labeled.")

    features.to_csv("breakout_features.csv", index=False)
    print("\nSaved full feature table (labeled + unlabeled) to breakout_features.csv")
