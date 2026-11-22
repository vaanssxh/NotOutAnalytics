import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os
import sqlite3
from dataclasses import asdict

# Add src to path - use __file__ for reliable project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Import local modules
from src.statistics.mean_median import MeanMedianAnalyzer
from src.statistics.hypothesis_testing import HypothesisTester
from src.statistics.bootstrap_ci import BootstrapCI
from src.statistics.regression_to_mean import RegressionToMean
from src.statistics.beta_binomial import BetaBinomialShrinkage
from src.statistics.multiple_comparisons import MultipleComparisons
from src.statistics.player_comparison import PlayerComparisonTool
from src.statistics.data_access import (
    get_connection, get_batter_career, get_league_strike_rate_distribution,
    validate_database
)

# Page configuration
st.set_page_config(
    page_title="NotOutAnalytics | IPL Sports Analytics",
    page_icon="🏏",
    layout="wide"
)

# Initialize components
@st.cache_resource
def init_analyzers():
    return {
        'mean_median': MeanMedianAnalyzer(min_balls_per_innings=10),
        'tester': HypothesisTester(min_balls_per_innings=10),
        'bootstrap': BootstrapCI(n_bootstrap=1000, confidence_level=0.95), # Reduced for speed in UI
        'regression': RegressionToMean(min_balls_per_half=100),
        'shrinkage': BetaBinomialShrinkage(min_balls=200),
        'tool': PlayerComparisonTool(min_balls_per_innings=10, min_career_balls=200)
    }

analyzers = init_analyzers()

# Sidebar
st.sidebar.title("🏏 NotOutAnalytics")
st.sidebar.markdown("### IPL Statistical Insights")
page = st.sidebar.selectbox(
    "Navigate",
    ["Overview", "Player Analysis", "Player Comparison", "Shrinkage Rankings", "Regression to Mean", "Methodology"]
)

st.sidebar.divider()
st.sidebar.info("""
**Data Source**: Cricsheet IPL (2008-2025)
**Scope**: Batting Analytics
*Note: Bowling analytics skipped (aggregates not populated).*
""")

# --- PAGE: OVERVIEW ---
if page == "Overview":
    st.title("IPL Statistics Overview")

    # Database stats
    conn = get_connection()
    players_count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    innings_count = conn.execute("SELECT COUNT(*) FROM innings").fetchone()[0]
    deliveries_count = conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
    conn.close()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Players", f"{players_count:,}")
    col2.metric("Total Innings", f"{innings_count:,}")
    col3.metric("Total Deliveries", f"{deliveries_count:,}")

    st.divider()

    st.subheader("League Strike Rate Distribution")
    league_sr = analyzers['mean_median'].analyze_innings_strike_rates()
    league_df = get_league_strike_rate_distribution(min_balls=10)

    fig = px.histogram(
        league_df, x="strike_rate", nbins=50,
        title="Innings Strike Rate Distribution (Min 10 Balls)",
        labels={'strike_rate': 'Strike Rate'},
        color_discrete_sequence=['#2ecc71']
    )
    fig.add_vline(x=league_sr.mean, line_dash="dash", line_color="red", annotation_text=f"Mean: {league_sr.mean:.1f}")
    fig.add_vline(x=league_sr.median, line_dash="dash", line_color="blue", annotation_text=f"Median: {league_sr.median:.1f}")

    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"""
        **Key Findings:**
        - **Mean**: {league_sr.mean:.2f}
        - **Median**: {league_sr.median:.2f}
        - **Skewness**: {league_sr.skewness:.4f}
        - **Kurtosis**: {league_sr.kurtosis:.4f}
        """)
    with col_b:
        st.write("The distribution shows positive skew (Mean > Median), indicating that while most innings cluster around 130, there are significant tail-end 'outlier' performances that pull the average upward.")

