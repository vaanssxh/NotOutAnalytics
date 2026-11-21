"""
Data Cleaning Module

Applies cricket scoring rules and cleans raw Cricsheet data.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Set
from collections import defaultdict
import logging

from src.data_loader import RawDelivery, load_season_mapping

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Team name canonicalization mapping
TEAM_CANONICAL_NAMES = {
    'Delhi Capitals': 'Delhi Capitals',
    'Delhi Daredevils': 'Delhi Capitals',
    'Kings XI Punjab': 'Punjab Kings',
    'Punjab Kings': 'Punjab Kings',
    'Royal Challengers Bangalore': 'Royal Challengers Bengaluru',
    'Royal Challengers Bengaluru': 'Royal Challengers Bengaluru',
    'Rising Pune Supergiant': 'Rising Pune Supergiants',
    'Rising Pune Supergiants': 'Rising Pune Supergiants',
    'Deccan Chargers': 'Deccan Chargers',
    'Gujarat Lions': 'Gujarat Lions',
    'Kochi Tuskers Kerala': 'Kochi Tuskers Kerala',
    'Pune Warriors': 'Pune Warriors',
    'Mumbai Indians': 'Mumbai Indians',
    'Chennai Super Kings': 'Chennai Super Kings',
    'Kolkata Knight Riders': 'Kolkata Knight Riders',
    'Rajasthan Royals': 'Rajasthan Royals',
    'Sunrisers Hyderabad': 'Sunrisers Hyderabad',
    'Gujarat Titans': 'Gujarat Titans',
    'Lucknow Super Giants': 'Lucknow Super Giants',
}


def canonicalize_team_name(team: str) -> str:
    """Map historical team names to canonical names."""
    return TEAM_CANONICAL_NAMES.get(team.strip(), team.strip())


def parse_ball_string(ball: str) -> Tuple[int, int]:
    """
    Parse ball string like '0.1' or '19.6' into (over, ball_in_over).
    Handles cases like '19.7' for wides.
    """
    try:
        parts = ball.split('.')
        over = int(parts[0])
        ball_in_over = int(parts[1])
        return over, ball_in_over
    except (ValueError, IndexError):
        logger.warning(f"Could not parse ball string: {ball}")
        return 0, 0


def parse_actual_delivery(actual: str) -> int:
    """Parse actual_delivery string to integer."""
    try:
        return int(actual)
    except (ValueError, TypeError):
        return 0


def parse_int_or_zero(value: str) -> int:
    """Parse string to int, treating empty strings as 0."""
    if not value or value.strip() == '':
        return 0
    try:
        return int(float(value))  # Handle '1.0' format
    except (ValueError, TypeError):
        return 0


def parse_bool(value: str) -> bool:
    """Parse string to boolean."""
    return value.strip().lower() == 'true'


@dataclass
class CleanedDelivery:
    """Cleaned delivery record with derived cricket fields."""
    # Original identifiers
    match_id: int
    season: str
    season_start_year: int
    season_end_year: int
    start_date: str
    venue: str
    innings: int
    over: int
    ball_in_over: int
    actual_delivery_seq: int
    batting_team: str
    bowling_team: str
    striker: str
    non_striker: str
    bowler: str

    # Runs
    runs_off_bat: int
    extras_total: int
    wides: int
    noballs: int
    byes: int
    legbyes: int
    penalty: int

    # Derived cricket fields
    is_legal_delivery: bool  # False for wides, True for everything including no-balls
    is_wide: bool
    is_noball: bool
    total_runs: int  # runs_off_bat + extras_total
    batter_runs: int  # runs_off_bat only (excludes byes/legbyes)
    bowler_conceded_runs: int  # runs_off_bat + wides + noballs + penalty (excludes byes/legbyes)
    is_boundary: bool  # 4 or 6 off bat
    is_six: bool
    is_four: bool

    # Dismissal info
    wicket_type: str
    player_dismissed: str
    fielder_1: str
    fielder_2: str
    fielder_3: str
    is_wicket: bool
    is_bowler_wicket: bool  # Excludes run outs, retired hurt/out
    dismissal_kind: str  # Normalized wicket type

    # Quality flags
    quality_flags: List[str] = field(default_factory=list)


class DataCleaner:
    """Cleans raw deliveries and applies cricket scoring rules."""

    # Wicket types that count as bowler wickets
    BOWLER_WICKET_TYPES = {
        'bowled', 'caught', 'caught and bowled', 'lbw', 'stumped',
        'hit wicket', 'obstructing the field'
    }

    # Wicket types that don't count as bowler wickets
    NON_BOWLER_WICKET_TYPES = {
        'run out', 'retired hurt', 'retired out'
    }

    def __init__(self):
        self.season_mapping = load_season_mapping()
        self.stats = defaultdict(int)
        self.quality_issues = []

    def clean_delivery(self, raw: RawDelivery) -> CleanedDelivery:
        """Clean a single raw delivery record."""

        # Parse basic fields
        match_id = int(raw.match_id)
        season = raw.season.strip()
        season_start, season_end = self.season_mapping.get(season, (0, 0))
        start_date = raw.start_date.strip()
        venue = raw.venue.strip()
        innings = int(raw.innings)
        over, ball_in_over = parse_ball_string(raw.ball)
        actual_delivery_seq = parse_actual_delivery(raw.actual_delivery)
        batting_team = canonicalize_team_name(raw.batting_team)
        bowling_team = canonicalize_team_name(raw.bowling_team)
        striker = raw.striker.strip()
        non_striker = raw.non_striker.strip()
        bowler = raw.bowler.strip()

        # Parse runs and extras
        runs_off_bat = parse_int_or_zero(raw.runs_off_bat)
        extras_total = parse_int_or_zero(raw.extras)
        wides = parse_int_or_zero(raw.wides)
        noballs = parse_int_or_zero(raw.noballs)
        byes = parse_int_or_zero(raw.byes)
        legbyes = parse_int_or_zero(raw.legbyes)
        penalty = parse_int_or_zero(raw.penalty)

        # Derived cricket fields
        is_wide = wides > 0
        is_noball = noballs > 0
        is_legal_delivery = not is_wide  # Wides are not legal deliveries; no-balls are

        total_runs = runs_off_bat + extras_total
        batter_runs = runs_off_bat  # Byes/legbyes don't count as batter runs
        bowler_conceded_runs = runs_off_bat + wides + noballs + penalty  # Excludes byes/legbyes

        is_boundary = runs_off_bat in (4, 6)
        is_four = runs_off_bat == 4
        is_six = runs_off_bat == 6

        # Dismissal info
        wicket_type = raw.wicket_type.strip() if raw.wicket_type else ''
        player_dismissed = raw.player_dismissed.strip() if raw.player_dismissed else ''
        fielder_1 = raw.fielder_1.strip() if raw.fielder_1 else ''
        fielder_2 = raw.fielder_2.strip() if raw.fielder_2 else ''
        fielder_3 = raw.fielder_3.strip() if raw.fielder_3 else ''

        is_wicket = bool(wicket_type)
        is_bowler_wicket = wicket_type.lower() in self.BOWLER_WICKET_TYPES
        dismissal_kind = wicket_type.lower() if wicket_type else ''

        # Quality flags
        quality_flags = self._check_quality(raw, runs_off_bat, extras_total, wides, noballs, byes, legbyes, penalty, is_wicket, wicket_type)

        cleaned = CleanedDelivery(
            match_id=match_id,
            season=season,
            season_start_year=season_start,
            season_end_year=season_end,
            start_date=start_date,
            venue=venue,
            innings=innings,
            over=over,
            ball_in_over=ball_in_over,
            actual_delivery_seq=actual_delivery_seq,
            batting_team=batting_team,
            bowling_team=bowling_team,
            striker=striker,
            non_striker=non_striker,
            bowler=bowler,
            runs_off_bat=runs_off_bat,
            extras_total=extras_total,
            wides=wides,
            noballs=noballs,
            byes=byes,
            legbyes=legbyes,
            penalty=penalty,
            is_legal_delivery=is_legal_delivery,
            is_wide=is_wide,
            is_noball=is_noball,
            total_runs=total_runs,
            batter_runs=batter_runs,
            bowler_conceded_runs=bowler_conceded_runs,
            is_boundary=is_boundary,
            is_six=is_six,
            is_four=is_four,
            wicket_type=wicket_type,
            player_dismissed=player_dismissed,
            fielder_1=fielder_1,
            fielder_2=fielder_2,
            fielder_3=fielder_3,
            is_wicket=is_wicket,
            is_bowler_wicket=is_bowler_wicket,
            dismissal_kind=dismissal_kind,
            quality_flags=quality_flags,
        )

        self.stats['total_deliveries'] += 1
        for flag in quality_flags:
            self.stats[f'quality_{flag}'] += 1

        return cleaned

    def _check_quality(self, raw: RawDelivery, runs_off_bat: int, extras_total: int,
                       wides: int, noballs: int, byes: int, legbyes: int, penalty: int,
                       is_wicket: bool, wicket_type: str) -> List[str]:
        """Check data quality and return list of flags."""
        flags = []

        # Check extras consistency
        expected_extras = wides + noballs + byes + legbyes + penalty
        if extras_total != expected_extras:
            flags.append('extras_mismatch')
            self.quality_issues.append({
                'match_id': raw.match_id,
                'ball': raw.ball,
                'issue': 'extras_mismatch',
                'detail': f'extras={extras_total} but sum={expected_extras} (w={wides}, nb={noballs}, b={byes}, lb={legbyes}, p={penalty})'
            })

        # Check non_boundary field (often unreliable)
        non_boundary = parse_bool(raw.non_boundary)
        if non_boundary and runs_off_bat in (4, 6):
            flags.append('non_boundary_conflict')
        if not non_boundary and runs_off_bat in (1, 2, 3):
            flags.append('non_boundary_missing')

        # Check for impossible runs
        if runs_off_bat == 5:
            flags.append('five_runs_off_bat')
        if runs_off_bat > 6:
            flags.append('impossible_runs_off_bat')

        # Check wicket without dismissal
        if is_wicket and not raw.player_dismissed.strip():
            flags.append('wicket_no_dismissed_player')

        # Check run out credited to bowler
        if wicket_type and wicket_type.lower() == 'run out' and is_wicket:
            flags.append('run_out_not_bowler_wicket')

        # Check actual_delivery vs ball consistency for wides
        if wides > 0:
            # On wides, actual_delivery should not increment (or should be same as previous)
            pass  # This is expected behavior in Cricsheet

        # Check penalty runs (always 0 in this dataset)
        if penalty > 0:
            flags.append('penalty_runs_present')

        return flags

    def clean_all(self, raw_deliveries) -> List[CleanedDelivery]:
        """Clean all raw deliveries."""
        cleaned = []
        for raw in raw_deliveries:
            cleaned.append(self.clean_delivery(raw))
        return cleaned

    def get_stats(self) -> Dict:
        """Get cleaning statistics."""
        return dict(self.stats)

    def get_quality_issues(self) -> List[Dict]:
        """Get quality issues found."""
        return self.quality_issues


def get_bowler_wicket_types() -> Set[str]:
    """Return set of wicket types that count for bowlers."""
    return DataCleaner.BOWLER_WICKET_TYPES.copy()


def get_non_bowler_wicket_types() -> Set[str]:
    """Return set of wicket types that don't count for bowlers."""
    return DataCleaner.NON_BOWLER_WICKET_TYPES.copy()