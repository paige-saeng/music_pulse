"""
Music Pulse dashboard -- Streamlit UI.

Reads directly from music_pulse.db, so every page load/refresh shows
whatever ingest.py's daily cron run last wrote. This is a daily-updating
dashboard, not a live-streaming one -- see README for that distinction.

Run with:
    streamlit run dashboard.py
"""

from html import escape

import streamlit as st
import altair as alt

import dashboard_data as dd

st.set_page_config(page_title="Music Pulse", page_icon="🎵", layout="wide")

# ---------------------------------------------------------------------------
# Look and feel: Spotify-style dark surfaces + green accent.
# Colors live in one place (CSS variables / the constants below).
# ---------------------------------------------------------------------------
GREEN = "#18A94D"        # chart green (validated against the dark surface)
BLUE = "#4A90E2"         # second series
MUTED = "#B3B3B3"
GRID = "#2A2A2A"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800&display=swap');

:root {
  --bg: #121212;
  --card: #181818;
  --card-hover: #242424;
  --line: #2a2a2a;
  --text: #ffffff;
  --muted: #b3b3b3;
  --green: #1ed760;
}

html, body, [class*="css"], .stApp, button, input, textarea {
  font-family: 'Figtree', 'Helvetica Neue', Arial, sans-serif !important;
}
.stApp { background: var(--bg); }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1120px; padding-top: 2.5rem; padding-bottom: 4rem; }

/* ---- page title ---- */
.mp-title { font-size: 2.6rem; font-weight: 800; letter-spacing: -0.03em; margin: 0; line-height: 1.1; }
.mp-title span { color: var(--green); }
.mp-sub { color: var(--muted); margin: 0.35rem 0 1.5rem 0; font-size: 1rem; }

/* ---- hero + stat tiles ---- */
.mp-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-bottom: 8px; }
.mp-side { display: grid; grid-template-rows: 1fr 1fr; gap: 16px; }
@media (max-width: 800px) { .mp-grid { grid-template-columns: 1fr; } }

