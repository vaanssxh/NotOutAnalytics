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
    players_total = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    innings_count = conn.execute("SELECT COUNT(*) FROM innings").fetchone()[0]
    deliveries_count = conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]

    # Qualified batters (min 200 career balls)
    qualified_batters = conn.execute(
        "SELECT COUNT(*) FROM v_batter_career WHERE balls_faced >= 200"
    ).fetchone()[0]

    # Qualified bowlers (min 100 career balls)
    qualified_bowlers = conn.execute(
        "SELECT COUNT(*) FROM v_bowler_career WHERE balls_bowled >= 100"
    ).fetchone()[0]
    conn.close()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Players", f"{players_total:,}")
    col2.metric("Qualified Batters (≥200 balls)", f"{qualified_batters:,}")
    col3.metric("Qualified Bowlers (≥100 balls)", f"{qualified_bowlers:,}")
    col4.metric("Total Deliveries", f"{deliveries_count:,}")

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

    # Boundary Rate (converted to percentage)
    c5 = st.columns(1)[0]
    c5.metric("Boundary %", f"{player_data['boundary_rate']*100:.2f}%")

    st.divider()

    # Bootstrap CI for Strike Rate
    with st.spinner("Computing Bootstrap Confidence Intervals..."):
        ci_sr = analyzers['bootstrap'].player_career_sr_ci(selected_player)
        ci_br = analyzers['bootstrap'].player_boundary_rate_ci(selected_player)

    st.subheader(f"Statistical Reliability: {selected_player}")

    col_ci1, col_ci2 = st.columns(2)

    with col_ci1:
        # Strike Rate Bootstrap Distribution
        sr_boot = analyzers['bootstrap'].player_career_sr_ci(selected_player, return_bootstrap=True)
        if sr_boot.bootstrap_distribution is not None and len(sr_boot.bootstrap_distribution) > 0:
            fig_sr = px.histogram(
                x=sr_boot.bootstrap_distribution, nbins=40,
                title=f"Bootstrap Distribution: Strike Rate ({selected_player})",
                labels={'x': 'Strike Rate', 'y': 'Frequency'},
                color_discrete_sequence=['#3498db']
            )
            fig_sr.add_vline(x=sr_boot.original_estimate, line_dash="dash", line_color="red",
                           annotation_text=f"Estimate: {sr_boot.original_estimate:.1f}")
            fig_sr.add_vline(x=sr_boot.ci_lower, line_dash="dot", line_color="green",
                           annotation_text=f"CI Lower: {sr_boot.ci_lower:.1f}")
            fig_sr.add_vline(x=sr_boot.ci_upper, line_dash="dot", line_color="green",
                           annotation_text=f"CI Upper: {sr_boot.ci_upper:.1f}")
            st.plotly_chart(fig_sr, use_container_width=True)
        else:
            st.info("Bootstrap samples not available for distribution plot")

    with col_ci2:
        # Boundary Rate Bootstrap Distribution
        br_boot = analyzers['bootstrap'].player_boundary_rate_ci(selected_player, return_bootstrap=True)
        if br_boot.bootstrap_distribution is not None and len(br_boot.bootstrap_distribution) > 0:
            fig_br = px.histogram(
                x=br_boot.bootstrap_distribution * 100, nbins=40,
                title=f"Bootstrap Distribution: Boundary Rate ({selected_player})",
                labels={'x': 'Boundary Rate (%)', 'y': 'Frequency'},
                color_discrete_sequence=['#e74c3c']
            )
            fig_br.add_vline(x=br_boot.original_estimate * 100, line_dash="dash", line_color="red",
                           annotation_text=f"Estimate: {br_boot.original_estimate*100:.1f}%")
            fig_br.add_vline(x=br_boot.ci_lower * 100, line_dash="dot", line_color="green",
                           annotation_text=f"CI Lower: {br_boot.ci_lower*100:.1f}%")
            fig_br.add_vline(x=br_boot.ci_upper * 100, line_dash="dot", line_color="green",
                           annotation_text=f"CI Upper: {br_boot.ci_upper*100:.1f}%")
            st.plotly_chart(fig_br, use_container_width=True)
        else:
            st.info("Bootstrap samples not available for distribution plot")

    # Summary table
    st.divider()
    st.subheader("95% Bootstrap Confidence Intervals Summary")
    summary_df = pd.DataFrame({
        "Metric": ["Strike Rate", "Boundary Rate (%)"],
        "Estimate": [f"{ci_sr.original_estimate:.2f}", f"{ci_br.original_estimate*100:.2f}"],
        "CI Lower": [f"{ci_sr.ci_lower:.2f}", f"{ci_br.ci_lower*100:.2f}"],
        "CI Upper": [f"{ci_sr.ci_upper:.2f}", f"{ci_br.ci_upper*100:.2f}"],
        "CI Width": [f"{ci_sr.ci_upper - ci_sr.ci_lower:.2f}", f"{(ci_br.ci_upper - ci_br.ci_lower)*100:.2f}"]
    })
    st.table(summary_df)

    st.caption(f"Based on {int(player_data['balls_faced'])} balls faced. Bootstrap samples: {analyzers['bootstrap'].n_bootstrap}")

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
        col_res3.metric("Significant", "Yes" if welch.get('reject_null', False) else "No")

        st.write(f"**Interpretation**: {welch['interpretation']}")

        # Overall Verdict (based on hypothesis test)
        st.divider()
        st.subheader("Overall Verdict")
        if welch.get('reject_null', False):
            st.success(f"**Verdict**: {comparison.verdict}")
        else:
            st.info(f"**Verdict**: {comparison.verdict}")
        st.write(f"**Confidence**: {comparison.confidence.upper()}")

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

    col_reg1, col_reg2, col_reg3 = st.columns(3)
    col_reg1.metric("Correlation (r)", f"{summary.correlation:.4f}")
    col_reg2.metric("Regression Slope", f"{summary.slope:.4f}")
    col_reg3.metric("R²", f"{summary.r_squared:.4f}")

    st.write(f"""
    **Interpretation**:
    - **Correlation (r = {summary.correlation:.3f})**: Moderate positive correlation between first and second half performance.
      This means early career performance has some predictive power, but there's substantial variability.
    - **Slope = {summary.slope:.3f}**: A slope < 1.0 indicates regression toward the mean. For every 10 points
      a player's first-half strike rate deviates from the league average, their second-half strike rate is expected
      to deviate by only **{summary.slope * 10:.1f} points** (i.e., ~{(1-summary.slope)*100:.0f}% regression toward the mean).
    - **R² = {summary.r_squared:.3f}**: About {summary.r_squared*100:.0f}% of the variance in second-half strike rates
      is explained by first-half performance.
    """)

    # Statistical significance of slope != 1
    st.divider()
    st.subheader("Statistical Significance")

    # Test if slope is significantly different from 1 (no regression)
    # t = (slope - 1) / SE(slope)
    n = summary.n_players
    x = df_reg['first_half_strike_rate'].values
    y = df_reg['second_half_strike_rate'].values
    x_mean = np.mean(x)
    ss_x = np.sum((x - x_mean) ** 2)
    y_pred = summary.slope * x + summary.intercept
    residuals = y - y_pred
    mse = np.sum(residuals ** 2) / (n - 2)
    se_slope = np.sqrt(mse / ss_x)
    t_stat = (summary.slope - 1) / se_slope

    from scipy import stats
    p_value = 2 * stats.t.sf(abs(t_stat), n - 2)

    col_sig1, col_sig2 = st.columns(2)
    col_sig1.metric("t-statistic (slope ≠ 1)", f"{t_stat:.2f}")
    col_sig2.metric("p-value", f"{p_value:.2e}")

    if p_value < 0.05:
        st.success(f"The slope ({summary.slope:.3f}) is **significantly different from 1** (p = {p_value:.2e}). This provides statistical evidence for regression to the mean — extreme first-half performances tend to regress toward the league average in the second half.")
    else:
        st.info(f"The slope ({summary.slope:.3f}) is **not significantly different from 1** (p = {p_value:.3f}). There is insufficient evidence to conclude regression to the mean from this analysis.")

    st.caption(f"Based on {summary.n_players} players with ≥{analyzers['regression'].min_balls_per_half} balls per career half.")

