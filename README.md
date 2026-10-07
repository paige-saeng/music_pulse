# 🎵 Music Pulse

A daily-updating pipeline and dashboard that tracks what's trending on Last.fm, groups tracks into data-driven genre clusters, and predicts which tracks currently *outside* the top 20 are most likely to break into it within 5 days.

**Stack:** Python · SQLite · pandas · scikit-learn · LightGBM · Streamlit · Altair · cron

<!-- Add a dashboard screenshot here: ![dashboard](docs/dashboard.png) -->

## What it does

1. **Ingests daily.** A cron job pulls the Last.fm global and US top-50 charts and stores rank, playcount, and listeners as one snapshot per track per day (`UNIQUE(track_id, snapshot_date, source)`).
2. **Clusters by genre.** It fetches each track's user-applied tags, builds a vocabulary from the data itself, and runs k-means (k=4) to group tracks into genre clusters named after their top tags.
3. **Predicts breakouts.** From the rank history it engineers velocity, acceleration, and volatility features and trains a model to answer: *will a track currently outside the top 20 reach it within 5 days?*
4. **Shows it.** A Streamlit dashboard leads with the day's story (biggest riser, dominant sound, cross-chart overlap), then offers the chart, genre clusters, a per-track rank history, and the breakout candidates.

## Architecture

```
Last.fm API ──cron (daily)──> ingest.py ──> SQLite (tracks, snapshots, tags, clusters)
                                                │
                       breakout_features.py <───┤  gap-tolerant feature engineering
                                │               │
                 train_breakout_model.py        │
                                │               │
                     breakout_model.joblib      │
                                └──> dashboard.py (Streamlit) <──┘
```

## Results (honest version)

Trained on ~5 weeks of daily snapshots. Split **by date** (earlier dates train, latest 25% of dates test) so a track's later behavior can't leak into its earlier rows.

| Model | Test ROC-AUC | Breakout precision / recall |
|---|---|---|
| Logistic regression (median-imputed) | 0.964 | 0.75 / 0.50 |
| LightGBM (native NaN handling) | 0.917 | 0.55 / 0.92 |

Base rate in the test set is ~16% (12 breakouts out of 76 rows).

- **The simple model won on AUC.** With this little data, logistic regression is competitive with LightGBM. LightGBM catches more breakouts (higher recall) but with more false alarms.
- **The test set is small.** 76 rows and 12 positives means these numbers move a lot with one or two tracks. Treat them as directional, not precise.

## Decisions and pivots

This section shows how the project actually evolved, including what didn't work.

- **Spotify → Last.fm tags.** Spotify deprecated `audio-features` for new apps, so there was no path to numeric audio data. I switched to Last.fm's crowdsourced tags as the "sound" signal. Noisier, but free and accessible.
- **Hand-picked mood vocabulary → data-driven genre vocabulary.** The first design matched tracks against a fixed list (`chill`, `energetic`, `sad`). On real data, only 1 of ~70 tags matched. Most tags were genres or one-person noise. The vocabulary is now built from the data: tags appearing on 2+ tracks, top 40.
- **Choosing k = 4.** The elbow plot had no clear elbow, so I chose k for interpretability (each cluster reads as a recognizable genre group) rather than claiming the data dictated it.
- **Label leakage, found and fixed.** The label is "reaches rank ≤ 20 within 5 days." For a track *already* in the top 20 that is trivially true, so half my training rows were free wins and the first model's AUC (0.92) was partly inflated. I noticed the dashboard listing top-20 tracks as "breakout candidates," first patched it at display level, then fixed the root cause: the model now trains and is evaluated only on rows that *start* outside the top 20.
- **Gap-tolerant features.** The cron job only fires when my laptop is awake, so some days are missing. Feature lookups use the closest available day (±1 day tolerance) instead of assuming a perfect daily series, and rows with missing history keep NaN rather than being dropped.
- **Probabilities → High / Medium / Low.** Scores like 99% implied more precision than ~300 training rows can support, so the dashboard shows a coarse signal plus a caveat.

## Known limitations

- **Small data.** ~300 usable training rows, 12 test positives. The model is likely overconfident, especially for tracks with short chart histories (a track with 8 days on chart and falling can still score high).
- **Rank features only.** The model sees rank movement, not tags or cluster membership yet. Adding genre cluster as a feature is the obvious next step.
- **No automatic retraining.** The model is trained manually with `python train_breakout_model.py`; the dashboard scores with whatever model file exists.
- **Daily, not real-time.** The dashboard reads the SQLite database, so it updates once a day when the cron job runs.
- **Vocabulary noise.** The 2+ tracks filter isn't perfect; a noisy tag can occasionally slip into the vocabulary.

## Setup

```bash
conda create -n music_pulse python=3.11
conda activate music_pulse
pip install -r requirements.txt
```

Get a free Last.fm API key at https://www.last.fm/api/account/create and set it as an environment variable (never commit it):

```bash
export LASTFM_API_KEY=your_key_here
```

## Run

```bash
python ingest.py                 # pull today's charts, tags, and clusters
python breakout_features.py      # build breakout_features.csv from rank history
python train_breakout_model.py   # evaluate and save breakout_model.joblib
streamlit run dashboard.py       # open the dashboard
```

To run ingestion daily, add a cron entry (the laptop must be awake at that time):

```
0 12 * * * cd /path/to/music_pulse && LASTFM_API_KEY=... /path/to/env/bin/python ingest.py >> ingest_log.txt 2>&1
```

## Files

- `db.py`: SQLite schema and helpers
- `lastfm_client.py`: Last.fm API wrapper (charts, country charts, tags)
- `tag_features.py`: data-driven tag vocabulary and vectorization
- `clustering.py`, `choose_k.py`: k-means and elbow analysis
- `ingest.py`: the daily pipeline
- `data_summary.py`: quick data-quality summary
- `breakout_features.py`: velocity / acceleration / volatility features and labels
- `breakout_eda.ipynb`: exploratory analysis behind the modeling decisions
- `train_breakout_model.py`: date-split evaluation, then final model fit
- `dashboard.py`, `dashboard_data.py`: Streamlit UI and its queries

## Next steps

- Add genre cluster and tag features to the breakout model
- Weekly scheduled retraining and tracking of model performance over time
- Host the dashboard (needs a sample or hosted database, since `music_pulse.db` is gitignored)
- Revisit the model once there are several months of data
