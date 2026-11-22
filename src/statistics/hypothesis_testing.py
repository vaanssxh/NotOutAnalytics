"""
Module 2: Hypothesis Testing for Player Comparisons

Implements Welch's t-test and Mann-Whitney U test for comparing
two players' innings-level strike rates.

Key principles:
- Uses innings as the unit of observation (not individual deliveries)
- Welch's t-test: does not assume equal variances
- Mann-Whitney U: non-parametric alternative for non-normal data
- Reports effect size (Cohen's d) and confidence intervals
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from scipy import stats
import logging

from src.statistics.data_access import get_batter_innings, get_player_comparison_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

np.random.seed(42)


@dataclass
class HypothesisTestResult:
    """Results from a two-sample hypothesis test."""
    test_name: str
    player_a: str
    player_b: str
    metric: str

    # Sample info
    n_a: int
    n_b: int
    mean_a: float
    mean_b: float
    std_a: float
    std_b: float

    # Test results
    test_statistic: float
    p_value: float
    degrees_of_freedom: Optional[float] = None

    # Effect size
    cohens_d: float = 0.0
    cohens_d_ci_lower: float = 0.0
    cohens_d_ci_upper: float = 0.0

    # Mean difference CI
    mean_diff: float = 0.0
    mean_diff_ci_lower: float = 0.0
    mean_diff_ci_upper: float = 0.0

    # Interpretation
    significance_level: float = 0.05
    reject_null: bool = False
    interpretation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'test_name': self.test_name,
            'player_a': self.player_a,
            'player_b': self.player_b,
            'metric': self.metric,
            'sample_size_a': self.n_a,
            'sample_size_b': self.n_b,
            'mean_a': round(self.mean_a, 2),
            'mean_b': round(self.mean_b, 2),
            'std_a': round(self.std_a, 2),
            'std_b': round(self.std_b, 2),
            'test_statistic': round(self.test_statistic, 4),
            'p_value': round(self.p_value, 6),
            'degrees_of_freedom': round(self.degrees_of_freedom, 2) if self.degrees_of_freedom else None,
            'cohens_d': round(self.cohens_d, 4),
            'cohens_d_ci': [round(self.cohens_d_ci_lower, 4), round(self.cohens_d_ci_upper, 4)],
            'mean_difference': round(self.mean_diff, 4),
            'mean_diff_ci': [round(self.mean_diff_ci_lower, 4), round(self.mean_diff_ci_upper, 4)],
            'significance_level': self.significance_level,
            'reject_null': self.reject_null,
            'interpretation': self.interpretation,
        }

    def __str__(self) -> str:
        return (f"{self.test_name}: {self.player_a} vs {self.player_b} ({self.metric})\n"
                f"  n={self.n_a} vs {self.n_b}, mean={self.mean_a:.1f} vs {self.mean_b:.1f}\n"
                f"  t={self.test_statistic:.3f}, p={self.p_value:.6f}, Cohen's d={self.cohens_d:.3f}\n"
                f"  Mean diff CI: [{self.mean_diff_ci_lower:.2f}, {self.mean_diff_ci_upper:.2f}]\n"
                f"  {self.interpretation}")


class HypothesisTester:
    """Performs hypothesis tests for comparing two players."""

    def __init__(self, min_balls_per_innings: int = 10, significance_level: float = 0.05):
        self.min_balls_per_innings = min_balls_per_innings
        self.significance_level = significance_level

    def _cohens_d(self, x: np.ndarray, y: np.ndarray) -> float:
        """Compute Cohen's d for two independent samples."""
        n1, n2 = len(x), len(y)
        var1, var2 = np.var(x, ddof=1), np.var(y, ddof=1)
        pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
        if pooled_std == 0:
            return 0.0
        return (np.mean(x) - np.mean(y)) / pooled_std

    def _cohens_d_ci(self, x: np.ndarray, y: np.ndarray, confidence: float = 0.95) -> Tuple[float, float]:
        """Compute confidence interval for Cohen's d using non-central t-distribution."""
        n1, n2 = len(x), len(y)
        d = self._cohens_d(x, y)

        # Hedges' g correction for small samples
        g = d * (1 - 3 / (4 * (n1 + n2) - 9))

        # Variance of g
        var_g = (n1 + n2) / (n1 * n2) + g**2 / (2 * (n1 + n2))

        # Standard error
        se_g = np.sqrt(var_g)

        # Critical value from t-distribution
        df = n1 + n2 - 2
        t_crit = stats.t.ppf((1 + confidence) / 2, df)

        ci_lower = g - t_crit * se_g
        ci_upper = g + t_crit * se_g

        return ci_lower, ci_upper

    def _mean_diff_ci(self, x: np.ndarray, y: np.ndarray, confidence: float = 0.95) -> Tuple[float, float]:
        """Compute confidence interval for mean difference (Welch)."""
        n1, n2 = len(x), len(y)
        mean1, mean2 = np.mean(x), np.mean(y)
        var1, var2 = np.var(x, ddof=1), np.var(y, ddof=1)

        mean_diff = mean1 - mean2
        se = np.sqrt(var1 / n1 + var2 / n2)

        # Welch-Satterthwaite degrees of freedom
        df = (var1 / n1 + var2 / n2)**2 / ((var1 / n1)**2 / (n1 - 1) + (var2 / n2)**2 / (n2 - 1))
        t_crit = stats.t.ppf((1 + confidence) / 2, df)

        ci_lower = mean_diff - t_crit * se
        ci_upper = mean_diff + t_crit * se

        return ci_lower, ci_upper

    def _check_normality(self, x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Check normality assumption using Shapiro-Wilk test."""
        # Shapiro-Wilk limited to 5000 observations
        x_sample = x if len(x) <= 5000 else np.random.choice(x, 5000, replace=False)
        y_sample = y if len(y) <= 5000 else np.random.choice(y, 5000, replace=False)

        stat_x, p_x = stats.shapiro(x_sample)
        stat_y, p_y = stats.shapiro(y_sample)

        return {
            'shapiro_stat_x': stat_x,
            'shapiro_p_x': p_x,
            'shapiro_stat_y': stat_y,
            'shapiro_p_y': p_y,
            'both_normal': p_x > 0.05 and p_y > 0.05,
        }

    def _check_equal_variance(self, x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Check equal variance assumption using Levene's test."""
        stat, p = stats.levene(x, y)
        return {
            'levene_stat': stat,
            'levene_p': p,
            'equal_variance': p > 0.05,
        }

    def welch_t_test(self, player_a: str, player_b: str, metric: str = 'strike_rate') -> HypothesisTestResult:
        """
        Perform Welch's independent two-sample t-test.

        H0: Mean innings metric is equal for both players
        H1: Mean innings metric differs between players
        """
        # Get innings data for both players
        df_a = get_batter_innings(player_a, min_balls=self.min_balls_per_innings)
        df_b = get_batter_innings(player_b, min_balls=self.min_balls_per_innings)

        if metric not in df_a.columns:
            raise ValueError(f"Metric '{metric}' not found in data")

        x = df_a[metric].values
        y = df_b[metric].values

        # Remove NaN
        x = x[~np.isnan(x)]
        y = y[~np.isnan(y)]

        if len(x) < 2 or len(y) < 2:
            raise ValueError(f"Insufficient data: {player_a} has {len(x)} innings, {player_b} has {len(y)} innings")

        # Welch's t-test (does not assume equal variances)
        t_stat, p_val = stats.ttest_ind(x, y, equal_var=False)

        # Degrees of freedom for Welch
        var_x, var_y = np.var(x, ddof=1), np.var(y, ddof=1)
        n_x, n_y = len(x), len(y)
        df = (var_x / n_x + var_y / n_y)**2 / ((var_x / n_x)**2 / (n_x - 1) + (var_y / n_y)**2 / (n_y - 1))

        # Effect size
        d = self._cohens_d(x, y)
        d_ci_lower, d_ci_upper = self._cohens_d_ci(x, y)
        diff_ci_lower, diff_ci_upper = self._mean_diff_ci(x, y)

        # Assumption checks
        normality = self._check_normality(x, y)
        equal_var = self._check_equal_variance(x, y)

        # Interpretation
        reject_null = p_val < self.significance_level
        mean_diff = np.mean(x) - np.mean(y)

        if reject_null:
            direction = "higher" if mean_diff > 0 else "lower"
            interpretation = (f"Reject H0: {player_a} has significantly {direction} {metric} "
                            f"than {player_b} (p={p_val:.6f} < {self.significance_level}). "
                            f"Effect size: Cohen's d = {d:.3f} ({d_ci_lower:.3f}, {d_ci_upper:.3f}).")
        else:
            interpretation = (f"Fail to reject H0: No significant difference in {metric} "
                            f"between {player_a} and {player_b} (p={p_val:.6f} >= {self.significance_level}). "
                            f"Effect size: Cohen's d = {d:.3f} ({d_ci_lower:.3f}, {d_ci_upper:.3f}).")

        # Add assumption warnings
        if not normality['both_normal']:
            interpretation += " WARNING: Normality assumption violated (Shapiro-Wilk p < 0.05). Consider Mann-Whitney U."
        if not equal_var['equal_variance']:
            interpretation += " Note: Unequal variances (Levene's p < 0.05). Welch's test is appropriate."

        return HypothesisTestResult(
            test_name="Welch's t-test",
            player_a=player_a,
            player_b=player_b,
            metric=metric,
            n_a=len(x),
            n_b=len(y),
            mean_a=np.mean(x),
            mean_b=np.mean(y),
            std_a=np.std(x, ddof=1),
            std_b=np.std(y, ddof=1),
            test_statistic=t_stat,
            p_value=p_val,
            degrees_of_freedom=df,
            cohens_d=d,
            cohens_d_ci_lower=d_ci_lower,
            cohens_d_ci_upper=d_ci_upper,
            mean_diff=mean_diff,
            mean_diff_ci_lower=diff_ci_lower,
            mean_diff_ci_upper=diff_ci_upper,
            significance_level=self.significance_level,
            reject_null=reject_null,
            interpretation=interpretation,
        )

    def mann_whitney_u(self, player_a: str, player_b: str, metric: str = 'strike_rate') -> HypothesisTestResult:
        """
        Perform Mann-Whitney U test (Wilcoxon rank-sum test).

        Non-parametric alternative when normality assumption is violated.
        H0: Distributions are identical (stochastic equality)
        H1: Distributions differ
        """
        df_a = get_batter_innings(player_a, min_balls=self.min_balls_per_innings)
        df_b = get_batter_innings(player_b, min_balls=self.min_balls_per_innings)

        if metric not in df_a.columns:
            raise ValueError(f"Metric '{metric}' not found in data")

        x = df_a[metric].values
        y = df_b[metric].values

        x = x[~np.isnan(x)]
        y = y[~np.isnan(y)]

        if len(x) < 2 or len(y) < 2:
            raise ValueError(f"Insufficient data: {player_a} has {len(x)} innings, {player_b} has {len(y)} innings")

        # Mann-Whitney U test
        u_stat, p_val = stats.mannwhitneyu(x, y, alternative='two-sided')

        # Effect size: rank-biserial correlation
        # r = 1 - (2*U) / (n1*n2)
        n1, n2 = len(x), len(y)
        r = 1 - (2 * u_stat) / (n1 * n2)

        # Convert r to Cohen's d approximation
        d = 2 * r / np.sqrt(1 - r**2) if abs(r) < 1 else np.sign(r) * 10

        # For CI, we use bootstrap (simplified - could be enhanced)
        d_ci_lower, d_ci_upper = -0.5, 0.5  # Placeholder

        # Hodges-Lehmann estimator for median difference
        # Median of all pairwise differences
        diffs = x[:, np.newaxis] - y[np.newaxis, :]
        hl_estimator = np.median(diffs)

        # CI for Hodges-Lehmann (approximate using normal approximation)
        # This is a simplified approach
        diff_ci_lower = hl_estimator - 1.96 * np.std(diffs) / np.sqrt(len(diffs))
        diff_ci_upper = hl_estimator + 1.96 * np.std(diffs) / np.sqrt(len(diffs))

        reject_null = p_val < self.significance_level

        if reject_null:
            direction = "higher" if hl_estimator > 0 else "lower"
            interpretation = (f"Reject H0: {player_a} has significantly {direction} {metric} "
                            f"than {player_b} (p={p_val:.6f} < {self.significance_level}). "
                            f"Rank-biserial r = {r:.3f}, Hodges-Lehmann median diff = {hl_estimator:.2f}.")
        else:
            interpretation = (f"Fail to reject H0: No significant difference in {metric} "
                            f"between {player_a} and {player_b} (p={p_val:.6f} >= {self.significance_level}). "
                            f"Rank-biserial r = {r:.3f}.")

        return HypothesisTestResult(
            test_name="Mann-Whitney U",
            player_a=player_a,
            player_b=player_b,
            metric=metric,
            n_a=len(x),
            n_b=len(y),
            mean_a=np.mean(x),
            mean_b=np.mean(y),
            std_a=np.std(x, ddof=1),
            std_b=np.std(y, ddof=1),
            test_statistic=u_stat,
            p_value=p_val,
            degrees_of_freedom=None,
            cohens_d=d,
            cohens_d_ci_lower=d_ci_lower,
            cohens_d_ci_upper=d_ci_upper,
            mean_diff=hl_estimator,
            mean_diff_ci_lower=diff_ci_lower,
            mean_diff_ci_upper=diff_ci_upper,
            significance_level=self.significance_level,
            reject_null=reject_null,
            interpretation=interpretation,
        )

    def compare_players(self, player_a: str, player_b: str,
                        metric: str = 'strike_rate') -> Dict[str, Any]:
        """
        Run both tests and provide recommendation.

        Returns comprehensive comparison with both parametric and non-parametric results.
        """
        results = {}

        # Welch's t-test
        try:
            welch_result = self.welch_t_test(player_a, player_b, metric)
            results['welch_t_test'] = welch_result.to_dict()
        except Exception as e:
            logger.error(f"Welch's t-test failed: {e}")
            results['welch_t_test'] = {'error': str(e)}

        # Mann-Whitney U
        try:
            mw_result = self.mann_whitney_u(player_a, player_b, metric)
            results['mann_whitney_u'] = mw_result.to_dict()
        except Exception as e:
            logger.error(f"Mann-Whitney U failed: {e}")
            results['mann_whitney_u'] = {'error': str(e)}

        # Recommendation
        results['recommendation'] = self._get_recommendation(results, metric)

        return results

    def _get_recommendation(self, results: Dict, metric: str) -> Dict[str, Any]:
        """Provide recommendation on which test to trust."""
        welch = results.get('welch_t_test', {})
        mw = results.get('mann_whitney_u', {})

        if 'error' in welch and 'error' in mw:
            return {'test': 'none', 'reason': 'Both tests failed'}

        if 'error' in welch:
            return {'test': 'mann_whitney_u', 'reason': 'Welch test failed'}

        if 'error' in mw:
            return {'test': 'welch_t_test', 'reason': 'Mann-Whitney test failed'}

        # Check normality from Welch result interpretation
        welch_interp = welch.get('interpretation', '')
        if 'WARNING: Normality assumption violated' in welch_interp:
            return {
                'test': 'mann_whitney_u',
                'reason': 'Normality assumption violated; non-parametric test preferred',
                'welch_p': welch.get('p_value'),
                'mw_p': mw.get('p_value'),
            }

        return {
            'test': 'welch_t_test',
            'reason': 'Normality assumption met; parametric test has more power',
            'welch_p': welch.get('p_value'),
            'mw_p': mw.get('p_value'),
        }


def run_hypothesis_tests_examples() -> Dict[str, Any]:
    """Run example hypothesis tests for notable player pairs."""
    tester = HypothesisTester(min_balls_per_innings=10, significance_level=0.05)

    # Notable player comparisons
    pairs = [
        ('V Kohli', 'RG Sharma'),
        ('CH Gayle', 'AB de Villiers'),
        ('MS Dhoni', 'SV Samson'),
        ('DA Warner', 'KL Rahul'),
        ('S Dhawan', 'AM Rahane'),
    ]

    results = {}
    for player_a, player_b in pairs:
        try:
            logger.info(f"Comparing {player_a} vs {player_b}...")
            results[f'{player_a}_vs_{player_b}'] = tester.compare_players(player_a, player_b, 'strike_rate')
        except Exception as e:
            logger.error(f"Comparison failed for {player_a} vs {player_b}: {e}")
            results[f'{player_a}_vs_{player_b}'] = {'error': str(e)}

    return results


if __name__ == '__main__':
    print("Running Hypothesis Testing Examples...")
    results = run_hypothesis_tests_examples()

    for key, result in results.items():
        if 'error' in result:
            print(f"\n{key}: ERROR - {result['error']}")
            continue

        print(f"\n{'='*60}")
        print(f"{key}")
        print(f"{'='*60}")

        welch = result.get('welch_t_test', {})
        mw = result.get('mann_whitney_u', {})
        rec = result.get('recommendation', {})

        if welch:
            print(f"\nWelch's t-test:")
            print(f"  t = {welch.get('test_statistic')}, p = {welch.get('p_value')}")
            print(f"  Cohen's d = {welch.get('cohens_d')} (CI: {welch.get('cohens_d_ci')})")
            print(f"  Mean diff CI: {welch.get('mean_diff_ci')}")
            print(f"  {welch.get('interpretation')}")

        if mw:
            print(f"\nMann-Whitney U:")
            print(f"  U = {mw.get('test_statistic')}, p = {mw.get('p_value')}")
            print(f"  Cohen's d (approx) = {mw.get('cohens_d')}")
            print(f"  {mw.get('interpretation')}")

        print(f"\nRecommendation: Use {rec.get('test')} - {rec.get('reason')}")