"""
Module 5: Beta-Binomial Shrinkage (Empirical Bayes)

Implements empirical Bayes shrinkage for boundary rate estimation.
Shrinks individual player boundary rates toward league average based on sample size.

Key principles:
- Boundary rate follows binomial distribution: boundaries ~ Binomial(balls_faced, p)
- Prior: Beta(alpha, beta) estimated from league-wide data (empirical Bayes)
- Posterior: Beta(alpha + boundaries, beta + balls_faced - boundaries)
- Shrunken estimate = posterior mean = (alpha + boundaries) / (alpha + beta + balls_faced)
- Players with fewer balls faced shrink more toward league average
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

from src.statistics.data_access import (
    get_league_boundary_stats,
    get_batter_career_balls_boundaries,
    get_boundary_rate_by_player,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

np.random.seed(42)


@dataclass
class BetaBinomialResult:
    """Results from beta-binomial shrinkage for a player."""
    player_name: str
    balls_faced: int
    boundaries: int
    raw_boundary_rate: float  # boundaries / balls_faced * 100
    shrunken_boundary_rate: float  # posterior mean * 100
    prior_alpha: float
    prior_beta: float
    posterior_alpha: float
    posterior_beta: float
    shrinkage_factor: float  # how much shrunk toward prior (0-1)
    ci_lower: float  # 95% credible interval
    ci_upper: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'player_name': self.player_name,
            'balls_faced': self.balls_faced,
            'boundaries': self.boundaries,
            'raw_boundary_rate': round(self.raw_boundary_rate, 4),
            'shrunken_boundary_rate': round(self.shrunken_boundary_rate, 4),
            'prior_alpha': round(self.prior_alpha, 4),
            'prior_beta': round(self.prior_beta, 4),
            'posterior_alpha': round(self.posterior_alpha, 4),
            'posterior_beta': round(self.posterior_beta, 4),
            'shrinkage_factor': round(self.shrinkage_factor, 4),
            'ci_lower': round(self.ci_lower, 4),
            'ci_upper': round(self.ci_upper, 4),
        }


@dataclass
class PriorEstimate:
    """Empirical Bayes prior parameters."""
    alpha: float
    beta: float
    league_boundary_rate: float
    total_boundaries: int
    total_balls: int
    n_players: int
    method: str  # 'moments' or 'mle'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'alpha': round(self.alpha, 4),
            'beta': round(self.beta, 4),
            'league_boundary_rate': round(self.league_boundary_rate, 4),
            'total_boundaries': self.total_boundaries,
            'total_balls': self.total_balls,
            'n_players': self.n_players,
            'method': self.method,
        }


class BetaBinomialShrinkage:
    """Empirical Bayes shrinkage for boundary rates using Beta-Binomial model."""

    def __init__(self, min_balls: int = 200, method: str = 'moments'):
        """
        Args:
            min_balls: Minimum career balls to include in prior estimation
            method: 'moments' for method of moments, 'mle' for maximum likelihood
        """
        self.min_balls = min_balls
        self.method = method
        self.prior: Optional[PriorEstimate] = None

    def estimate_prior_moments(self) -> PriorEstimate:
        """Estimate Beta prior using method of moments."""
        total_boundaries, total_balls, n_players = get_league_boundary_stats(self.min_balls)

        # League-wide boundary rate
        league_rate = total_boundaries / total_balls if total_balls > 0 else 0

        # Get individual player rates for variance calculation
        df = get_boundary_rate_by_player(min_balls=self.min_balls)

        if len(df) < 2:
            # Fallback: use weak prior
            return PriorEstimate(alpha=1.0, beta=1.0, league_boundary_rate=league_rate,
                                 total_boundaries=total_boundaries, total_balls=total_balls,
                                 n_players=n_players, method='moments')

        # Observed variance in boundary rates
        observed_rates = df['boundary_rate'].values / 100  # Convert from percentage
        observed_mean = np.mean(observed_rates)
        observed_var = np.var(observed_rates, ddof=1)

        # Method of moments for Beta distribution:
        # mean = alpha / (alpha + beta)
        # var = alpha * beta / ((alpha + beta)^2 * (alpha + beta + 1))
        # Solve for alpha, beta:
        # alpha = mean * (mean * (1 - mean) / var - 1)
        # beta = (1 - mean) * (mean * (1 - mean) / var - 1)

        if observed_var > 0 and observed_mean > 0 and observed_mean < 1:
            factor = observed_mean * (1 - observed_mean) / observed_var - 1
            if factor > 0:
                alpha = observed_mean * factor
                beta = (1 - observed_mean) * factor
            else:
                # Variance too large, use weak prior
                alpha, beta = 1.0, 1.0
        else:
            alpha, beta = 1.0, 1.0

        # Ensure minimum values
        alpha = max(alpha, 0.1)
        beta = max(beta, 0.1)

        prior = PriorEstimate(
            alpha=alpha,
            beta=beta,
            league_boundary_rate=league_rate,
            total_boundaries=total_boundaries,
            total_balls=total_balls,
            n_players=n_players,
            method='moments',
        )

        self.prior = prior
        return prior

    def estimate_prior_mle(self) -> PriorEstimate:
        """Estimate Beta prior using MLE (via scipy optimization)."""
        try:
            from scipy import optimize
            from scipy.special import digamma, polygamma
        except ImportError:
            logger.warning("scipy not available for MLE, falling back to moments")
            return self.estimate_prior_moments()

        df = get_boundary_rate_by_player(min_balls=self.min_balls)
        if len(df) < 2:
            return self.estimate_prior_moments()

        # MLE for Beta distribution
        # Log-likelihood: sum(log(gamma(alpha+beta)) - log(gamma(alpha)) - log(gamma(beta))
        #                  + (alpha-1)*log(x_i) + (beta-1)*log(1-x_i))

        rates = df['boundary_rate'].values / 100
        rates = np.clip(rates, 1e-6, 1 - 1e-6)  # Avoid boundary issues

        def neg_log_likelihood(params):
            alpha, beta = params
            if alpha <= 0 or beta <= 0:
                return 1e10
            ll = (len(rates) * (np.log(np.math.gamma(alpha + beta))
                   - np.log(np.math.gamma(alpha)) - np.log(np.math.gamma(beta)))
                   + (alpha - 1) * np.sum(np.log(rates))
                   + (beta - 1) * np.sum(np.log(1 - rates)))
            return -ll

        # Initial guess from moments
        moments_prior = self.estimate_prior_moments()
        initial_guess = [moments_prior.alpha, moments_prior.beta]

        try:
            result = optimize.minimize(neg_log_likelihood, initial_guess,
                                       bounds=[(0.01, None), (0.01, None)],
                                       method='L-BFGS-B')
            alpha, beta = result.x
        except Exception as e:
            logger.warning(f"MLE optimization failed: {e}, using moments")
            return moments_prior

        total_boundaries, total_balls, n_players = get_league_boundary_stats(self.min_balls)
        league_rate = total_boundaries / total_balls if total_balls > 0 else 0

        prior = PriorEstimate(
            alpha=alpha,
            beta=beta,
            league_boundary_rate=league_rate,
            total_boundaries=total_boundaries,
            total_balls=total_balls,
            n_players=n_players,
            method='mle',
        )

        self.prior = prior
        return prior

    def get_prior(self) -> PriorEstimate:
        """Get or compute the prior."""
        if self.prior is None:
            if self.method == 'mle':
                return self.estimate_prior_mle()
            else:
                return self.estimate_prior_moments()
        return self.prior

    def shrunken_rate(self, boundaries: int, balls_faced: int) -> Tuple[float, float, float, float, float]:
        """
        Compute shrunken boundary rate and credible interval.

        Returns:
            (shrunken_rate, shrinkage_factor, ci_lower, ci_upper, posterior_alpha, posterior_beta)
        """
        prior = self.get_prior()
        alpha, beta = prior.alpha, prior.beta

        # Posterior parameters
        post_alpha = alpha + boundaries
        post_beta = beta + balls_faced - boundaries

        # Posterior mean (shrunken estimate)
        shrunken = post_alpha / (post_alpha + post_beta)

        # Shrinkage factor: weight given to prior
        # shrinkage = (alpha + beta) / (alpha + beta + balls_faced)
        shrinkage = (alpha + beta) / (alpha + beta + balls_faced)

        # 95% credible interval using Beta quantiles
        from scipy.stats import beta as beta_dist
        ci_lower = beta_dist.ppf(0.025, post_alpha, post_beta)
        ci_upper = beta_dist.ppf(0.975, post_alpha, post_beta)

        return shrunken, shrinkage, ci_lower, ci_upper, post_alpha, post_beta

    def analyze_player(self, player_name: str) -> Optional[BetaBinomialResult]:
        """Analyze boundary rate shrinkage for a specific player."""
        balls_faced, boundaries = get_batter_career_balls_boundaries(player_name)

        if balls_faced < self.min_balls:
            logger.warning(f"{player_name} has only {balls_faced} balls (min {self.min_balls})")
            return None

        raw_rate = boundaries / balls_faced if balls_faced > 0 else 0

        shrunken, shrinkage, ci_lower, ci_upper, post_alpha, post_beta = self.shrunken_rate(
            boundaries, balls_faced
        )

        prior = self.get_prior()

        return BetaBinomialResult(
            player_name=player_name,
            balls_faced=balls_faced,
            boundaries=boundaries,
            raw_boundary_rate=raw_rate * 100,
            shrunken_boundary_rate=shrunken * 100,
            prior_alpha=prior.alpha,
            prior_beta=prior.beta,
            posterior_alpha=post_alpha,
            posterior_beta=post_beta,
            shrinkage_factor=shrinkage,
            ci_lower=ci_lower * 100,
            ci_upper=ci_upper * 100,
        )

    def analyze_all_players(self) -> Tuple[pd.DataFrame, PriorEstimate]:
        """Analyze boundary rate shrinkage for all qualified players."""
        df = get_boundary_rate_by_player(min_balls=self.min_balls)
        prior = self.get_prior()

        results = []
        for _, row in df.iterrows():
            player_name = row['player_name']
            balls_faced = int(row['balls_faced'])
            boundaries = int(row['boundaries'])

            raw_rate = boundaries / balls_faced if balls_faced > 0 else 0
            shrunken, shrinkage, ci_lower, ci_upper, post_alpha, post_beta = self.shrunken_rate(
                boundaries, balls_faced
            )

            results.append({
                'player_name': player_name,
                'balls_faced': balls_faced,
                'boundaries': boundaries,
                'raw_boundary_rate': raw_rate * 100,
                'shrunken_boundary_rate': shrunken * 100,
                'shrinkage_factor': shrinkage,
                'ci_lower': ci_lower * 100,
                'ci_upper': ci_upper * 100,
                'posterior_alpha': post_alpha,
                'posterior_beta': post_beta,
                'difference': (shrunken - raw_rate) * 100,
            })

        result_df = pd.DataFrame(results)
        result_df = result_df.sort_values('shrunken_boundary_rate', ascending=False)

        return result_df, prior

    def get_top_shrunken(self, n: int = 20) -> pd.DataFrame:
        """Get top N players by shrunken boundary rate."""
        df, _ = self.analyze_all_players()
        return df.head(n)

    def get_most_shrunken(self, n: int = 20) -> pd.DataFrame:
        """Get players with most shrinkage (smallest sample sizes)."""
        df, _ = self.analyze_all_players()
        return df.nlargest(n, 'shrinkage_factor')

    def compare_raw_vs_shrunken(self) -> Dict[str, Any]:
        """Compare raw vs shrunken estimates across all players."""
        df, prior = self.analyze_all_players()

        # Correlation
        corr = df['raw_boundary_rate'].corr(df['shrunken_boundary_rate'])

        # Mean absolute difference
        mean_abs_diff = (df['raw_boundary_rate'] - df['shrunken_boundary_rate']).abs().mean()

        # Players where ranking changes significantly
        df['raw_rank'] = df['raw_boundary_rate'].rank(ascending=False)
        df['shrunken_rank'] = df['shrunken_boundary_rate'].rank(ascending=False)
        df['rank_change'] = df['raw_rank'] - df['shrunken_rank']

        large_rank_changes = df.nlargest(10, 'rank_change')[['player_name', 'raw_rank', 'shrunken_rank', 'rank_change']]
        large_rank_changes_neg = df.nsmallest(10, 'rank_change')[['player_name', 'raw_rank', 'shrunken_rank', 'rank_change']]

        return {
            'prior': prior.to_dict(),
            'n_players': len(df),
            'correlation': round(corr, 4),
            'mean_abs_difference': round(mean_abs_diff, 4),
            'mean_shrinkage': round(df['shrinkage_factor'].mean(), 4),
            'max_shrinkage': round(df['shrinkage_factor'].max(), 4),
            'min_shrinkage': round(df['shrinkage_factor'].min(), 4),
            'top_rank_increases': large_rank_changes.to_dict('records'),
            'top_rank_decreases': large_rank_changes_neg.to_dict('records'),
        }


def run_beta_binomial_analysis() -> Dict[str, Any]:
    """Run complete beta-binomial shrinkage analysis."""
    # Method of moments
    logger.info("Estimating prior (method of moments)...")
    shrinkage_mom = BetaBinomialShrinkage(min_balls=200, method='moments')
    df_mom, prior_mom = shrinkage_mom.analyze_all_players()
    comparison_mom = shrinkage_mom.compare_raw_vs_shrunken()

    # MLE
    logger.info("Estimating prior (MLE)...")
    shrinkage_mle = BetaBinomialShrinkage(min_balls=200, method='mle')
    df_mle, prior_mle = shrinkage_mle.analyze_all_players()
    comparison_mle = shrinkage_mle.compare_raw_vs_shrunken()

    # Top players
    top_mom = shrinkage_mom.get_top_shrunken(20)
    top_mle = shrinkage_mle.get_top_shrunken(20)

    # Specific players
    notable_players = ['V Kohli', 'RG Sharma', 'CH Gayle', 'AB de Villiers', 'MS Dhoni',
                       'DA Warner', 'KL Rahul', 'S Dhawan', 'AM Rahane', 'HH Pandya']
    player_results = {}
    for player in notable_players:
        try:
            result = shrinkage_mom.analyze_player(player)
            if result:
                player_results[player] = result.to_dict()
        except Exception as e:
            logger.warning(f"Could not analyze {player}: {e}")

    return {
        'moments': {
            'prior': prior_mom.to_dict(),
            'comparison': comparison_mom,
            'top_20': top_mom.to_dict('records'),
        },
        'mle': {
            'prior': prior_mle.to_dict(),
            'comparison': comparison_mle,
            'top_20': top_mle.to_dict('records'),
        },
        'notable_players': player_results,
    }


if __name__ == '__main__':
    print("Running Beta-Binomial Shrinkage Analysis...")
    results = run_beta_binomial_analysis()

    print("\n" + "="*60)
    print("PRIOR (MOMENTS)")
    print("="*60)
    p = results['moments']['prior']
    print(f"Alpha: {p['alpha']:.4f}, Beta: {p['beta']:.4f}")
    print(f"League boundary rate: {p['league_boundary_rate']:.4f} ({p['league_boundary_rate']*100:.2f}%)")
    print(f"Total boundaries: {p['total_boundaries']}, Total balls: {p['total_balls']}")
    print(f"N players: {p['n_players']}")

    print("\n" + "="*60)
    print("PRIOR (MLE)")
    print("="*60)
    p = results['mle']['prior']
    print(f"Alpha: {p['alpha']:.4f}, Beta: {p['beta']:.4f}")
    print(f"League boundary rate: {p['league_boundary_rate']:.4f} ({p['league_boundary_rate']*100:.2f}%)")

    print("\n" + "="*60)
    print("COMPARISON (MOMENTS)")
    print("="*60)
    c = results['moments']['comparison']
    print(f"N players: {c['n_players']}")
    print(f"Correlation raw vs shrunken: {c['correlation']:.4f}")
    print(f"Mean abs difference: {c['mean_abs_difference']:.4f}%")
    print(f"Mean shrinkage factor: {c['mean_shrinkage']:.4f}")
    print(f"Max shrinkage: {c['max_shrinkage']:.4f}")

    print("\n" + "="*60)
    print("TOP 10 SHRUNKEN BOUNDARY RATES (MOMENTS)")
    print("="*60)
    for i, row in enumerate(results['moments']['top_20'][:10]):
        print(f"  {i+1}. {row['player_name']}: raw={row['raw_boundary_rate']:.2f}%, "
              f"shrunken={row['shrunken_boundary_rate']:.2f}%, "
              f"shrinkage={row['shrinkage_factor']:.3f}, "
              f"balls={row['balls_faced']}")

    print("\n" + "="*60)
    print("NOTABLE PLAYERS")
    print("="*60)
    for player, data in results['notable_players'].items():
        print(f"  {player}: raw={data['raw_boundary_rate']:.2f}%, "
              f"shrunken={data['shrunken_boundary_rate']:.2f}%, "
              f"shrinkage={data['shrinkage_factor']:.3f}, "
              f"95% CI=[{data['ci_lower']:.2f}, {data['ci_upper']:.2f}]")

    print("\nDone!")