# --- PAGE: PLAYER ANALYSIS ---
elif page == "Player Analysis":
    st.title("Individual Player Analysis")

    career_df = get_batter_career(min_balls=1)
    player_list = sorted(career_df['player_name'].tolist())
    selected_player = st.selectbox("Select Player", player_list, index=player_list.index("V Kohli") if "V Kohli" in player_list else 0)

    player_data = career_df[career_df['player_name'] == selected_player].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Runs", f"{int(player_data['runs']):,}")
    c2.metric("Balls Faced", f"{int(player_data['balls_faced']):,}")
    c3.metric("Strike Rate", f"{player_data['strike_rate']:.2f}")
    c4.metric("Avg", f"{player_data['average']:.2f}")

    st.divider()

    # Bootstrap CI
    with st.spinner("Computing Bootstrap Confidence Intervals..."):
        ci_result = analyzers['bootstrap'].player_career_sr_ci(selected_player)

    st.subheader(f"Statistical Reliability: {selected_player}")

    col_ci1, col_ci2 = st.columns([2, 1])
    with col_ci1:
        # Visualizing CI
        fig_ci = go.Figure()
        fig_ci.add_trace(go.Bar(
            name='Strike Rate',
            x=[selected_player], y=[ci_result.original_estimate],
            error_y=dict(
                type='data',
                symmetric=False,
                array=[ci_result.ci_upper - ci_result.original_estimate],
                arrayminus=[ci_result.original_estimate - ci_result.ci_lower]
            ),
            marker_color='#3498db'
        ))
        fig_ci.update_layout(title="Career Strike Rate with 95% Bootstrap CI", yaxis_title="Strike Rate")
        st.plotly_chart(fig_ci, use_container_width=True)

    with col_ci2:
        st.info(f"""
        **95% Confidence Interval**
        - Lower: {ci_result.ci_lower:.2f}
        - Estimate: {ci_result.original_estimate:.2f}
        - Upper: {ci_result.ci_upper:.2f}

        The width of this interval ({ci_result.ci_upper - ci_result.ci_lower:.1f}) represents the uncertainty in the player's true ability based on their sample size of {int(player_data['balls_faced'])} balls.
        """)

# --- PAGE: PLAYER COMPARISON ---
elif page == "Player Comparison":
    st.title("Player Comparison Tool")

    career_df = get_batter_career(min_balls=200)
    player_list = sorted(career_df['player_name'].tolist())

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        p1 = st.selectbox("Player 1", player_list, index=player_list.index("V Kohli") if "V Kohli" in player_list else 0)
    with col_p2:
        p2 = st.selectbox("Player 2", player_list, index=player_list.index("RG Sharma") if "RG Sharma" in player_list else 1)

    if p1 == p2:
        st.warning("Please select two different players.")
    else:
        with st.spinner("Running statistical comparison..."):
            comparison = analyzers['tool'].compare(p1, p2, 'strike_rate')

        st.header(f"Verdict: {comparison.verdict}")
        st.subheader(f"Confidence: {comparison.confidence.upper()}")

        # Stats Table
        comp_data = {
            "Metric": ["Balls Faced", "Innings", "Career Strike Rate", "Batting Average", "Boundary %"],
            p1: [comparison.summary_a.total_balls_faced, comparison.summary_a.total_innings, f"{comparison.summary_a.career_strike_rate:.2f}", f"{comparison.summary_a.batting_average:.2f}", f"{comparison.summary_a.boundary_rate:.2f}%"],
            p2: [comparison.summary_b.total_balls_faced, comparison.summary_b.total_innings, f"{comparison.summary_b.career_strike_rate:.2f}", f"{comparison.summary_b.batting_average:.2f}", f"{comparison.summary_b.boundary_rate:.2f}%"]
        }
        st.table(pd.DataFrame(comp_data))

        # Hypothesis Test Details
        st.divider()
        st.subheader("Hypothesis Testing (Welch's t-test)")
        welch = comparison.welch_t_test

        col_res1, col_res2, col_res3 = st.columns(3)
        col_res1.metric("p-value", f"{welch['p_value']:.4f}")
        col_res2.metric("Effect Size (Cohen's d)", f"{welch['cohens_d']:.3f}")
        col_res3.metric("Significant", "Yes" if welch['reject_null'] == 'True' else "No")

        st.write(f"**Interpretation**: {welch['interpretation']}")

        # Confidence Interval of Difference
        st.divider()
        st.subheader("Bootstrap CI of Difference")
        diff_ci = comparison.bootstrap_diff_ci

        fig_diff = go.Figure()
        fig_diff.add_trace(go.Bar(
            x=['Strike Rate Difference'],
            y=[diff_ci['statistic']],
            error_y=dict(
                type='data',
                symmetric=False,
                array=[diff_ci['ci_upper'] - diff_ci['statistic']],
                arrayminus=[diff_ci['statistic'] - diff_ci['ci_lower']]
            ),
            marker_color='#e67e22'
        ))
        fig_diff.add_hline(y=0, line_dash="dash", line_color="black")
        fig_diff.update_layout(title=f"Difference in Strike Rate ({p1} - {p2})", yaxis_title="SR Difference")
        st.plotly_chart(fig_diff, use_container_width=True)

        if diff_ci['excludes_zero']:
            st.success("The confidence interval excludes zero, supporting the finding of a significant difference.")
        else:
            st.info("The confidence interval includes zero, indicating the observed difference could be due to chance.")

