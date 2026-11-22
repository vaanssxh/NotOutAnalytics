"""
Module 6: Multiple Comparisons Correction

Implements family-wise error rate (FWER) and false discovery rate (FDR)
corrections for multiple hypothesis testing.

Key methods:
- Holm-Bonferroni: Step-down FWER control (more powerful than Bonferroni)
- Benjamini-Hochberg: FDR control (less conservative, more powerful)
- Benjamini-Yekutieli: FDR control under arbitrary dependence

Application: When comparing many players against each other or against a benchmark,
multiple comparisons correction prevents false positives.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from scipy import stats
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

np.random.seed(42)


@dataclass
class MultipleTestResult:
    """Results from multiple comparisons correction."""
    test_names: List[str]
    raw_p_values: List[float]
    corrected_p_values: List[float]
    rejected: List[bool]
    method: str
    alpha: float
    n_tests: int
    n_rejected: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'method': self.method,
            'alpha': self.alpha,
            'n_tests': self.n_tests,
            'n_rejected': self.n_rejected,
            'results': [
                {
                    'test': self.test_names[i],
                    'raw_p': round(self.raw_p_values[i], 6),
                    'corrected_p': round(self.corrected_p_values[i], 6),
                    'rejected': self.rejected[i],
                }
                for i in range(self.n_tests)
            ],
        }

    def __str__(self) -> str:
        lines = [f"{self.method} Correction (alpha={self.alpha})",
                 f"Tests: {self.n_tests}, Rejected: {self.n_rejected}"]
        for i in range(self.n_tests):
            status = "REJECT" if self.rejected[i] else "FAIL TO REJECT"
            lines.append(f"  {self.test_names[i]}: p={self.raw_p_values[i]:.6f} -> "
                         f"p_adj={self.corrected_p_values[i]:.6f} [{status}]")
        return "\n".join(lines)


class MultipleComparisons:
    """Multiple hypothesis testing corrections."""

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def holm_bonferroni(self, p_values: np.ndarray, test_names: Optional[List[str]] = None) -> MultipleTestResult:
        """
        Holm-Bonferroni step-down procedure (FWER control).

        More powerful than standard Bonferroni. Controls family-wise error rate.
        """
        p_values = np.array(p_values, dtype=float)
        n = len(p_values)

        if test_names is None:
            test_names = [f"Test_{i+1}" for i in range(n)]

        # Sort by p-value
        sorted_idx = np.argsort(p_values)
        sorted_p = p_values[sorted_idx]

        # Step-down procedure
        corrected = np.zeros(n)
        rejected = np.zeros(n, dtype=bool)

        for i, idx in enumerate(sorted_idx):
            # Adjusted alpha for this step: alpha / (n - i)
            adj_alpha = self.alpha / (n - i)
            corrected[idx] = min(p_values[idx] * (n - i), 1.0)
            rejected[idx] = p_values[idx] <= adj_alpha

            # If we fail to reject, all subsequent (larger p-values) also fail
            if not rejected[idx]:
                # But we still need to compute corrected p-values for remaining
                for j in range(i + 1, n):
                    next_idx = sorted_idx[j]
                    corrected[next_idx] = min(p_values[next_idx] * (n - j), 1.0)
                    rejected[next_idx] = False
                break

        return MultipleTestResult(
            test_names=test_names,
            raw_p_values=p_values.tolist(),
            corrected_p_values=corrected.tolist(),
            rejected=rejected.tolist(),
            method="Holm-Bonferroni",
            alpha=self.alpha,
            n_tests=n,
            n_rejected=int(rejected.sum()),
        )

    def benjamini_hochberg(self, p_values: np.ndarray, test_names: Optional[List[str]] = None) -> MultipleTestResult:
        """
        Benjamini-Hochberg procedure (FDR control).

        Controls False Discovery Rate. Less conservative than FWER methods.
        Assumes independence or positive dependence.
        """
        p_values = np.array(p_values, dtype=float)
        n = len(p_values)

        if test_names is None:
            test_names = [f"Test_{i+1}" for i in range(n)]

        # Sort by p-value
        sorted_idx = np.argsort(p_values)
        sorted_p = p_values[sorted_idx]

        # BH critical values: (i / n) * alpha
        critical_values = np.arange(1, n + 1) / n * self.alpha

        # Find largest k where p_(k) <= (k/n) * alpha
        rejected_sorted = sorted_p <= critical_values

        # Step-up: reject all with p <= p_(k)
        if np.any(rejected_sorted):
            k = np.max(np.where(rejected_sorted)[0])
            rejected_sorted[:k+1] = True
        else:
            rejected_sorted[:] = False

        # Compute adjusted p-values
        # BH adjusted p = min_{j>=i} (n/j * p_(j))
        adjusted_sorted = np.zeros(n)
        for i in range(n - 1, -1, -1):
            if i == n - 1:
                adjusted_sorted[i] = min(sorted_p[i] * n / (i + 1), 1.0)
            else:
                adjusted_sorted[i] = min(adjusted_sorted[i + 1],
                                         min(sorted_p[i] * n / (i + 1), 1.0))

        # Map back to original order
        corrected = np.zeros(n)
        rejected = np.zeros(n, dtype=bool)
        for i, idx in enumerate(sorted_idx):
            corrected[idx] = adjusted_sorted[i]
            rejected[idx] = rejected_sorted[i]

        return MultipleTestResult(
            test_names=test_names,
            raw_p_values=p_values.tolist(),
            corrected_p_values=corrected.tolist(),
            rejected=rejected.tolist(),
            method="Benjamini-Hochberg",
            alpha=self.alpha,
            n_tests=n,
            n_rejected=int(rejected.sum()),
        )

    def benjamini_yekutieli(self, p_values: np.ndarray, test_names: Optional[List[str]] = None) -> MultipleTestResult:
        """
        Benjamini-Yekutieli procedure (FDR control under arbitrary dependence).

        More conservative than BH, controls FDR under any dependence structure.
        Critical values divided by harmonic number sum(1/i).
        """
        p_values = np.array(p_values, dtype=float)
        n = len(p_values)

        if test_names is None:
            test_names = [f"Test_{i+1}" for i in range(n)]

        # Harmonic number
        harmonic = np.sum(1 / np.arange(1, n + 1))

        # Sort by p-value
        sorted_idx = np.argsort(p_values)
        sorted_p = p_values[sorted_idx]

        # BY critical values: (i / (n * harmonic)) * alpha
        critical_values = np.arange(1, n + 1) / (n * harmonic) * self.alpha

        # Step-up procedure
        rejected_sorted = sorted_p <= critical_values

        if np.any(rejected_sorted):
            k = np.max(np.where(rejected_sorted)[0])
            rejected_sorted[:k+1] = True
        else:
            rejected_sorted[:] = False

        # Adjusted p-values
        adjusted_sorted = np.zeros(n)
        for i in range(n - 1, -1, -1):
            if i == n - 1:
                adjusted_sorted[i] = min(sorted_p[i] * n * harmonic / (i + 1), 1.0)
            else:
                adjusted_sorted[i] = min(adjusted_sorted[i + 1],
                                         min(sorted_p[i] * n * harmonic / (i + 1), 1.0))

        # Map back
        corrected = np.zeros(n)
        rejected = np.zeros(n, dtype=bool)
        for i, idx in enumerate(sorted_idx):
            corrected[idx] = adjusted_sorted[i]
            rejected[idx] = rejected_sorted[i]

        return MultipleTestResult(
            test_names=test_names,
            raw_p_values=p_values.tolist(),
            corrected_p_values=corrected.tolist(),
            rejected=rejected.tolist(),
            method="Benjamini-Yekutieli",
            alpha=self.alpha,
            n_tests=n,
            n_rejected=int(rejected.sum()),
        )

    def bonferroni(self, p_values: np.ndarray, test_names: Optional[List[str]] = None) -> MultipleTestResult:
        """Standard Bonferroni correction (FWER control, very conservative)."""
        p_values = np.array(p_values, dtype=float)
        n = len(p_values)

        if test_names is None:
            test_names = [f"Test_{i+1}" for i in range(n)]

        corrected = np.minimum(p_values * n, 1.0)
        rejected = corrected <= self.alpha

        return MultipleTestResult(
            test_names=test_names,
            raw_p_values=p_values.tolist(),
            corrected_p_values=corrected.tolist(),
            rejected=rejected.tolist(),
            method="Bonferroni",
            alpha=self.alpha,
            n_tests=n,
            n_rejected=int(rejected.sum()),
        )

    def compare_methods(self, p_values: np.ndarray, test_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Compare all correction methods."""
        p_values = np.array(p_values, dtype=float)

        results = {}

        # Bonferroni
        bonf = self.bonferroni(p_values, test_names)
        results['bonferroni'] = bonf.to_dict()

        # Holm-Bonferroni
        holm = self.holm_bonferroni(p_values, test_names)
        results['holm_bonferroni'] = holm.to_dict()

        # Benjamini-Hochberg
        bh = self.benjamini_hochberg(p_values, test_names)
        results['benjamini_hochberg'] = bh.to_dict()

        # Benjamini-Yekutieli
        by = self.benjamini_yekutieli(p_values, test_names)
        results['benjamini_yekutieli'] = by.to_dict()

        # Summary
        results['summary'] = {
            'n_tests': len(p_values),
            'raw_p_values': [round(p, 6) for p in p_values],
            'test_names': test_names or [f"Test_{i+1}" for i in range(len(p_values))],
            'rejections': {
                'bonferroni': int(bonf.n_rejected),
                'holm_bonferroni': int(holm.n_rejected),
                'benjamini_hochberg': int(bh.n_rejected),
                'benjamini_yekutieli': int(by.n_rejected),
            },
            'recommendation': self._get_recommendation(p_values),
        }

        return results

    def _get_recommendation(self, p_values: np.ndarray) -> Dict[str, str]:
        """Provide recommendation on which method to use."""
        n = len(p_values)

        if n <= 5:
            return {
                'primary': 'holm_bonferroni',
                'reason': 'Small number of tests; Holm-Bonferroni controls FWER with good power',
            }
        elif n <= 20:
            return {
                'primary': 'benjamini_hochberg',
                'reason': 'Moderate number of tests; FDR control balances power and error control',
                'caveat': 'Assumes independence or positive dependence',
            }
        else:
            return {
                'primary': 'benjamini_hochberg',
                'reason': 'Large number of tests; FDR control is standard for high-dimensional testing',
                'caveat': 'Consider Benjamini-Yekutieli if tests may have arbitrary dependence',
            }

    def player_comparison_correction(self, player_name: str,
                                      comparison_players: List[str],
                                      metric: str = 'strike_rate',
                                      min_balls: int = 10) -> Dict[str, Any]:
        """
        Apply multiple comparisons correction for one player vs many others.

        Uses hypothesis testing module to get raw p-values, then corrects.
        """
        from src.statistics.hypothesis_testing import HypothesisTester
        from src.statistics.data_access import get_player_comparison_data

        tester = HypothesisTester(min_balls_per_innings=min_balls)

        p_values = []
        test_names = []
        test_details = []

        for other_player in comparison_players:
            try:
                result = tester.welch_t_test(player_name, other_player, metric)
                p_values.append(result.p_value)
                test_names.append(f"{player_name} vs {other_player}")
                test_details.append({
                    'player_a': player_name,
                    'player_b': other_player,
                    'metric': metric,
                    'test_statistic': result.test_statistic,
                    'cohens_d': result.cohens_d,
                    'mean_diff': result.mean_diff,
                })
            except Exception as e:
                logger.warning(f"Test failed for {player_name} vs {other_player}: {e}")
                p_values.append(1.0)  # Non-significant
                test_names.append(f"{player_name} vs {other_player}")
                test_details.append({'error': str(e)})

        if not p_values:
            return {'error': 'No valid comparisons'}

        # Apply corrections
        correction_results = self.compare_methods(np.array(p_values), test_names)

        # Add test details
        for method in ['bonferroni', 'holm_bonferroni', 'benjamini_hochberg', 'benjamini_yekutieli']:
            if method in correction_results:
                for i, detail in enumerate(test_details):
                    correction_results[method]['results'][i]['details'] = detail

        return correction_results


