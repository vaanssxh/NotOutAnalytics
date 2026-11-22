"""
IPL Sports Analytics Dashboard
Professional Streamlit dashboard for cricket statistical analysis.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
from pathlib import Path
import sys
import logging

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.statistics.data_access import (
    get_connection,
    get_batter_career,
    get_batter_season,
    get_bowler_career,
    get_bowler_season,
    get_batter_innings,
    get_bowler_innings,
    get_player_innings,
    get_league_boundary_stats,
    get_batter_career_balls_boundaries,
    get_all_batter_innings_strike_rates,
    get_career_halves_strike_rate,
    get_player_comparison_data,
    get_league_strike_rate_distribution,
    get_top_batters_by_strike_rate,
    get_boundary_rate_by_player,
    validate_database,
)
from src.statistics.mean_median import MeanMedianAnalyzer
from src.statistics.hypothesis_testing import HypothesisTester
from src.statistics.bootstrap_ci import BootstrapCI
from src.statistics.regression_to_mean import RegressionToMean
from src.statistics.beta_binomial import BetaBinomialShrinkage
from src.statistics.multiple_comparisons import MultipleComparisons
from src.statistics.player_comparison import PlayerComparisonTool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="IPL Sports Analytics",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for dark navy/charcoal theme with green accents
st.markdown("""
<style>
    /* Main theme colors */
    :root {
        --bg-primary: #0d1117;
        --bg-secondary: #161b22;
        --bg-tertiary: #21262d;
        --border-color: #30363d;
        --text-primary: #e6edf3;
        --text-secondary: #8b949e;
        --accent-green: #3fb950;
        --accent-green-dim: #238636;
        --accent-blue: #58a6ff;
        --accent-red: #f85149;
        --accent-yellow: #d29922;
    }

    /* Override Streamlit defaults */
    .stApp {
        background-color: var(--bg-primary);
        color: var(--text-primary);
    }

    .stSidebar {
        background-color: var(--bg-secondary);
        border-right: 1px solid var(--border-color);
    }

    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
    }

    /* Metrics */
    [data-testid="metric-container"] {
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-color);
        padding: 1rem;
        border-radius: 0.5rem;
    }

    [data-testid="metric-container"] > div {
        color: var(--text-primary) !important;
    }

    /* Buttons */
    .stButton > button {
        background-color: var(--accent-green);
        color: white;
        border: none;
        border-radius: 0.375rem;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: background-color 0.2s;
    }

    .stButton > button:hover {
        background-color: var(--accent-green-dim);
    }

    .stButton > button[kind="secondary"] {
        background-color: var(--bg-tertiary);
        color: var(--text-primary);
        border: 1px solid var(--border-color);
    }

    /* Selectbox, multiselect */
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        background-color: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        color: var(--text-primary);
    }

    /* Input fields */
    .stNumberInput > div > div > input,
    .stTextInput > div > div > input {
        background-color: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        color: var(--text-primary);
    }

    /* Slider */
    .stSlider > div > div > div > div {
        background-color: var(--accent-green);
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background-color: var(--bg-secondary);
        padding: 0.5rem;
        border-radius: 0.5rem;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: var(--text-secondary);
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.375rem;
    }

    .stTabs [aria-selected="true"] {
        background-color: var(--accent-green) !important;
        color: white !important;
    }

    /* Expander */
    .stExpander {
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 0.5rem;
    }

    .stExpander > details > summary {
        color: var(--text-primary);
    }

    /* Dataframe */
    .stDataFrame {
        background-color: var(--bg-secondary);
    }

    /* Plotly charts container */
    .js-plotly-plot {
        background-color: var(--bg-secondary) !important;
    }

    /* Info/Success/Warning/Error boxes */
    .stAlert {
        border-radius: 0.5rem;
    }

    /* Custom card */
    .stat-card {
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 0.5rem;
    }

    .stat-card h4 {
        margin: 0 0 0.5rem 0;
        color: var(--accent-green);
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .stat-card .value {
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--text-primary);
    }

    /* Loading spinner */
    .stSpinner > div {
        border-top-color: var(--accent-green) !important;
    }

    /* Hide default Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ============================================================
# Utility Functions
# ============================================================

@st.cache_data(ttl=3600)
def load_batter_career(min_balls: int = 200) -> pd.DataFrame:
    """Load career batting stats with caching."""
    try:
        return get_batter_career(min_balls)
    except Exception as e:
        logger.error(f"Error loading batter career: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_batter_season(min_balls: int = 100) -> pd.DataFrame:
    """Load season batting stats with caching."""
    try:
        return get_batter_season(min_balls)
    except Exception as e:
        logger.error(f"Error loading batter season: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_bowler_career(min_balls: int = 100) -> pd.DataFrame:
    """Load career bowling stats with caching."""
    try:
        return get_bowler_career(min_balls)
    except Exception as e:
        logger.error(f"Error loading bowler career: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_all_players() -> list:
    """Load all player names for dropdown."""
    try:
        df = get_batter_career(min_balls=1)
        return sorted(df['player_name'].unique().tolist())
    except Exception as e:
        logger.error(f"Error loading players: {e}")
        return []


@st.cache_data(ttl=3600)
def load_seasons() -> list:
    """Load all seasons for dropdown."""
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT season_name FROM seasons ORDER BY season_name", conn)
        conn.close()
        return df['season_name'].tolist()
    except Exception as e:
        logger.error(f"Error loading seasons: {e}")
        return []


def get_player_summary(player_name: str, min_balls: int = 10) -> dict:
    """Get comprehensive player summary."""
    try:
        bat_innings = get_batter_innings(player_name, min_balls=min_balls)
        career = get_batter_career(min_balls=1).query(f"player_name == '{player_name}'")

        if len(career) == 0:
            return None

        career_row = career.iloc[0]
        bowl_innings = get_bowler_innings(player_name, min_balls=1)
        bowl_career = get_bowler_career(min_balls=1).query(f"player_name == '{player_name}'")

        summary = {
            'player_name': player_name,
            'total_innings': len(bat_innings),
            'total_balls_faced': int(career_row['balls_faced']),
            'total_runs': int(career_row['runs']),
            'career_strike_rate': float(career_row['strike_rate']),
            'avg_innings_strike_rate': float(bat_innings['strike_rate'].mean()) if len(bat_innings) > 0 else 0,
            'batting_average': float(career_row['average']) if career_row['dismissals'] > 0 else float('inf'),
            'boundary_rate': float(career_row['boundary_rate']) * 100,
            'dismissal_rate': float(career_row['dismissals']) / len(bat_innings) * 100 if len(bat_innings) > 0 else 0,
            'fours': int(career_row['fours']),
            'sixes': int(career_row['sixes']),
            'boundaries': int(career_row['boundaries']),
            'dismissals': int(career_row['dismissals']),
            'not_outs': int(career_row['not_outs']),
            'hundreds': int(career_row['hundreds']),
            'fifties': int(career_row['fifties']),
            'ducks': int(career_row['ducks']),
            'highest_score': int(career_row['highest_score']),
            'total_balls_bowled': 0,
            'total_wickets': 0,
            'economy_rate': 0.0,
            'bowling_average': 0.0,
            'bowling_strike_rate': 0.0,
        }

        if len(bowl_career) > 0:
            bowl_row = bowl_career.iloc[0]
            summary['total_balls_bowled'] = int(bowl_row['balls_bowled'])
            summary['total_wickets'] = int(bowl_row['wickets'])
            summary['economy_rate'] = float(bowl_row['economy'])
            summary['bowling_average'] = float(bowl_row['average']) if bowl_row['wickets'] > 0 else float('inf')
            summary['bowling_strike_rate'] = float(bowl_row['strike_rate']) if bowl_row['wickets'] > 0 else 0

        return summary
    except Exception as e:
        logger.error(f"Error getting player summary for {player_name}: {e}")
        return None


# ============================================================
# Page Functions
# ============================================================

def page_overview():
    """Page 1: Overview - League statistics and quality indicators."""
    st.title("🏏 IPL Sports Analytics Dashboard")
    st.markdown("### League Overview & Data Quality")

    # Load data with loading state
    with st.spinner("Loading league data..."):
        try:
            conn = get_connection()

            # Get overall stats
            total_matches = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
            total_players = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
            total_innings = conn.execute("SELECT COUNT(*) FROM player_innings WHERE balls_faced > 0").fetchone()[0]
            total_deliveries = conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
            total_seasons = conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0]

            # Batting overview
            bat_stats = conn.execute("""
                SELECT
                    SUM(runs) as total_runs,
                    SUM(balls_faced) as total_balls,
                    AVG(strike_rate) as avg_strike_rate,
                    SUM(fours) as total_fours,
                    SUM(sixes) as total_sixes
                FROM player_innings WHERE balls_faced > 0
            """).fetchone()

            # Bowling overview
            bowl_stats = conn.execute("""
                SELECT
                    SUM(wickets_taken) as total_wickets,
                    SUM(balls_bowled) as total_balls_bowled,
                    AVG(economy_rate) as avg_economy
                FROM player_innings WHERE balls_bowled > 0
            """).fetchone()

            conn.close()

        except Exception as e:
            st.error(f"Error loading overview data: {e}")
            return

    # Key Metrics Row
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("🏏 Matches", f"{total_matches:,}")
    with col2:
        st.metric("👥 Players", f"{total_players:,}")
    with col3:
        st.metric("📊 Innings", f"{total_innings:,}")
    with col4:
        st.metric("⚾ Deliveries", f"{total_deliveries:,}")
    with col5:
        st.metric("📅 Seasons", f"{total_seasons:,}")

    st.markdown("---")

    # Batting & Bowling Overview
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🏏 Batting Overview")
        if bat_stats:
            total_runs, total_balls, avg_sr, total_fours, total_sixes = bat_stats
            boundary_pct = (total_fours + total_sixes) / total_balls * 100 if total_balls > 0 else 0

            bcol1, bcol2 = st.columns(2)
            with bcol1:
                st.metric("Total Runs", f"{total_runs:,}")
                st.metric("Total Balls Faced", f"{total_balls:,}")
                st.metric("Avg Strike Rate", f"{avg_sr:.2f}")
            with bcol2:
                st.metric("Fours", f"{total_fours:,}")
                st.metric("Sixes", f"{total_sixes:,}")
                st.metric("Boundary %", f"{boundary_pct:.2f}%")

    with col2:
        st.markdown("#### 🎯 Bowling Overview")
        if bowl_stats:
            total_wickets, total_balls_bowled, avg_economy = bowl_stats

            bcol1, bcol2 = st.columns(2)
            with bcol1:
                st.metric("Total Wickets", f"{total_wickets:,}")
                st.metric("Total Balls Bowled", f"{total_balls_bowled:,}")
            with bcol2:
                st.metric("Avg Economy", f"{avg_economy:.2f}")
                if total_balls_bowled > 0:
                    st.metric("Avg Bowling SR", f"{total_balls_bowled/total_wickets:.2f}" if total_wickets > 0 else "N/A")

    st.markdown("---")

    # Data Quality Indicators
    st.markdown("#### 🔍 Data Quality Indicators")

    try:
        conn = get_connection()

        # Quality checks
        quality_checks = []

        # Check for missing player names
        missing_names = conn.execute("SELECT COUNT(*) FROM players WHERE player_name IS NULL OR player_name = ''").fetchone()[0]
        quality_checks.append(("Missing Player Names", missing_names, "✅" if missing_names == 0 else "⚠️"))

        # Check for duplicate matches
        dup_matches = conn.execute("SELECT COUNT(*) - COUNT(DISTINCT match_id) FROM matches").fetchone()[0]
        quality_checks.append(("Duplicate Matches", dup_matches, "✅" if dup_matches == 0 else "⚠️"))

        # Check deliveries with missing runs
        missing_runs = conn.execute("SELECT COUNT(*) FROM deliveries WHERE runs_off_bat IS NULL").fetchone()[0]
        quality_checks.append(("Deliveries Missing Runs", missing_runs, "✅" if missing_runs == 0 else "⚠️"))

        # Check wides/no-balls
        wides = conn.execute("SELECT COUNT(*) FROM deliveries WHERE wides > 0").fetchone()[0]
        noballs = conn.execute("SELECT COUNT(*) FROM deliveries WHERE noballs > 0").fetchone()[0]
        quality_checks.append(("Wides Recorded", wides, "ℹ️"))
        quality_checks.append(("No-balls Recorded", noballs, "ℹ️"))

        # Check byes/legbyes
        byes = conn.execute("SELECT COUNT(*) FROM deliveries WHERE byes > 0").fetchone()[0]
        legbyes = conn.execute("SELECT COUNT(*) FROM deliveries WHERE legbyes > 0").fetchone()[0]
        quality_checks.append(("Byes Recorded", byes, "ℹ️"))
        quality_checks.append(("Leg-byes Recorded", legbyes, "ℹ️"))

        conn.close()

        # Display quality checks
        qcols = st.columns(3)
        for i, (check, value, status) in enumerate(quality_checks):
            with qcols[i % 3]:
                st.markdown(f"""
                <div class="stat-card">
                    <h4>{status} {check}</h4>
                    <div class="value">{value:,}</div>
                </div>
                """, unsafe_allow_html=True)

    except Exception as e:
        st.warning(f"Could not load quality checks: {e}")

    # Top Performers Quick View
    st.markdown("---")
    st.markdown("#### 🏆 Quick Stats - Top 10 Career Strike Rate (min 500 balls)")

    with st.spinner("Loading top performers..."):
        top_batters = get_top_batters_by_strike_rate(min_balls=500, limit=10)

    if not top_batters.empty:
        fig = px.bar(
            top_batters,
            x='strike_rate',
            y='player_name',
            orientation='h',
            title="Top 10 Batters by Career Strike Rate",
            color='strike_rate',
            color_continuous_scale='Greens',
            labels={'strike_rate': 'Strike Rate', 'player_name': 'Player'}
        )
        fig.update_layout(
            plot_bgcolor='#161b22',
            paper_bgcolor='#161b22',
            font_color='#e6edf3',
            yaxis={'categoryorder': 'total ascending'},
            height=400
        )
        fig.update_traces(texttemplate='%{x:.2f}', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for top performers")


def page_player_analysis():
    """Page 2: Player Analysis - Individual player deep dive."""
    st.title("👤 Player Analysis")
    st.markdown("### Individual Player Performance Deep Dive")

    # Sidebar filters
    with st.sidebar:
        st.markdown("### Filters")
        players = load_all_players()
        if not players:
            st.error("No players loaded")
            return

        selected_player = st.selectbox("Select Player", players, index=0)
        seasons = load_seasons()
        selected_seasons = st.multiselect("Filter by Season", seasons, default=seasons)
        min_balls = st.number_input("Minimum Balls per Innings", min_value=1, max_value=100, value=10, step=1)
        min_career_balls = st.number_input("Minimum Career Balls", min_value=50, max_value=1000, value=200, step=50)

    if not selected_player:
        st.warning("Please select a player")
        return

    # Load player data
    with st.spinner(f"Loading data for {selected_player}..."):
        summary = get_player_summary(selected_player, min_balls)
        bat_innings = get_batter_innings(selected_player, min_balls=min_balls)
        season_stats = get_batter_season(min_balls=min_career_balls)
        player_seasons = season_stats[season_stats['player_name'] == selected_player] if not season_stats.empty else pd.DataFrame()

        # Run mean/median analysis
        analyzer = MeanMedianAnalyzer(min_balls_per_innings=min_balls)
        player_mm = analyzer.analyze_innings_strike_rates(selected_player)

    if not summary:
        st.error(f"Player {selected_player} not found or insufficient data")
        return

    # Player Header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"## {selected_player}")
        role = "Batter" if summary['total_balls_faced'] >= min_career_balls else "Bowler"
        if summary['total_balls_faced'] >= min_career_balls and summary['total_balls_bowled'] >= 100:
            role = "All-rounder"
        st.caption(f"Role: {role}")
    with col2:
        st.metric("Career Strike Rate", f"{summary['career_strike_rate']:.2f}")
    with col3:
        st.metric("Batting Average", f"{summary['batting_average']:.2f}" if summary['batting_average'] != float('inf') else "N/A")

    # Key Metrics Row
    st.markdown("---")
    mcol1, mcol2, mcol3, mcol4, mcol5, mcol6 = st.columns(6)

    with mcol1:
        st.metric("Runs", f"{summary['total_runs']:,}")
    with mcol2:
        st.metric("Balls Faced", f"{summary['total_balls_faced']:,}")
    with mcol3:
        st.metric("Innings", f"{summary['total_innings']}")
    with mcol4:
        st.metric("Boundary %", f"{summary['boundary_rate']:.2f}%")
    with mcol5:
        st.metric("Avg Innings SR", f"{summary['avg_innings_strike_rate']:.2f}")
    with mcol6:
        st.metric("Dismissal Rate", f"{summary['dismissal_rate']:.2f}%")

    # Mean vs Median Analysis
    st.markdown("---")
    st.markdown("#### 📊 Mean vs Median Analysis (Innings Strike Rates)")

    mm_col1, mm_col2 = st.columns(2)

    with mm_col1:
        st.markdown(f"""
        <div class="stat-card">
            <h4>Mean Strike Rate</h4>
            <div class="value">{player_mm.mean:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="stat-card">
            <h4>Median Strike Rate</h4>
            <div class="value">{player_mm.median:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="stat-card">
            <h4>Std Deviation</h4>
            <div class="value">{player_mm.std:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with mm_col2:
        st.markdown(f"""
        <div class="stat-card">
            <h4>Skewness</h4>
            <div class="value">{player_mm.skewness:.3f}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="stat-card">
            <h4>Kurtosis</h4>
            <div class="value">{player_mm.kurtosis:.3f}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="stat-card">
            <h4>Outliers (IQR)</h4>
            <div class="value">{player_mm.outlier_count}</div>
        </div>
        """, unsafe_allow_html=True)

    st.info(f"📈 **Interpretation**: {player_mm.interpret()}")

    # Innings Strike Rate Distribution
    st.markdown("---")
    st.markdown("#### 📈 Innings Strike Rate Distribution")

    if not bat_innings.empty:
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("Histogram", "Box Plot"),
            column_widths=[0.7, 0.3]
        )

        fig.add_trace(
            go.Histogram(
                x=bat_innings['strike_rate'],
                nbinsx=30,
                name="Strike Rate",
                marker_color='#3fb950',
                opacity=0.7
            ),
            row=1, col=1
        )

        # Add mean/median lines
        fig.add_vline(x=player_mm.mean, line_dash="dash", line_color="#58a6ff",
                      annotation_text=f"Mean: {player_mm.mean:.1f}", row=1, col=1)
        fig.add_vline(x=player_mm.median, line_dash="dash", line_color="#f85149",
                      annotation_text=f"Median: {player_mm.median:.1f}", row=1, col=1)

        fig.add_trace(
            go.Box(
                y=bat_innings['strike_rate'],
                name="Strike Rate",
                marker_color='#3fb950',
                boxpoints='outliers'
            ),
            row=1, col=2
        )

        fig.update_layout(
            plot_bgcolor='#161b22',
            paper_bgcolor='#161b22',
            font_color='#e6edf3',
            showlegend=False,
            height=400
        )

        st.plotly_chart(fig, use_container_width=True)

    # Season-by-Season Performance
    st.markdown("---")
    st.markdown("#### 📅 Season-by-Season Performance")

    if not player_seasons.empty:
        # Filter by selected seasons
        if selected_seasons:
            player_seasons = player_seasons[player_seasons['season_name'].isin(selected_seasons)]

        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("Runs per Season", "Strike Rate per Season",
                           "Boundary Rate per Season", "Average per Season"),
            vertical_spacing=0.12
        )

        fig.add_trace(
            go.Bar(x=player_seasons['season_name'], y=player_seasons['runs'],
                   name="Runs", marker_color='#3fb950'),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(x=player_seasons['season_name'], y=player_seasons['strike_rate'],
                       mode='lines+markers', name="Strike Rate", line=dict(color='#58a6ff', width=3)),
            row=1, col=2
        )

        fig.add_trace(
            go.Bar(x=player_seasons['season_name'], y=player_seasons['boundary_rate']*100,
                   name="Boundary %", marker_color='#d29922'),
            row=2, col=1
        )

        fig.add_trace(
            go.Scatter(x=player_seasons['season_name'], y=player_seasons['average'],
                       mode='lines+markers', name="Average", line=dict(color='#f85149', width=3)),
            row=2, col=2
        )

        fig.update_layout(
            plot_bgcolor='#161b22',
            paper_bgcolor='#161b22',
            font_color='#e6edf3',
            showlegend=False,
            height=600
        )

        fig.update_xaxes(tickangle=45)

        st.plotly_chart(fig, use_container_width=True)

        # Season table
        with st.expander("📋 View Season Details Table"):
            display_cols = ['season_name', 'matches', 'innings', 'runs', 'balls_faced',
                          'fours', 'sixes', 'strike_rate', 'average', 'boundary_rate',
                          'hundreds', 'fifties', 'ducks', 'highest_score']
            available_cols = [c for c in display_cols if c in player_seasons.columns]
            st.dataframe(
                player_seasons[available_cols].style.format({
                    'strike_rate': '{:.2f}',
                    'average': '{:.2f}',
                    'boundary_rate': '{:.2%}'
                }),
                use_container_width=True
            )
    else:
        st.info("No season data available for this player")

    # Bowling Stats (if applicable)
    if summary['total_balls_bowled'] > 0:
        st.markdown("---")
        st.markdown("#### 🎯 Bowling Performance")

        bcol1, bcol2, bcol3, bcol4 = st.columns(4)
        with bcol1:
            st.metric("Wickets", summary['total_wickets'])
        with bcol2:
            st.metric("Economy", f"{summary['economy_rate']:.2f}")
        with bcol3:
            st.metric("Bowling Avg", f"{summary['bowling_average']:.2f}" if summary['bowling_average'] != float('inf') else "N/A")
        with bcol4:
            st.metric("Bowling SR", f"{summary['bowling_strike_rate']:.2f}" if summary['bowling_strike_rate'] > 0 else "N/A")

        bowl_innings = get_bowler_innings(selected_player, min_balls=1)
        if not bowl_innings.empty:
            bowl_seasons = get_bowler_season(min_balls=50)
            player_bowl_seasons = bowl_seasons[bowl_seasons['player_name'] == selected_player]
            if not player_bowl_seasons.empty and selected_seasons:
                player_bowl_seasons = player_bowl_seasons[player_bowl_seasons['season_name'].isin(selected_seasons)]

            if not player_bowl_seasons.empty:
                with st.expander("📋 View Bowling Season Details"):
                    display_cols = ['season_name', 'matches', 'overs_bowled', 'balls_bowled', 'maidens',
                                  'runs_conceded', 'wickets_taken', 'economy_rate', 'bowling_average',
                                  'bowling_strike_rate', 'wides_bowled', 'noballs_bowled']
                    available_cols = [c for c in display_cols if c in player_bowl_seasons.columns]
                    st.dataframe(
                        player_bowl_seasons[available_cols].style.format({
                            'economy_rate': '{:.2f}',
                            'bowling_average': '{:.2f}',
                            'bowling_strike_rate': '{:.2f}'
                        }),
                        use_container_width=True
                    )


def page_player_comparison():
    """Page 3: Player Comparison - Two players head-to-head."""
    st.title("⚔️ Player Comparison")
    st.markdown("### Head-to-Head Statistical Comparison with Uncertainty Quantification")

    # Sidebar filters
    with st.sidebar:
        st.markdown("### Comparison Settings")
        players = load_all_players()

        col1, col2 = st.columns(2)
        with col1:
            player_a = st.selectbox("Player A", players, index=0, key="comp_a")
        with col2:
            player_b = st.selectbox("Player B", players, index=min(1, len(players)-1), key="comp_b")

        metric = st.selectbox(
            "Comparison Metric",
            ["strike_rate", "boundary_rate", "batting_average", "avg_innings_sr"],
            format_func=lambda x: {
                "strike_rate": "Career Strike Rate",
                "boundary_rate": "Boundary Rate",
                "batting_average": "Batting Average",
                "avg_innings_sr": "Avg Innings Strike Rate"
            }[x]
        )

        min_balls = st.number_input("Min Balls per Innings", min_value=1, max_value=100, value=10, key="comp_min_balls")
        min_career_balls = st.number_input("Min Career Balls", min_value=50, max_value=1000, value=200, key="comp_min_career")
        n_bootstrap = st.number_input("Bootstrap Iterations", min_value=1000, max_value=50000, value=2000, step=1000,
                                       help="Lower values for faster computation")

    if player_a == player_b:
        st.warning("Please select two different players")
        return

    # Run comparison
    with st.spinner(f"Comparing {player_a} vs {player_b}..."):
        try:
            tool = PlayerComparisonTool(min_balls_per_innings=min_balls, min_career_balls=min_career_balls)
            # Override bootstrap iterations for speed
            tool.bootstrap.n_bootstrap = n_bootstrap

            result = tool.compare(player_a, player_b, metric)

        except Exception as e:
            st.error(f"Comparison failed: {e}")
            logger.error(f"Comparison error: {e}", exc_info=True)
            return

    # Display Results
    st.markdown("---")

    # Verdict Banner
    verdict_color = {
        'high': '#3fb950',
        'medium': '#d29922',
        'low': '#8b949e'
    }.get(result.confidence, '#8b949e')

    st.markdown(f"""
    <div style="background-color: {verdict_color}22; border: 2px solid {verdict_color}; border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 1rem;">
        <h3 style="color: {verdict_color}; margin: 0;">{result.verdict}</h3>
        <p style="margin: 0.5rem 0 0 0; color: var(--text-secondary);">Confidence: {result.confidence.upper()}</p>
    </div>
    """, unsafe_allow_html=True)

    # Player Summaries Side by Side
    st.markdown("#### 📊 Player Summaries")
    col_a, col_b = st.columns(2)

    for col, player, summary in [(col_a, result.player_a, result.summary_a),
                                   (col_b, result.player_b, result.summary_b)]:
        with col:
            st.markdown(f"##### {player}")

            metrics = [
                ("Career Strike Rate", f"{summary.career_strike_rate:.2f}"),
                ("Avg Innings SR", f"{summary.avg_innings_strike_rate:.2f}"),
                ("Batting Average", f"{summary.batting_average:.2f}" if summary.batting_average != float('inf') else "N/A"),
                ("Boundary Rate", f"{summary.boundary_rate:.2f}%"),
                ("Dismissal Rate", f"{summary.dismissal_rate:.2f}%"),
                ("Total Runs", f"{summary.total_runs:,}"),
                ("Balls Faced", f"{summary.total_balls_faced:,}"),
                ("Innings", f"{summary.total_innings}"),
            ]

            for label, value in metrics:
                st.markdown(f"""
                <div class="stat-card" style="margin-bottom: 0.25rem;">
                    <h4>{label}</h4>
                    <div class="value">{value}</div>
                </div>
                """, unsafe_allow_html=True)

    # Hypothesis Tests
    st.markdown("---")
    st.markdown("#### 🧪 Hypothesis Tests")

    hcol1, hcol2 = st.columns(2)

    with hcol1:
        st.markdown("##### Welch's t-test")
        welch = result.welch_t_test
        if 'error' not in welch:
            reject = welch.get('reject_null', False)
            status = "✅ **Significant**" if reject else "❌ **Not Significant**"
            st.markdown(f"""
            <div class="stat-card">
                <h4>{status}</h4>
                <div class="value">p = {welch.get('p_value', 0):.6f}</div>
                <small>t = {welch.get('test_statistic', 0):.3f} | Cohen's d = {welch.get('cohens_d', 0):.3f} | Mean diff = {welch.get('mean_diff', 0):.2f}</small>
            </div>
            """, unsafe_allow_html=True)
            if 'interpretation' in welch:
                st.caption(welch['interpretation'][:200] + "..." if len(welch['interpretation']) > 200 else welch['interpretation'])
        else:
            st.error(f"Error: {welch.get('error', 'Unknown')}")

    with hcol2:
        st.markdown("##### Mann-Whitney U Test")
        mw = result.mann_whitney_u
        if 'error' not in mw:
            reject = mw.get('reject_null', False)
            status = "✅ **Significant**" if reject else "❌ **Not Significant**"
            st.markdown(f"""
            <div class="stat-card">
                <h4>{status}</h4>
                <div class="value">p = {mw.get('p_value', 0):.6f}</div>
                <small>U = {mw.get('test_statistic', 0):.1f} | Effect size = {mw.get('effect_size', 0):.3f}</small>
            </div>
            """, unsafe_allow_html=True)
            if 'interpretation' in mw:
                st.caption(mw['interpretation'][:200] + "..." if len(mw['interpretation']) > 200 else mw['interpretation'])
        else:
            st.error(f"Error: {mw.get('error', 'Unknown')}")

    st.info(f"🎯 **Recommended Test**: {result.recommended_test}")

    # Bootstrap Confidence Intervals
    st.markdown("---")
    st.markdown("#### 📈 Bootstrap Confidence Intervals (n=10,000)")

    bcol1, bcol2, bcol3 = st.columns(3)

    for col, label, ci_data in [
        (bcol1, f"{player_a}", result.bootstrap_ci_a),
        (bcol2, f"{player_b}", result.bootstrap_ci_b),
        (bcol3, "Difference", result.bootstrap_diff_ci)
    ]:
        with col:
            st.markdown(f"##### {label}")
            if 'error' not in ci_data:
                ci_lower = ci_data.get('ci_lower', 0)
                ci_upper = ci_data.get('ci_upper', 0)
                point = ci_data.get('point_estimate', 0)
                excludes_zero = ci_data.get('excludes_zero', False)

                status = "✅ Excludes Zero" if excludes_zero else "❌ Includes Zero"
                st.markdown(f"""
                <div class="stat-card">
                    <h4>{status}</h4>
                    <div class="value">{point:.2f}</div>
                    <small>95% CI: [{ci_lower:.2f}, {ci_upper:.2f}]</small>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.error(ci_data.get('error', 'Unknown error'))

    # Innings Distributions Comparison
    st.markdown("---")
    st.markdown("#### 📊 Innings Distributions Comparison")

    # Get innings data for both players
    with st.spinner("Loading innings distributions..."):
        innings_a = get_batter_innings(player_a, min_balls=min_balls)
        innings_b = get_batter_innings(player_b, min_balls=min_balls)

    if not innings_a.empty and not innings_b.empty:
        fig = go.Figure()

        fig.add_trace(go.Histogram(
            x=innings_a['strike_rate'],
            name=player_a,
            opacity=0.6,
            nbinsx=30,
            marker_color='#3fb950'
        ))

        fig.add_trace(go.Histogram(
            x=innings_b['strike_rate'],
            name=player_b,
            opacity=0.6,
            nbinsx=30,
            marker_color='#58a6ff'
        ))

        fig.update_layout(
            barmode='overlay',
            title="Innings Strike Rate Distributions",
            xaxis_title="Strike Rate",
            yaxis_title="Frequency",
            plot_bgcolor='#161b22',
            paper_bgcolor='#161b22',
            font_color='#e6edf3',
            height=400
        )

        st.plotly_chart(fig, use_container_width=True)

    # Key Findings
    st.markdown("---")
    st.markdown("#### 🔑 Key Findings")
    for finding in result.key_findings:
        st.markdown(f"- {finding}")

    # Regression to Mean
    st.markdown("---")
    st.markdown("#### 📉 Regression to Mean Analysis")

    rcol1, rcol2 = st.columns(2)

    for col, player, reg_data in [(rcol1, player_a, result.regression_a),
                                   (rcol2, player_b, result.regression_b)]:
        with col:
            st.markdown(f"##### {player}")
            if 'error' not in reg_data:
                reg_mag = reg_data.get('regression_magnitude', 0)
                reg_pct = reg_data.get('regression_percentage', 0)
                first_sr = reg_data.get('first_half_strike_rate', 0)
                second_sr = reg_data.get('second_half_strike_rate', 0)

                direction = "📉 Regressed" if reg_mag > 0 else "📈 Improved"

                st.markdown(f"""
                <div class="stat-card">
                    <h4>{direction}</h4>
                    <div class="value">{reg_mag:.2f} ({reg_pct:.1f}%)</div>
                    <small>1st Half: {first_sr:.2f} | 2nd Half: {second_sr:.2f}</small>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning(reg_data.get('error', 'Insufficient data'))

    # Shrinkage
    st.markdown("---")
    st.markdown("#### 🎯 Beta-Binomial Shrinkage (Boundary Rate)")

    scol1, scol2 = st.columns(2)

    for col, player, shrink_data in [(scol1, player_a, result.shrinkage_a),
                                      (scol2, player_b, result.shrinkage_b)]:
        with col:
            st.markdown(f"##### {player}")
            if 'error' not in shrink_data:
                raw = shrink_data.get('raw_boundary_rate', 0)
                shrunken = shrink_data.get('shrunken_boundary_rate', 0)
                shrinkage = shrink_data.get('shrinkage_factor', 0)
                ci_l = shrink_data.get('ci_lower', 0)
                ci_u = shrink_data.get('ci_upper', 0)

                st.markdown(f"""
                <div class="stat-card">
                    <h4>Raw: {raw:.2f}% → Shrunken: {shrunken:.2f}%</h4>
                    <div class="value">Shrinkage: {shrinkage:.1%}</div>
                    <small>95% CI: [{ci_l:.2f}%, {ci_u:.2f}%]</small>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning(shrink_data.get('error', 'Insufficient data'))


def page_shrinkage_rankings():
    """Page 4: Shrinkage Rankings - Beta-Binomial Empirical Bayes."""
    st.title("🎯 Shrinkage Rankings")
    st.markdown("### Beta-Binomial Empirical Bayes Shrinkage for Boundary Rates")

    # Sidebar filters
    with st.sidebar:
        st.markdown("### Shrinkage Settings")
        min_balls = st.number_input("Minimum Career Balls", min_value=50, max_value=1000, value=200, step=50, key="shrink_min_balls")
        method = st.selectbox("Prior Estimation Method", ["moments", "mle"], key="shrink_method")
        top_n = st.number_input("Top N Players", min_value=10, max_value=100, value=20, step=5, key="shrink_top_n")

    # Run analysis
    with st.spinner("Computing beta-binomial shrinkage..."):
        try:
            shrinkage = BetaBinomialShrinkage(min_balls=min_balls, method=method)
            df_all, prior = shrinkage.analyze_all_players()
            top_players = shrinkage.get_top_shrunken(top_n)
            comparison = shrinkage.compare_raw_vs_shrunken()
        except Exception as e:
            st.error(f"Shrinkage analysis failed: {e}")
            logger.error(f"Shrinkage error: {e}", exc_info=True)
            return

    if df_all.empty:
        st.warning("No qualified players found")
        return

    # Prior Info
    st.markdown("#### 📊 Empirical Bayes Prior")
    pcol1, pcol2, pcol3, pcol4 = st.columns(4)

    with pcol1:
        st.metric("Prior α", f"{prior.alpha:.3f}")
    with pcol2:
        st.metric("Prior β", f"{prior.beta:.3f}")
    with pcol3:
        st.metric("League Boundary Rate", f"{prior.league_boundary_rate*100:.2f}%")
    with pcol4:
        st.metric("Players in Prior", f"{prior.n_players}")

    st.caption(f"Method: {prior.method} | Total Boundaries: {prior.total_boundaries:,} | Total Balls: {prior.total_balls:,}")

    # Comparison Summary
    st.markdown("---")
    st.markdown("#### 📈 Raw vs Shrunken Comparison")

    ccol1, ccol2, ccol3, ccol4 = st.columns(4)

    with ccol1:
        st.metric("Correlation", f"{comparison['correlation']:.4f}")
    with ccol2:
        st.metric("Mean Abs Diff", f"{comparison['mean_abs_difference']:.4f}%")
    with ccol3:
        st.metric("Mean Shrinkage", f"{comparison['mean_shrinkage']:.1%}")
    with ccol4:
        st.metric("Max Shrinkage", f"{comparison['max_shrinkage']:.1%}")

    # Top Players Table
    st.markdown("---")
    st.markdown(f"#### 🏆 Top {top_n} Players by Shrunken Boundary Rate")

    # Raw vs Shrunken Scatter
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_all['raw_boundary_rate'],
        y=df_all['shrunken_boundary_rate'],
        mode='markers',
        marker=dict(
            size=8,
            color=df_all['shrinkage_factor'],
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title="Shrinkage Factor")
        ),
        text=df_all['player_name'],
        hovertemplate="<b>%{text}</b><br>Raw: %{x:.2f}%<br>Shrunken: %{y:.2f}%<br>Shrinkage: %{marker.color:.1%}<extra></extra>",
        name="All Players"
    ))

    # Highlight top players
    fig.add_trace(go.Scatter(
        x=top_players['raw_boundary_rate'],
        y=top_players['shrunken_boundary_rate'],
        mode='markers+text',
        marker=dict(size=12, color='#3fb950', symbol='star'),
        text=top_players['player_name'],
        textposition="top center",
        name=f"Top {top_n}",
        hovertemplate="<b>%{text}</b><br>Raw: %{x:.2f}%<br>Shrunken: %{y:.2f}%<extra></extra>"
    ))

    # y=x line
    max_val = max(df_all['raw_boundary_rate'].max(), df_all['shrunken_boundary_rate'].max())
    fig.add_trace(go.Scatter(
        x=[0, max_val], y=[0, max_val],
        mode='lines',
        line=dict(dash='dash', color='#8b949e'),
        name="y = x (no shrinkage)",
        showlegend=True
    ))

    fig.update_layout(
        title="Raw vs Shrunken Boundary Rates",
        xaxis_title="Raw Boundary Rate (%)",
        yaxis_title="Shrunken Boundary Rate (%)",
        plot_bgcolor='#161b22',
        paper_bgcolor='#161b22',
        font_color='#e6edf3',
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)

    # Detailed Table
    st.markdown("---")
    st.markdown("#### 📋 Detailed Rankings")

    display_df = top_players[['player_name', 'balls_faced', 'boundaries',
                              'raw_boundary_rate', 'shrunken_boundary_rate',
                              'shrinkage_factor', 'ci_lower', 'ci_upper']].copy()
    display_df.columns = ['Player', 'Balls Faced', 'Boundaries', 'Raw %',
                          'Shrunken %', 'Shrinkage', 'CI Lower', 'CI Upper']

    st.dataframe(
        display_df.style.format({
            'Raw %': '{:.2f}%',
            'Shrunken %': '{:.2f}%',
            'Shrinkage': '{:.1%}',
            'CI Lower': '{:.2f}%',
            'CI Upper': '{:.2f}%'
        }).background_gradient(subset=['Shrunken %'], cmap='Greens'),
        use_container_width=True,
        height=500
    )

    # Rank Changes
    st.markdown("---")
    st.markdown("#### 🔄 Significant Rank Changes")

    rcol1, rcol2 = st.columns(2)

    with rcol1:
        st.markdown("##### Biggest Rank Improvements (Shrunken > Raw)")
        if comparison['top_rank_increases']:
            rank_inc = pd.DataFrame(comparison['top_rank_increases'])
            rank_inc.columns = ['Player', 'Raw Rank', 'Shrunken Rank', 'Rank Change']
            st.dataframe(rank_inc, use_container_width=True)
        else:
            st.info("No significant rank improvements")

    with rcol2:
        st.markdown("##### Biggest Rank Declines (Raw > Shrunken)")
        if comparison['top_rank_decreases']:
            rank_dec = pd.DataFrame(comparison['top_rank_decreases'])
            rank_dec.columns = ['Player', 'Raw Rank', 'Shrunken Rank', 'Rank Change']
            st.dataframe(rank_dec, use_container_width=True)
        else:
            st.info("No significant rank declines")

    # Most Shrunken Players
    st.markdown("---")
    st.markdown("#### 🔍 Most Shrunken Players (Smallest Sample Sizes)")

    most_shrunk = shrinkage.get_most_shrunken(15)
    if not most_shrunk.empty:
        fig = px.bar(
            most_shrunk,
            x='shrinkage_factor',
            y='player_name',
            orientation='h',
            title="Players with Highest Shrinkage (Lowest Sample Sizes)",
            color='shrinkage_factor',
            color_continuous_scale='Reds',
            labels={'shrinkage_factor': 'Shrinkage Factor', 'player_name': 'Player'}
        )
        fig.update_layout(
            plot_bgcolor='#161b22',
            paper_bgcolor='#161b22',
            font_color='#e6edf3',
            yaxis={'categoryorder': 'total ascending'},
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)


def page_regression_to_mean():
    """Page 5: Regression to Mean - Career halves analysis."""
    st.title("📉 Regression to Mean")
    st.markdown("### Career Halves Analysis: First Half vs Second Half Performance")

    # Sidebar filters
    with st.sidebar:
        st.markdown("### Regression Settings")
        min_balls_half = st.number_input("Min Balls per Half", min_value=50, max_value=500, value=100, step=50, key="reg_min_balls")
        threshold_pct = st.number_input("Over/Under Performer Threshold (%)", min_value=5, max_value=50, value=20, step=5, key="reg_threshold")

    # Run analysis
    with st.spinner("Analyzing regression to mean..."):
        try:
            analyzer = RegressionToMean(min_balls_per_half=min_balls_half)
            df, summary = analyzer.analyze_all_players()
            theory = analyzer.theory_vs_experiment()
            performers = analyzer.identify_overperformers_underperformers(threshold_pct=threshold_pct)
            plot_data = analyzer.plot_data()
        except Exception as e:
            st.error(f"Regression analysis failed: {e}")
            logger.error(f"Regression error: {e}", exc_info=True)
            return

    if df.empty:
        st.warning("No qualified players found")
        return

    # Summary Stats
    st.markdown("#### 📊 Overall Summary")

    scol1, scol2, scol3, scol4, scol5, scol6 = st.columns(6)

    with scol1:
        st.metric("Players Analyzed", summary.n_players)
    with scol2:
        st.metric("Mean 1st Half SR", f"{summary.mean_first_half_sr:.2f}")
    with scol3:
        st.metric("Mean 2nd Half SR", f"{summary.mean_second_half_sr:.2f}")
    with scol4:
        st.metric("Mean Regression", f"{summary.mean_regression:.2f}")
    with scol5:
        st.metric("Correlation", f"{summary.correlation:.4f}")
    with scol6:
        st.metric("R²", f"{summary.r_squared:.4f}")

    st.caption(f"Players Regressed: {summary.players_regressed} | Players Improved: {summary.players_improved} | Regression Line: y = {summary.slope:.4f}x + {summary.intercept:.2f}")

    # Theory vs Experiment
    st.markdown("---")
    st.markdown("#### 🧮 Theory vs Experiment")

    tcol1, tcol2, tcol3 = st.columns(3)

    with tcol1:
        st.metric("League Avg SR", f"{theory['league_average_sr']:.2f}")
    with tcol2:
        st.metric("Est. Reliability", f"{theory['estimated_reliability']:.4f}")
    with tcol3:
        st.metric("Mean Expected Reg", f"{theory['mean_expected_regression']:.2f}")

    st.metric("Mean Observed Reg", f"{theory['mean_observed_regression']:.2f}")

    # Extreme performers
    eh = theory['extreme_high_players']
    el = theory['extreme_low_players']

    ecol1, ecol2 = st.columns(2)

    with ecol1:
        st.markdown("##### Extreme High Performers (Top 25% First Half)")
        st.markdown(f"""
        - Count: {eh['count']}
        - Mean 1st Half SR: {eh['mean_first_half']:.2f}
        - Mean 2nd Half SR: {eh['mean_second_half']:.2f}
        - Observed Regression: {eh['mean_observed_regression']:.2f}
        - Expected Regression: {eh['mean_expected_regression']:.2f}
        """)

    with ecol2:
        st.markdown("##### Extreme Low Performers (Bottom 25% First Half)")
        st.markdown(f"""
        - Count: {el['count']}
        - Mean 1st Half SR: {el['mean_first_half']:.2f}
        - Mean 2nd Half SR: {el['mean_second_half']:.2f}
        - Observed Regression: {el['mean_observed_regression']:.2f}
        - Expected Regression: {el['mean_expected_regression']:.2f}
        """)

    # Scatter Plot
    st.markdown("---")
    st.markdown("#### 📈 First Half vs Second Half Strike Rate")

    fig = go.Figure()

    # All players
    fig.add_trace(go.Scatter(
        x=plot_data['first_half_strike_rate'],
        y=plot_data['second_half_strike_rate'],
        mode='markers',
        marker=dict(
            size=8,
            color=plot_data['regression_magnitude'],
            colorscale='RdBu',
            showscale=True,
            colorbar=dict(title="Regression<br>Magnitude"),
            cmid=0
        ),
        text=plot_data['player_name'],
        hovertemplate="<b>%{text}</b><br>1st Half: %{x:.2f}<br>2nd Half: %{y:.2f}<br>Regression: %{marker.color:.2f}<extra></extra>",
        name="All Players"
    ))

    # y=x line
    min_val = min(plot_data['first_half_strike_rate'].min(), plot_data['second_half_strike_rate'].min())
    max_val = max(plot_data['first_half_strike_rate'].max(), plot_data['second_half_strike_rate'].max())
    fig.add_trace(go.Scatter(
        x=[min_val, max_val], y=[min_val, max_val],
        mode='lines',
        line=dict(dash='dash', color='#8b949e', width=2),
        name="y = x (No Regression)",
        showlegend=True
    ))

    # Regression line
    x_range = np.linspace(min_val, max_val, 100)
    y_range = summary.slope * x_range + summary.intercept
    fig.add_trace(go.Scatter(
        x=x_range, y=y_range,
        mode='lines',
        line=dict(color='#3fb950', width=3),
        name=f"Regression Line (y={summary.slope:.3f}x+{summary.intercept:.1f})",
        showlegend=True
    ))

    # League average lines
    league_avg = theory['league_average_sr']
    fig.add_hline(y=league_avg, line_dash="dot", line_color="#58a6ff",
                  annotation_text=f"League Avg: {league_avg:.1f}", annotation_position="right")
    fig.add_vline(x=league_avg, line_dash="dot", line_color="#58a6ff")

    fig.update_layout(
        title="First Half vs Second Half Career Strike Rate",
        xaxis_title="First Half Strike Rate",
        yaxis_title="Second Half Strike Rate",
        plot_bgcolor='#161b22',
        paper_bgcolor='#161b22',
        font_color='#e6edf3',
        height=600,
        legend=dict(x=0.01, y=0.99)
    )

    st.plotly_chart(fig, use_container_width=True)

    # Over/Under Performers
    st.markdown("---")
    st.markdown(f"#### 🎯 Over/Under Performers (Threshold: ±{threshold_pct}%)")

    pcol1, pcol2 = st.columns(2)

    with pcol1:
        st.markdown("##### 🏆 Overperformers (Improved More Than Expected)")
        if performers['overperformers']:
            over_df = pd.DataFrame(performers['overperformers'][:15])
            display_cols = ['player_name', 'first_half_strike_rate', 'second_half_strike_rate',
                          'regression_magnitude', 'regression_percentage', 'expected_regression', 'residual']
            available = [c for c in display_cols if c in over_df.columns]
            st.dataframe(
                over_df[available].style.format({
                    'first_half_strike_rate': '{:.2f}',
                    'second_half_strike_rate': '{:.2f}',
                    'regression_magnitude': '{:.2f}',
                    'regression_percentage': '{:.2f}%',
                    'expected_regression': '{:.2f}',
                    'residual': '{:.2f}'
                }).background_gradient(subset=['residual'], cmap='Greens'),
                use_container_width=True
            )
        else:
            st.info("No overperformers found")

    with pcol2:
        st.markdown("##### 📉 Underperformers (Regressed More Than Expected)")
        if performers['underperformers']:
            under_df = pd.DataFrame(performers['underperformers'][:15])
            display_cols = ['player_name', 'first_half_strike_rate', 'second_half_strike_rate',
                          'regression_magnitude', 'regression_percentage', 'expected_regression', 'residual']
            available = [c for c in display_cols if c in under_df.columns]
            st.dataframe(
                under_df[available].style.format({
                    'first_half_strike_rate': '{:.2f}',
                    'second_half_strike_rate': '{:.2f}',
                    'regression_magnitude': '{:.2f}',
                    'regression_percentage': '{:.2f}%',
                    'expected_regression': '{:.2f}',
                    'residual': '{:.2f}'
                }).background_gradient(subset=['residual'], cmap='Reds'),
                use_container_width=True
            )
        else:
            st.info("No underperformers found")

    # Full Player Table
    with st.expander("📋 View All Players Regression Data"):
        st.dataframe(
            df[['player_name', 'first_half_strike_rate', 'second_half_strike_rate',
                'first_half_balls', 'second_half_balls', 'regression_magnitude',
                'regression_percentage']].style.format({
                    'first_half_strike_rate': '{:.2f}',
                    'second_half_strike_rate': '{:.2f}',
                    'regression_magnitude': '{:.2f}',
                    'regression_percentage': '{:.2f}%'
                }),
            use_container_width=True,
            height=400
        )


def page_methodology():
    """Page 6: Statistical Methodology - Explanation of methods."""
    st.title("📚 Statistical Methodology")
    st.markdown("### Comprehensive Guide to Statistical Methods Used")

    st.markdown("""
    This dashboard implements a rigorous statistical framework for cricket performance analysis.
    All methods follow established statistical principles with cricket-specific adaptations.
    """)

    # Method 1: Descriptive Statistics
    with st.expander("📊 **1. Descriptive Statistics: Mean vs Median Analysis**", expanded=True):
        st.markdown("""
        **Purpose**: Understand the distribution of cricket performance metrics and identify skew/outliers.

        **Key Distinction**:
        - **Career Aggregate Strike Rate** = Total Runs / Total Balls Faced (weighted by innings length)
        - **Average Innings Strike Rate** = Mean of individual innings strike rates (unweighted)

        **Metrics Computed**:
        - Mean, Median, Standard Deviation, Min, Max
        - **Skewness** (Fisher-Pearson coefficient): Measures asymmetry
        - **Kurtosis** (Excess, Fisher's definition): Measures tail heaviness
        - **Outlier Detection**: IQR method (Q1 - 1.5×IQR, Q3 + 1.5×IQR)

        **Cricket Context**: Strike rate distributions are typically right-skewed due to explosive innings.
        The mean > median indicates positive skew - a few high-SR innings pull the mean up.
        """)

        st.latex(r"""
        \text{Skewness} = \frac{n}{(n-1)(n-2)} \sum \left(\frac{x_i - \bar{x}}{s}\right)^3
        """)

        st.latex(r"""
        \text{Kurtosis} = \frac{n(n+1)}{(n-1)(n-2)(n-3)} \sum \left(\frac{x_i - \bar{x}}{s}\right)^4 - \frac{3(n-1)^2}{(n-2)(n-3)}
        """)

    # Method 2: Hypothesis Testing
    with st.expander("🧪 **2. Two-Group Hypothesis Tests**", expanded=False):
        st.markdown("""
        **Purpose**: Determine if performance differences between players are statistically significant.

        **Welch's t-test** (Parametric):
        - Does not assume equal variances
        - Test statistic: $t = \frac{\bar{x}_1 - \bar{x}_2}{\sqrt{s_1^2/n_1 + s_2^2/n_2}}$
        - Degrees of freedom: Welch-Satterthwaite approximation
        - **Effect Size**: Cohen's d = $\frac{\bar{x}_1 - \bar{x}_2}{s_{pooled}}$
        - Assumptions: Independence, approximate normality (robust for n>30)

        **Mann-Whitney U Test** (Non-parametric):
        - Tests if one distribution is stochastically greater than the other
        - No normality assumption
        - **Effect Size**: Rank-biserial correlation
        - Better for skewed distributions or small samples

        **Automatic Recommendation**:
        - Normality check (Shapiro-Wilk) + Equal variance check (Levene)
        - If both pass → Welch's t-test
        - Otherwise → Mann-Whitney U
        """)

    # Method 3: Bootstrap CIs
    with st.expander("📈 **3. Bootstrap Confidence Intervals**", expanded=False):
        st.markdown("""
        **Purpose**: Estimate uncertainty without distributional assumptions.

        **Method**: Percentile Bootstrap (n=10,000 resamples)
        1. Resample innings with replacement (same sample size)
        2. Compute statistic (career SR, boundary rate, batting average) for each resample
        3. Take 2.5th and 97.5th percentiles as 95% CI

        **Statistics Supported**:
        - Career Strike Rate (total runs / total balls)
        - Boundary Rate (boundaries / balls faced)
        - Batting Average (runs / dismissals)
        - Average Innings Strike Rate
        - Difference between two players

        **Advantages**: No normality assumption, works for any statistic, captures true sampling variability.

        **Cricket Note**: Resampling is done at the **innings level** to preserve within-player correlation structure.
        """)

        st.latex(r"""
        \text{CI}_{95\%} = [\hat{\theta}_{(0.025)}, \hat{\theta}_{(0.975)}]
        \quad \text{where } \hat{\theta}_{(p)} \text{ is the } p\text{-th percentile of bootstrap estimates}
        """)

    # Method 4: Regression to Mean
    with st.expander("📉 **4. Regression to Mean Analysis**", expanded=False):
        st.markdown("""
        **Purpose**: Quantify how much extreme early-career performance regresses toward league average.

        **Method**:
        1. Split each player's career chronologically into two halves (NTILE(2) by match date)
        2. Compute aggregate strike rate for each half
        3. Compare first-half vs second-half performance

        **Theory vs Experiment**:
        - **Theoretical Prediction**: If reliability = r (correlation between halves),
          expected 2nd half = League Avg + r × (1st half - League Avg)
        - **Observed**: Actual 2nd half performance
        - **Residual** = Observed regression - Expected regression

        **Key Metrics**:
        - Regression Magnitude = 1st Half SR - 2nd Half SR
        - Correlation between halves (reliability estimate)
        - R² = Correlation² (proportion of variance explained)
        - Regression line slope (should be < 1 if regression to mean exists)

        **Interpretation**:
        - Positive regression = player slowed down (common for high early performers)
        - Negative regression = player improved (rare, indicates skill development)
        - Large residuals = over/under-performance relative to statistical expectation
        """)

    # Method 5: Beta-Binomial Shrinkage
    with st.expander("🎯 **5. Beta-Binomial Shrinkage (Empirical Bayes)**", expanded=False):
        st.markdown("""
        **Purpose**: Stabilize boundary rate estimates for players with small sample sizes.

        **Model**:
        - Boundaries ~ Binomial(balls_faced, p) where p = true boundary probability
        - Prior: p ~ Beta(α, β) estimated from league-wide data (Empirical Bayes)
        - Posterior: p | data ~ Beta(α + boundaries, β + balls_faced - boundaries)
        - **Shrunken Estimate** = Posterior Mean = $\frac{\alpha + \text{boundaries}}{\alpha + \beta + \text{balls\_faced}}$

        **Prior Estimation**:
        - **Method of Moments**: Match sample mean and variance of player boundary rates
        - **MLE**: Maximum likelihood estimation via optimization

        **Shrinkage Factor** = $\frac{\alpha + \beta}{\alpha + \beta + \text{balls\_faced}}$
        - Players with fewer balls faced → more shrinkage toward league average
        - Players with many balls faced → minimal shrinkage (data dominates)

        **Credible Intervals**: 95% interval from Beta posterior quantiles

        **Why This Matters**: Raw boundary rates for players with <500 balls are unreliable.
        Shrinkage provides better estimates for ranking and comparison.
        """)

        st.latex(r"""
        \text{Posterior Mean} = \frac{\alpha + x}{\alpha + \beta + n}
        \quad \text{Shrinkage} = \frac{\alpha + \beta}{\alpha + \beta + n}
        """)

    # Method 6: Multiple Comparisons
    with st.expander("⚖️ **6. Multiple Comparisons Correction**", expanded=False):
        st.markdown("""
        **Purpose**: Control false positives when making many simultaneous comparisons.

        **Methods Implemented**:
        1. **Bonferroni**: FWER control, very conservative. p_adj = min(p × m, 1)
        2. **Holm-Bonferroni**: Step-down FWER control, more powerful than Bonferroni
        3. **Benjamini-Hochberg (BH)**: FDR control, assumes independence/positive dependence
        4. **Benjamini-Yekutieli (BY)**: FDR control under arbitrary dependence

        **When to Use Which**:
        - **m ≤ 5 tests**: Holm-Bonferroni (FWER control with good power)
        - **5 < m ≤ 20**: Benjamini-Hochberg (FDR control, standard for moderate m)
        - **m > 20**: Benjamini-Hochberg (standard for high-dimensional testing)
        - **Unknown dependence**: Benjamini-Yekutieli (conservative but safe)

        **Application**: Comparing one player against many others, or ranking many players simultaneously.
        """)

    # Method 7: Player Comparison Tool
    with st.expander("⚔️ **7. Integrated Player Comparison Tool**", expanded=False):
        st.markdown("""
        **Purpose**: Unified interface answering "Is Player A really better than Player B?"

        **Integrates All Modules**:
        1. Descriptive statistics for both players
        2. Hypothesis tests (Welch's t + Mann-Whitney U)
        3. Bootstrap CIs for each player and difference
        4. Regression to mean analysis for both
        5. Beta-binomial shrinkage for boundary rates
        6. Multiple comparisons when comparing against many players

        **Verdict Logic**:
        - **High Confidence**: Both parametric test significant AND bootstrap CI excludes zero
        - **Medium Confidence**: One test significant OR bootstrap CI excludes zero
        - **Low Confidence**: Neither test significant AND bootstrap CI includes zero

        **Key Findings Reported**:
        - Direction and magnitude of difference
        - Statistical significance with p-values and effect sizes
        - Uncertainty quantification via bootstrap CIs
        - Regression to mean context
        - Shrinkage-adjusted boundary rates
        """)

    # Sample Size Guidelines
    with st.expander("📏 **Sample Size Guidelines & Limitations**", expanded=False):
        st.markdown("""
        **Minimum Sample Sizes Used**:
        - **Innings-level analysis**: ≥ 10 balls faced per innings
        - **Career analysis**: ≥ 200 balls faced total
        - **Regression to mean**: ≥ 100 balls per career half
        - **Beta-binomial shrinkage**: ≥ 200 balls for prior estimation

        **Limitations**:
        1. **Survivorship Bias**: Only players with sufficient career balls are analyzed
        2. **Era Effects**: No adjustment for changing game conditions across seasons
        3. **Opposition Quality**: No adjustment for bowler quality faced
        4. **Venue Effects**: No park factor adjustments
        5. **Toss/Match Situation**: Not accounted for in current model

        **Assumptions**:
        - Innings are independent (may not hold due to form/momentum)
        - Beta-binomial assumes constant boundary probability per player
        - Bootstrap assumes innings are exchangeable
        - Career halves split assumes stationarity within halves

        **Reproducibility**: All stochastic methods use fixed random seed (42).
        """)

    # References
    with st.expander("📖 **References & Further Reading**", expanded=False):
        st.markdown("""
        **Statistical Methods**:
        - Efron & Tibshirani (1993). *An Introduction to the Bootstrap*
        - Gelman et al. (2013). *Bayesian Data Analysis*, 3rd ed.
        - Benjamini & Hochberg (1995). Controlling the False Discovery Rate. JRSS-B.
        - Holm (1979). A Simple Sequentially Rejective Multiple Test Procedure. Scand J Stat.

        **Cricket Analytics**:
        - Kimber & Hansford (1993). A Statistical Analysis of Batting in Cricket. JRSS-A.
        - Stern (2016). *Cricket Statistics and Analysis*.
        - Cricsheet data format documentation.

        **Project Context**:
        - Probability & Statistics Project Handbook, BTech CSE, JG University
        - Project 11: Sports Analytics — "Is the Player Really Better?"
        - Dataset: Cricsheet IPL ball-by-ball (18 seasons, 1,243 matches, 295,557 deliveries)
        """)


# ============================================================
# Main App
# ============================================================

def main():
    """Main dashboard application."""

    # Sidebar navigation
    with st.sidebar:
        st.markdown("# 🏏 IPL Analytics")
        st.markdown("---")

        page = st.radio(
            "Navigate",
            [
                "🏠 Overview",
                "👤 Player Analysis",
                "⚔️ Player Comparison",
                "🎯 Shrinkage Rankings",
                "📉 Regression to Mean",
                "📚 Methodology"
            ],
            label_visibility="collapsed"
        )

        st.markdown("---")
        st.caption("IPL Sports Analytics Dashboard")
        st.caption("Project 11: Is the Player Really Better?")
        st.caption("BTech CSE, JG University")

    # Route to page
    if page == "🏠 Overview":
        page_overview()
    elif page == "👤 Player Analysis":
        page_player_analysis()
    elif page == "⚔️ Player Comparison":
        page_player_comparison()
    elif page == "🎯 Shrinkage Rankings":
        page_shrinkage_rankings()
    elif page == "📉 Regression to Mean":
        page_regression_to_mean()
    elif page == "📚 Methodology":
        page_methodology()


if __name__ == "__main__":
    main()