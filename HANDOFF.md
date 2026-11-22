# Sports Analytics Project Handoff Document

**Project**: Project 11: Sports Analytics — Is the Player Really Better?
**Course**: Probability & Statistics, BTech CSE, JG University
**Last Updated**: 2026-11-22
**Status**: Phase 7 Complete (Final Report). All phases complete.

---

## 1. Project Objective & Requirements

### 1.1 Real-World Use Case
Teams and analysts decide on selection and auctions by comparing players, but small samples mislead. The project must compare batters or bowlers using IPL ball-by-ball data, test whether differences in strike rate or economy are statistically meaningful, and show how much a small-sample average should be trusted. Rank players using a shrinkage estimate.

### 1.2 Statistics You Must Apply (from Handbook)
- **Mean vs Median** — When to use which, effect of skew/outliers
- **Hypothesis tests for two groups** — Welch's t-test, Mann-Whitney U
- **Bootstrap confidence intervals** — Percentile method
- **Regression to the mean** — Split career into two halves, show extreme first-half performance regresses
- **Beta-binomial shrinkage (Empirical Bayes)** — Shrink observed rates toward league average
- **Multiple comparisons correction** — Benjamini-Hochberg FDR

### 1.3 DBMS & DSA Requirements
- Load ball-by-ball data into relational tables
- SQL to compute per-player and per-season aggregates
- ER diagram, CREATE TABLE scripts, at least 5 analytical SQL queries (aggregations, joins, window functions)

### 1.4 Theory vs Experiment (Required)
Split each player's career into two halves and show that extreme performance in the first half regresses toward the average in the second half.

### 1.5 Stretch Goal
Build a player comparison tool with uncertainty bars.

---

## 2. Dataset Source & Format

### 2.1 Source
**Cricsheet IPL data** — `data/raw/ipl_csv2.zip`
- Ashwin Raman's CSV format (2 files per match)
- 18 IPL seasons (2008-2025, excluding 2020 which was in UAE)

### 2.2 Original Format
**Two CSV files per match:**
1. `<match_id>.csv` — Ball-by-ball data (27 columns)
2. `<match_id>_info.csv` — Match metadata

**Ball-by-ball columns (27):**
```
match_id, season, start_date, venue, innings, ball, actual_delivery,
batting_team, bowling_team, striker, non_striker, bowler,
runs_off_bat, extras, wides, noballs, byes, legbyes, penalty,
non_boundary, wicket_type, player_dismissed, other_wicket_type,
other_player_dismissed, fielder_1, fielder_2, fielder_3
```

### 2.3 Data Types & Missing Values
- `runs_off_bat`: 0-6 (int), missing = empty string
- Extras fields (`wides`, `noballs`, `byes`, `legbyes`, `penalty`): int, missing = empty string
- `wicket_type`: string (bowled, caught, lbw, run out, stumped, hit wicket, obstructing the field), missing = empty
- `player_dismissed`: player name, missing = empty
- `ball`: string like "0.1" to "19.6", wides show "19.7", "19.8"
- `actual_delivery`: sequential integer per innings (includes wides)
- `innings`: 1-2 regular, 3+ super overs

### 2.4 Cricket-Specific Representations
| Concept | Cricsheet Representation |
|---------|-------------------------|
| Batter runs | `runs_off_bat` (0-6) |
| Extras breakdown | Separate columns: wides, noballs, byes, legbyes, penalty |
| Balls faced | Count of legal deliveries (excludes wides, includes no-balls) |
| Boundaries | `runs_off_bat` = 4 or 6; distinguish from running 4/6 via `non_boundary` field |
| Dismissals | `wicket_type` + `player_dismissed`; `other_wicket_type` for second dismissal |
| Wickets credited to bowler | All except run out, retired out, obstructing field |
| Seasons | 18 seasons: 2007/08, 2009, 2009/10, 2010, ..., 2025 |