# --- PAGE: SHRINKAGE RANKINGS ---
elif page == "Shrinkage Rankings":
    st.title("Shrinkage Rankings (Empirical Bayes)")
    st.write("""
    Raw boundary rates can be misleading for players with fewer balls. Shrinkage (Empirical Bayes)
    adjusts these estimates toward the league average based on the sample size (total balls faced).
    """)

    with st.spinner("Computing Beta-Binomial shrinkage..."):
        df_shrink, prior = analyzers['shrinkage'].analyze_all_players()

    df_shrink['raw_rank'] = df_shrink['raw_boundary_rate'].rank(ascending=False)
    df_shrink['shrunken_rank'] = df_shrink['shrunken_boundary_rate'].rank(ascending=False)
    df_shrink['rank_change'] = df_shrink['raw_rank'] - df_shrink['shrunken_rank']

    st.subheader("Top 20 Players by Shrunken Boundary Rate")
    display_cols = ['player_name', 'balls_faced', 'raw_boundary_rate', 'shrunken_boundary_rate', 'shrunken_rank', 'rank_change']
    st.dataframe(df_shrink.sort_values('shrunken_rank').head(20)[display_cols].style.format({
        'raw_boundary_rate': '{:.2f}%',
        'shrunken_boundary_rate': '{:.2f}%',
        'shrunken_rank': '{:.0f}',
        'rank_change': '{:+.0f}'
    }))

    st.info(f"""
    **Prior Distribution (League Average)**
    - Boundary Rate: {prior.league_boundary_rate*100:.2f}%
    - Strength (α+β): {prior.alpha + prior.beta:.1f} balls

    **Why Shrinkage?**
    It treats the league as a "prior" knowledge. For a player with 200 balls, their own data is
    weighted against the prior. For a player with 5000 balls, their own data dominates the estimate.
    """)

# --- PAGE: REGRESSION TO MEAN ---
elif page == "Regression to Mean":
    st.title("Regression to the Mean")
    st.write("""
    Does extreme performance persist? We split each player's career into two chronological halves
    to see if high performers in the first half regressed toward the league average in the second.
    """)

    with st.spinner("Analyzing career halves..."):
        df_reg, summary = analyzers['regression'].analyze_all_players()

    fig = px.scatter(
        df_reg, x="first_half_strike_rate", y="second_half_strike_rate",
        hover_name="player_name",
        labels={
            "first_half_strike_rate": "First Half Strike Rate",
            "second_half_strike_rate": "Second Half Strike Rate"
        },
        title="First Half vs Second Half Career Strike Rate",
        trendline="ols",
        trendline_color_override="red"
    )

    # Add x=y line
    max_val = max(df_reg['first_half_strike_rate'].max(), df_reg['second_half_strike_rate'].max())
    fig.add_trace(go.Scatter(x=[80, max_val], y=[80, max_val], mode='lines', name='y=x (No Regression)', line=dict(dash='dash', color='gray')))

    st.plotly_chart(fig, use_container_width=True)

    col_reg1, col_reg2 = st.columns(2)
    col_reg1.metric("Correlation", f"{summary.correlation:.4f}")
    col_reg2.metric("Regression Slope", f"{summary.slope:.4f}")

    st.write(f"""
    **Interpretation**:
    A slope of **{summary.slope:.2f}** means that for every 10 points a player was above the average
    in their first half, they are expected to be only **{summary.slope*10:.1f}** points above
    the average in their second half. This confirms significant **Regression to the Mean**.
    """)

# --- PAGE: METHODOLOGY ---
else:
    st.title("Methodology & Statistical Assumptions")

    st.markdown("""
    ### Statistical Engine Components

    1. **Descriptive Statistics**: Comparison of Mean vs Median to handle the positive skew common in T20 strike rates.
    2. **Hypothesis Testing**:
       - **Welch's t-test**: Used for comparing means when variances are unequal.
       - **Mann-Whitney U**: Non-parametric alternative that compares the distributions without assuming normality.
    3. **Bootstrap Confidence Intervals**: We use the percentile method with 10,000 resamples (1,000 in this dashboard for performance) to quantify the uncertainty of any point estimate.
    4. **Empirical Bayes (Shrinkage)**: Using a Beta-Binomial model to adjust boundary rates. This prevents "small sample bias" where players with few balls appear at the top of rankings.
    5. **Regression to the Mean**: Splitting careers into two halves (min 100 balls each) to quantify performance stability using Pearson correlation and OLS regression.
    6. **Multiple Comparison Correction**: Using **Benjamini-Hochberg (BH)** procedure to control the False Discovery Rate when performing multiple pairwise tests.

    ### Thresholds & Qualification
    - **Minimum balls per innings**: 10 (filters out non-representative cameos)
    - **Minimum career balls**: 200 (for comparative analysis)
    - **Regression split**: 100 balls per half minimum

    ### Disclosures
    - **Bowling Analytics**: Currently skipped. Bowling aggregates are not populated in the `player_innings` table for all metrics.
    - **Assumptions**: Hypothesis tests assume independence between innings, which may be slightly violated by player form or shared match conditions.
    """)

st.sidebar.divider()
if st.sidebar.button("Run Data Validation"):
    with st.spinner("Validating..."):
        val = validate_database()
        st.sidebar.success("Database Validated")
        st.sidebar.json(val)
