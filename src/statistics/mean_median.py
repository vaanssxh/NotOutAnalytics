"""
Module 1: Mean vs Median Analysis

Analyzes the difference between mean and median innings strike rates,
demonstrating the impact of outliers and skew in cricket data.

Key distinction:
- Career aggregate strike rate = total runs / total balls faced (weighted by innings length)
- Average innings strike rate = mean of individual innings strike rates (unweighted)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

from src.statistics.data_access import (
    get_batter_career,
    get_batter_innings,
    get_all_batter_innings_strike_rates,
    get_league_strike_rate_distribution,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fixed random seed for reproducibility
np.random.seed(42)


@dataclass
class MeanMedianResult:
    """Results from mean vs median analysis."""
    metric_name: str
    values: np.ndarray
    mean: float
    median: float
    std: float
    minimum: float
    maximum: float
    skewness: float
    kurtosis: float
    n_observations: int
    outlier_count: int
    outlier_threshold_low: float
    outlier_threshold_high: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'metric_name': self.metric_name,
            'mean': round(self.mean, 4),
            'median': round(self.median, 4),
            'std': round(self.std, 4),
            'minimum': round(self.minimum, 4),
            'maximum': round(self.maximum, 4),
            'skewness': round(self.skewness, 4),
            'kurtosis': round(self.kurtosis, 4),
            'n_observations': self.n_observations,
            'outlier_count': self.outlier_count,
            'outlier_threshold_low': round(self.outlier_threshold_low, 4),
            'outlier_threshold_high': round(self.outlier_threshold_high, 4),
            'mean_vs_median_diff': round(self.mean - self.median, 4),
            'mean_vs_median_pct_diff': round((self.mean - self.median) / self.median * 100, 2) if self.median != 0 else None,
        }

    def interpret(self) -> str:
        """Provide interpretation of mean vs median difference."""
        diff = self.mean - self.median
        pct_diff = abs(diff / self.median * 100) if self.median != 0 else 0

        if pct_diff < 5:
            interpretation = "Mean and median are close - distribution is approximately symmetric."
        elif diff > 0:
            interpretation = f"Mean ({self.mean:.2f}) > Median ({self.median:.2f}) - positive skew. Outliers pull mean upward."
        else:
            interpretation = f"Mean ({self.mean:.2f}) < Median ({self.median:.2f}) - negative skew. Outliers pull mean downward."

        if self.outlier_count > 0:
            interpretation += f" Detected {self.outlier_count} outliers using IQR method."

        return interpretation


class MeanMedianAnalyzer:
    """Analyzes mean vs median for cricket performance metrics."""

    def __init__(self, min_balls_per_innings: int = 10):
        self.min_balls_per_innings = min_balls_per_innings

    def compute_skewness(self, data: np.ndarray) -> float:
        """Compute Fisher-Pearson coefficient of skewness."""
        n = len(data)
        if n < 3:
            return 0.0
        mean = np.mean(data)
        std = np.std(data, ddof=1)
        if std == 0:
            return 0.0
        return np.sum(((data - mean) / std) ** 3) * n / ((n - 1) * (n - 2))

    def compute_kurtosis(self, data: np.ndarray) -> float:
        """Compute excess kurtosis (Fisher's definition, normal = 0)."""
        n = len(data)
        if n < 4:
            return 0.0
        mean = np.mean(data)
        std = np.std(data, ddof=1)
        if std == 0:
            return 0.0
        return np.sum(((data - mean) / std) ** 4) * n * (n + 1) / ((n - 1) * (n - 2) * (n - 3)) \
            - 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))

    def detect_outliers_iqr(self, data: np.ndarray) -> Tuple[np.ndarray, float, float]:
        """Detect outliers using IQR method. Returns (outlier_mask, lower_bound, upper_bound)."""
        q1 = np.percentile(data, 25)
        q3 = np.percentile(data, 75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        mask = (data < lower) | (data > upper)
        return mask, lower, upper

    def analyze_innings_strike_rates(self, player_name: Optional[str] = None) -> MeanMedianResult:
        """Analyze mean vs median for innings strike rates.

        Args:
            player_name: If provided, analyze specific player's innings.
                        If None, analyze league-wide distribution.
        """
        if player_name:
            df = get_batter_innings(player_name, min_balls=self.min_balls_per_innings)
            values = df['strike_rate'].values
            metric_name = f"Innings Strike Rate - {player_name}"
        else:
            df = get_league_strike_rate_distribution(min_balls=self.min_balls_per_innings)
            values = df['strike_rate'].values
            metric_name = "League-wide Innings Strike Rate"

        if len(values) == 0:
            raise ValueError(f"No data found for {metric_name}")

        return self._analyze_array(values, metric_name)

    def analyze_career_strike_rates(self, min_career_balls: int = 200) -> MeanMedianResult:
        """Analyze mean vs median for career strike rates (aggregate)."""
        df = get_batter_career(min_balls=min_career_balls)
        values = df['strike_rate'].values
        metric_name = f"Career Aggregate Strike Rate (min {min_career_balls} balls)"
        return self._analyze_array(values, metric_name)

    def analyze_average_innings_strike_rate(self, min_career_balls: int = 200) -> MeanMedianResult:
        """Analyze mean vs median for average innings strike rate per player.

        This is the UNWEIGHTED mean of each player's innings strike rates,
        different from career aggregate strike rate.
        """
        df_all = get_all_batter_innings_strike_rates(min_balls=self.min_balls_per_innings)

        # Compute average innings strike rate per player
        player_avg_sr = df_all.groupby('player_name')['strike_rate'].mean()
        # Filter players with enough career balls
        career_balls = df_all.groupby('player_name')['balls_faced'].sum()
        qualified_players = career_balls[career_balls >= min_career_balls].index
        player_avg_sr = player_avg_sr[qualified_players]

        values = player_avg_sr.values
        metric_name = f"Average Innings Strike Rate per Player (min {min_career_balls} career balls)"
        return self._analyze_array(values, metric_name)

    def _analyze_array(self, values: np.ndarray, metric_name: str) -> MeanMedianResult:
        """Core analysis function for any numeric array."""
        values = np.array(values, dtype=float)
        values = values[~np.isnan(values)]  # Remove NaN

        if len(values) == 0:
            raise ValueError(f"No valid values for {metric_name}")

        mean_val = np.mean(values)
        median_val = np.median(values)
        std_val = np.std(values, ddof=1)
        min_val = np.min(values)
        max_val = np.max(values)
        skew = self.compute_skewness(values)
        kurt = self.compute_kurtosis(values)

        outlier_mask, lower, upper = self.detect_outliers_iqr(values)
        outlier_count = int(np.sum(outlier_mask))

        return MeanMedianResult(
            metric_name=metric_name,
            values=values,
            mean=mean_val,
            median=median_val,
            std=std_val,
            minimum=min_val,
            maximum=max_val,
            skewness=skew,
            kurtosis=kurt,
            n_observations=len(values),
            outlier_count=outlier_count,
            outlier_threshold_low=lower,
            outlier_threshold_high=upper,
        )

    def compare_career_vs_average_innings(self, min_career_balls: int = 200) -> Dict[str, Any]:
        """Compare career aggregate strike rate vs average innings strike rate.

        This is a key conceptual distinction:
        - Career aggregate SR = total_runs / total_balls (weighted by innings length)
        - Average innings SR = mean of (runs_i / balls_i) for each innings (unweighted)
        """
        df = get_all_batter_innings_strike_rates(min_balls=self.min_balls_per_innings)

        results = []
        for player_name in df['player_name'].unique():
            player_df = df[df['player_name'] == player_name]
            total_runs = player_df['runs_scored'].sum()
            total_balls = player_df['balls_faced'].sum()

            if total_balls >= min_career_balls:
                career_sr = total_runs / total_balls * 100
                avg_innings_sr = player_df['strike_rate'].mean()
                diff = career_sr - avg_innings_sr

                results.append({
                    'player_name': player_name,
                    'career_strike_rate': round(career_sr, 2),
                    'avg_innings_strike_rate': round(avg_innings_sr, 2),
                    'difference': round(diff, 2),
                    'innings_count': len(player_df),
                    'total_balls': int(total_balls),
                })

        result_df = pd.DataFrame(results)
        result_df = result_df.sort_values('difference', key=abs, ascending=False)

        return {
            'comparison': result_df.to_dict('records'),
            'summary': {
                'mean_career_sr': round(result_df['career_strike_rate'].mean(), 2),
                'mean_avg_innings_sr': round(result_df['avg_innings_strike_rate'].mean(), 2),
                'mean_difference': round(result_df['difference'].mean(), 2),
                'median_difference': round(result_df['difference'].median(), 2),
                'n_players': len(result_df),
            }
        }


def run_mean_median_analysis() -> Dict[str, Any]:
    """Run complete mean vs median analysis suite."""
    analyzer = MeanMedianAnalyzer(min_balls_per_innings=10)

    results = {}

    # 1. League-wide innings strike rate
    logger.info("Analyzing league-wide innings strike rates...")
    results['league_innings_sr'] = analyzer.analyze_innings_strike_rates().to_dict()

    # 2. Career aggregate strike rate
    logger.info("Analyzing career aggregate strike rates...")
    results['career_sr'] = analyzer.analyze_career_strike_rates(min_career_balls=200).to_dict()

    # 3. Average innings strike rate per player
    logger.info("Analyzing average innings strike rate per player...")
    results['avg_innings_sr'] = analyzer.analyze_average_innings_strike_rate(min_career_balls=200).to_dict()

    # 4. Key comparison: career vs average innings
    logger.info("Comparing career vs average innings strike rates...")
    results['career_vs_avg_innings'] = analyzer.compare_career_vs_average_innings(min_career_balls=200)

    # 5. Specific player examples
    logger.info("Analyzing specific players...")
    for player in ['V Kohli', 'RG Sharma', 'CH Gayle', 'AB de Villiers', 'MS Dhoni']:
        try:
            results[f'player_{player.replace(" ", "_")}'] = analyzer.analyze_innings_strike_rates(player).to_dict()
        except Exception as e:
            logger.warning(f"Could not analyze {player}: {e}")

    return results


if __name__ == '__main__':
    print("Running Mean vs Median Analysis...")
    results = run_mean_median_analysis()

    print("\n" + "="*60)
    print("LEAGUE-WIDE INNINGS STRIKE RATE")
    print("="*60)
    r = results['league_innings_sr']
    print(f"Mean: {r['mean']:.2f}, Median: {r['median']:.2f}")
    print(f"Std: {r['std']:.2f}, Skew: {r['skewness']:.2f}, Kurt: {r['kurtosis']:.2f}")
    print(f"Outliers: {r['outlier_count']} (bounds: {r['outlier_threshold_low']:.1f} - {r['outlier_threshold_high']:.1f})")
    print(f"Interpretation: Mean vs median diff = {r['mean_vs_median_diff']:.2f} ({r['mean_vs_median_pct_diff']:.1f}%)")

    print("\n" + "="*60)
    print("CAREER AGGREGATE STRIKE RATE (min 200 balls)")
    print("="*60)
    r = results['career_sr']
    print(f"Mean: {r['mean']:.2f}, Median: {r['median']:.2f}")
    print(f"Std: {r['std']:.2f}, Skew: {r['skewness']:.2f}, Kurt: {r['kurtosis']:.2f}")

    print("\n" + "="*60)
    print("AVERAGE INNINGS STRIKE RATE PER PLAYER")
    print("="*60)
    r = results['avg_innings_sr']
    print(f"Mean: {r['mean']:.2f}, Median: {r['median']:.2f}")
    print(f"Std: {r['std']:.2f}, Skew: {r['skewness']:.2f}, Kurt: {r['kurtosis']:.2f}")

    print("\n" + "="*60)
    print("CAREER vs AVERAGE INNINGS COMPARISON")
    print("="*60)
    comp = results['career_vs_avg_innings']['summary']
    print(f"Mean Career SR: {comp['mean_career_sr']:.2f}")
    print(f"Mean Avg Innings SR: {comp['mean_avg_innings_sr']:.2f}")
    print(f"Mean Difference: {comp['mean_difference']:.2f}")
    print(f"Median Difference: {comp['median_difference']:.2f}")
    print(f"N Players: {comp['n_players']}")

    print("\nDone!")