### 2.5 Data Quality Issues Identified
1. **Empty strings for numeric fields** — All extras fields use "" instead of 0
2. **Team name changes** — 5 teams have historical names (Delhi Daredevils→Capitals, Kings XI Punjab→Punjab Kings, RCB→RC Bengaluru, Rising Pune Supergiant→Supergiants, Deccan Chargers→Sunrisers Hyderabad)
3. **Duplicate deliveries** — Same match_id, innings, ball can appear multiple times
4. **Missing player registry IDs** — Cricsheet uses names only; need canonical registry mapping
5. **Super over innings** — innings 3-6 exist but are rare
6. **Inconsistent venue names** — Same venue spelled differently across seasons
7. **Penalty runs** — Rare but present; must be handled in total_runs
8. **Two dismissals per ball** — `other_wicket_type` / `other_player_dismissed` for run-out + caught etc.
9. **Wide/No-ball ball numbering** — `ball` shows "19.7" for wides; `actual_delivery` is sequential
10. **Missing match_info files** — Some matches lack _info.csv

---

## 3. Project Architecture & Folder Structure

```
Sports-Analytics/
├── data/
│   ├── raw/
│   │   └── ipl_csv2.zip          # Original Cricsheet data (NEVER MODIFY)
│   └── processed/                # Pipeline outputs (optional)
├── logs/
│   └── data_quality_report.json  # Validation report
├── requirements/
│   └── Probability & Statistics Project Handbook.pdf
├── sql/
│   ├── schema.sql                # Normalized CREATE TABLE + indexes + views
│   ├── analysis_queries.sql      # 10 analytical queries
│   ├── seed_database.py          # DatabaseSeeder class
│   └── er_diagram.md             # Mermaid ER diagram
├── src/
│   ├── data_loader.py            # Extract: RawDelivery, MatchInfo, DataLoader
│   ├── data_cleaning.py          # Transform: CleanedDelivery, DataCleaner
│   ├── data_processor.py         # Aggregate: 4-level derived records
│   ├── data_validation.py        # Validate: DataValidator, quality report
│   ├── pipeline.py               # Main orchestration script
│   ├── statistics/               # Statistical engine (Phase 4)
│   │   ├── mean_median.py
│   │   ├── hypothesis_testing.py
│   │   ├── bootstrap_ci.py
│   │   ├── regression_to_mean.py
│   │   ├── beta_binomial.py
│   │   ├── multiple_comparisons.py
│   │   ├── player_comparison.py
│   │   └── data_access.py
│   └── dashboard.py              # Streamlit Dashboard (Phase 6)
├── tests/
│   ├── test_data_processing.py   # 26 unit tests (all passing)
│   └── test_statistics.py        # 44 unit tests (42 pass, 2 skip)
├── notebooks/                    # Analysis outputs
│   ├── analysis_results.json
│   ├── distributions.png
│   └── regression_to_mean.png
├── reports/                      # Phase 7 report
│   ├── generate_report.py        # PDF generator (fpdf2)
│   └── final_report.pdf          # 15-page final report
├── requirements.txt              # Python dependencies
├── HANDOFF.md                    # This file
└── CLAUDE.md                     # Permanent instructions
```

---

## 4. Implementation Completed (Phases 1-5)

### 4.1 Phase 1: Inspection & Planning ✅
- Inspected raw zip file structure using `zipfile` + `csv` (no pandas)
- Extracted handbook content via `pdftotext`
- Documented all 27 columns, data types, missing patterns
- Identified 10 data quality issues with mitigations
- Designed normalized PostgreSQL/SQLite schema with canonical team names
- Created 6-phase implementation plan

### 4.2 Phase 2: Data Ingestion & Preprocessing Pipeline ✅

**`src/data_loader.py`** — Extraction
- `RawDelivery` dataclass: All 27 raw fields as strings
- `MatchInfo` dataclass: Match metadata from _info.csv
- `DataLoader` class: Context manager for zip file
- `load_all_matches()`: Iterates all match IDs, yields RawDelivery
- `load_match_info(match_id)`: Parses _info.csv
- `load_season_mapping()`: Maps 18 season names to (start_year, end_year)

