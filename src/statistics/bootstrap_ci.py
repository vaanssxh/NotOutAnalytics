"""
Module 3: Bootstrap Confidence Intervals

Implements bootstrap percentile method for confidence intervals on cricket metrics.
Uses n=10,000 bootstrap samples for robust estimation.

Key principles:
- Resamples at the innings level (not delivery level) to preserve within-innings correlation
- Percentile method: CI = [2.5th, 97.5th] percentiles of bootstrap distribution
- Fixed random seed for reproducibility
- Supports various metrics: strike rate, boundary rate, average, economy rate, etc.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
import logging

from src.statistics.data_access import (
    get_batter_innings,
    get_bowler_innings,
    get_player_comparison_data,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fixed random seed for reproducibility
np.random.seed(42)


@dataclass
class BootstrapResult:
    """Results from bootstrap confidence interval estimation."""
    metric_name: str
    player_name: Optional[str]
    statistic: Callable
    original_estimate: float
    n_bootstrap: int
    ci_lower: float
    ci_upper: float
    confidence_level: float
    bootstrap_distribution: np.ndarray
    bias: float
    std_error: float

    @property
    def n_samples(self) -> int:
        """Alias for n_bootstrap for API compatibility."""
        return self.n_bootstrap

    @property
    def statistic_value(self) -> float:
        """Returns original_estimate for CI comparisons (statistic is a Callable)."""
        return self.original_estimate

    def to_dict(self) -> Dict[str, Any]:
        return {
            'metric_name': self.metric_name,
            'player_name': self.player_name,
            'original_estimate': round(self.original_estimate, 4),
            'n_bootstrap': self.n_bootstrap,
            'ci_lower': round(self.ci_lower, 4),
            'ci_upper': round(self.ci_upper, 4),
            'confidence_level': self.confidence_level,
            'bias': round(self.bias, 4),
            'std_error': round(self.std_error, 4),
            'ci_width': round(self.ci_upper - self.ci_lower, 4),
        }

    def __str__(self) -> str:
        return (f"Bootstrap CI ({self.confidence_level*100:.0f}%): {self.metric_name}\n"
                f"  Player: {self.player_name or 'League'}\n"
                f"  Estimate: {self.original_estimate:.3f}\n"
                f"  CI: [{self.ci_lower:.3f}, {self.ci_upper:.3f}]\n"
                f"  Bias: {self.bias:.4f}, SE: {self.std_error:.4f}")


class BootstrapCI:
    """Bootstrap confidence intervals using percentile method."""

    def __init__(self, n_bootstrap: int = 10000, confidence_level: float = 0.95,
                 min_balls_per_innings: int = 10, random_seed: int = 42):
        self.n_bootstrap = n_bootstrap
        self.confidence_level = confidence_level
        self.min_balls_per_innings = min_balls_per_innings
        self.random_seed = random_seed
        np.random.seed(random_seed)

    def _bootstrap_sample(self, data: np.ndarray, statistic: Callable,
                          n_samples: int) -> np.ndarray:
        """Generate bootstrap samples of a statistic."""
        n = len(data)
        if n == 0:
            return np.array([])

        bootstrap_stats = np.zeros(n_samples)
        for i in range(n_samples):
            # Sample with replacement
            sample_idx = np.random.choice(n, size=n, replace=True)
            sample = data[sample_idx]
            bootstrap_stats[i] = statistic(sample)

        return bootstrap_stats

    def _percentile_ci(self, bootstrap_stats: np.ndarray) -> Tuple[float, float]:
        """Compute percentile confidence interval."""
        alpha = 1 - self.confidence_level
        lower_pct = alpha / 2 * 100
        upper_pct = (1 - alpha / 2) * 100
        ci_lower = np.percentile(bootstrap_stats, lower_pct)
        ci_upper = np.percentile(bootstrap_stats, upper_pct)
        return ci_lower, ci_upper

    def compute_ci(self, data: np.ndarray, statistic: Callable,
                   metric_name: str = "metric",
                   player_name: Optional[str] = None) -> BootstrapResult:
        """Compute bootstrap CI for a statistic on given data."""
        data = np.array(data, dtype=float)
        data = data[~np.isnan(data)]

        if len(data) < 2:
            raise ValueError(f"Insufficient data: {len(data)} observations")

        # Original estimate
        original = statistic(data)

        # Bootstrap distribution
        bootstrap_stats = self._bootstrap_sample(data, statistic, self.n_bootstrap)

        # Percentile CI
        ci_lower, ci_upper = self._percentile_ci(bootstrap_stats)

        # Bias and standard error
        bias = np.mean(bootstrap_stats) - original
        std_error = np.std(bootstrap_stats, ddof=1)

        return BootstrapResult(
            metric_name=metric_name,
            player_name=player_name,
            statistic=statistic,
            original_estimate=original,
            n_bootstrap=self.n_bootstrap,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=self.confidence_level,
            bootstrap_distribution=bootstrap_stats,
            bias=bias,
            std_error=std_error,
        )

    # --- Pre-defined statistics for cricket metrics ---

    @staticmethod
    def mean_statistic(x: np.ndarray) -> float:
        return np.mean(x)

    @staticmethod
    def median_statistic(x: np.ndarray) -> float:
        return np.median(x)

    @staticmethod
    def strike_rate_statistic(innings_df: pd.DataFrame) -> float:
        """Career aggregate strike rate = total runs / total balls * 100"""
        total_runs = innings_df['runs_scored'].sum()
        total_balls = innings_df['balls_faced'].sum()
        if total_balls == 0:
            return np.nan
        return total_runs / total_balls * 100

    @staticmethod
    def avg_innings_strike_rate(innings_df: pd.DataFrame) -> float:
        """Average of innings strike rates (unweighted)"""
        return innings_df['strike_rate'].mean()

    @staticmethod
    def boundary_rate_statistic(innings_df: pd.DataFrame) -> float:
        """Boundary rate = (fours + sixes) / balls_faced"""
        total_boundaries = innings_df['boundaries'].sum()
        total_balls = innings_df['balls_faced'].sum()
        if total_balls == 0:
            return np.nan
        return total_boundaries / total_balls * 100

    @staticmethod
    def batting_average_statistic(innings_df: pd.DataFrame) -> float:
        """Batting average = total runs / dismissals"""
        total_runs = innings_df['runs_scored'].sum()
        dismissals = innings_df['dismissed'].sum()
        if dismissals == 0:
            return np.nan
        return total_runs / dismissals

    @staticmethod
    def economy_rate_statistic(innings_df: pd.DataFrame) -> float:
        """Bowling economy = runs_conceded / overs_bowled"""
        total_runs = innings_df['runs_conceded'].sum()
        total_balls = innings_df['balls_bowled'].sum()
        if total_balls == 0:
            return np.nan
        return total_runs / (total_balls / 6)

    @staticmethod
    def bowling_average_statistic(innings_df: pd.DataFrame) -> float:
        """Bowling average = runs_conceded / wickets"""
        total_runs = innings_df['runs_conceded'].sum()
        total_wickets = innings_df['wickets'].sum()
        if total_wickets == 0:
            return np.nan
        return total_runs / total_wickets

    @staticmethod
    def bowling_strike_rate_statistic(innings_df: pd.DataFrame) -> float:
        """Bowling strike rate = balls_per_wicket"""
        total_balls = innings_df['balls_bowled'].sum()
        total_wickets = innings_df['wickets'].sum()
        if total_wickets == 0:
            return np.nan
        return total_balls / total_wickets

    # --- Public methods for player analysis ---

    def player_career_sr_ci(self, player_name: str) -> BootstrapResult:
        """Bootstrap CI for player's career aggregate strike rate."""
        df = get_batter_innings(player_name, min_balls=self.min_balls_per_innings)
        if len(df) < 2:
            raise ValueError(f"Insufficient innings for {player_name}")

        # We need to bootstrap at innings level, so use a wrapper
        def sr_statistic(indices):
            sample_df = df.iloc[indices]
            return self.strike_rate_statistic(sample_df)

        # Bootstrap indices
        n = len(df)
        bootstrap_stats = np.zeros(self.n_bootstrap)
        for i in range(self.n_bootstrap):
            idx = np.random.choice(n, size=n, replace=True)
            bootstrap_stats[i] = sr_statistic(idx)

        original = self.strike_rate_statistic(df)
        ci_lower, ci_upper = self._percentile_ci(bootstrap_stats)
        bias = np.mean(bootstrap_stats) - original
        se = np.std(bootstrap_stats, ddof=1)

        return BootstrapResult(
            metric_name="Career Aggregate Strike Rate",
            player_name=player_name,
            statistic=self.strike_rate_statistic,
            original_estimate=original,
            n_bootstrap=self.n_bootstrap,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=self.confidence_level,
            bootstrap_distribution=bootstrap_stats,
            bias=bias,
            std_error=se,
        )

    def player_avg_innings_sr_ci(self, player_name: str) -> BootstrapResult:
        """Bootstrap CI for player's average innings strike rate."""
        df = get_batter_innings(player_name, min_balls=self.min_balls_per_innings)
        values = df['strike_rate'].values
        return self.compute_ci(values, self.mean_statistic,
                               "Average Innings Strike Rate", player_name)

    def player_boundary_rate_ci(self, player_name: str) -> BootstrapResult:
        """Bootstrap CI for player's boundary rate."""
        df = get_batter_innings(player_name, min_balls=self.min_balls_per_innings)
        if len(df) < 2:
            raise ValueError(f"Insufficient innings for {player_name}")

        n = len(df)
        bootstrap_stats = np.zeros(self.n_bootstrap)
        for i in range(self.n_bootstrap):
            idx = np.random.choice(n, size=n, replace=True)
            sample_df = df.iloc[idx]
            bootstrap_stats[i] = self.boundary_rate_statistic(sample_df)

        original = self.boundary_rate_statistic(df)
        ci_lower, ci_upper = self._percentile_ci(bootstrap_stats)
        bias = np.mean(bootstrap_stats) - original
        se = np.std(bootstrap_stats, ddof=1)

        return BootstrapResult(
            metric_name="Boundary Rate (%)",
            player_name=player_name,
            statistic=self.boundary_rate_statistic,
            original_estimate=original,
            n_bootstrap=self.n_bootstrap,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=self.confidence_level,
            bootstrap_distribution=bootstrap_stats,
            bias=bias,
            std_error=se,
        )

    def player_batting_average_ci(self, player_name: str) -> BootstrapResult:
        """Bootstrap CI for player's batting average."""
        df = get_batter_innings(player_name, min_balls=self.min_balls_per_innings)
        if len(df) < 2:
            raise ValueError(f"Insufficient innings for {player_name}")

        n = len(df)
        bootstrap_stats = np.zeros(self.n_bootstrap)
        for i in range(self.n_bootstrap):
            idx = np.random.choice(n, size=n, replace=True)
            sample_df = df.iloc[idx]
            bootstrap_stats[i] = self.batting_average_statistic(sample_df)

        original = self.batting_average_statistic(df)
        ci_lower, ci_upper = self._percentile_ci(bootstrap_stats)
        bias = np.mean(bootstrap_stats) - original
        se = np.std(bootstrap_stats, ddof=1)

        return BootstrapResult(
            metric_name="Batting Average",
            player_name=player_name,
            statistic=self.batting_average_statistic,
            original_estimate=original,
            n_bootstrap=self.n_bootstrap,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=self.confidence_level,
            bootstrap_distribution=bootstrap_stats,
            bias=bias,
            std_error=se,
        )

    def bowler_economy_ci(self, player_name: str) -> BootstrapResult:
        """Bootstrap CI for bowler's economy rate."""
        df = get_bowler_innings(player_name, min_balls=self.min_balls_per_innings)
        if len(df) < 2:
            raise ValueError(f"Insufficient bowling innings for {player_name}")

        n = len(df)
        bootstrap_stats = np.zeros(self.n_bootstrap)
        for i in range(self.n_bootstrap):
            idx = np.random.choice(n, size=n, replace=True)
            sample_df = df.iloc[idx]
            bootstrap_stats[i] = self.economy_rate_statistic(sample_df)

        original = self.economy_rate_statistic(df)
        ci_lower, ci_upper = self._percentile_ci(bootstrap_stats)
        bias = np.mean(bootstrap_stats) - original
        se = np.std(bootstrap_stats, ddof=1)

        return BootstrapResult(
            metric_name="Economy Rate",
            player_name=player_name,
            statistic=self.economy_rate_statistic,
            original_estimate=original,
            n_bootstrap=self.n_bootstrap,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=self.confidence_level,
            bootstrap_distribution=bootstrap_stats,
            bias=bias,
            std_error=se,
        )

    def bowler_average_ci(self, player_name: str) -> BootstrapResult:
        """Bootstrap CI for bowler's bowling average."""
        df = get_bowler_innings(player_name, min_balls=self.min_balls_per_innings)
        if len(df) < 2:
            raise ValueError(f"Insufficient bowling innings for {player_name}")

        n = len(df)
        bootstrap_stats = np.zeros(self.n_bootstrap)
        for i in range(self.n_bootstrap):
            idx = np.random.choice(n, size=n, replace=True)
            sample_df = df.iloc[idx]
            bootstrap_stats[i] = self.bowling_average_statistic(sample_df)

        original = self.bowling_average_statistic(df)
        ci_lower, ci_upper = self._percentile_ci(bootstrap_stats)
        bias = np.mean(bootstrap_stats) - original
        se = np.std(bootstrap_stats, ddof=1)

        return BootstrapResult(
            metric_name="Bowling Average",
            player_name=player_name,
            statistic=self.bowling_average_statistic,
            original_estimate=original,
            n_bootstrap=self.n_bootstrap,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=self.confidence_level,
            bootstrap_distribution=bootstrap_stats,
            bias=bias,
            std_error=se,
        )

    def compare_players_ci(self, player_a: str, player_b: str,
                           metric: str = 'strike_rate') -> Dict[str, Any]:
        """Compare two players with bootstrap CIs for difference."""
        df_a = get_batter_innings(player_a, min_balls=self.min_balls_per_innings)
        df_b = get_batter_innings(player_b, min_balls=self.min_balls_per_innings)

        if len(df_a) < 2 or len(df_b) < 2:
            raise ValueError("Insufficient data for one or both players")

        # Define statistic functions
        if metric == 'strike_rate':
            stat_func = self.strike_rate_statistic
            metric_name = "Career Strike Rate"
        elif metric == 'boundary_rate':
            stat_func = self.boundary_rate_statistic
            metric_name = "Boundary Rate"
        elif metric == 'batting_average':
            stat_func = self.batting_average_statistic
            metric_name = "Batting Average"
        elif metric == 'avg_innings_sr':
            stat_func = self.avg_innings_strike_rate
            metric_name = "Avg Innings Strike Rate"
        else:
            raise ValueError(f"Unknown metric: {metric}")

        # Bootstrap difference
        n_a, n_b = len(df_a), len(df_b)
        bootstrap_diffs = np.zeros(self.n_bootstrap)

        for i in range(self.n_bootstrap):
            idx_a = np.random.choice(n_a, size=n_a, replace=True)
            idx_b = np.random.choice(n_b, size=n_b, replace=True)
            sample_a = df_a.iloc[idx_a]
            sample_b = df_b.iloc[idx_b]
            bootstrap_diffs[i] = stat_func(sample_a) - stat_func(sample_b)

        original_diff = stat_func(df_a) - stat_func(df_b)
        ci_lower, ci_upper = self._percentile_ci(bootstrap_diffs)

        # Check if CI excludes zero
        excludes_zero = ci_lower > 0 or ci_upper < 0

        return {
            'player_a': player_a,
            'player_b': player_b,
            'metric': metric_name,
            'estimate_a': stat_func(df_a),
            'estimate_b': stat_func(df_b),
            'statistic': original_diff,
            'difference': original_diff,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'confidence_level': self.confidence_level,
            'excludes_zero': excludes_zero,
            'interpretation': (f"{player_a} {'higher' if original_diff > 0 else 'lower'} than {player_b} "
                             f"by {abs(original_diff):.2f}. CI: [{ci_lower:.2f}, {ci_upper:.2f}]. "
                             f"{'Significant' if excludes_zero else 'Not significant'} at {self.confidence_level*100:.0f}%"),
        }

    def league_metric_ci(self, metric: str = 'strike_rate',
                         min_balls: int = 10) -> BootstrapResult:
        """Bootstrap CI for league-wide metric."""
        from src.statistics.data_access import get_league_strike_rate_distribution

        if metric == 'strike_rate':
            df = get_league_strike_rate_distribution(min_balls=min_balls)
            values = df['strike_rate'].values
            return self.compute_ci(values, self.mean_statistic,
                                   "League-wide Mean Innings Strike Rate", None)
        elif metric == 'boundary_rate':
            # Need to compute boundary rate per innings
            df = get_league_strike_rate_distribution(min_balls=min_balls)
            # This is simplified - would need boundaries per innings
            raise NotImplementedError("League boundary rate needs boundary data per innings")
        else:
            raise ValueError(f"Unknown league metric: {metric}")