def run_multiple_comparisons_examples() -> Dict[str, Any]:
    """Run example multiple comparisons corrections."""
    mc = MultipleComparisons(alpha=0.05)

    # Example 1: Simulated p-values
    print("Example 1: Simulated p-values")
    np.random.seed(42)
    # Mix of null and alternative
    n_null = 15
    n_alt = 5
    p_null = np.random.uniform(0, 1, n_null)
    p_alt = np.random.beta(0.5, 5, n_alt)  # Skewed toward 0
    p_values = np.concatenate([p_null, p_alt])
    np.random.shuffle(p_values)
    test_names = [f"Test_{i+1}" for i in range(len(p_values))]

    results_sim = mc.compare_methods(p_values, test_names)
    print(f"  Raw p-values: {[round(p, 4) for p in p_values]}")
    print(f"  Bonferroni rejections: {results_sim['summary']['rejections']['bonferroni']}")
    print(f"  Holm rejections: {results_sim['summary']['rejections']['holm_bonferroni']}")
    print(f"  BH rejections: {results_sim['summary']['rejections']['benjamini_hochberg']}")
    print(f"  BY rejections: {results_sim['summary']['rejections']['benjamini_yekutieli']}")

    # Example 2: Kohli vs many players
    print("\nExample 2: V Kohli vs other top batters")
    comparison_players = ['RG Sharma', 'CH Gayle', 'AB de Villiers', 'MS Dhoni',
                          'DA Warner', 'KL Rahul', 'S Dhawan', 'AM Rahane',
                          'JC Buttler', 'HH Pandya', 'Q de Kock', 'F du Plessis']

    kohli_results = mc.player_comparison_correction('V Kohli', comparison_players, 'strike_rate', min_balls=10)

    return {
        'simulated': results_sim,
        'kohli_vs_others': kohli_results,
    }