**`src/data_cleaning.py`** — Transformation & Cricket Rules
- `CleanedDelivery` dataclass: 46 fields including all derived cricket fields
- `DataCleaner` class with `TEAM_CANONICAL_NAMES` mapping for 5 teams
- **Cricket scoring rules implemented:**
  - Wides: NOT balls faced, NOT batter runs, ARE bowler conceded runs, NOT legal delivery
  - No-balls: ARE balls faced, runs_off_bat count for batter, +1 run for bowler, ARE legal delivery
  - Byes/Leg-byes: NOT batter runs, NOT bowler conceded runs, ARE legal delivery
  - Boundaries: Distinguished from running 4/6 via `runs_off_bat` (4/6 = boundary)
  - Bowler wickets: All except run out, retired out, obstructing field
- `canonicalize_team_name()`: Maps historical → canonical
- Quality flags for suspicious records

**`src/data_processor.py`** — 4-Level Aggregation
- **Innings level**: `BatterInnings`, `BowlerInnings`
- **Season level**: `BatterSeason`, `BowlerSeason`
- **Career level**: `BatterCareer`, `BowlerCareer`
- `DataProcessor` class: Single-pass processing, dict-based aggregation
- Keys: `(player, match_id, innings)` for innings; `(player, season)` for season; `player` for career

**`src/data_validation.py`** — Validation & Quality Report
- `ValidationResult` dataclass: check_name, passed, message, severity
- `DataQualityReport` dataclass: All counts, validation results, quality issues, duplicates, summary stats
- `DataValidator` class: 8 validation methods
  1. Raw delivery count vs expected
  2. Cleaned delivery count
  3. Batter innings non-empty
  4. Bowler innings non-empty
  5. Run conservation (total_runs = batter_runs + extras)
  6. Ball accounting (legal deliveries counted correctly)
  7. Dismissal consistency
  8. Season mapping completeness
- `run_validation_pipeline()`: End-to-end validation

**`tests/test_data_processing.py`** — 26 Unit Tests
- `TestDataLoader`: Season mapping, sort keys
- `TestDataCleaning`: 12 tests covering all cricket rules
- `TestDataProcessor`: 8 tests for aggregation, edge cases
- `TestDataValidation`: End-to-end pipeline test
- All tests pass (verified)

### 4.3 Phase 3: Relational Database ✅

**`sql/schema.sql`** — Normalized Schema (11 tables)
| Table | Purpose | Key Fields |
|-------|---------|------------|
| `seasons` | 18 IPL seasons | season_id PK, start_year, end_year, name |
| `teams` | Canonical team names | team_id PK, canonical_name UK, short_name |
| `team_aliases` | Historical names | alias_id PK, team_id FK, alias_name, valid_from/to |
| `venues` | Stadiums | venue_id PK, name UK, city, country |
| `players` | Player registry | player_id PK, registry_id UK, full_name, short_name, dob, styles |
| `player_aliases` | Name variations | alias_id PK, player_id FK, alias_name, source |
| `matches` | Match metadata | match_id PK, cricsheet_id UK, season_id FK, team_a/b FK, venue_id FK, date, toss, result |
| `innings` | Per-innings summary | innings_id PK, match_id FK, innings_number, batting/bowling_team FK, runs, wickets |
| `deliveries` | Ball-by-ball (295,557 rows) | delivery_id PK, innings_id FK, match_id FK, over, ball_in_over, actual_delivery_seq, striker/non_striker/bowler FK, all runs/extras, wicket info, derived flags |
| `player_innings` | Per-player per-innings (18,768 rows) | player_innings_id PK, innings_id FK, match_id FK, player_id FK, team_id FK, is_batter/is_bowler, runs, balls, 4s/6s, wickets, economy |
| `player_seasons` | Pre-computed season aggregates | player_season_id PK, player_id FK, season_id FK, team_id FK, all batting/bowling stats |