def run_bootstrap_examples() -> Dict[str, Any]:
    """Run example bootstrap analyses."""
    bootstrap = BootstrapCI(n_bootstrap=10000, confidence_level=0.95,
                            min_balls_per_innings=10, random_seed=42)

    players = ['V Kohli', 'RG Sharma', 'CH Gayle', 'AB de Villiers', 'MS Dhoni',
               'DA Warner', 'KL Rahul', 'JC Buttler', 'HH Pandya', 'RG Sharma']

    results = {}

    # Individual player CIs
    for player in players:
        try:
            logger.info(f"Bootstrap CI for {player}...")
            results[f'{player}_career_sr'] = bootstrap.player_career_sr_ci(player).to_dict()
            results[f'{player}_avg_innings_sr'] = bootstrap.player_avg_innings_sr_ci(player).to_dict()
            results[f'{player}_boundary_rate'] = bootstrap.player_boundary_rate_ci(player).to_dict()
            results[f'{player}_batting_avg'] = bootstrap.player_batting_average_ci(player).to_dict()
        except Exception as e:
            logger.warning(f"Could not analyze {player}: {e}")
            results[f'{player}_error'] = str(e)

    # Player comparisons
    pairs = [
        ('V Kohli', 'RG Sharma'),
        ('CH Gayle', 'AB de Villiers'),
        ('DA Warner', 'KL Rahul'),
    ]

    for p1, p2 in pairs:
        try:
            results[f'{p1}_vs_{p2}_sr'] = bootstrap.compare_players_ci(p1, p2, 'strike_rate')
            results[f'{p1}_vs_{p2}_br'] = bootstrap.compare_players_ci(p1, p2, 'boundary_rate')
        except Exception as e:
            logger.warning(f"Comparison {p1} vs {p2} failed: {e}")
            results[f'{p1}_vs_{p2}_error'] = str(e)

    # League-wide
    try:
        results['league_sr'] = bootstrap.league_metric_ci('strike_rate', min_balls=10).to_dict()
    except Exception as e:
        logger.warning(f"League analysis failed: {e}")

    return results


if __name__ == '__main__':
    print("Running Bootstrap CI Examples (n=10,000)...")
    results = run_bootstrap_examples()

    print("\n" + "="*60)
    print("PLAYER CAREER STRIKE RATE CIs")
    print("="*60)
    for key, val in results.items():
        if 'career_sr' in key and 'error' not in key:
            print(f"\n{val.get('player_name', key)}:")
            print(f"  Estimate: {val['original_estimate']:.2f}")
            print(f"  95% CI: [{val['ci_lower']:.2f}, {val['ci_upper']:.2f}]")
            print(f"  Bias: {val['bias']:.4f}, SE: {val['std_error']:.4f}")

    print("\n" + "="*60)
    print("PLAYER COMPARISONS")
    print("="*60)
    for key, val in results.items():
        if '_vs_' in key and 'error' not in key and isinstance(val, dict):
            print(f"\n{val['player_a']} vs {val['player_b']} ({val['metric']}):")
            print(f"  Diff: {val['difference']:.2f}, CI: [{val['ci_lower']:.2f}, {val['ci_upper']:.2f}]")
            print(f"  {val['interpretation']}")