.mp-hero {
  background: linear-gradient(155deg, #1f8f4a 0%, #14532d 48%, #181818 100%);
  border-radius: 16px; padding: 28px 30px; min-height: 230px;
  display: flex; flex-direction: column; justify-content: flex-end;
}
.mp-hero .kicker { font-size: 0.95rem; font-weight: 600; color: #e8f5ec; margin-bottom: 6px; }
.mp-hero .big { font-size: 2.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.08; color: #fff; }
.mp-hero .by { font-size: 1.1rem; color: #e8f5ec; margin-top: 4px; }
.mp-hero .move { margin-top: 18px; font-size: 1.15rem; font-weight: 700; color: #fff; }
.mp-hero .move em { font-style: normal; opacity: .75; font-weight: 600; margin: 0 8px; }

.mp-tile { background: var(--card); border-radius: 16px; padding: 20px 22px;
  display: flex; flex-direction: column; justify-content: center; }
.mp-tile .label { color: var(--muted); font-size: 0.9rem; font-weight: 500; }
.mp-tile .val { font-size: 1.7rem; font-weight: 800; letter-spacing: -0.02em; margin-top: 2px; line-height: 1.15; }
.mp-tile .note { color: var(--muted); font-size: 0.9rem; margin-top: 2px; }

/* ---- methodology + stats ---- */
.mp-h2 { font-size: 1.3rem; font-weight: 700; letter-spacing: -0.01em; margin: 2rem 0 0.4rem 0; }
.mp-intro { color: var(--muted); margin: 0 0 1rem 0; max-width: 75ch; }
.mp-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 8px; }
.mp-stat { background: var(--card); border-radius: 16px; padding: 16px 22px; }
.mp-stat .n { font-size: 1.9rem; font-weight: 800; letter-spacing: -0.02em; line-height: 1.1; }
.mp-stat .l { color: var(--muted); font-size: 0.9rem; }
.mp-flow { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 20px 0 16px 0; }
.mp-flow span { background: #2a2a2a; border-radius: 999px; padding: 6px 14px; font-weight: 600; font-size: 0.9rem; }
.mp-flow i { color: var(--muted); font-style: normal; }
.mp-stage { display: grid; grid-template-columns: 220px 1fr; gap: 28px; background: var(--card);
  border-radius: 16px; padding: 22px 26px; margin-bottom: 12px; }
@media (max-width: 800px) { .mp-stage { grid-template-columns: 1fr; gap: 10px; } }
.mp-stage .name { font-size: 1.1rem; font-weight: 700; }
.mp-stage .tools { color: var(--muted); font-size: 0.85rem; margin-top: 4px; }
.mp-stage .lead { font-size: 1rem; font-weight: 600; line-height: 1.45; margin: 0 0 10px 0; max-width: 75ch; }
.mp-stage ul { margin: 0; padding-left: 1.1rem; color: #d9d9d9; font-size: 0.92rem; line-height: 1.55; max-width: 78ch; }
.mp-stage li { margin-bottom: 6px; }
.mp-stage li b { color: #fff; font-weight: 600; }
.mp-stage code { background: #2a2a2a; padding: 1px 6px; border-radius: 4px; font-size: 0.85em; }

/* ---- tabs as Spotify-style chips ---- */
.stTabs [role="tablist"] { gap: 8px !important; border: 0 !important; border-bottom: 0 !important; box-shadow: none !important; margin-top: 18px; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"],
.stTabs [role="tablist"] > :not([role="tab"]) { display: none !important; height: 0 !important; }
.stTabs [role="tablist"], .stTabs [role="tablist"] + div, [data-testid="stTabs"] > div:first-child { border-bottom: 0 !important; box-shadow: none !important; }
.stTabs [role="tab"] {
  background: #2a2a2a !important; color: #fff !important; border-radius: 999px !important;
  height: 36px !important; padding: 0 18px !important; font-weight: 600; border: 0 !important;
}
.stTabs [class*="SelectionIndicator"] { display: none !important; }
.stTabs [role="tablist"]::after, .stTabs [role="tablist"]::before { display: none !important; content: none !important; }
.stTabs [role="tab"] p { font-size: 0.92rem; font-weight: 600; color: inherit !important; }
.stTabs [role="tab"]:hover { background: #333 !important; }
.stTabs [role="tab"][aria-selected="true"] { background: #fff !important; color: #000 !important; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 1.1rem; }

/* ---- track rows ---- */
.mp-list { background: transparent; max-height: 640px; overflow-y: auto; padding-right: 4px; }
.mp-row { display: grid; grid-template-columns: 44px 1fr auto; align-items: center; gap: 12px;
  padding: 9px 12px; border-radius: 8px; }
.mp-row:hover { background: var(--card-hover); }
.mp-rank { color: var(--muted); font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }
.mp-name { font-weight: 600; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mp-artist { color: var(--muted); font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mp-meta { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.88rem; }
.mp-chip { border: 1px solid #3a3a3a; color: var(--muted); border-radius: 999px; padding: 2px 10px; font-size: 0.78rem; }
.mp-up { color: var(--green); font-weight: 700; }
.mp-down { color: var(--muted); font-weight: 700; }
.mp-pill { border-radius: 999px; padding: 3px 12px; font-size: 0.82rem; font-weight: 700; min-width: 64px; text-align: center; }
.mp-pill.high { background: var(--green); color: #000; }
.mp-pill.medium { background: transparent; color: var(--green); border: 1px solid var(--green); }
.mp-pill.low { background: #2a2a2a; color: var(--muted); }

/* ---- genre bars ---- */
.mp-bar-row { display: grid; grid-template-columns: minmax(120px, 1fr) 3fr 40px; gap: 14px; align-items: center; padding: 8px 0; }
.mp-bar-label { font-weight: 600; }
.mp-bar-track { background: #232323; border-radius: 4px 4px 4px 4px; height: 10px; }
.mp-bar-fill { background: var(--green); height: 10px; border-radius: 0 4px 4px 0; }
.mp-bar-count { color: var(--muted); text-align: right; font-variant-numeric: tabular-nums; }

/* ---- misc ---- */
.mp-section { font-size: 1.3rem; font-weight: 700; letter-spacing: -0.01em; margin: 0.4rem 0 0.6rem 0; }
.mp-note { color: var(--muted); font-size: 0.88rem; margin-top: 14px; max-width: 70ch; }
[data-testid="stExpander"] { background: var(--card); border: 0; border-radius: 12px; }
[data-testid="stExpander"] summary { font-weight: 600; }
.stSelectbox label, .stRadio label, .stTextInput label { color: var(--muted) !important; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Small HTML helpers. Everything that comes from the database is escaped.
# ---------------------------------------------------------------------------
SOURCE_LABELS = {"lastfm_global": "Global", "lastfm_us": "US"}


def track_rows_html(rows):
    """rows: iterable of dicts with rank, title, artist, and optional meta_html."""
    out = ['<div class="mp-list">']
    for r in rows:
        out.append(
            '<div class="mp-row">'
            f'<div class="mp-rank">{escape(str(r["rank"]))}</div>'
            f'<div style="min-width:0"><div class="mp-name">{escape(str(r["title"]))}</div>'
            f'<div class="mp-artist">{escape(str(r["artist"]))}</div></div>'
            f'<div class="mp-meta">{r.get("meta_html", "")}</div>'
            "</div>"
        )
    out.append("</div>")
    return "".join(out)


def style_chart(chart):
    return (
        chart.configure(background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(
            gridColor=GRID, domain=False, tickColor=GRID,
            labelColor=MUTED, titleColor=MUTED, labelFontSize=12, titleFontSize=12,
        )
        .configure_legend(labelColor="#ffffff", titleColor=MUTED, orient="top", symbolType="stroke")
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    '<h1 class="mp-title">Music <span>Pulse</span></h1>'
    '<p class="mp-sub">What\'s trending on Last.fm today, which sounds it belongs to, '
    "and which tracks look ready to break into the top 20.</p>",
    unsafe_allow_html=True,
)

stats = dd.get_overall_stats()
if stats["total_days"] == 0:
    st.warning("No data yet -- run ingest.py at least once before using this dashboard.")
    st.stop()

available_dates = dd.get_available_dates()
selected_date = st.selectbox("Date", available_dates, index=0)

# ---------------------------------------------------------------------------
# Headline: the day's story -- one hero card + two supporting tiles
# ---------------------------------------------------------------------------
insights = dd.get_headline_insights(selected_date)
riser = insights["biggest_riser"]
cluster = insights["dominant_cluster"]
overlap = insights["both_charts_count"]

if riser:
    hero = (
        '<div class="mp-hero">'
        '<div class="kicker">Biggest riser</div>'
        f'<div class="big">{escape(str(riser["title"]))}</div>'
        f'<div class="by">{escape(str(riser["artist"]))}</div>'
        f'<div class="move">#{riser["from_rank"]}<em>to</em>#{riser["to_rank"]}</div>'
        "</div>"
    )
else:
    hero = (
        '<div class="mp-hero"><div class="kicker">Biggest riser</div>'
        '<div class="big">Not enough history yet</div>'
        '<div class="by">Needs a prior day to compare against.</div></div>'
    )

if cluster:
    sound_tile = (
        '<div class="mp-tile"><div class="label">Dominant sound</div>'
        f'<div class="val">{escape(str(cluster["label"]))}</div>'
        f'<div class="note">{cluster["count"]} of {cluster["total"]} songs with tags</div></div>'
    )
else:
    sound_tile = '<div class="mp-tile"><div class="label">Dominant sound</div><div class="val">-</div></div>'

overlap_tile = (
    '<div class="mp-tile"><div class="label">On both charts</div>'
    f'<div class="val">{overlap if overlap is not None else "-"} tracks</div>'
    '<div class="note">Charting in both the global and US lists</div></div>'
)

st.markdown(
    f'<div class="mp-grid">{hero}<div class="mp-side">{sound_tile}{overlap_tile}</div></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Methodology (homepage): data engineering first, then the modeling
# ---------------------------------------------------------------------------
def stage(name, tools, lead, bullets):
    items = "".join(f"<li>{b}</li>" for b in bullets)
    return (
        '<div class="mp-stage"><div>'
        f'<div class="name">{name}</div><div class="tools">{tools}</div></div>'
        f'<div><p class="lead">{lead}</p><ul>{items}</ul></div></div>'
    )


METHOD_STAGES = [
    stage(
        "1. Collection", "Last.fm API, requests, cron",
        "Every day a scheduled job pulls the top 50 songs from two Last.fm charts and saves where each one ranked.",
        [
            "<b>Two sources.</b> The global chart (<code>chart.gettoptracks</code>) and the US chart "
            "(<code>geo.gettoptracks</code>). Songs on both lists count once as a song but keep a row per chart, "
            "so about 60 distinct songs make up roughly 100 entries a day.",
            "<b>One record format.</b> Responses are normalized into artist, title, rank (from list position), "
            "playcount and listeners, so every later step reads the same shape.",
            "<b>Careful API use.</b> The key lives in an environment variable and never in the code or repo. "
            "Requests time out after 10 seconds, HTTP errors raise instead of passing silently, and calls are spaced 0.25 seconds apart.",
            "<b>Known limit.</b> The job runs from cron on my laptop, so it only fires when the laptop is awake. "
            "That created gaps in the history (see below).",
        ],
    ),
    stage(
        "2. Storage", "SQLite",
        "Everything lands in a small relational database built so that re-running a day never creates duplicates.",
        [
            "<b>Four tables.</b> <code>tracks</code> (one row per artist and title), <code>snapshots</code> "
            "(one row per song, chart and day), <code>tags</code> and <code>clusters</code>.",
            "<b>Idempotent writes.</b> A uniqueness constraint on song, date and chart plus insert-or-replace means "
            "a second run on the same day overwrites instead of duplicating. Tags are replaced as a set each run, "
            "and cluster assignments are keyed by song and run date so every day's grouping is kept.",
            "<b>Raw first.</b> Only raw daily snapshots are stored. Features and labels are rebuilt from them on demand, "
            "so a change to a feature definition never requires re-collecting data.",
        ],
    ),
    stage(
        "3. Tags", "Last.fm track.gettoptags",
        "A song's sound comes from the tags listeners give it, because Spotify's audio features are closed to new apps.",
        [
            "<b>One request per distinct song</b>, deduplicated across both charts, with Last.fm's autocorrect on so "
            "spelling variants of an artist or title resolve to the same track.",
            "<b>Weighted tags.</b> Each tag carries a relative weight from Last.fm. Names are lowercased and trimmed before storing.",
            "<b>API quirks handled.</b> A single tag comes back as an object instead of a list, counts can be missing or "
            "malformed, and new releases often return no tags at all.",
        ],
    ),
    stage(
        "4. Genre groups", "pandas, NumPy, scikit-learn",
        "Songs are grouped by how similar their tags are, using a vocabulary built from the data itself.",
        [
            "<b>Vocabulary from the data.</b> Count how many different songs use each tag, keep tags used by at least 2 songs "
            "(this removes one-off noise like usernames and memes), and take the top 40. My first attempt used a hand-picked "
            "mood list, and it matched only 1 of about 70 real tags, so I replaced it.",
            "<b>Feature vectors.</b> Each song becomes 40 numbers, its weight on each vocabulary tag, scaled to sum to 1 "
            "so heavily tagged songs don't dominate.",
            "<b>Clustering.</b> k-means with k=4 and a fixed random seed. The elbow plot had no clear elbow (inertia fell "
            "roughly linearly), so I picked k for interpretability. Each group is named after the three heaviest tags in its center.",
            "<b>Untagged songs</b> are counted and reported separately instead of being forced into a group.",
        ],
    ),
    stage(
        "5. Breakout model", "pandas, scikit-learn, LightGBM",
        "A model estimates which songs ranked 21st or lower will reach the top 20 within 5 days.",
        [
            "<b>Features</b> for each song and day: best rank across both charts, rank change over 1, 3 and 7 days, "
            "acceleration, 14-day volatility, days on the chart and number of charts.",
            "<b>Label.</b> Reached rank 20 or better within 5 days (give or take 1 day). Rows without enough future data stay "
            "unlabeled instead of being counted as a miss.",
            "<b>Evaluation.</b> Train on earlier dates, test on later ones, so a song's future never leaks into its past. "
            "Logistic regression is the baseline; LightGBM handles missing values natively.",
            "<b>Result.</b> Test ROC-AUC of 0.92 for LightGBM and 0.96 for logistic regression, on 76 held-out rows with "
            "12 breakouts. That sample is too small to trust past the first decimal, so read it as a ranking, not exact odds.",
        ],
    ),
    stage(
        "6. Dashboard", "Streamlit, Altair",
        "The app reads the database directly, so each daily run appears on the next page load.",
        [
            "<b>Model scores</b> come from a saved model file that I retrain by hand, so they drift out of date until it is rerun.",
            "<b>Safe rendering.</b> Anything that comes from the database is HTML-escaped before it is displayed.",
        ],
    ),
]

METHOD_PROBLEMS = stage(
    "Problems along the way", "What broke and what I changed",
    "The pipeline looked fine until the data showed otherwise. These are the problems that mattered most.",
    [
        "<b>Missing days.</b> In the first month, 18 of 36 calendar days had no data because the laptop was asleep when the job "
        "was due. Feature lookups now use the nearest available day within a tolerance window and leave a blank when none "
        "exists, instead of assuming an unbroken daily series.",
        "<b>Label leakage.</b> My first model treated songs already in the top 20 as breakouts, which inflated its score. "
        "It now trains and is judged only on songs that start outside the top 20.",
        "<b>Silent data loss.</b> Roughly 1 in 5 charting songs had no tags and was being dropped from the genre counts "
        "without any warning. They are now tracked and called out on the Genres tab.",
        "<b>A vocabulary that didn't fit.</b> The fixed mood list failed on real tags, which led to the data-driven vocabulary above.",
        "<b>Scale.</b> About a month of data and roughly 300 training rows. Everything is reported as directional, and the model "
        "should be rechecked as history grows.",
    ],
)

st.markdown(
    '<div class="mp-h2">Methodology</div>'
    '<p class="mp-intro">How the data is collected, stored, grouped and modeled, built on the Last.fm API.</p>'
    '<div class="mp-stats">'
    f'<div class="mp-stat"><div class="n">{stats["total_days"]:,}</div><div class="l">days of data collected</div></div>'
    f'<div class="mp-stat"><div class="n">{stats["total_unique_tracks"]:,}</div><div class="l">different songs tracked</div></div>'
    f'<div class="mp-stat"><div class="n">{stats["total_snapshots"]:,}</div><div class="l">daily chart entries saved</div></div>'
    '</div>'
    '<div class="mp-flow"><span>Last.fm API</span><i>›</i><span>Python and cron</span><i>›</i>'
    '<span>SQLite</span><i>›</i><span>scikit-learn, LightGBM</span><i>›</i><span>Streamlit</span></div>'
    + "".join(METHOD_STAGES) + METHOD_PROBLEMS,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["Trending", "Genres", "Track history", "Breakout watch"])

# --- Tab 1: today's chart as a track list ---
with tab1:
    source_filter = st.radio("Chart", ["Both", "Global", "US"], horizontal=True)
    source_map = {"Both": None, "Global": "lastfm_global", "US": "lastfm_us"}

    top_tracks = dd.get_top_tracks_for_date(selected_date, source=source_map[source_filter], limit=50)
    if top_tracks.empty:
        st.info("No tracks found for this date and chart.")
    else:
        rows = [
            {
                "rank": r["rank"], "title": r["title"], "artist": r["artist"],
                "meta_html": f'<span class="mp-chip">{escape(SOURCE_LABELS.get(r["source"], str(r["source"])))}</span>',
            }
            for _, r in top_tracks.iterrows()
        ]
        st.markdown(track_rows_html(rows), unsafe_allow_html=True)

# --- Tab 2: genre clusters ---
with tab2:
    summary, detail = dd.get_cluster_summary_for_date(selected_date)
    # Songs Last.fm hasn't tagged yet are stored as group 99. They aren't a genre,
    # so keep them out of the chart and mention them in a footnote instead.
    untagged_count = int(summary.loc[summary["cluster_id"] == 99, "track_count"].sum())
    summary = summary[summary["cluster_id"] != 99]
    if summary.empty:
        st.info("No genre data for this date.")
    else:
        summary = summary.sort_values("track_count", ascending=False)
        top = max(int(summary["track_count"].max()), 1)
        bars = []
        for _, r in summary.iterrows():
            pct = 100 * int(r["track_count"]) / top
            bars.append(
                '<div class="mp-bar-row">'
                f'<div class="mp-bar-label">{escape(str(r["cluster_label"]))}</div>'
                f'<div class="mp-bar-track"><div class="mp-bar-fill" style="width:{pct:.0f}%"></div></div>'
                f'<div class="mp-bar-count">{int(r["track_count"])}</div></div>'
            )
        st.markdown('<div class="mp-section">Tracks per genre group</div>' + "".join(bars), unsafe_allow_html=True)

        st.markdown('<div class="mp-section" style="margin-top:1.4rem">Browse by group</div>', unsafe_allow_html=True)
        for _, row in summary.iterrows():
            with st.expander(f"{row['cluster_label']} ({row['track_count']} tracks)"):
                cluster_tracks = detail[detail["cluster_id"] == row["cluster_id"]].reset_index(drop=True)
                st.markdown(
                    track_rows_html(
                        [{"rank": i + 1, "title": t["title"], "artist": t["artist"]}
                         for i, t in cluster_tracks.iterrows()]
                    ),
                    unsafe_allow_html=True,
                )

        if untagged_count:
            st.markdown(
                f'<div class="mp-note">{untagged_count} more songs charted on this date but aren\'t shown here '
                "because Last.fm hasn't tagged them yet (mostly new releases).</div>",
                unsafe_allow_html=True,
            )

# --- Tab 3: individual track history ---
with tab3:
    search_query = st.text_input("Search for a track by artist or title")
    if search_query:
        results = dd.search_tracks(search_query)
        if results.empty:
            st.info("No matching tracks found.")
        else:
            results["label"] = results["artist"] + " — " + results["title"]
            choice = st.selectbox("Select a track", results["label"])
            chosen_id = results[results["label"] == choice]["track_id"].iloc[0]

            history = dd.get_track_history(chosen_id)
            if history.empty:
                st.info("No history found for this track.")
            else:
                history = history.copy()
                history["Chart"] = history["source"].map(SOURCE_LABELS).fillna(history["source"])
                chart = alt.Chart(history).mark_line(point=alt.OverlayMarkDef(size=60, filled=True), strokeWidth=2).encode(
                    x=alt.X("snapshot_date:T", title=None),
                    y=alt.Y("rank:Q", title="Rank (1 is the top)", scale=alt.Scale(reverse=True)),
                    color=alt.Color(
                        "Chart:N", title=None,
                        scale=alt.Scale(domain=["Global", "US"], range=[GREEN, BLUE]),
                    ),
                    strokeDash=alt.StrokeDash(
                        "Chart:N", title=None,
                        scale=alt.Scale(domain=["Global", "US"], range=[[1, 0], [6, 4]]),
                    ),
                    tooltip=["snapshot_date:T", "rank:Q", "Chart:N"],
                ).properties(height=340)
                st.altair_chart(style_chart(chart), width="stretch")
    else:
        st.caption("Search for a track above to see how its rank has moved day by day.")

# --- Tab 4: breakout predictions from the saved model ---
with tab4:
    st.markdown(
        '<div class="mp-section">Tracks outside the top 20 that look ready to break in</div>'
        '<div class="mp-sub" style="margin:0 0 .8rem 0">Ranked by the model\'s estimated chance of '
        "reaching the top 20 within 5 days.</div>",
        unsafe_allow_html=True,
    )
    candidates, error = dd.get_breakout_candidates()
    if error:
        st.info(error)
    elif candidates.empty:
        st.info("No candidates to show.")
    else:
        def signal(p):
            return "High" if p >= 70 else "Medium" if p >= 40 else "Low"

        rows = []
        for _, r in candidates.iterrows():
            climbed = r["spots_climbed_3d"]
            if climbed != climbed:  # NaN: not enough history for a 3-day change
                move = '<span class="mp-down">-</span>'
            elif climbed >= 0:
                move = f'<span class="mp-up">▲ {climbed:.0f}</span> in 3 days'
            else:
                move = f'<span class="mp-down">▼ {abs(climbed):.0f}</span> in 3 days'
            sig = signal(r["breakout_probability"])
            rows.append({
                "rank": int(r["current_rank"]), "title": r["title"], "artist": r["artist"],
                "meta_html": (
                    f"<span>{move}</span>"
                    f'<span>{int(r["days_tracked_so_far"])} days on chart</span>'
                    f'<span class="mp-pill {sig.lower()}">{sig}</span>'
                ),
            })
        st.markdown(track_rows_html(rows), unsafe_allow_html=True)
        st.markdown(
            '<div class="mp-note">The number on the left is the track\'s current rank. '
            "High means a model score of 70% or more, Medium 40-70%, Low under 40%. "
            "The model learned from about 300 examples, so read this as a ranking of who looks "
            "most likely to break in, not exact odds. Tracks with short chart histories "
            "(under about 10 days) can score higher than they should.</div>",
            unsafe_allow_html=True,
        )