**Indexes**: All FKs indexed; composite on (match_id, innings_number), (player_id, season_id), (innings_id, over_number, ball_in_over)

**Views** (4): `v_batter_career`, `v_bowler_career`, `v_batter_season`, `v_bowler_season`

**`sql/analysis_queries.sql`** — 10 Analytical Queries
1. Career batting aggregates (min 200 balls)
2. Career bowling aggregates (min 100 balls)
3. Season batting aggregates with ROW_NUMBER ranking
4. Season bowling aggregates
5. Innings-level stats with ROW_NUMBER, NTILE, PERCENT_RANK window functions
6. Boundary percentage analysis (4s/6s per 100 balls)
7. Strike rate leaders with qualification (min 200 balls)
8. First-half vs second-half career comparison (regression to mean)
9. Powerplay (1-6) vs Middle (7-15) vs Death (16-20) overs
10. Player comparison with percentiles & z-scores

**`sql/seed_database.py`** — DatabaseSeeder
- Loads pipeline data → populates all 11 tables
- Handles player/team/venue canonicalization with upserts
- Batches deliveries insert (1000 rows/batch)
- Verified: 1,243 matches, 2,514 innings, 295,557 deliveries, 18,768 player_innings
- All 10 queries execute successfully against populated database

**`sql/er_diagram.md`** — Mermaid ER diagram with full schema

---

## 5. Database Schema Details

### 5.1 Key Design Decisions
1. **Canonical team names**: `teams.canonical_name` stores current name; `team_aliases` maps historical names with date ranges
2. **Player registry ID**: Uses Cricsheet's unique `registry_id` as natural key; auto `player_id` as surrogate PK
3. **Deliveries table**: Stores both raw fields AND derived cricket fields (is_legal_delivery, batter_runs, bowler_conceded_runs, is_boundary, etc.)
4. **Innings numbering**: 1-2 = regular; 3+ = super overs
5. **Player innings**: Single row per player per innings; `is_batter`/`is_bowler` flags track dual roles
6. **Views**: Pre-compute career/season aggregates for fast querying

### 5.2 Verified Data Counts
| Table | Rows |
|-------|------|
| seasons | 18 |
| teams | 15 |
| team_aliases | 20 |
| venues | 52 |
| players | 823 |
| player_aliases | ~1,200 |
| matches | 1,243 |
| innings | 2,514 |
| deliveries | 295,557 |
| player_innings | 18,768 |
| player_seasons | ~3,500 |

---

## 6. Files Created/Modified

| File | Purpose | Status |
|------|---------|--------|
| `src/data_loader.py` | Extract from zip, RawDelivery/MatchInfo | ✅ Complete |
| `src/data_cleaning.py` | Transform, cricket rules, canonical teams | ✅ Complete |
| `src/data_processor.py` | 4-level aggregation (innings/season/career) | ✅ Complete |
| `src/data_validation.py` | Validation, quality report | ✅ Complete |
| `src/pipeline.py` | Main orchestration, prints top players | ✅ Complete |
| `tests/test_data_processing.py` | 26 unit tests (all pass) | ✅ Complete |
| `sql/schema.sql` | Normalized CREATE TABLE + indexes + views | ✅ Complete |
| `sql/analysis_queries.sql` | 10 analytical SQL queries | ✅ Complete |
| `sql/seed_database.py` | DatabaseSeeder class | ✅ Complete |
| `sql/er_diagram.md` | Mermaid ER diagram | ✅ Complete |
| `requirements.txt` | Python dependencies | ✅ Complete |
| `logs/data_quality_report.json` | Pipeline validation output | ✅ Generated |
| `src/statistics/` | Statistical engine package | ✅ Complete |
| `src/statistics/mean_median.py` | Descriptive statistics module | ✅ Complete |
| `src/statistics/hypothesis_testing.py` | Welch's t-test, Mann-Whitney U | ✅ Complete |
| `src/statistics/bootstrap_ci.py` | Bootstrap confidence intervals | ✅ Complete |
| `src/statistics/regression_to_mean.py` | Theory vs experiment analysis | ✅ Complete |
| `src/statistics/beta_binomial.py` | Empirical Bayes shrinkage | ✅ Complete |
| `src/statistics/multiple_comparisons.py` | FDR correction (BH) | ✅ Complete |
| `src/statistics/player_comparison.py` | Player comparison tool | ✅ Complete |
| `src/statistics/data_access.py` | Database queries for stats | ✅ Complete |
| `tests/test_statistics.py` | 44 unit tests (42 pass, 2 skip) | ✅ Complete |
| `src/dashboard.py` | Streamlit dashboard (6 pages) | ✅ Complete |
| `reports/generate_report.py` | PDF report generator (fpdf2) | ✅ Complete |
| `reports/final_report.pdf` | 15-page final statistical report | ✅ Generated |

