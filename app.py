# NBA Game Momentum Visualizer — Web App
# ---------------------------------------
# Run with:  streamlit run app.py
# Reuses all data + chart logic from main.py; only the UI layer is new.

import streamlit as st
import pandas as pd

# Import the existing pipeline — nothing in main.py runs on import
# because main() is guarded by `if __name__ == "__main__"`.
from main import (
    fetch_teams,
    fetch_completed_games,
    fetch_game_data,
    build_team_map,
    parse_plays,
    compute_momentum,
    find_top_swings,
    plot_momentum,
)

st.set_page_config(page_title="NBA Game Momentum Visualizer", layout="wide")
st.title("NBA Game Momentum Visualizer")

# --- Cached wrappers so we don't re-hit ESPN on every interaction ---
# Streamlit reruns the whole script on each click; caching makes that cheap.

@st.cache_data(ttl=3600, show_spinner="Loading teams...")
def get_teams():
    return fetch_teams()

@st.cache_data(ttl=600, show_spinner="Loading schedule...")
def get_games(team_id, season):
    return fetch_completed_games(team_id, season)

@st.cache_data(ttl=3600, show_spinner="Loading play-by-play...")
def get_game_df(game_id):
    raw = fetch_game_data(game_id)
    header = raw.get("header", {})
    team_map = build_team_map(header)

    competitions = header.get("competitions", [{}])
    competitors = competitions[0].get("competitors", [])
    home_name, away_name = "Home", "Away"
    for c in competitors:
        name = c.get("team", {}).get("displayName", "")
        if c.get("homeAway") == "home":
            home_name = name
        else:
            away_name = name

    rows = parse_plays(raw.get("plays", []), team_map)
    if not rows:
        return None, home_name, away_name

    df = compute_momentum(pd.DataFrame(rows))
    return df, home_name, away_name

# --- Sidebar: the three choices that used to be input() prompts ---

with st.sidebar:
    st.header("Pick a game")

    teams = get_teams()
    team = st.selectbox(
        "Team",
        teams,
        format_func=lambda t: f"{t['abbr']} — {t['name']}",
    )

    season = st.selectbox(
        "Season",
        [None] + list(range(2026, 2002, -1)),
        index=1,   # default to the most recent completed season
        format_func=lambda s: "Current" if s is None else f"{s - 1}–{str(s)[2:]}",
    )

    games = get_games(team["id"], season)

    if not games:
        st.warning("No completed games found for that team/season. Try another season.")
        st.stop()

    st.caption(f"{len(games)} completed games — scroll the list below")
    with st.container(height=320):
        game = st.radio(
            "Game",
            games,
            format_func=lambda g: f"{g['date']}  {g['name']}  ({g['score']})",
            label_visibility="collapsed",
        )

# --- Main panel: summary + chart ---

df, home_name, away_name = get_game_df(game["id"])

if df is None or df.empty:
    st.error("No play data found for this game.")
    st.stop()

final_home = int(df["homeScore"].iloc[-1])
final_away = int(df["awayScore"].iloc[-1])

col1, col2, col3 = st.columns(3)
col1.metric(f"{home_name} (home)", final_home)
col2.metric(f"{away_name} (away)", final_away)
col3.metric("Total plays", len(df))

top_swings = find_top_swings(df, n=5)
fig = plot_momentum(df, top_swings, home_name=home_name, away_name=away_name)
st.plotly_chart(fig, width="stretch")

with st.expander("Top 5 momentum swings"):
    for i, (_, row) in enumerate(top_swings.iterrows(), 1):
        swing_val = int(row["swing"]) if pd.notna(row["swing"]) else 0
        st.write(f"{i}. **[{row['team']}]** {row['text']}  (swing: +{swing_val})")

st.download_button(
    "Download play-by-play CSV",
    df.to_csv(index=False),
    file_name=f"play_by_play_{game['id']}.csv",
    mime="text/csv",
)