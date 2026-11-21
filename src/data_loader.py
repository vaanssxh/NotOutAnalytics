"""
Data Loader Module

Loads raw Cricsheet IPL data from zip files without modifying source files.
"""

import zipfile
import csv
import io
from pathlib import Path
from typing import Iterator, Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RawDelivery:
    """Raw delivery record from Cricsheet CSV."""
    match_id: str
    season: str
    start_date: str
    venue: str
    innings: str
    ball: str
    actual_delivery: str
    batting_team: str
    bowling_team: str
    striker: str
    non_striker: str
    bowler: str
    runs_off_bat: str
    extras: str
    wides: str
    noballs: str
    byes: str
    legbyes: str
    penalty: str
    non_boundary: str
    wicket_type: str
    player_dismissed: str
    other_wicket_type: str
    other_player_dismissed: str
    fielder_1: str
    fielder_2: str
    fielder_3: str


@dataclass
class MatchInfo:
    """Match metadata from info CSV."""
    match_id: str
    season: str
    date: str
    venue: str
    city: str
    team1: str
    team2: str
    toss_winner: str
    toss_decision: str
    winner: str
    winner_runs: Optional[str]
    winner_wickets: Optional[str]
    player_of_match: str
    balls_per_over: int
    overs: int
    match_type: str
    players: Dict[str, List[str]]  # team -> list of players
    registry: Dict[str, str]  # name -> registry_id


class DataLoader:
    """Loads Cricsheet IPL data from zip archives."""

    def __init__(self, zip_path: Path):
        self.zip_path = Path(zip_path)
        if not self.zip_path.exists():
            raise FileNotFoundError(f"Zip file not found: {zip_path}")
        self._zip = None

    def __enter__(self):
        self._zip = zipfile.ZipFile(self.zip_path, 'r')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._zip:
            self._zip.close()

    def _get_zip(self):
        """Get zip file handle, opening if needed."""
        if self._zip is None:
            self._zip = zipfile.ZipFile(self.zip_path, 'r')
        return self._zip

    def list_files(self) -> List[str]:
        """List all files in the zip archive."""
        return self._get_zip().namelist()

    def load_all_matches(self) -> Iterator[RawDelivery]:
        """Load all deliveries from all_matches.csv."""
        z = self._get_zip()
        with z.open('all_matches.csv') as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
            for row in reader:
                yield RawDelivery(
                    match_id=row['match_id'],
                    season=row['season'],
                    start_date=row['start_date'],
                    venue=row['venue'],
                    innings=row['innings'],
                    ball=row['ball'],
                    actual_delivery=row['actual_delivery'],
                    batting_team=row['batting_team'],
                    bowling_team=row['bowling_team'],
                    striker=row['striker'],
                    non_striker=row['non_striker'],
                    bowler=row['bowler'],
                    runs_off_bat=row['runs_off_bat'],
                    extras=row['extras'],
                    wides=row['wides'],
                    noballs=row['noballs'],
                    byes=row['byes'],
                    legbyes=row['legbyes'],
                    penalty=row['penalty'],
                    non_boundary=row['non_boundary'],
                    wicket_type=row['wicket_type'],
                    player_dismissed=row['player_dismissed'],
                    other_wicket_type=row['other_wicket_type'],
                    other_player_dismissed=row['other_player_dismissed'],
                    fielder_1=row['fielder_1'],
                    fielder_2=row['fielder_2'],
                    fielder_3=row['fielder_3'],
                )

    def load_match_info(self, match_id: str) -> Optional[MatchInfo]:
        """Load match info from {match_id}_info.csv."""
        z = self._get_zip()
        info_filename = f"{match_id}_info.csv"
        if info_filename not in z.namelist():
            logger.warning(f"Info file not found: {info_filename}")
            return None

        with z.open(info_filename) as f:
            reader = csv.reader(io.TextIOWrapper(f, encoding='utf-8'))
            info = {}
            players = {}
            registry = {}

            for row in reader:
                if len(row) >= 2:
                    key = row[0]
                    value = row[1]
                    info[key] = value
                if len(row) >= 3 and row[0] == 'info' and row[1] == 'player':
                    team = row[2]
                    player = row[3] if len(row) > 3 else ''
                    if team not in players:
                        players[team] = []
                    players[team].append(player)
                if len(row) >= 4 and row[0] == 'info' and row[1] == 'registry' and row[2] == 'people':
                    name = row[3]
                    reg_id = row[4] if len(row) > 4 else ''
                    registry[name] = reg_id

            return MatchInfo(
                match_id=info.get('info,match_id', match_id).replace('info,match_id,', ''),
                season=info.get('info,season', ''),
                date=info.get('info,date', ''),
                venue=info.get('info,venue', ''),
                city=info.get('info,city', ''),
                team1=info.get('info,team', [''])[0] if isinstance(info.get('info,team'), list) else info.get('info,team', ''),
                team2=info.get('info,team', ['', ''])[1] if len(info.get('info,team', [''])) > 1 else '',
                toss_winner=info.get('info,toss_winner', ''),
                toss_decision=info.get('info,toss_decision', ''),
                winner=info.get('info,winner', ''),
                winner_runs=info.get('info,winner_runs'),
                winner_wickets=info.get('info,winner_wickets'),
                player_of_match=info.get('info,player_of_match', ''),
                balls_per_over=int(info.get('info,balls_per_over', 6)),
                overs=int(info.get('info,overs', 20)),
                match_type=info.get('info,match_type', 'T20'),
                players=players,
                registry=registry,
            )

    def get_unique_match_ids(self) -> List[str]:
        """Get list of unique match IDs from all_matches.csv."""
        match_ids = set()
        for delivery in self.load_all_matches():
            match_ids.add(delivery.match_id)
        return sorted(match_ids)

    def load_deliveries_for_match(self, match_id: str) -> Iterator[RawDelivery]:
        """Load deliveries for a specific match."""
        for delivery in self.load_all_matches():
            if delivery.match_id == match_id:
                yield delivery


def load_season_mapping() -> Dict[str, Tuple[int, int]]:
    """
    Map season labels to (start_year, end_year) tuples for sorting.
    IPL seasons: 2007/08, 2009, 2009/10, 2011-2026
    """
    return {
        '2007/08': (2007, 2008),
        '2009': (2009, 2009),
        '2009/10': (2009, 2010),
        '2011': (2011, 2011),
        '2012': (2012, 2012),
        '2013': (2013, 2013),
        '2014': (2014, 2014),
        '2015': (2015, 2015),
        '2016': (2016, 2016),
        '2017': (2017, 2017),
        '2018': (2018, 2018),
        '2019': (2019, 2019),
        '2020/21': (2020, 2021),
        '2021': (2021, 2021),
        '2022': (2022, 2022),
        '2023': (2023, 2023),
        '2024': (2024, 2024),
        '2025': (2025, 2025),
        '2026': (2026, 2026),
    }


def get_season_sort_key(season: str) -> int:
    """Get sort key for season (start year)."""
    mapping = load_season_mapping()
    return mapping.get(season, (9999, 9999))[0]