---

## 7. Dependencies & Commands

### 7.1 requirements.txt
```
pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0
statsmodels>=0.14.0
plotly>=5.15.0
streamlit>=1.25.0
pytest>=7.4.0
psycopg2-binary>=2.9.7
sqlalchemy>=2.0.0
matplotlib>=3.7.0
seaborn>=0.12.0
python-dotenv>=1.0.0
pyyaml>=6.0.1
tqdm>=4.65.0
```

### 7.2 Installation
```bash
cd C:/claudepro/Sports-Analytics
pip install -r requirements.txt
```

### 7.3 Run Pipeline
```bash
python src/pipeline.py
```
Outputs: data quality report to `logs/data_quality_report.json`, prints top 10 batters/bowlers

### 7.4 Run Tests
```bash
python -m pytest tests/test_data_processing.py -v
```
All 26 tests pass.

### 7.5 Seed Database
```bash
python sql/seed_database.py
```
Creates `data/ipl_analytics.db` (SQLite)

### 7.6 Run Analytical Queries
```bash
sqlite3 data/ipl_analytics.db < sql/analysis_queries.sql
```

---

## 8. What Has Been Tested

| Component | Test Status |
|-----------|-------------|
| Data loading (all 1,243 matches) | ✅ Verified via pipeline run |
| Cricket scoring rules (wides, no-balls, byes, boundaries, wickets) | ✅ 12 unit tests pass |
| Team name canonicalization (5 teams) | ✅ Unit test passes |
| 4-level aggregation (innings, season, career) | ✅ 8 unit tests pass |
| Duplicate handling | ✅ Unit test passes |
| Validation pipeline (8 checks) | ✅ End-to-end test passes |
| Database seeding (all 11 tables) | ✅ Verified row counts |
| All 10 analytical queries | ✅ Execute successfully |

---

## 9. What Remains Untested / Not Implemented

| Component | Status |
|-----------|--------|
| **Phase 5: Statistical Analysis Notebook** | ✅ COMPLETE |
| - Statistical analysis notebook with actual results | ✅ |
| - Strike rate distributions | ✅ |
| - Regression to mean visualization | ✅ |
| - Bootstrap CIs for players | ✅ |
| **Phase 6: Streamlit Dashboard** | ✅ COMPLETE |
| - Overview page with league statistics | ✅ |
| - Player Analysis with Bootstrap CIs | ✅ (fixed KeyError: 'total_balls_faced' → 'balls_faced') |
| - Player Comparison with hypothesis tests | ✅ |
| - Shrinkage Rankings (Empirical Bayes) | ✅ |
| - Regression to Mean visualization | ✅ (fixed TypeError: RegressionSummary attribute access) |
| - Methodology documentation | ✅ |
| **Phase 7: Final Report** | ✅ COMPLETE |
| 15-page PDF report per handbook template | ✅ Generated: reports/final_report.pdf |

