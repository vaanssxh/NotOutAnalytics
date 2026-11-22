"""
Module 7: Player Comparison Tool

Comprehensive tool for comparing two players with full uncertainty quantification.
Integrates all statistical modules: descriptive stats, hypothesis tests, bootstrap CIs,
regression to mean, beta-binomial shrinkage, and multiple comparisons.

Provides a unified interface for "Is Player A really better than Player B?"
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import logging
import json

from src.statistics.data_access import get_batter_innings, get_bowler_innings, get_batter_career, get_bowler_career
from src.statistics.mean_median import MeanMedianAnalyzer
from src.statistics.hypothesis_testing import HypothesisTester
from src.statistics.bootstrap_ci import BootstrapCI
from src.statistics.regression_to_mean import RegressionToMean
from src.statistics.beta_binomial import BetaBinomialShrinkage
from src.statistics.multiple_comparisons import MultipleComparisons

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

np.random.seed(42)


@dataclass
class PlayerSummary:
    """Summary statistics for a player."""
    player_name: str
    role: str  # 'batter', 'bowler', 'allrounder'
    total_innings: int
    total_balls_faced: int
    total_runs: int
    career_strike_rate: float
    avg_innings_strike_rate: float
    batting_average: float
    boundary_rate: float
    dismissal_rate: float
    # Bowling
    total_balls_bowled: int = 0
    total_wickets: int = 0
    economy_rate: float = 0.0
    bowling_average: float = 0.0
    bowling_strike_rate: float = 0.0


@dataclass
class ComparisonResult:
    """Complete comparison between two players."""
    player_a: str
    player_b: str
    metric: str

    # Descriptive
    summary_a: PlayerSummary
    summary_b: PlayerSummary

    # Hypothesis tests
    welch_t_test: Dict[str, Any]
    mann_whitney_u: Dict[str, Any]
    recommended_test: str

    # Bootstrap CIs
    bootstrap_ci_a: Dict[str, Any]
    bootstrap_ci_b: Dict[str, Any]
    bootstrap_diff_ci: Dict[str, Any]

    # Regression to mean
    regression_a: Dict[str, Any]
    regression_b: Dict[str, Any]

    # Beta-binomial shrinkage
    shrinkage_a: Dict[str, Any]
    shrinkage_b: Dict[str, Any]

    # Overall verdict
    verdict: str
    confidence: str  # 'high', 'medium', 'low'
    key_findings: List[str]


class PlayerComparisonTool:
    """Comprehensive player comparison with uncertainty quantification."""

    def __init__(self, min_balls_per_innings: int = 10, min_career_balls: int = 200):
        self.min_balls_per_innings = min_balls_per_innings
        self.min_career_balls = min_career_balls

        # Initialize sub-modules
        self.mean_median = MeanMedianAnalyzer(min_balls_per_innings=min_balls_per_innings)
        self.hypothesis = HypothesisTester(min_balls_per_innings=min_balls_per_innings)
        self.bootstrap = BootstrapCI(n_bootstrap=10000, confidence_level=0.95,
                                     min_balls_per_innings=min_balls_per_innings)
        self.regression = RegressionToMean(min_balls_per_half=min_career_balls // 2)
        self.shrinkage = BetaBinomialShrinkage(min_balls=min_career_balls)
        self.multiple = MultipleComparisons(alpha=0.05)

    def get_player_summary(self, player_name: str) -> PlayerSummary:
        """Get comprehensive summary for a player."""
        # Batting
        bat_innings = get_batter_innings(player_name, min_balls=self.min_balls_per_innings)
        career = get_batter_career(min_balls=1).query(f"player_name == '{player_name}'")

        if len(career) == 0:
            raise ValueError(f"Player {player_name} not found in career data")

        career_row = career.iloc[0]

        total_balls_faced = int(career_row['balls_faced'])
        total_runs = int(career_row['runs'])
        total_innings = len(bat_innings)
        career_sr = float(career_row['strike_rate'])
        avg_innings_sr = float(bat_innings['strike_rate'].mean()) if len(bat_innings) > 0 else 0
        batting_avg = float(career_row['average']) if career_row['dismissals'] > 0 else float('inf')
        boundary_rate = float(career_row['boundary_rate'])
        dismissal_rate = float(career_row['dismissals']) / total_innings if total_innings > 0 else 0

        # Bowling
        bowl_innings = get_bowler_innings(player_name, min_balls=1)
        bowl_career = get_bowler_career(min_balls=1).query(f"player_name == '{player_name}'")

        if len(bowl_career) > 0:
            bowl_row = bowl_career.iloc[0]
            total_balls_bowled = int(bowl_row['balls_bowled'])
            total_wickets = int(bowl_row['wickets'])
            economy = float(bowl_row['economy'])
            bowl_avg = float(bowl_row['average']) if total_wickets > 0 else float('inf')
            bowl_sr = float(bowl_row['strike_rate']) if total_wickets > 0 else 0
        else:
            total_balls_bowled = 0
            total_wickets = 0
            economy = 0.0
            bowl_avg = 0.0
            bowl_sr = 0.0

        # Determine role
        if total_balls_faced >= self.min_career_balls and total_balls_bowled >= 100:
            role = 'allrounder'
        elif total_balls_faced >= self.min_career_balls:
            role = 'batter'
        else:
            role = 'bowler'

        return PlayerSummary(
            player_name=player_name,
            role=role,
            total_innings=total_innings,
            total_balls_faced=total_balls_faced,
            total_runs=total_runs,
            career_strike_rate=career_sr,
            avg_innings_strike_rate=avg_innings_sr,
            batting_average=batting_avg,
            boundary_rate=boundary_rate,
            dismissal_rate=dismissal_rate * 100,
            total_balls_bowled=total_balls_bowled,
            total_wickets=total_wickets,
            economy_rate=economy,
            bowling_average=bowl_avg,
            bowling_strike_rate=bowl_sr,
        )

    def compare(self, player_a: str, player_b: str,
                metric: str = 'strike_rate') -> ComparisonResult:
        """Run complete comparison between two players."""
        logger.info(f"Comparing {player_a} vs {player_b} on {metric}")

        # 1. Player summaries
        summary_a = self.get_player_summary(player_a)
        summary_b = self.get_player_summary(player_b)

        # 2. Hypothesis tests
        hyp_results = self.hypothesis.compare_players(player_a, player_b, metric)
        welch = hyp_results.get('welch_t_test', {})
        mw = hyp_results.get('mann_whitney_u', {})
        rec = hyp_results.get('recommendation', {})

        # 3. Bootstrap CIs
        if metric == 'strike_rate':
            ci_a = self.bootstrap.player_career_sr_ci(player_a).to_dict()
            ci_b = self.bootstrap.player_career_sr_ci(player_b).to_dict()
            diff_ci = self.bootstrap.compare_players_ci(player_a, player_b, 'strike_rate')
        elif metric == 'boundary_rate':
            ci_a = self.bootstrap.player_boundary_rate_ci(player_a).to_dict()
            ci_b = self.bootstrap.player_boundary_rate_ci(player_b).to_dict()
            diff_ci = self.bootstrap.compare_players_ci(player_a, player_b, 'boundary_rate')
        elif metric == 'batting_average':
            ci_a = self.bootstrap.player_batting_average_ci(player_a).to_dict()
            ci_b = self.bootstrap.player_batting_average_ci(player_b).to_dict()
            diff_ci = self.bootstrap.compare_players_ci(player_a, player_b, 'batting_average')
        else:
            ci_a = self.bootstrap.player_avg_innings_sr_ci(player_a).to_dict()
            ci_b = self.bootstrap.player_avg_innings_sr_ci(player_b).to_dict()
            diff_ci = self.bootstrap.compare_players_ci(player_a, player_b, 'avg_innings_sr')

        # 4. Regression to mean
        reg_a = self.regression.analyze_player(player_a)
        reg_b = self.regression.analyze_player(player_b)
        reg_a_dict = reg_a.to_dict() if reg_a else {'error': 'Insufficient data'}
        reg_b_dict = reg_b.to_dict() if reg_b else {'error': 'Insufficient data'}

        # 5. Beta-binomial shrinkage
        shrink_a = self.shrinkage.analyze_player(player_a)
        shrink_b = self.shrinkage.analyze_player(player_b)
        shrink_a_dict = shrink_a.to_dict() if shrink_a else {'error': 'Insufficient data'}
        shrink_b_dict = shrink_b.to_dict() if shrink_b else {'error': 'Insufficient data'}

        # 6. Overall verdict
        verdict, confidence, key_findings = self._generate_verdict(
            player_a, player_b, metric, summary_a, summary_b,
            welch, mw, rec, diff_ci, reg_a_dict, reg_b_dict,
            shrink_a_dict, shrink_b_dict
        )

        return ComparisonResult(
            player_a=player_a,
            player_b=player_b,
            metric=metric,
            summary_a=summary_a,
            summary_b=summary_b,
            welch_t_test=welch,
            mann_whitney_u=mw,
            recommended_test=rec.get('test', 'unknown'),
            bootstrap_ci_a=ci_a,
            bootstrap_ci_b=ci_b,
            bootstrap_diff_ci=diff_ci,
            regression_a=reg_a_dict,
            regression_b=reg_b_dict,
            shrinkage_a=shrink_a_dict,
            shrinkage_b=shrink_b_dict,
            verdict=verdict,
            confidence=confidence,
            key_findings=key_findings,
        )

    def _generate_verdict(self, player_a: str, player_b: str, metric: str,
                          summary_a: PlayerSummary, summary_b: PlayerSummary,
                          welch: Dict, mw: Dict, rec: Dict,
                          diff_ci: Dict, reg_a: Dict, reg_b: Dict,
                          shrink_a: Dict, shrink_b: Dict) -> Tuple[str, str, List[str]]:
        """Generate overall verdict from all analyses."""
        findings = []

        # Descriptive comparison
        if metric == 'strike_rate':
            val_a = summary_a.career_strike_rate
            val_b = summary_b.career_strike_rate
            diff = val_a - val_b
            metric_name = "Career Strike Rate"
        elif metric == 'boundary_rate':
            val_a = summary_a.boundary_rate
            val_b = summary_b.boundary_rate
            diff = val_a - val_b
            metric_name = "Boundary Rate"
        elif metric == 'batting_average':
            val_a = summary_a.batting_average
            val_b = summary_b.batting_average
            diff = val_a - val_b
            metric_name = "Batting Average"
        else:
            val_a = summary_a.avg_innings_strike_rate
            val_b = summary_b.avg_innings_strike_rate
            diff = val_a - val_b
            metric_name = "Avg Innings Strike Rate"

        direction = "higher" if diff > 0 else "lower"
        findings.append(f"{player_a} has {direction} {metric_name} ({val_a:.1f} vs {val_b:.1f})")

        # Hypothesis test
        if 'error' not in welch:
            if welch.get('reject_null', False):
                findings.append(f"Welch's t-test: Significant difference (p={welch['p_value']:.6f}, Cohen's d={welch['cohens_d']:.3f})")
            else:
                findings.append(f"Welch's t-test: No significant difference (p={welch['p_value']:.6f})")

        if 'error' not in mw:
            if mw.get('reject_null', False):
                findings.append(f"Mann-Whitney U: Significant difference (p={mw['p_value']:.6f})")
            else:
                findings.append(f"Mann-Whitney U: No significant difference (p={mw['p_value']:.6f})")

        # Recommended test
        if rec.get('test') != 'none':
            findings.append(f"Recommended test: {rec['test']} ({rec['reason']})")

        # Bootstrap difference CI
        if 'error' not in diff_ci and isinstance(diff_ci, dict):
            ci_lower = diff_ci.get('ci_lower', 0)
            ci_upper = diff_ci.get('ci_upper', 0)
            excludes_zero = diff_ci.get('excludes_zero', False)
            if excludes_zero:
                findings.append(f"Bootstrap 95% CI for difference: [{ci_lower:.1f}, {ci_upper:.1f}] - EXCLUDES ZERO (significant)")
            else:
                findings.append(f"Bootstrap 95% CI for difference: [{ci_lower:.1f}, {ci_upper:.1f}] - INCLUDES ZERO (not significant)")

        # Regression to mean
        for player, reg in [(player_a, reg_a), (player_b, reg_b)]:
            if 'error' not in reg and 'regression_magnitude' in reg:
                reg_mag = reg['regression_magnitude']
                if reg_mag > 10:
                    findings.append(f"{player}: Large regression to mean ({reg_mag:.1f} points)")
                elif reg_mag < -10:
                    findings.append(f"{player}: Improved in second half ({abs(reg_mag):.1f} points)")

        # Shrinkage
        for player, shrink in [(player_a, shrink_a), (player_b, shrink_b)]:
            if 'error' not in shrink and 'shrinkage_factor' in shrink:
                sf = shrink['shrinkage_factor']
                if sf > 0.3:
                    findings.append(f"{player}: High shrinkage ({sf:.1%}) - small sample")

        # Overall verdict
        if 'error' not in diff_ci and diff_ci.get('excludes_zero', False):
            if 'error' not in welch and welch.get('reject_null', False):
                verdict = f"{player_a} is statistically significantly better than {player_b} on {metric}"
                confidence = "high"
            else:
                verdict = f"{player_a} appears better than {player_b} on {metric}, but parametric test not significant"
                confidence = "medium"
        else:
            verdict = f"No statistically significant difference between {player_a} and {player_b} on {metric}"
            confidence = "low" if diff == 0 else "medium"

        return verdict, confidence, findings

    def compare_multiple(self, target_player: str,
                         comparison_players: List[str],
                         metric: str = 'strike_rate') -> Dict[str, Any]:
        """Compare one player against many with multiple comparisons correction."""
        logger.info(f"Comparing {target_player} vs {len(comparison_players)} players")

        results = {}
        for other in comparison_players:
            try:
                results[other] = self.compare(target_player, other, metric)
            except Exception as e:
                logger.error(f"Comparison failed for {other}: {e}")
                results[other] = {'error': str(e)}

        # Apply multiple comparisons correction
        p_values = []
        names = []
        for other, result in results.items():
            if isinstance(result, ComparisonResult) and 'error' not in result.welch_t_test:
                p_values.append(result.welch_t_test.get('p_value', 1.0))
                names.append(other)

        if p_values:
            mc_result = self.multiple.compare_methods(np.array(p_values), names)
        else:
            mc_result = {'error': 'No valid p-values for correction'}

        return {
            'target_player': target_player,
            'comparisons': {k: v.__dict__ if isinstance(v, ComparisonResult) else v
                           for k, v in results.items()},
            'multiple_comparisons': mc_result,
        }

    def to_dict(self, result: ComparisonResult) -> Dict[str, Any]:
        """Convert ComparisonResult to dictionary."""
        return {
            'player_a': result.player_a,
            'player_b': result.player_b,
            'metric': result.metric,
            'summary_a': asdict(result.summary_a),
            'summary_b': asdict(result.summary_b),
            'welch_t_test': result.welch_t_test,
            'mann_whitney_u': result.mann_whitney_u,
            'recommended_test': result.recommended_test,
            'bootstrap_ci_a': result.bootstrap_ci_a,
            'bootstrap_ci_b': result.bootstrap_ci_b,
            'bootstrap_diff_ci': result.bootstrap_diff_ci,
            'regression_a': result.regression_a,
            'regression_b': result.regression_b,
            'shrinkage_a': result.shrinkage_a,
            'shrinkage_b': result.shrinkage_b,
            'verdict': result.verdict,
            'confidence': result.confidence,
            'key_findings': result.key_findings,
        }

    def save_report(self, result: ComparisonResult, filepath: str) -> None:
        """Save comparison report as JSON."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(result), f, indent=2, default=str)
        logger.info(f"Report saved to {filepath}")


