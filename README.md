# Music Pulse — Trending Tracks + Mood Clustering

Pulls daily trending tracks from Last.fm, stores rank history, fetches
user-applied tags, and clusters tracks into mood groups based on those
tags. Built to run daily so history accumulates for a breakout-prediction
model later.

## Why tags instead of Spotify audio features

Spotify deprecated `audio-features` for all new apps in Nov 2024 — no
path to access it for a new project. This pipeline uses Last.fm's
crowdsourced tags instead (`chill`, `energetic`, `sad`, etc.) as the
mood signal. Noisier than clean numeric scores, but fully accessible
and free.

## Setup

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Get a free Last.fm API key: https://www.last.fm/api/account/create
(only the key is needed, not the shared secret, for these read-only
methods).

Set it as an environment variable before running:

```bash
export LASTFM_API_KEY=your_key_here      # Windows: set LASTFM_API_KEY=your_key_here
```

## Run

```bash
python ingest.py
```

This will:
1. Pull the current global top 50 tracks from Last.fm
2. Store a rank/playcount/listeners snapshot for today
3. Fetch tags for each track
4. Cluster tracks into mood groups (k=4 by default) and store assignments

Run it daily (cron / Task Scheduler / a simple `while True: sleep 24h`
loop) to build up the rank history needed for breakout prediction later.

## Files

- `db.py` — SQLite schema (tracks, snapshots, tags, clusters) and helpers
- `lastfm_client.py` — API wrapper (chart data + tag data)
- `tag_features.py` — mood vocabulary + tag normalization/vectorization
- `clustering.py` — k-means clustering + elbow method + cluster naming
- `ingest.py` — the daily pipeline script that ties it together

## Tuning the mood vocabulary

`tag_features.py`'s `MOOD_VOCAB` dict is a starting point, not a final
answer. After your first few runs, check what raw tags are actually
showing up (query the `tags` table directly) and adjust — you'll likely
find genre tags dominating (since most Last.fm tags are genres, not
moods) and need to expand the mood-tag variants you're folding in.

## Choosing k for clustering

`ingest.py` currently hardcodes `k=4`. Better approach: pull a real
day's data, then in a notebook run:

```python
from clustering import find_optimal_k
results = find_optimal_k(feature_matrix)
# plot k vs inertia, look for the elbow
```

and hardcode whatever k looks right once you've actually seen the curve.

## Next steps

- Once you have a few weeks of `snapshots` history, start building the
  breakout-prediction model (rank velocity/acceleration as features,
  cluster membership as an additional feature, label = "in top 20 in
  5 days")
- Consider pulling `tag.gettoptracks` for a specific genre tag you care
  about, in addition to the global chart, to narrow scope
- The `tags` table stores raw, ungrouped tag names too — worth keeping
  even after normalization, since you may want to revisit the vocabulary
  later without re-fetching from the API