| **PostgreSQL Migration** | ⚠️ OPTIONAL |
| **PostgreSQL Migration** | ⚠️ OPTIONAL |
| Currently SQLite; handbook mentions PostgreSQL | Document if needed |

---

## 10. Implementation Details

### Phase 4: Statistical Engine (COMPLETE)
Created `src/statistics/` package with 7 modules:

**Module 1: Descriptive Statistics** (`mean_median.py`)
- `MeanMedianAnalyzer.analyze_innings_strike_rates()` - Innings-level SR analysis with skewness/kurtosis
- `MeanMedianAnalyzer.analyze_career_strike_rates()` - Career-level analysis
- `MeanMedianAnalyzer.analyze_average_innings_strike_rate()` - Boundary rate analysis

**Module 2: Hypothesis Testing** (`hypothesis_testing.py`)
- `HypothesisTester.welch_t_test()` - Welch's t-test with Cohen's d, CI
- `HypothesisTester.mann_whitney_u()` - Mann-Whitney U test
- `HypothesisTester.compare_players()` - Comprehensive comparison

**Module 3: Bootstrap Confidence Intervals** (`bootstrap_ci.py`)
- `BootstrapCI.player_career_sr_ci()` - Career strike rate CI
- `BootstrapCI.player_boundary_rate_ci()` - Boundary rate CI
- `BootstrapCI.compare_players_ci()` - Difference CI between players

**Module 4: Regression to Mean** (`regression_to_mean.py`)
- `RegressionToMean.analyze_player()` - Single player career split
- `RegressionToMean.analyze_all_players()` - League-wide analysis
- `RegressionToMean.theory_vs_experiment()` - Theory vs experimental comparison
- `RegressionToMean.identify_overperformers_underperformers()` - Player identification

**Module 5: Beta-Binomial Shrinkage** (`beta_binomial.py`)
- `BetaBinomialShrinkage.estimate_prior_moments()` - Method of moments prior
- `BetaBinomialShrinkage.estimate_prior_mle()` - MLE prior
- `BetaBinomialShrinkage.analyze_player()` - Single player shrinkage
- `BetaBinomialShrinkage.analyze_all_players()` - League-wide shrinkage
- `BetaBinomialShrinkage.compare_raw_vs_shrunken()` - Ranking comparison

**Module 6: Multiple Comparisons** (`multiple_comparisons.py`)
- `MultipleComparisons.holm_bonferroni()` - Holm-Bonferroni correction
- `MultipleComparisons.benjamini_hochberg()` - BH FDR correction
- `MultipleComparisons.benjamini_yekutieli()` - BY conservative correction

**Module 7: Player Comparison Tool** (`player_comparison.py`)
- `PlayerComparisonTool.compare()` - Full player comparison
- `PlayerComparisonTool.compare_multiple()` - Multiple player comparison
- `PlayerComparisonTool.get_player_summary()` - Player statistics summary

**Data Access Module** (`data_access.py`)
- Database queries for batter/bowler career/innings data
- `get_batter_career_balls_boundaries()` - Career boundaries data
- `get_boundary_rate_by_player()` - Per-player boundary rates

**Output**: `tests/test_statistics.py` with 44 tests (42 passed, 2 skipped)

### Phase 5: Statistical Analysis Notebook ✅ COMPLETE

**Execution Results** (from actual IPL data):

**Descriptive Statistics:**
- Career Strike Rate (min 200 balls): Mean=133.35, Median=133.14, Skewness=0.67, Kurtosis=2.50
- League-wide Innings SR (min 10 balls): Mean=134.58, Median=130.77, Skewness=0.63, Kurtosis=1.23
- Distribution is positively skewed (mean > median), justifying non-parametric alternatives

