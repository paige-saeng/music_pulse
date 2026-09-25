"""
Music Pulse dashboard -- Streamlit UI.

Reads directly from music_pulse.db, so every page load/refresh shows
whatever ingest.py's daily cron run last wrote. This is a daily-updating
dashboard, not a live-streaming one -- see README for that distinction.

Run with:
    streamlit run dashboard.py
"""

import streamlit as st
import altair as alt

import dashboard_data as dd

st.set_page_config(page_title="Music Pulse", page_icon="🎵", layout="wide")

st.title("🎵 Music Pulse")
st.caption("Daily trending-track tracking and genre clustering, built on Last.fm data.")

stats = dd.get_overall_stats()
if stats["total_days"] == 0:
    st.warning("No data yet -- run ingest.py at least once before using this dashboard.")
    st.stop()

available_dates = dd.get_available_dates()
selected_date = st.selectbox("Date", available_dates, index=0)

# --- Headline: the day's actual story, front and center ---
insights = dd.get_headline_insights(selected_date)

st.subheader(f"What happened on {selected_date}")

riser = insights["biggest_riser"]
cluster = insights["dominant_cluster"]
overlap = insights["both_charts_count"]

if riser:
    st.markdown(
        f"**Biggest riser:** {riser['artist']} — \"{riser['title']}\" "
        f"jumped from #{riser['from_rank']} to #{riser['to_rank']}."
    )
else:
    st.markdown("**Biggest riser:** not enough prior-day data yet to compare.")

if cluster:
    st.markdown(
        f"**Dominant sound today:** {cluster['label']} "
        f"({cluster['count']} of {cluster['total']} tracked tracks)."
    )

if overlap is not None:
    st.markdown(f"**Cross-chart overlap:** {overlap} tracks charted in both the global and US lists today.")

st.divider()

with st.expander("How this works: the approach behind this dashboard"):
    st.markdown(
"""
**Genre clustering (what you see above):** each day, tracks are pulled from Last.fm's
global and US trending charts. Since Last.fm's tags turned out to be overwhelmingly
genre-based rather than mood-based (an early assumption that didn't hold up against
real data), the clustering vocabulary is built directly from that day's most common
tags rather than a fixed list — then grouped with k-means into the clusters shown in
the Genre Clusters tab.

**Breakout prediction (in development, not yet shown live here):** a separate model
predicts whether a track will reach the top 20 within 5 days, based on its rank
trajectory — velocity, acceleration, and volatility computed from real accumulated
history (gap-tolerant, since some days were missed during initial setup). A logistic
regression baseline and a LightGBM model are trained on this data with a date-based
train/test split, so the model is only ever evaluated on *future* dates it hasn't
seen — not randomly held-out rows, which could leak a track's later trajectory into
training. The trained model is saved and used to score currently-tracked tracks —
see the Breakout Candidates tab. Note this reflects a single trained snapshot of
the model; it isn't automatically retrained as new daily data arrives, so
predictions will grow gradually more dated until it's retrained (rerun
train_breakout_model.py periodically).
"""
    )

st.divider()

# --- Pipeline stats: still available, but as a minor footnote, not the headline ---
with st.expander("Pipeline stats (days tracked, data volume)"):
    col1, col2, col3 = st.columns(3)
    col1.metric("Days tracked", stats["total_days"])
    col2.metric("Unique tracks seen", stats["total_unique_tracks"])
    col3.metric("Total snapshot rows", stats["total_snapshots"])

tab1, tab2, tab3, tab4 = st.tabs(["Today's Trending", "Genre Clusters", "Track History", "Breakout Candidates"])

# --- Tab 1: Trending tracks table ---
with tab1:
    source_filter = st.radio("Chart", ["Both", "Global", "US"], horizontal=True)
    source_map = {"Both": None, "Global": "lastfm_global", "US": "lastfm_us"}

    top_tracks = dd.get_top_tracks_for_date(selected_date, source=source_map[source_filter], limit=50)
    if top_tracks.empty:
        st.info("No tracks found for this date/filter combination.")
    else:
        st.dataframe(
            top_tracks.rename(columns={
                "rank": "Rank", "artist": "Artist", "title": "Title", "source": "Chart"
            }),
            hide_index=True,
            width='stretch',
        )

# --- Tab 2: Genre cluster breakdown ---
with tab2:
    summary, detail = dd.get_cluster_summary_for_date(selected_date)
    if summary.empty:
        st.info("No cluster data available for this date.")
    else:
        chart = alt.Chart(summary).mark_bar().encode(
            x=alt.X("cluster_label:N", title="Cluster", sort="-y"),
            y=alt.Y("track_count:Q", title="Number of tracks"),
            tooltip=["cluster_label", "track_count"],
        ).properties(height=350)
        st.altair_chart(chart, width='stretch')

        st.subheader("Tracks by cluster")
        for _, row in summary.iterrows():
            with st.expander(f"{row['cluster_label']} ({row['track_count']} tracks)"):
                cluster_tracks = detail[detail["cluster_id"] == row["cluster_id"]]
                st.dataframe(
                    cluster_tracks[["artist", "title"]].rename(
                        columns={"artist": "Artist", "title": "Title"}
                    ),
                    hide_index=True,
                    width='stretch',
                )

# --- Tab 3: Individual track history ---
with tab3:
    search_query = st.text_input("Search for a track (by artist or title)")
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
                chart = alt.Chart(history).mark_line(point=True).encode(
                    x=alt.X("snapshot_date:T", title="Date"),
                    y=alt.Y("rank:Q", title="Rank", scale=alt.Scale(reverse=True)),  # reversed: rank 1 at top
                    color="source:N",
                    tooltip=["snapshot_date:T", "rank:Q", "source:N"],
                ).properties(height=350)
                st.altair_chart(chart, width='stretch')
    else:
        st.caption("Enter an artist or track name above to see its rank history over time.")

# --- Tab 4: Breakout predictions from the saved model ---
with tab4:
    st.caption(
        "Tracks currently trending, ranked by the model's predicted probability "
        "of reaching the top 20 within 5 days."
    )
    candidates, error = dd.get_breakout_candidates()
    if error:
        st.info(error)
    elif candidates.empty:
        st.info("No candidates to show.")
    else:
        display_df = candidates.rename(columns={
            "artist": "Artist", "title": "Title",
            "current_rank": "Current Rank", "breakout_probability": "Breakout Probability",
        })
        st.dataframe(
            display_df,
            column_config={
                "Breakout Probability": st.column_config.ProgressColumn(
                    "Breakout Probability", min_value=0, max_value=1, format="%.0f%%"
                )
            },
            hide_index=True,
            width='stretch',
        )