# --- PAGE: METHODOLOGY ---
else:
    st.title("Methodology & Statistical Assumptions")

    st.markdown("""
    This dashboard implements a complete statistical engine for IPL batting analytics.
    Below are the methods, assumptions, and limitations for each component.
    """)

    # --- 1. Data Pipeline ---
    with st.expander("📊 1. Data Pipeline & Quality", expanded=True):
        st.markdown("""
        **Source**: Cricsheet IPL ball-by-ball data (2008-2025), 18 seasons, 1,243 matches, ~295K deliveries.

        **Pipeline Stages**:
        1. **Raw** (`data/raw/`): Immutable Cricsheet CSVs (2 files/match, 27 columns)
        2. **Cleaned** (`data/processed/`): Cricket rules applied (wides ≠ balls faced, no-balls = balls faced,
           byes/leg-byes ≠ batter runs, boundaries from `runs_off_bat=4/6`, bowler wickets exclude run outs)
        3. **Aggregated**: 4-level hierarchy — Innings → Season → Career (batter & bowler)
        4. **Database** (`data/ipl_analytics.db`): Normalized schema (11 tables, 4 views)

        **Quality Controls**:
        - Fixed random seeds (`np.random.seed(42)`, `random.seed(42)`) for reproducibility
        - Validation report on every pipeline run (`validation_report.json`)
        - Quality flags on suspicious records (no silent discards)
        """)

    # --- 2. Statistical Engine ---
    with st.expander("📈 2. Statistical Engine Components", expanded=True):
        st.markdown("""
        #### 2.1 Descriptive Statistics (`mean_median.py`)
        - Mean, median, skewness, kurtosis for strike rates, boundary rates, batting averages
        - Handles positive skew in T20 strike rate distributions

        #### 2.2 Hypothesis Testing (`hypothesis_testing.py`)
        - **Welch's t-test**: Unequal variances, compares means of innings-level metrics
        - **Mann-Whitney U**: Non-parametric, compares full distributions without normality assumption
        - **Cohen's d**: Effect size for practical significance
        - **Recommendation engine**: Chooses test based on normality (Shapiro-Wilk) and variance equality (Levene's)

        #### 2.3 Bootstrap Confidence Intervals (`bootstrap_ci.py`)
        - **Method**: Percentile bootstrap (bias-corrected available)
        - **Resamples**: 10,000 (production) / 1,000 (dashboard for speed)
        - **Confidence level**: 95%
        - **Metrics**: Career SR, Boundary Rate, Batting Average, Avg Innings SR, Difference between players

        #### 2.4 Empirical Bayes Shrinkage (`beta_binomial.py`)
        - **Model**: Boundaries ~ Binomial(balls_faced, p), Prior: p ~ Beta(α, β)
        - **Prior estimation**: Method of moments (default) or MLE (scipy)
        - **Posterior**: Beta(α + boundaries, β + balls_faced - boundaries)
        - **Shrunken estimate**: Posterior mean = (α + boundaries) / (α + β + balls_faced)
        - **Qualification**: Min 200 career balls for prior estimation

        #### 2.5 Regression to Mean (`regression_to_mean.py`)
        - **Split**: Chronological career halves (min 100 balls each half)
        - **Metrics**: Pearson correlation, OLS slope/intercept, regression magnitude
        - **Theory vs Experiment**: Compares observed regression to theoretical prediction from reliability
        - **Significance**: Tests H₀: slope = 1 (no regression) vs H₁: slope < 1

        #### 2.6 Multiple Comparisons (`multiple_comparisons.py`)
        - **Holm-Bonferroni**: Family-wise error rate control
        - **Benjamini-Hochberg (BH)**: False Discovery Rate control (default)
        - **Benjamini-Yekutieli**: FDR under arbitrary dependence
        - **Bonferroni**: Conservative FWER control
        """)

    # --- 3. Thresholds & Qualification ---
    with st.expander("⚙️ 3. Thresholds & Qualification Criteria", expanded=True):
        st.markdown("""
        | Parameter | Value | Rationale |
        |-----------|-------|-----------|
        | Min balls per innings | 10 | Filters non-representative cameos |
        | Min career balls (comparison) | 200 | Ensures stable estimates for hypothesis tests |
        | Min career balls (shrinkage prior) | 200 | Sufficient data for prior estimation |
        | Min balls per career half (regression) | 100 | Each half needs meaningful sample |
        | Bootstrap resamples (dashboard) | 1,000 | Performance vs accuracy tradeoff |
        | Bootstrap resamples (production) | 10,000 | Publication quality |
        | Confidence level | 95% | Standard |
        | Significance level (α) | 0.05 | Standard |
        """)

    # --- 4. Database Views Used ---
    with st.expander("🗄️ 4. Database Views", expanded=True):
        st.markdown("""
        | View | Purpose | Key Columns |
        |------|---------|-------------|
        | `v_batter_career` | Career batting aggregates | `player_name`, `runs`, `balls_faced`, `strike_rate`, `average`, `boundary_rate`, `dismissals` |
        | `v_bowler_career` | Career bowling aggregates | `player_name`, `balls_bowled`, `wickets`, `economy`, `average`, `strike_rate` |
        | `v_batter_season` | Season batting aggregates | Same as career + `season` |
        | `v_bowler_season` | Season bowling aggregates | Same as career + `season` |

        **Note**: `boundary_rate` in database = `boundaries / balls_faced` (fraction, not percentage).
        Dashboard displays multiply by 100 for percentage.
        """)

    # --- 5. Disclosures & Limitations ---
    with st.expander("⚠️ 5. Disclosures & Limitations", expanded=True):
        st.markdown("""
        **Known Limitations**:
        - **Bowling Analytics**: Bowling aggregates exist in career/season views, but `player_innings` table
          does not have populated bowler innings for all metrics. Bowling comparison is disabled.
        - **Independence Assumption**: Hypothesis tests assume independence between innings.
          This may be violated by player form, shared match conditions, or team strategies.
        - **Sample Size**: Some players have few qualifying innings (≥10 balls); bootstrap CIs may be wide.
        - **Temporal Effects**: League-wide strike rates have increased over time; career comparisons
          across eras don't adjust for this.
        - **Positional Context**: Batting position not accounted for — openers vs finishers have different roles.

        **Reproducibility**:
        - All stochastic code uses fixed seeds (`np.random.seed(42)`, `random.seed(42)`)
        - Pipeline can be re-run: `python src/pipeline.py`
        - Database seeded: `python sql/seed_database.py`
        - Statistical analysis: `python execute_analysis.py`
        - Full test suite: `python -m pytest tests/ -v`
        """)

    # --- 6. References ---
    with st.expander("📚 6. References & Handbook Alignment", expanded=True):
        st.markdown("""
        This project follows the **Probability & Statistics Project Handbook** (JG University, BTech CSE):

        - **Section 1**: Exploratory Data Analysis — Distribution visualizations, skewness/kurtosis
        - **Section 2**: Estimation — Bootstrap CIs, Empirical Bayes shrinkage
        - **Section 3**: Hypothesis Testing — Welch's t-test, Mann-Whitney U, effect sizes
        - **Section 4**: Regression — Career split analysis, regression to mean
        - **Section 5**: Multiple Comparisons — Holm-Bonferroni, Benjamini-Hochberg corrections

        **Statistical References**:
        - Efron & Tibshirani (1993): *An Introduction to the Bootstrap*
        - Gelman et al. (2013): *Bayesian Data Analysis* (Empirical Bayes)
        - Benjamini & Hochberg (1995): *Controlling the False Discovery Rate*
        - Handbook: *Probability & Statistics Project Handbook.pdf* (in `requirements/`)
        """)

st.sidebar.divider()
if st.sidebar.button("Run Data Validation"):
    with st.spinner("Validating..."):
        val = validate_database()
        st.sidebar.success("Database Validated")
        st.sidebar.json(val)