**Hypothesis Tests (4 player pairs compared):**
| Comparison | Welch's t-test p | Mann-Whitney p | Outcome |
|------------|-----------------|----------------|---------|
| V Kohli vs RG Sharma | 0.8903 | 0.6229 | No significant diff |
| CH Gayle vs AB de Villiers | 0.7239 | 0.5947 | No significant diff |
| DA Warner vs KL Rahul | 0.2677 | 0.1385 | No significant diff |
| MS Dhoni vs SV Samson | 0.9148 | 0.8221 | No significant diff |

**Bootstrap CIs (95%, n=10,000):**
| Player | Estimate | CI Lower | CI Upper |
|--------|----------|----------|----------|
| V Kohli | 136.5 | 132.0 | 140.9 |
| RG Sharma | 137.2 | 132.1 | 142.1 |
| CH Gayle | 152.8 | 143.4 | 162.1 |
| AB de Villiers | 155.7 | 146.9 | 164.6 |
| DA Warner | 142.8 | 137.0 | 148.7 |
| MS Dhoni | 138.8 | 131.7 | 146.1 |

**Regression to Mean:**
- Correlation: 0.5993, R²: 0.36, Slope: 0.68
- Reliability: 0.599 (substantial measurement error)
- Mean regression: 1.01 points toward mean
- Players regressed: 118, Improved: 95

**Beta-Binomial Shrinkage (Empirical Bayes):**
| Player | Raw Boundary Rate | Shrunken Rate | Shrinkage |
|--------|------------------|---------------|-----------|
| CH Gayle | 22.86% | 6.20% | 73.5% |
| MS Dhoni | 16.15% | 4.97% | 69.9% |
| KL Rahul | 17.88% | 5.69% | 68.8% |

**Multiple Comparisons (12 tests, BH correction):**
- 4 tests significant at α=0.05 after BH correction
- Recommended: V Kohli vs CH Gayle, AB de Villiers, JC Buttler, HH Pandya

**Output Files Generated:**
- `notebooks/analysis_results.json` - Full results in JSON format
- `notebooks/distributions.png` - Distribution visualizations
- `notebooks/regression_to_mean.png` - First vs second half scatter plot

### Phase 6: Streamlit Dashboard (COMPLETE)
Created `src/dashboard.py` with 6 interactive pages:

1. **Overview** — Database statistics (players, innings, deliveries), league strike rate distribution with mean/median/skewness
2. **Player Analysis** — Player selection, career stats, Bootstrap 95% CI for strike rate
3. **Player Comparison** — Two-player comparison, Welch's t-test, effect size (Cohen's d), Bootstrap CI of difference, clear verdict with confidence level
4. **Shrinkage Rankings** — Raw vs Beta-Binomial shrunken boundary rates, rank changes, prior parameters
5. **Regression to Mean** — First half vs second half career scatterplot, OLS trendline, correlation and slope
6. **Methodology** — Statistical methods, assumptions, thresholds, disclosures

**Run Dashboard:**
```bash
streamlit run src/dashboard.py
```

**Features:**
- Uses `@st.cache_resource` for expensive statistical analyzers
- Reuses all Phase 4 statistical modules (no duplicate calculations)
- Actual database queries via `data_access.py`
- Sample sizes displayed alongside all statistics
- Uncertainty intervals shown wherever available
- Clear disclosures: bowling analytics skipped, two bowling tests skipped
- Explains BH correction: 4 non-significant legend-vs-legend pairs (Kohli/Sharma etc.) vs 4 significant Kohli-vs-12-peers tests

### Phase 7: Final Report (COMPLETE)
Created `reports/generate_report.py` using fpdf2 to generate a 15-page PDF report following the handbook's 9-section template:

