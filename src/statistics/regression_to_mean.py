"""
Module 4: Regression to Mean Analysis

Analyzes regression toward the mean by splitting player careers into halves
and comparing first-half vs second-half performance.

Key concepts:
- Regression to mean: Extreme early performance tends to be followed by more average performance
- Split career chronologically into two halves by matches played
- Compare first-half vs second-half strike rates
- Quantify regression magnitude
- THEORY vs EXPERIMENT: theoretical prediction vs observed data
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

from src.statistics.data_access import (
    get_career_halves_strike_rate,
    get_batter_career,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

np.random.seed(42)


@dataclass
class RegressionResult:
    """Results from regression to mean analysis for a player."""
    player_name: str
    player_id: int
    first_half_strike_rate: float
    second_half_strike_rate: float
    first_half_balls: int
    second_half_balls: int
    first_half_innings: int
    second_half_innings: int
    regression_magnitude: float  # first_half - second_half
    regression_percentage: float  # as % of first half

    @property
    def first_half_sr(self) -> float:
        """Alias for first_half_strike_rate for API compatibility."""
        return self.first_half_strike_rate

    def to_dict(self) -> Dict[str, Any]:
        return {
            'player_name': self.player_name,
            'player_id': self.player_id,
            'first_half_strike_rate': round(self.first_half_strike_rate, 2),
            'second_half_strike_rate': round(self.second_half_strike_rate, 2),
            'first_half_balls': self.first_half_balls,
            'second_half_balls': self.second_half_balls,
            'first_half_innings': self.first_half_innings,
            'second_half_innings': self.second_half_innings,
            'regression_magnitude': round(self.regression_magnitude, 2),
            'regression_percentage': round(self.regression_percentage, 2),
        }


@dataclass
class RegressionSummary:
    """Summary of regression to mean across all qualified players."""
    n_players: int
    mean_first_half_sr: float
    mean_second_half_sr: float
    mean_regression: float
    median_regression: float
    correlation: float
    r_squared: float
    slope: float
    intercept: float
    players_regressed: int
    players_improved: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'n_players': self.n_players,
            'mean_first_half_sr': round(self.mean_first_half_sr, 2),
            'mean_second_half_sr': round(self.mean_second_half_sr, 2),
            'mean_regression': round(self.mean_regression, 2),
            'median_regression': round(self.median_regression, 2),
            'correlation': round(self.correlation, 4),
            'r_squared': round(self.r_squared, 4),
            'slope': round(self.slope, 4),
            'intercept': round(self.intercept, 2),
            'players_regressed': self.players_regressed,
            'players_improved': self.players_improved,
        }


class RegressionToMean:
    """Analyzes regression to mean in player careers."""

    def __init__(self, min_balls_per_half: int = 100):
        self.min_balls_per_half = min_balls_per_half

    def analyze_player(self, player_name: str) -> Optional[RegressionResult]:
        """Analyze regression to mean for a specific player."""
        df = get_career_halves_strike_rate(min_balls_per_half=self.min_balls_per_half)
        player_df = df[df['player_name'] == player_name]

        if player_df.empty:
            logger.warning(f"No data for {player_name} with min {self.min_balls_per_half} balls per half")
            return None

        row = player_df.iloc[0]
        first_half = row['first_half_strike_rate']
        second_half = row['second_half_strike_rate']

        if pd.isna(first_half) or pd.isna(second_half):
            return None

        regression = first_half - second_half
        pct = (regression / first_half * 100) if first_half != 0 else 0

        return RegressionResult(
            player_name=row['player_name'],
            player_id=int(row['player_id']),
            first_half_strike_rate=first_half,
            second_half_strike_rate=second_half,
            first_half_balls=int(row['first_half_balls']),
            second_half_balls=int(row['second_half_balls']),
            first_half_innings=int(row['first_half_innings']),
            second_half_innings=int(row['second_half_innings']),
            regression_magnitude=regression,
            regression_percentage=pct,
        )

    def analyze_all_players(self) -> Tuple[pd.DataFrame, RegressionSummary]:
        """Analyze regression to mean for all qualified players."""
        df = get_career_halves_strike_rate(min_balls_per_half=self.min_balls_per_half)

        # Remove rows with missing strike rates
        df = df.dropna(subset=['first_half_strike_rate', 'second_half_strike_rate'])

        if df.empty:
            raise ValueError("No qualified players found")

        # Compute regression metrics
        df['regression_magnitude'] = df['first_half_strike_rate'] - df['second_half_strike_rate']
        df['regression_percentage'] = (df['regression_magnitude'] / df['first_half_strike_rate'] * 100).replace([np.inf, -np.inf], 0)
        df['regressed'] = df['regression_magnitude'] > 0

        # Summary statistics
        n_players = len(df)
        mean_first = df['first_half_strike_rate'].mean()
        mean_second = df['second_half_strike_rate'].mean()
        mean_regression = df['regression_magnitude'].mean()
        median_regression = df['regression_magnitude'].median()

        # Correlation and regression line
        correlation = df['first_half_strike_rate'].corr(df['second_half_strike_rate'])
        r_squared = correlation ** 2

        # Linear regression: second_half = slope * first_half + intercept
        x = df['first_half_strike_rate'].values
        y = df['second_half_strike_rate'].values
        slope, intercept = np.polyfit(x, y, 1)

        players_regressed = int(df['regressed'].sum())
        players_improved = n_players - players_regressed

        summary = RegressionSummary(
            n_players=n_players,
            mean_first_half_sr=mean_first,
            mean_second_half_sr=mean_second,
            mean_regression=mean_regression,
            median_regression=median_regression,
            correlation=correlation,
            r_squared=r_squared,
            slope=slope,
            intercept=intercept,
            players_regressed=players_regressed,
            players_improved=players_improved,
        )

        # Sort by regression magnitude
        df = df.sort_values('regression_magnitude', ascending=False)

        return df, summary

    def theory_vs_experiment(self) -> Dict[str, Any]:
        """
        Compare theoretical prediction vs experimental observation.

        Theory: If performance is purely skill + noise, and first half is extreme
        due to luck, second half should regress toward league mean.
        Expected regression depends on reliability (signal-to-noise ratio).
        """
        df, summary = self.analyze_all_players()

        # League average strike rate
        career_df = get_batter_career(min_balls=200)
        league_avg_sr = career_df['strike_rate'].mean()

        # Theoretical prediction: regression toward mean
        # If reliability = r, then expected second_half = league_avg + r * (first_half - league_avg)
        # So expected regression = (1 - r) * (first_half - league_avg)
        # We can estimate r from the correlation
        reliability = summary.correlation

        df = df.copy()
        df['league_avg_sr'] = league_avg_sr
        df['expected_second_half'] = league_avg_sr + reliability * (df['first_half_strike_rate'] - league_avg_sr)
        df['expected_regression'] = df['first_half_strike_rate'] - df['expected_second_half']
        df['observed_regression'] = df['regression_magnitude']
        df['residual'] = df['observed_regression'] - df['expected_regression']

        # Overall comparison
        mean_expected_regression = df['expected_regression'].mean()
        mean_observed_regression = df['observed_regression'].mean()

        # Players with extreme first-half performance (top/bottom 25%)
        q75 = df['first_half_strike_rate'].quantile(0.75)
        q25 = df['first_half_strike_rate'].quantile(0.25)

        extreme_high = df[df['first_half_strike_rate'] >= q75]
        extreme_low = df[df['first_half_strike_rate'] <= q25]

        return {
            'summary': summary.to_dict(),
            'league_average_sr': round(league_avg_sr, 2),
            'estimated_reliability': round(reliability, 4),
            'mean_expected_regression': round(mean_expected_regression, 2),
            'mean_observed_regression': round(mean_observed_regression, 2),
            'extreme_high_players': {
                'count': len(extreme_high),
                'mean_first_half': round(extreme_high['first_half_strike_rate'].mean(), 2),
                'mean_second_half': round(extreme_high['second_half_strike_rate'].mean(), 2),
                'mean_observed_regression': round(extreme_high['observed_regression'].mean(), 2),
                'mean_expected_regression': round(extreme_high['expected_regression'].mean(), 2),
            },
            'extreme_low_players': {
                'count': len(extreme_low),
                'mean_first_half': round(extreme_low['first_half_strike_rate'].mean(), 2),
                'mean_second_half': round(extreme_low['second_half_strike_rate'].mean(), 2),
                'mean_observed_regression': round(extreme_low['observed_regression'].mean(), 2),
                'mean_expected_regression': round(extreme_low['expected_regression'].mean(), 2),
            },
            'player_details': df[['player_name', 'first_half_strike_rate', 'second_half_strike_rate',
                                  'regression_magnitude', 'regression_percentage',
                                  'expected_regression', 'residual']].to_dict('records'),
        }

    def identify_overperformers_underperformers(self, threshold_pct: float = 20.0) -> Dict[str, List[Dict]]:
        """Identify players who significantly over/under-performed relative to expectation."""
        theory = self.theory_vs_experiment()

        overperformers = []  # Positive residual = improved more than expected (or regressed less)
        underperformers = []  # Negative residual = regressed more than expected

        for player in theory['player_details']:
            residual = player['residual']
            if residual > threshold_pct:
                overperformers.append(player)
            elif residual < -threshold_pct:
                underperformers.append(player)

        overperformers.sort(key=lambda x: x['residual'], reverse=True)
        underperformers.sort(key=lambda x: x['residual'])

        return {
            'overperformers': overperformers,
            'underperformers': underperformers,
            'threshold_pct': threshold_pct,
        }

    def plot_data(self) -> pd.DataFrame:
        """Get data formatted for scatter plot: first half vs second half strike rate."""
        df, _ = self.analyze_all_players()
        return df[['player_name', 'first_half_strike_rate', 'second_half_strike_rate',
                   'first_half_balls', 'second_half_balls', 'regression_magnitude']].copy()


def run_regression_analysis() -> Dict[str, Any]:
    """Run complete regression to mean analysis."""
    analyzer = RegressionToMean(min_balls_per_half=100)

    logger.info("Analyzing all players...")
    df, summary = analyzer.analyze_all_players()

    logger.info("Theory vs Experiment...")
    theory = analyzer.theory_vs_experiment()

    logger.info("Identifying over/under performers...")
    performers = analyzer.identify_overperformers_underperformers(threshold_pct=20.0)

    return {
        'summary': summary.to_dict(),
        'theory_vs_experiment': theory,
        'overperformers': performers['overperformers'][:10],  # Top 10
        'underperformers': performers['underperformers'][:10],  # Bottom 10
        'all_players': df.to_dict('records'),
    }


if __name__ == '__main__':
    print("Running Regression to Mean Analysis...")
    results = run_regression_analysis()

    print("\n" + "="*60)
    print("REGRESSION TO MEAN SUMMARY")
    print("="*60)
    s = results['summary']
    print(f"Players analyzed: {s['n_players']}")
    print(f"Mean 1st half SR: {s['mean_first_half_sr']:.2f}")
    print(f"Mean 2nd half SR: {s['mean_second_half_sr']:.2f}")
    print(f"Mean regression: {s['mean_regression']:.2f} ({s['players_regressed']} regressed, {s['players_improved']} improved)")
    print(f"Correlation: {s['correlation']:.4f}, R²: {s['r_squared']:.4f}")
    print(f"Regression line: y = {s['slope']:.4f}x + {s['intercept']:.2f}")

    print("\n" + "="*60)
    print("THEORY vs EXPERIMENT")
    print("="*60)
    t = results['theory_vs_experiment']
    print(f"League avg SR: {t['league_average_sr']:.2f}")
    print(f"Estimated reliability: {t['estimated_reliability']:.4f}")
    print(f"Mean expected regression: {t['mean_expected_regression']:.2f}")
    print(f"Mean observed regression: {t['mean_observed_regression']:.2f}")

    print("\nExtreme high performers (top 25% first half):")
    eh = t['extreme_high_players']
    print(f"  Count: {eh['count']}, Mean 1st: {eh['mean_first_half']:.1f}, Mean 2nd: {eh['mean_second_half']:.1f}")
    print(f"  Observed regression: {eh['mean_observed_regression']:.1f}, Expected: {eh['mean_expected_regression']:.1f}")

    print("\nExtreme low performers (bottom 25% first half):")
    el = t['extreme_low_players']
    print(f"  Count: {el['count']}, Mean 1st: {el['mean_first_half']:.1f}, Mean 2nd: {el['mean_second_half']:.1f}")
    print(f"  Observed regression: {el['mean_observed_regression']:.1f}, Expected: {el['mean_expected_regression']:.1f}")

    print("\n" + "="*60)
    print("TOP OVERPERFORMERS (improved more than expected)")
    print("="*60)
    for p in results['overperformers'][:5]:
        print(f"  {p['player_name']}: 1st={p['first_half_strike_rate']:.1f}, 2nd={p['second_half_strike_rate']:.1f}, "
              f"residual={p['residual']:.1f}")

    print("\nTOP UNDERPERFORMERS (regressed more than expected)")
    print("="*60)
    for p in results['underperformers'][:5]:
        print(f"  {p['player_name']}: 1st={p['first_half_strike_rate']:.1f}, 2nd={p['second_half_strike_rate']:.1f}, "
              f"residual={p['residual']:.1f}")

    print("\nDone!")