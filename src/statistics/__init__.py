"""
Statistics Engine Package for IPL Sports Analytics.

This package implements statistical analysis modules for cricket player performance:
- Module 1: Mean vs Median analysis
- Module 2: Hypothesis Testing (Welch's t-test, Mann-Whitney U)
- Module 3: Bootstrap Confidence Intervals
- Module 4: Regression to Mean
- Module 5: Beta-Binomial Shrinkage (Empirical Bayes)
- Module 6: Multiple Comparisons Correction
"""

from src.statistics.mean_median import MeanMedianAnalyzer
from src.statistics.hypothesis_testing import HypothesisTester
from src.statistics.bootstrap_ci import BootstrapCI
from src.statistics.regression_to_mean import RegressionToMean
from src.statistics.beta_binomial import BetaBinomialShrinkage
from src.statistics.multiple_comparisons import MultipleComparisons
from src.statistics.player_comparison import PlayerComparisonTool

__all__ = [
    'MeanMedianAnalyzer',
    'HypothesisTester',
    'BootstrapCI',
    'RegressionToMean',
    'BetaBinomialShrinkage',
    'MultipleComparisons',
    'PlayerComparisonTool',
]