if __name__ == '__main__':
    print("Running Multiple Comparisons Examples...")
    results = run_multiple_comparisons_examples()

    print("\n" + "="*60)
    print("SIMULATED DATA - ALL METHODS")
    print("="*60)
    sim = results['simulated']
    print(f"Recommendation: {sim['summary']['recommendation']}")

    print("\nMethod comparisons:")
    for method in ['bonferroni', 'holm_bonferroni', 'benjamini_hochberg', 'benjamini_yekutieli']:
        m = sim[method]
        print(f"\n  {m['method']}: {m['n_rejected']}/{m['n_tests']} rejected")
        for r in m['results']:
            if r['rejected']:
                print(f"    {r['test']}: p={r['raw_p']:.6f} -> p_adj={r['corrected_p']:.6f} [REJECT]")

    print("\n" + "="*60)
    print("KOHLI VS OTHERS - HOLM-BONFERRONI")
    print("="*60)
    kohli = results['kohli_vs_others']
    if 'holm_bonferroni' in kohli:
        h = kohli['holm_bonferroni']
        print(f"Rejected: {h['n_rejected']}/{h['n_tests']}")
        for r in h['results']:
            status = "REJECT" if r['rejected'] else "FAIL TO REJECT"
            print(f"  {r['test']}: p={r['raw_p']:.6f} -> p_adj={r['corrected_p']:.6f} [{status}]")
            if 'details' in r and 'cohens_d' in r['details']:
                print(f"    Cohen's d={r['details']['cohens_d']:.3f}, diff={r['details']['mean_diff']:.2f}")

    print("\nDone!")