def run_comparison_examples() -> Dict[str, Any]:
    """Run example comparisons."""
    tool = PlayerComparisonTool(min_balls_per_innings=10, min_career_balls=200)

    pairs = [
        ('V Kohli', 'RG Sharma', 'strike_rate'),
        ('CH Gayle', 'AB de Villiers', 'strike_rate'),
        ('DA Warner', 'KL Rahul', 'strike_rate'),
        ('MS Dhoni', 'SV Samson', 'strike_rate'),
        ('V Kohli', 'RG Sharma', 'boundary_rate'),
        ('V Kohli', 'RG Sharma', 'batting_average'),
    ]

    results = {}
    for p1, p2, metric in pairs:
        try:
            logger.info(f"Comparing {p1} vs {p2} on {metric}...")
            result = tool.compare(p1, p2, metric)
            results[f'{p1}_vs_{p2}_{metric}'] = tool.to_dict(result)
        except Exception as e:
            logger.error(f"Comparison failed: {e}")
            results[f'{p1}_vs_{p2}_{metric}'] = {'error': str(e)}

    # Multiple comparisons
    try:
        multi = tool.compare_multiple('V Kohli', ['RG Sharma', 'CH Gayle', 'AB de Villiers',
                                                   'DA Warner', 'KL Rahul', 'MS Dhoni'],
                                      'strike_rate')
        results['kohli_vs_many'] = multi
    except Exception as e:
        logger.error(f"Multiple comparison failed: {e}")
        results['kohli_vs_many'] = {'error': str(e)}

    return results


