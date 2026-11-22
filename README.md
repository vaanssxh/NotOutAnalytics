# NotOutAnalytics

IPL Sports Analytics using Python, SQL, and statistical methods to evaluate player performance, test statistical significance, estimate uncertainty, and rank players using Beta-Binomial shrinkage.

## Project Overview

This project analyzes 18 seasons of IPL ball-by-ball data (Cricsheet format) to answer: **"Is the player really better?"**

It applies statistical rigor to cricket analytics:
- **Descriptive Statistics**: Mean vs Median, Skewness/Kurtosis
- **Hypothesis Testing**: Welch's t-test, Mann-Whitney U, Effect Sizes (Cohen's d)
- **Bootstrap Confidence Intervals**: Percentile method (10,000 resamples)
- **Regression to the Mean**: Career split analysis
- **Beta-Binomial Shrinkage**: Empirical Bayes for boundary/strike/dismissal rates
- **Multiple Comparisons**: Benjamini-Hochberg FDR correction

## Quick Start

```bash
# Clone and install
git clone https://github.com/vaanssxh/NotOutAnalytics

cd Sports-Analytics

pip install -r requirements.txt

# Run data pipeline (generates quality report)
python src/pipeline.py

# Seed database
python sql/seed_database.py

# Run statistical analysis
python execute_analysis.py

# Launch Streamlit Dashboard //main function of the app
streamlit run src/dashboard.py
```

## Project Structure

```
Sports-Analytics/
├── data/
│   ├── raw/ipl_csv2.zip           # Original Cricsheet data (NEVER MODIFY)
│   └── processed/                  # Pipeline outputs
├── logs/
│   └── data_quality_report.json    # Validation report
├── sql/
│   ├── schema.sql                  # Normalized schema (11 tables, 4 views)
│   ├── analysis_queries.sql        # 10 analytical queries
│   ├── seed_database.py            # DatabaseSeeder
│   └── er_diagram.md               # Mermaid ER diagram
├── src/
│   ├── data_loader.py              # Extract: RawDelivery, MatchInfo, DataLoader
│   ├── data_cleaning.py            # Transform: CleanedDelivery, cricket rules
│   ├── data_processor.py           # Aggregate: 4-level (innings/season/career)
│   ├── data_validation.py          # Validate: DataValidator, quality report
│   ├── pipeline.py                 # Main orchestration
│   ├── statistics/                 # Statistical engine (Phase 4)
│   │   ├── mean_median.py
│   │   ├── hypothesis_testing.py
│   │   ├── bootstrap_ci.py
│   │   ├── regression_to_mean.py
│   │   ├── beta_binomial.py
│   │   ├── multiple_comparisons.py
│   │   ├── player_comparison.py
│   │   └── data_access.py
│   └── dashboard.py                # Streamlit Dashboard (Phase 6)
├── tests/
│   ├── test_data_processing.py     # 26 unit tests
│   └── test_statistics.py          # 44 unit tests (42 pass, 2 skip)
├── notebooks/                      # Analysis outputs
│   ├── analysis_results.json
│   ├── distributions.png
│   └── regression_to_mean.png
└── requirements.txt
```

## Dashboard Pages

The Streamlit dashboard (`src/dashboard.py`) provides 6 interactive pages:

1. **Overview** — League statistics, strike rate distribution
2. **Player Analysis** — Career stats + Bootstrap 95% CI for strike rate
3. **Player Comparison** — Two-player comparison with Welch's t-test, effect size, and Bootstrap CI of difference
4. **Shrinkage Rankings** — Raw vs shrunken boundary rates (Beta-Binomial Empirical Bayes)
5. **Regression to Mean** — First half vs second half career scatterplot
6. **Methodology** — Statistical methods, assumptions, thresholds

### Launch Dashboard

```bash
streamlit run src/dashboard.py
```

Then open http://localhost:8501 in your browser.

### Data Validation Button

The sidebar has a "Run Data Validation" button that checks all 8 database tables and displays row counts as JSON.

## Key Findings (from 18 seasons, 1,243 matches, 295,557 deliveries)

| Metric | Value |
|--------|-------|
| Career SR Mean (min 200 balls) | 133.35 |
| Career SR Median | 133.14 |
| League Innings SR Mean (min 10 balls) | 134.58 |
| League Innings SR Median | 130.77 |
| Regression Correlation | 0.599 |
| Regression Slope | 0.683 |

### Player Comparisons (No Significant Difference)
- V Kohli vs RG Sharma (p=0.89)
- CH Gayle vs AB de Villiers (p=0.72)
- DA Warner vs KL Rahul (p=0.27)
- MS Dhoni vs SV Samson (p=0.91)

### Multiple Comparisons (BH Corrected)
- 4 of 12 Kohli-vs-peer comparisons significant at α=0.05
- Significant: Kohli vs Gayle, de Villiers, Buttler, Pandya

## Testing

```bash
# All tests (68 pass, 2 skip)
python -m pytest tests/ -v

# Data processing tests only
python -m pytest tests/test_data_processing.py -v

# Statistical engine tests only
python -m pytest tests/test_statistics.py -v
```

## Constraints & Disclosures

- **Raw data is read-only**: `data/raw/ipl_csv2.zip` never modified
- **Reproducibility**: Fixed random seeds (`np.random.seed(42)`, `random.seed(42)`)
- **Actual data only**: No synthetic/invented statistics
- **Bowling analytics**: Skipped — bowling aggregates not populated in `player_innings`
- **Two bowling tests**: Skipped in test suite for same reason

## Course Information

- **Course**: Probability & Statistics, BTech CSE, JG University
- **Project**: Project 11 — Sports Analytics
- **Handbook**: `requirements/Probability & Statistics Project Handbook.pdf`