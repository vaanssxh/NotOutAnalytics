"""
Data Processor Module

Creates derived records at delivery, batter innings, batter season, and batter career levels.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Iterator, Tuple
from collections import defaultdict
import logging
from datetime import datetime

from src.data_loader import RawDelivery, DataLoader
from src.data_cleaning import CleanedDelivery, DataCleaner, canonicalize_team_name

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BatterInnings:
    """Batter performance in a single innings."""
    match_id: int
    season: str
    season_start_year: int
    start_date: str
    venue: str
    innings: int
    batting_team: str
    bowler_team: str
    batter: str

    # Batting stats
    runs_scored: int = 0
    balls_faced: int = 0  # Legal deliveries faced (excludes wides)
    fours: int = 0
    sixes: int = 0
    boundaries: int = 0
    strike_rate: float = 0.0

    # Dismissal info
    dismissed: bool = False
    dismissal_kind: str = ''
    fielder: str = ''

    # Context
    match_result: str = ''  # 'won', 'lost', 'tied', 'no_result'
    batting_position: int = 0  # Approximate from order faced


@dataclass
class BatterSeason:
    """Batter aggregate for a season."""
    batter: str
    season: str
    season_start_year: int
    team: str  # Primary team for season

    # Aggregate stats
    matches: int = 0
    innings: int = 0
    runs: int = 0
    balls_faced: int = 0
    fours: int = 0
    sixes: int = 0
    boundaries: int = 0
    dismissals: int = 0
    not_outs: int = 0

    # Derived
    average: float = 0.0
    strike_rate: float = 0.0
    boundary_rate: float = 0.0  # boundaries per ball faced
    runs_per_match: float = 0.0
    balls_per_match: float = 0.0

    # Advanced
    highest_score: int = 0
    fifties: int = 0
    hundreds: int = 0
    ducks: int = 0


@dataclass
class BatterCareer:
    """Batter career aggregate."""
    batter: str
    seasons_played: List[str] = field(default_factory=list)
    teams: List[str] = field(default_factory=list)

    # Aggregate stats
    matches: int = 0
    innings: int = 0
    runs: int = 0
    balls_faced: int = 0
    fours: int = 0
    sixes: int = 0
    boundaries: int = 0
    dismissals: int = 0
    not_outs: int = 0

    # Derived
    average: float = 0.0
    strike_rate: float = 0.0
    boundary_rate: float = 0.0
    runs_per_match: float = 0.0
    balls_per_match: float = 0.0

    # Advanced
    highest_score: int = 0
    fifties: int = 0
    hundreds: int = 0
    ducks: int = 0
    debut_season: str = ''
    last_season: str = ''


@dataclass
class BowlerInnings:
    """Bowler performance in a single innings."""
    match_id: int
    season: str
    season_start_year: int
    start_date: str
    venue: str
    innings: int
    bowling_team: str
    batter_team: str
    bowler: str

    # Bowling stats
    overs: float = 0.0  # Legal overs bowled
    balls_bowled: int = 0  # Legal deliveries bowled
    maidens: int = 0
    runs_conceded: int = 0  # Bowler conceded (excludes byes/legbyes)
    wickets: int = 0
    wides: int = 0
    noballs: int = 0
    dot_balls: int = 0

    # Derived
    economy: float = 0.0
    strike_rate: float = 0.0  # Balls per wicket
    average: float = 0.0  # Runs per wicket


@dataclass
class BowlerSeason:
    """Bowler aggregate for a season."""
    bowler: str
    season: str
    season_start_year: int
    team: str

    matches: int = 0
    innings: int = 0
    overs: float = 0.0
    balls_bowled: int = 0
    runs_conceded: int = 0
    wickets: int = 0
    wides: int = 0
    noballs: int = 0
    maidens: int = 0
    dot_balls: int = 0

    economy: float = 0.0
    strike_rate: float = 0.0
    average: float = 0.0


@dataclass
class BowlerCareer:
    """Bowler career aggregate."""
    bowler: str
    seasons_played: List[str] = field(default_factory=list)
    teams: List[str] = field(default_factory=list)

    matches: int = 0
    innings: int = 0
    overs: float = 0.0
    balls_bowled: int = 0
    runs_conceded: int = 0
    wickets: int = 0
    wides: int = 0
    noballs: int = 0
    maidens: int = 0
    dot_balls: int = 0

    economy: float = 0.0
    strike_rate: float = 0.0
    average: float = 0.0

    debut_season: str = ''
    last_season: str = ''


class DataProcessor:
    """Processes cleaned deliveries into derived records."""

    def __init__(self):
        self.batter_innings_list: List[BatterInnings] = []
        self.bowler_innings_list: List[BowlerInnings] = []
        self.batter_seasons: Dict[Tuple[str, str], BatterSeason] = {}
        self.bowler_seasons: Dict[Tuple[str, str], BowlerSeason] = {}
        self.batter_careers: Dict[str, BatterCareer] = {}
        self.bowler_careers: Dict[str, BowlerCareer] = {}

    def process_deliveries(self, cleaned_deliveries: List[CleanedDelivery]) -> None:
        """Process all cleaned deliveries into derived records."""
        logger.info(f"Processing {len(cleaned_deliveries)} deliveries...")

        # Group by match, innings, batter
        batter_innings_map: Dict[Tuple[int, int, str], BatterInnings] = {}
        bowler_innings_map: Dict[Tuple[int, int, str], BowlerInnings] = {}

        # Track batter order per innings for batting position
        batter_order: Dict[Tuple[int, int], List[str]] = defaultdict(list)
        batter_seen: Dict[Tuple[int, int], set] = defaultdict(set)

        for delivery in cleaned_deliveries:
            # Skip super overs for standard analysis (innings 1-2 only)
            if delivery.innings > 2:
                continue

            # Process batter innings
            batter_key = (delivery.match_id, delivery.innings, delivery.striker)
            if batter_key not in batter_innings_map:
                # Determine batting position
                innings_key = (delivery.match_id, delivery.innings)
                if delivery.striker not in batter_seen[innings_key]:
                    batter_order[innings_key].append(delivery.striker)
                    batter_seen[innings_key].add(delivery.striker)

                batting_pos = len(batter_order[innings_key])

                batter_innings_map[batter_key] = BatterInnings(
                    match_id=delivery.match_id,
                    season=delivery.season,
                    season_start_year=delivery.season_start_year,
                    start_date=delivery.start_date,
                    venue=delivery.venue,
                    innings=delivery.innings,
                    batting_team=delivery.batting_team,
                    bowler_team=delivery.bowling_team,
                    batter=delivery.striker,
                    batting_position=batting_pos,
                )

            bi = batter_innings_map[batter_key]
            self._update_batter_innings(bi, delivery)

            # Process bowler innings
            bowler_key = (delivery.match_id, delivery.innings, delivery.bowler)
            if bowler_key not in bowler_innings_map:
                bowler_innings_map[bowler_key] = BowlerInnings(
                    match_id=delivery.match_id,
                    season=delivery.season,
                    season_start_year=delivery.season_start_year,
                    start_date=delivery.start_date,
                    venue=delivery.venue,
                    innings=delivery.innings,
                    bowling_team=delivery.bowling_team,
                    batter_team=delivery.batting_team,
                    bowler=delivery.bowler,
                )

            boli = bowler_innings_map[bowler_key]
            self._update_bowler_innings(boli, delivery)

        # Convert to lists
        self.batter_innings_list = list(batter_innings_map.values())
        self.bowler_innings_list = list(bowler_innings_map.values())

        # Calculate strike rates for batter innings
        for bi in self.batter_innings_list:
            if bi.balls_faced > 0:
                bi.strike_rate = round(bi.runs_scored / bi.balls_faced * 100, 2)

        # Calculate derived for bowler innings
        for boli in self.bowler_innings_list:
            if boli.balls_bowled > 0:
                boli.economy = round(boli.runs_conceded / (boli.balls_bowled / 6), 2)
            if boli.wickets > 0:
                boli.strike_rate = round(boli.balls_bowled / boli.wickets, 2)
                boli.average = round(boli.runs_conceded / boli.wickets, 2)

        # Aggregate to season and career
        self._aggregate_batter_seasons()
        self._aggregate_bowler_seasons()
        self._aggregate_batter_careers()
        self._aggregate_bowler_careers()

        logger.info(f"Created {len(self.batter_innings_list)} batter innings records")
        logger.info(f"Created {len(self.bowler_innings_list)} bowler innings records")
        logger.info(f"Created {len(self.batter_seasons)} batter season aggregates")
        logger.info(f"Created {len(self.bowler_seasons)} bowler season aggregates")
        logger.info(f"Created {len(self.batter_careers)} batter career aggregates")
        logger.info(f"Created {len(self.bowler_careers)} bowler career aggregates")

    def _update_batter_innings(self, bi: BatterInnings, delivery: CleanedDelivery) -> None:
        """Update batter innings with delivery data."""
        # Only count legal deliveries as balls faced
        if delivery.is_legal_delivery:
            bi.balls_faced += 1

        bi.runs_scored += delivery.batter_runs

        if delivery.is_four:
            bi.fours += 1
            bi.boundaries += 1
        if delivery.is_six:
            bi.sixes += 1
            bi.boundaries += 1

        if delivery.is_wicket and delivery.player_dismissed == delivery.striker:
            bi.dismissed = True
            bi.dismissal_kind = delivery.dismissal_kind
            bi.fielder = delivery.fielder_1

    def _update_bowler_innings(self, boli: BowlerInnings, delivery: CleanedDelivery) -> None:
        """Update bowler innings with delivery data."""
        # Count legal deliveries
        if delivery.is_legal_delivery:
            boli.balls_bowled += 1
            if delivery.total_runs == 0:
                boli.dot_balls += 1

        boli.runs_conceded += delivery.bowler_conceded_runs
        boli.wides += delivery.wides
        boli.noballs += delivery.noballs

        if delivery.is_bowler_wicket:
            boli.wickets += 1

    def _aggregate_batter_seasons(self) -> None:
        """Aggregate batter innings to season level."""
        season_map: Dict[Tuple[str, str], BatterSeason] = {}

        for bi in self.batter_innings_list:
            key = (bi.batter, bi.season)
            if key not in season_map:
                season_map[key] = BatterSeason(
                    batter=bi.batter,
                    season=bi.season,
                    season_start_year=bi.season_start_year,
                    team=bi.batting_team,
                )

            bs = season_map[key]
            bs.matches += 1  # Will deduplicate later
            bs.innings += 1
            bs.runs += bi.runs_scored
            bs.balls_faced += bi.balls_faced
            bs.fours += bi.fours
            bs.sixes += bi.sixes
            bs.boundaries += bi.boundaries
            if bi.dismissed:
                bs.dismissals += 1
            else:
                bs.not_outs += 1
            if bi.runs_scored > bs.highest_score:
                bs.highest_score = bi.runs_scored
            if bi.runs_scored >= 100:
                bs.hundreds += 1
            elif bi.runs_scored >= 50:
                bs.fifties += 1
            if bi.runs_scored == 0 and bi.balls_faced > 0:
                bs.ducks += 1

        # Deduplicate matches and calculate derived
        batter_match_count: Dict[Tuple[str, str], set] = defaultdict(set)
        for bi in self.batter_innings_list:
            batter_match_count[(bi.batter, bi.season)].add(bi.match_id)

        for (batter, season), bs in season_map.items():
            bs.matches = len(batter_match_count[(batter, season)])
            if bs.dismissals > 0:
                bs.average = round(bs.runs / bs.dismissals, 2)
            if bs.balls_faced > 0:
                bs.strike_rate = round(bs.runs / bs.balls_faced * 100, 2)
                bs.boundary_rate = round(bs.boundaries / bs.balls_faced, 4)
            if bs.matches > 0:
                bs.runs_per_match = round(bs.runs / bs.matches, 2)
                bs.balls_per_match = round(bs.balls_faced / bs.matches, 2)

        self.batter_seasons = season_map

    def _aggregate_bowler_seasons(self) -> None:
        """Aggregate bowler innings to season level."""
        season_map: Dict[Tuple[str, str], BowlerSeason] = {}

        for boli in self.bowler_innings_list:
            key = (boli.bowler, boli.season)
            if key not in season_map:
                season_map[key] = BowlerSeason(
                    bowler=boli.bowler,
                    season=boli.season,
                    season_start_year=boli.season_start_year,
                    team=boli.bowling_team,
                )

            bs = season_map[key]
            bs.matches += 1
            bs.innings += 1
            bs.balls_bowled += boli.balls_bowled
            bs.runs_conceded += boli.runs_conceded
            bs.wickets += boli.wickets
            bs.wides += boli.wides
            bs.noballs += boli.noballs
            bs.dot_balls += boli.dot_balls

        # Deduplicate matches and calculate derived
        bowler_match_count: Dict[Tuple[str, str], set] = defaultdict(set)
        for boli in self.bowler_innings_list:
            bowler_match_count[(boli.bowler, boli.season)].add(boli.match_id)

        for (bowler, season), bs in season_map.items():
            bs.matches = len(bowler_match_count[(bowler, season)])
            bs.overs = round(bs.balls_bowled / 6, 1)
            if bs.overs > 0:
                bs.economy = round(bs.runs_conceded / bs.overs, 2)
            if bs.wickets > 0:
                bs.strike_rate = round(bs.balls_bowled / bs.wickets, 2)
                bs.average = round(bs.runs_conceded / bs.wickets, 2)

        self.bowler_seasons = season_map

    def _aggregate_batter_careers(self) -> None:
        """Aggregate batter seasons to career level."""
        career_map: Dict[str, BatterCareer] = {}

        for (batter, season), bs in self.batter_seasons.items():
            if batter not in career_map:
                career_map[batter] = BatterCareer(batter=batter)

            bc = career_map[batter]
            bc.seasons_played.append(season)
            if bs.team not in bc.teams:
                bc.teams.append(bs.team)

            bc.matches += bs.matches
            bc.innings += bs.innings
            bc.runs += bs.runs
            bc.balls_faced += bs.balls_faced
            bc.fours += bs.fours
            bc.sixes += bs.sixes
            bc.boundaries += bs.boundaries
            bc.dismissals += bs.dismissals
            bc.not_outs += bs.not_outs
            if bs.highest_score > bc.highest_score:
                bc.highest_score = bs.highest_score
            bc.fifties += bs.fifties
            bc.hundreds += bs.hundreds
            bc.ducks += bs.ducks

        # Sort seasons and calculate derived
        season_sort_key = lambda s: int(s.split('/')[0]) if '/' in s else int(s)

        for batter, bc in career_map.items():
            bc.seasons_played.sort(key=season_sort_key)
            bc.debut_season = bc.seasons_played[0] if bc.seasons_played else ''
            bc.last_season = bc.seasons_played[-1] if bc.seasons_played else ''

            if bc.dismissals > 0:
                bc.average = round(bc.runs / bc.dismissals, 2)
            if bc.balls_faced > 0:
                bc.strike_rate = round(bc.runs / bc.balls_faced * 100, 2)
                bc.boundary_rate = round(bc.boundaries / bc.balls_faced, 4)
            if bc.matches > 0:
                bc.runs_per_match = round(bc.runs / bc.matches, 2)
                bc.balls_per_match = round(bc.balls_faced / bc.matches, 2)

        self.batter_careers = career_map

    def _aggregate_bowler_careers(self) -> None:
        """Aggregate bowler seasons to career level."""
        career_map: Dict[str, BowlerCareer] = {}

        for (bowler, season), bs in self.bowler_seasons.items():
            if bowler not in career_map:
                career_map[bowler] = BowlerCareer(bowler=bowler)

            bc = career_map[bowler]
            bc.seasons_played.append(season)
            if bs.team not in bc.teams:
                bc.teams.append(bs.team)

            bc.matches += bs.matches
            bc.innings += bs.innings
            bc.balls_bowled += bs.balls_bowled
            bc.runs_conceded += bs.runs_conceded
            bc.wickets += bs.wickets
            bc.wides += bs.wides
            bc.noballs += bs.noballs
            bc.maidens += bs.maidens
            bc.dot_balls += bs.dot_balls

        season_sort_key = lambda s: int(s.split('/')[0]) if '/' in s else int(s)

        for bowler, bc in career_map.items():
            bc.seasons_played.sort(key=season_sort_key)
            bc.debut_season = bc.seasons_played[0] if bc.seasons_played else ''
            bc.last_season = bc.seasons_played[-1] if bc.seasons_played else ''

            bc.overs = round(bc.balls_bowled / 6, 1)
            if bc.overs > 0:
                bc.economy = round(bc.runs_conceded / bc.overs, 2)
            if bc.wickets > 0:
                bc.strike_rate = round(bc.balls_bowled / bc.wickets, 2)
                bc.average = round(bc.runs_conceded / bc.wickets, 2)

        self.bowler_careers = career_map

    def get_batter_innings(self) -> List[BatterInnings]:
        return self.batter_innings_list

    def get_bowler_innings(self) -> List[BowlerInnings]:
        return self.bowler_innings_list

    def get_batter_seasons(self) -> Dict[Tuple[str, str], BatterSeason]:
        return self.batter_seasons

    def get_bowler_seasons(self) -> Dict[Tuple[str, str], BowlerSeason]:
        return self.bowler_seasons

    def get_batter_careers(self) -> Dict[str, BatterCareer]:
        return self.batter_careers

    def get_bowler_careers(self) -> Dict[str, BowlerCareer]:
        return self.bowler_careers


def run_full_pipeline(zip_path: str) -> DataProcessor:
    """Run the complete data pipeline from raw zip to derived records."""
    from src.data_loader import DataLoader
    from src.data_cleaning import DataCleaner

    logger.info(f"Loading data from {zip_path}...")
    with DataLoader(zip_path) as loader:
        raw_deliveries = list(loader.load_all_matches())

    logger.info(f"Loaded {len(raw_deliveries)} raw deliveries")
    logger.info("Cleaning deliveries...")
    cleaner = DataCleaner()
    cleaned_deliveries = cleaner.clean_all(raw_deliveries)

    logger.info("Processing derived records...")
    processor = DataProcessor()
    processor.process_deliveries(cleaned_deliveries)

    return processor