**Report Sections:**
1. **Executive Summary** — Project scope, data, key question, methodology, and primary findings
2. **Data Description** — Source (Cricsheet IPL, 18 seasons, 1,243 matches, 295,557 deliveries), schema overview, data quality summary
3. **Descriptive Statistics** — Career strike rate mean/median/skewness/kurtosis, league-wide innings SR, boundary rate distributions
4. **Hypothesis Testing** — 4 player pair comparisons (Welch's t-test + Mann-Whitney U), all non-significant, effect sizes (Cohen's d)
5. **Bootstrap Confidence Intervals** — 95% CIs for 6 key players (n=10,000 resamples), percentile method
6. **Regression to the Mean** — Career split analysis: correlation=0.599, slope=0.683, reliability=0.599, 118 regressed/95 improved
7. **Beta-Binomial Shrinkage** — Empirical Bayes for boundary rate, top 8 players with raw vs shrunken rates and shrinkage %
8. **Multiple Comparisons** — 12 tests with BH FDR correction: 4 significant at α=0.05
9. **Conclusions & Limitations** — Summary, key disclosures (bowling skipped, registry incomplete, super overs), future work

**Generated Files:**
- `reports/generate_report.py` — 805-line PDF generator with ReportPDF class (FPDF2)
- `reports/final_report.pdf` — 15 pages, 31KB, all actual data from `notebooks/analysis_results.json`

**Run Report Generator:**
```bash
python reports/generate_report.py
```

---

## 11. Known Errors, Incomplete Tasks & Constraints

### 11.1 Known Issues
1. **Player registry mapping incomplete** — `player_aliases` populated from names only; no external registry ID source used. Some players may have multiple registry_ids or missing IDs.
2. **Super overs** — Included in data but not specially handled in aggregations (treated as regular innings)
3. **Penalty runs** — Added to total_runs but not separately tracked in player_innings
4. **Two dismissals per ball** — `other_wicket_type` logged in deliveries but not fully propagated to player_innings

### 11.2 Fixed Issues
1. **Dashboard Player Analysis KeyError** (2026-11-22) — Fixed `src/dashboard.py` line 159: changed `player_data['total_balls_faced']` to `player_data['balls_faced']` to match the `v_batter_career` view column name.
2. **Dashboard Regression to Mean TypeError** (2026-11-22) — Fixed `src/dashboard.py` lines 294-295: changed dict access `summary['correlation']` and `summary['slope']` to attribute access `summary.correlation` and `summary.slope` since `RegressionSummary` is a dataclass.
3. **Dashboard Data Validation JSON Error** (2026-11-22) — Fixed `src/statistics/data_access.py` `validate_database()` to return dict with table row counts instead of None, so `st.sidebar.json(val)` works correctly.

### 11.2 Important Constraints (from User Requirements)
- **NEVER modify raw source files** — `data/raw/ipl_csv2.zip` is read-only
- **Reproducible pipeline** — Fixed random seeds (numpy, random) in all stochastic code
- **Use actual data only** — Never invent statistical results or player data
- **Follow original dataset format** — Cricsheet CSV, 2 files per match
- **Cricket rules must be correct** — Wides/No-balls/Byes/Boundaries as specified
- **Log rejected/suspicious records** — Quality flags in CleanedDelivery, validation report
- **Handle missing values/duplicates carefully** — Don't silently discard; flag and report

### 11.3 Files That Need Updates When Progressing
- `HANDOFF.md` — Update after each major phase
- `logs/data_quality_report.json` — Regenerated after pipeline changes
- `data/ipl_analytics.db` — Re-seeded after schema/data changes

---

## 12. Quick Reference: Key Classes & Functions

```python
# Data Loading
from src.data_loader import DataLoader, RawDelivery, MatchInfo, load_season_mapping

# Data Cleaning
from src.data_cleaning import DataCleaner, CleanedDelivery, canonicalize_team_name

# Data Processing
from src.data_processor import DataProcessor, BatterInnings, BowlerInnings, BatterSeason, BowlerSeason, BatterCareer, BowlerCareer

# Validation
from src.data_validation import DataValidator, DataQualityReport, run_validation_pipeline

# Pipeline
from src.pipeline import main as run_pipeline

# Database
from sql.seed_database import DatabaseSeeder
```

---

**End of Handoff Document**
*Next session should read this file first, then proceed with Prompt 4 (Statistical Engine).*