if __name__ == '__main__':
    print("Running Player Comparison Examples...")
    results = run_comparison_examples()

    print("\n" + "="*70)
    print("PAIRWISE COMPARISONS")
    print("="*70)
    for key, val in results.items():
        if 'error' in val:
            print(f"\n{key}: ERROR - {val['error']}")
            continue
        if 'target_player' in val:  # Multiple comparison
            continue

        print(f"\n{'='*70}")
        print(f"{val['player_a']} vs {val['player_b']} ({val['metric']})")
        print(f"{'='*70}")

        print(f"\nVerdict: {val['verdict']}")
        print(f"Confidence: {val['confidence']}")
        print(f"Recommended test: {val['recommended_test']}")

        print("\nKey Findings:")
        for finding in val['key_findings']:
            print(f"  - {finding}")

        print(f"\n{val['player_a']}: SR={val['summary_a']['career_strike_rate']:.1f}, "
              f"Avg={val['summary_a']['batting_average']:.1f}, "
              f"Bound={val['summary_a']['boundary_rate']:.1f}%")
        print(f"{val['player_b']}: SR={val['summary_b']['career_strike_rate']:.1f}, "
              f"Avg={val['summary_b']['batting_average']:.1f}, "
              f"Bound={val['summary_b']['boundary_rate']:.1f}%")

        if 'interpretation' in val['welch_t_test']:
            print(f"\nWelch: {val['welch_t_test']['interpretation'][:100]}...")

    print("\nDone!")