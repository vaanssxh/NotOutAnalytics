#!/usr/bin/env python3
"""
Database Seeding Script

Populates the SQLite database with IPL data from the processed pipeline.
Creates tables from schema.sql and loads all reference data, matches, innings,
deliveries, and player_innings aggregates.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_loader import DataLoader, RawDelivery, load_season_mapping, get_season_sort_key
from src.data_cleaning import DataCleaner, CleanedDelivery
from src.data_processor import DataProcessor, run_full_pipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration."""
    db_path: str = "C:/claudepro/Sports-Analytics/data/ipl_analytics.db"
    schema_path: str = "C:/claudepro/Sports-Analytics/sql/schema.sql"
    batch_size: int = 10000


class DatabaseSeeder:
    """Seeds the SQLite database with IPL cricket data."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

        # Mapping dictionaries for ID lookups
        self.season_map: Dict[str, int] = {}           # season_name -> season_id
        self.team_map: Dict[str, int] = {}             # canonical_name -> team_id
        self.team_alias_map: Dict[str, int] = {}       # alias_name -> team_id
        self.venue_map: Dict[str, int] = {}            # venue_name -> venue_id
        self.player_map: Dict[str, int] = {}           # player_name -> player_id
        self.player_alias_map: Dict[str, int] = {}     # alias_name -> player_id
        self.match_id_map: Dict[int, int] = {}         # cricsheet_match_id -> match_id (same in our case)

        # Team canonical names from data_cleaning
        self.TEAM_CANONICAL = {
            'Delhi Daredevils': 'Delhi Capitals',
            'Deccan Chargers': 'Sunrisers Hyderabad',
            'Pune Warriors': 'Pune Warriors',  # Defunct
            'Kochi Tuskers Kerala': 'Kochi Tuskers Kerala',  # Defunct
            'Rising Pune Supergiant': 'Rising Pune Supergiant',  # Defunct
            'Rising Pune Supergiants': 'Rising Pune Supergiant',
            'Gujarat Lions': 'Gujarat Lions',  # Defunct
            'Mumbai Indians': 'Mumbai Indians',
            'Chennai Super Kings': 'Chennai Super Kings',
            'Royal Challengers Bangalore': 'Royal Challengers Bangalore',
            'Royal Challengers Bengaluru': 'Royal Challengers Bangalore',
            'Kolkata Knight Riders': 'Kolkata Knight Riders',
            'Kings XI Punjab': 'Punjab Kings',
            'Punjab Kings': 'Punjab Kings',
            'Rajasthan Royals': 'Rajasthan Royals',
            'Sunrisers Hyderabad': 'Sunrisers Hyderabad',
            'Gujarat Titans': 'Gujarat Titans',
            'Lucknow Super Giants': 'Lucknow Super Giants',
        }

        # Team colors for visualization
        self.TEAM_COLORS = {
            'Mumbai Indians': ('#004BA0', '#D1AB3E'),
            'Chennai Super Kings': ('#F9CD05', '#8B0000'),
            'Royal Challengers Bangalore': ('#EC1C24', '#000000'),
            'Royal Challengers Bengaluru': ('#EC1C24', '#000000'),
            'Kolkata Knight Riders': ('#3A225D', '#D4A81C'),
            'Punjab Kings': ('#ED1B24', '#FFFFFF'),
            'Kings XI Punjab': ('#ED1B24', '#FFFFFF'),
            'Rajasthan Royals': ('#254AA5', '#EA1A2C'),
            'Sunrisers Hyderabad': ('#FF822A', '#000000'),
            'Delhi Capitals': ('#17449B', '#DC143C'),
            'Delhi Daredevils': ('#17449B', '#DC143C'),
            'Gujarat Titans': ('#1C1C1C', '#FFFFFF'),
            'Lucknow Super Giants': ('#00A3E0', '#FFFFFF'),
            'Gujarat Lions': ('#F26522', '#000000'),
            'Rising Pune Supergiant': ('#7A0019', '#FFFFFF'),
            'Pune Warriors': ('#00A651', '#FFFFFF'),
            'Kochi Tuskers Kerala': ('#FF6600', '#000000'),
            'Deccan Chargers': ('#000000', '#1E90FF'),
        }

        # Team short names
        self.TEAM_SHORT = {
            'Mumbai Indians': 'MI',
            'Chennai Super Kings': 'CSK',
            'Royal Challengers Bangalore': 'RCB',
            'Royal Challengers Bengaluru': 'RCB',
            'Kolkata Knight Riders': 'KKR',
            'Punjab Kings': 'PBKS',
            'Kings XI Punjab': 'KXIP',
            'Rajasthan Royals': 'RR',
            'Sunrisers Hyderabad': 'SRH',
            'Delhi Capitals': 'DC',
            'Delhi Daredevils': 'DD',
            'Gujarat Titans': 'GT',
            'Lucknow Super Giants': 'LSG',
            'Gujarat Lions': 'GL',
            'Rising Pune Supergiant': 'RPS',
            'Pune Warriors': 'PWI',
            'Kochi Tuskers Kerala': 'KTK',
            'Deccan Chargers': 'DC',
        }

    def connect(self) -> None:
        """Establish database connection."""
        db_path = Path(self.config.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.config.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.cursor = self.conn.cursor()
        logger.info(f"Connected to database: {self.config.db_path}")

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.commit()
            self.conn.close()
            logger.info("Database connection closed")

    def create_schema(self) -> None:
        """Create database schema from SQL file."""
        schema_path = Path(self.config.schema_path)
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        # Split by semicolon and execute each statement
        statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
        for stmt in statements:
            if stmt:
                try:
                    self.cursor.execute(stmt)
                except sqlite3.Error as e:
                    logger.warning(f"Schema statement failed: {e}\nStatement: {stmt[:100]}...")

        self.conn.commit()
        logger.info("Database schema created successfully")

    def _get_or_create_season(self, season_name: str, start_year: int) -> int:
        """Get or create season record."""
        if season_name in self.season_map:
            return self.season_map[season_name]

        # Determine end_year
        if '/' in season_name:
            parts = season_name.split('/')
            end_year = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else start_year + 1
        else:
            end_year = start_year

        self.cursor.execute("""
            INSERT OR IGNORE INTO seasons (season_name, start_year, end_year)
            VALUES (?, ?, ?)
        """, (season_name, start_year, end_year))

        self.cursor.execute("SELECT season_id FROM seasons WHERE season_name = ?", (season_name,))
        row = self.cursor.fetchone()
        season_id = row[0] if row else None
        self.season_map[season_name] = season_id
        return season_id

    def _get_or_create_team(self, team_name: str) -> int:
        """Get or create team record using canonical name."""
        canonical = self.TEAM_CANONICAL.get(team_name, team_name)

        if canonical in self.team_map:
            # Also map the alias
            self.team_alias_map[team_name] = self.team_map[canonical]
            return self.team_map[canonical]

        short_name = self.TEAM_SHORT.get(canonical, canonical[:3].upper())
        primary_color, secondary_color = self.TEAM_COLORS.get(canonical, ('#000000', '#FFFFFF'))

        self.cursor.execute("""
            INSERT OR IGNORE INTO teams (canonical_name, display_name, short_name, primary_color, secondary_color)
            VALUES (?, ?, ?, ?, ?)
        """, (canonical, canonical, short_name, primary_color, secondary_color))

        self.cursor.execute("SELECT team_id FROM teams WHERE canonical_name = ?", (canonical,))
        row = self.cursor.fetchone()
        team_id = row[0] if row else None
        self.team_map[canonical] = team_id
        self.team_alias_map[team_name] = team_id

        # If different from canonical, also add alias
        if team_name != canonical:
            self.cursor.execute("""
                INSERT OR IGNORE INTO team_aliases (team_id, alias_name)
                VALUES (?, ?)
            """, (team_id, team_name))

        return team_id

    def _get_or_create_venue(self, venue_name: str) -> int:
        """Get or create venue record."""
        if venue_name in self.venue_map:
            return self.venue_map[venue_name]

        # Parse city from venue name if possible
        city = venue_name.split(',')[0].strip() if ',' in venue_name else venue_name

        self.cursor.execute("""
            INSERT OR IGNORE INTO venues (venue_name, city)
            VALUES (?, ?)
        """, (venue_name, city))

        self.cursor.execute("SELECT venue_id FROM venues WHERE venue_name = ?", (venue_name,))
        row = self.cursor.fetchone()
        venue_id = row[0] if row else None
        self.venue_map[venue_name] = venue_id
        return venue_id

    def _get_or_create_player(self, player_name: str) -> int:
        """Get or create player record."""
        if player_name in self.player_map:
            return self.player_map[player_name]

        # Generate short name (initials + surname)
        parts = player_name.split()
        if len(parts) >= 2:
            short_name = f"{parts[0][0]}. {' '.join(parts[1:])}"
        else:
            short_name = player_name

        self.cursor.execute("""
            INSERT OR IGNORE INTO players (player_name, short_name, known_as)
            VALUES (?, ?, ?)
        """, (player_name, short_name, player_name))

        self.cursor.execute("SELECT player_id FROM players WHERE player_name = ?", (player_name,))
        row = self.cursor.fetchone()
        player_id = row[0] if row else None
        self.player_map[player_name] = player_id
        return player_id

    def seed_reference_data(self, raw_deliveries: List[RawDelivery]) -> None:
        """Seed seasons, teams, venues, players from raw deliveries."""
        logger.info("Seeding reference data...")

        # Get season mapping from data_loader
        season_mapping = load_season_mapping()

        seasons_seen = set()
        teams_seen = set()
        venues_seen = set()
        players_seen = set()

        for delivery in raw_deliveries:
            # Seasons
            season_start_year = season_mapping.get(delivery.season, (9999, 9999))[0]
            season_key = (delivery.season, season_start_year)
            if season_key not in seasons_seen:
                self._get_or_create_season(delivery.season, season_start_year)
                seasons_seen.add(season_key)

            # Teams
            for team in [delivery.batting_team, delivery.bowling_team]:
                if team not in teams_seen:
                    self._get_or_create_team(team)
                    teams_seen.add(team)

            # Venues
            if delivery.venue not in venues_seen:
                self._get_or_create_venue(delivery.venue)
                venues_seen.add(delivery.venue)

            # Players
            for player in [delivery.striker, delivery.non_striker, delivery.bowler]:
                if player not in players_seen:
                    self._get_or_create_player(player)
                    players_seen.add(player)

            # Dismissed player
            if delivery.player_dismissed and delivery.player_dismissed not in players_seen:
                self._get_or_create_player(delivery.player_dismissed)
                players_seen.add(delivery.player_dismissed)

            # Fielders
            for fielder in [delivery.fielder_1, delivery.fielder_2, delivery.fielder_3]:
                if fielder and fielder not in players_seen:
                    self._get_or_create_player(fielder)
                    players_seen.add(fielder)

        self.conn.commit()
        logger.info(f"Reference data seeded: {len(seasons_seen)} seasons, "
                    f"{len(teams_seen)} teams, {len(venues_seen)} venues, "
                    f"{len(players_seen)} players")

    def seed_matches_and_innings(self, cleaned_deliveries: List[CleanedDelivery],
                                  match_info_list: List[Any]) -> None:
        """Seed matches and innings tables."""
        logger.info("Seeding matches and innings...")

        # Group deliveries by match
        matches_data: Dict[int, Dict] = {}
        innings_data: Dict[Tuple[int, int], Dict] = {}

        for delivery in cleaned_deliveries:
            mid = delivery.match_id
            inn = delivery.innings

            if mid not in matches_data:
                matches_data[mid] = {
                    'season': delivery.season,
                    'start_date': delivery.start_date,
                    'venue': delivery.venue,
                    'team1': delivery.batting_team,
                    'team2': delivery.bowling_team,
                    'innings': set(),
                }
            matches_data[mid]['innings'].add(inn)

            inn_key = (mid, inn)
            if inn_key not in innings_data:
                innings_data[inn_key] = {
                    'batting_team': delivery.batting_team,
                    'bowling_team': delivery.bowling_team,
                    'runs': 0,
                    'wickets': 0,
                    'balls': 0,
                    'overs': 0.0,
                }

            # Aggregate innings data
            inn_data = innings_data[inn_key]
            inn_data['runs'] += delivery.total_runs
            if delivery.is_wicket:
                inn_data['wickets'] += 1
            if delivery.is_legal_delivery:
                inn_data['balls'] += 1

        # Insert matches
        for match_id, mdata in matches_data.items():
            season_id = self.season_map.get(mdata['season'])
            venue_id = self.venue_map.get(mdata['venue'])
            team1_id = self.team_alias_map.get(mdata['team1'])
            team2_id = self.team_alias_map.get(mdata['team2'])

            # Determine match number within season
            self.cursor.execute("""
                SELECT COALESCE(MAX(match_number), 0) + 1
                FROM matches WHERE season_id = ?
            """, (season_id,))
            match_number = self.cursor.fetchone()[0]

            self.cursor.execute("""
                INSERT OR REPLACE INTO matches (
                    match_id, season_id, match_number, start_date, venue_id,
                    team1_id, team2_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (match_id, season_id, match_number, mdata['start_date'],
                  venue_id, team1_id, team2_id))

        # Insert innings
        for (match_id, inn_num), idata in innings_data.items():
            batting_team_id = self.team_alias_map.get(idata['batting_team'])
            bowling_team_id = self.team_alias_map.get(idata['bowling_team'])
            overs = round(idata['balls'] / 6.0, 1)

            self.cursor.execute("""
                INSERT OR REPLACE INTO innings (
                    match_id, innings_number, batting_team_id, bowling_team_id,
                    innings_total_runs, innings_wickets, innings_overs
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (match_id, inn_num, batting_team_id, bowling_team_id,
                  idata['runs'], idata['wickets'], overs))

        self.conn.commit()
        logger.info(f"Seeded {len(matches_data)} matches and {len(innings_data)} innings")

    def seed_deliveries(self, cleaned_deliveries: List[CleanedDelivery]) -> None:
        """Seed deliveries table in batches."""
        logger.info(f"Seeding {len(cleaned_deliveries)} deliveries...")

        batch = []
        for idx, d in enumerate(cleaned_deliveries):
            # Skip super overs for main deliveries table (optional, but keeps it cleaner)
            if d.innings > 2:
                continue

            # Get IDs
            match_id = d.match_id
            innings_id = self._get_innings_id(match_id, d.innings)
            if not innings_id:
                continue

            striker_id = self.player_map.get(d.striker)
            non_striker_id = self.player_map.get(d.non_striker)
            bowler_id = self.player_map.get(d.bowler)
            dismissed_id = self.player_map.get(d.player_dismissed) if d.player_dismissed else None
            fielder1_id = self.player_map.get(d.fielder_1) if d.fielder_1 else None
            fielder2_id = self.player_map.get(d.fielder_2) if d.fielder_2 else None
            fielder3_id = self.player_map.get(d.fielder_3) if d.fielder_3 else None
            batting_team_id = self.team_alias_map.get(d.batting_team)
            bowling_team_id = self.team_alias_map.get(d.bowling_team)

            # Calculate over/ball tracking
            is_over_start = (d.ball_in_over == 1 and d.is_legal_delivery)
            # is_over_end requires knowing the last ball of over - skip for now
            is_bye = d.byes > 0
            is_legbye = d.legbyes > 0
            is_penalty = d.penalty > 0

            batch.append((
                match_id, innings_id, d.innings, d.over, d.ball_in_over,
                d.actual_delivery_seq if hasattr(d, 'actual_delivery_seq') else idx + 1,
                striker_id, non_striker_id, bowler_id,
                d.runs_off_bat, d.wides, d.noballs,
                d.byes, d.legbyes, d.penalty,
                d.total_runs, d.batter_runs, d.bowler_conceded_runs,
                d.is_wide, d.is_noball, is_bye, is_legbye, is_penalty,
                d.is_boundary, d.is_four, d.is_six, d.is_legal_delivery,
                d.is_wicket, dismissed_id, d.dismissal_kind,
                fielder1_id, fielder2_id, fielder3_id,
                batting_team_id, bowling_team_id,
                is_over_start, 0, 0, 0,  # over_runs_so_far, over_wickets_so_far, etc.
                0, 0, None, None  # innings_runs_at_start, etc.
            ))

            if len(batch) >= self.config.batch_size:
                self._insert_delivery_batch(batch)
                batch = []

        if batch:
            self._insert_delivery_batch(batch)

        self.conn.commit()
        logger.info("Deliveries seeded successfully")

    def _get_innings_id(self, match_id: int, innings_number: int) -> Optional[int]:
        """Get innings_id for a match/innings combination."""
        self.cursor.execute("""
            SELECT innings_id FROM innings
            WHERE match_id = ? AND innings_number = ?
        """, (match_id, innings_number))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def _insert_delivery_batch(self, batch: List[Tuple]) -> None:
        """Insert a batch of deliveries."""
        self.cursor.executemany("""
            INSERT OR REPLACE INTO deliveries (
                match_id, innings_id, innings_number, over_number, ball_number,
                actual_delivery_number, striker_id, non_striker_id, bowler_id,
                runs_off_bat, extras_wides, extras_noballs, extras_byes,
                extras_legbyes, extras_penalty, total_runs, batter_runs,
                bowler_conceded_runs, is_wide, is_noball, is_bye, is_legbye,
                is_penalty, is_boundary, is_four, is_six, is_legal_delivery,
                is_wicket, player_dismissed_id, dismissal_kind,
                fielder1_id, fielder2_id, fielder3_id,
                batting_team_id, bowling_team_id,
                is_over_start, is_over_end, over_runs_so_far, over_wickets_so_far,
                innings_runs_at_start, innings_wickets_at_start,
                required_run_rate, balls_remaining
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch)

    def seed_player_innings(self, processor: DataProcessor) -> None:
        """Seed player_innings table from processed aggregates."""
        logger.info("Seeding player_innings aggregates...")

        # Batter innings
        for bi in processor.get_batter_innings():
            match_id = bi.match_id
            innings_id = self._get_innings_id(match_id, bi.innings)
            if not innings_id:
                continue

            player_id = self.player_map.get(bi.batter)
            team_id = self.team_alias_map.get(bi.batting_team)
            opponent_id = self.team_alias_map.get(bi.bowler_team)
            venue_id = self.venue_map.get(bi.venue)
            season_id = self.season_map.get(bi.season)

            # Determine match result
            self.cursor.execute("""
                SELECT winner_id, team1_id, team2_id
                FROM matches WHERE match_id = ?
            """, (match_id,))
            mrow = self.cursor.fetchone()
            match_result = ''
            is_batting_first = (bi.innings == 1)
            if mrow:
                winner_id, team1_id, team2_id = mrow
                if winner_id == team_id:
                    match_result = 'won'
                elif winner_id is not None:
                    match_result = 'lost'
                else:
                    match_result = 'no_result'

            self.cursor.execute("""
                INSERT OR REPLACE INTO player_innings (
                    match_id, innings_id, innings_number, player_id, team_id,
                    opponent_team_id, venue_id, season_id, start_date,
                    runs_scored, balls_faced, fours, sixes, boundaries,
                    strike_rate, batting_position, dismissed, dismissal_kind,
                    fielder_id, match_result, team_innings_total,
                    team_innings_wickets, is_batting_first
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id, innings_id, bi.innings, player_id, team_id,
                opponent_id, venue_id, season_id, bi.start_date,
                bi.runs_scored, bi.balls_faced, bi.fours, bi.sixes, bi.boundaries,
                bi.strike_rate, bi.batting_position, bi.dismissed,
                bi.dismissal_kind, self.player_map.get(bi.fielder) if bi.fielder else None,
                match_result, 0, 0, is_batting_first
            ))

        # Bowler innings - update existing rows
        for boli in processor.get_bowler_innings():
            match_id = boli.match_id
            innings_id = self._get_innings_id(match_id, boli.innings)
            if not innings_id:
                continue

            player_id = self.player_map.get(boli.bowler)
            team_id = self.team_alias_map.get(boli.bowling_team)

            self.cursor.execute("""
                UPDATE player_innings SET
                    overs_bowled = ?, balls_bowled = ?, maidens = ?,
                    runs_conceded = ?, wickets_taken = ?, wides_bowled = ?,
                    noballs_bowled = ?, dot_balls = ?, economy_rate = ?,
                    bowling_strike_rate = ?, bowling_average = ?
                WHERE match_id = ? AND innings_id = ? AND player_id = ?
            """, (
                boli.overs, boli.balls_bowled, boli.maidens,
                boli.runs_conceded, boli.wickets, boli.wides, boli.noballs,
                boli.dot_balls, boli.economy, boli.strike_rate, boli.average,
                match_id, innings_id, player_id
            ))

        self.conn.commit()
        logger.info("Player innings seeded successfully")

    def update_match_results(self) -> None:
        """Update match results, winner, player of match, etc."""
        logger.info("Updating match results and metadata...")

        # For each match, calculate winner from innings totals
        self.cursor.execute("SELECT match_id FROM matches")
        match_ids = [row[0] for row in self.cursor.fetchall()]

        for match_id in match_ids:
            # Get innings totals
            self.cursor.execute("""
                SELECT innings_number, batting_team_id, innings_total_runs, innings_wickets
                FROM innings WHERE match_id = ? AND innings_number <= 2
                ORDER BY innings_number
            """, (match_id,))
            innings = self.cursor.fetchall()

            if len(innings) == 2:
                inn1_num, team1_id, runs1, wkts1 = innings[0]
                inn2_num, team2_id, runs2, wkts2 = innings[1]

                winner_id = None
                win_by_runs = 0
                win_by_wickets = 0
                match_result = 'normal'

                if runs1 > runs2:
                    winner_id = team1_id
                    win_by_runs = runs1 - runs2
                elif runs2 > runs1:
                    winner_id = team2_id
                    win_by_wickets = 10 - wkts2
                else:
                    match_result = 'tie'

                # Get player of match (top performer)
                self.cursor.execute("""
                    SELECT player_id,
                           (runs_scored + wickets_taken * 20) as impact
                    FROM player_innings
                    WHERE match_id = ?
                    ORDER BY impact DESC
                    LIMIT 1
                """, (match_id,))
                pom = self.cursor.fetchone()
                pom_id = pom[0] if pom else None

                self.cursor.execute("""
                    UPDATE matches SET
                        winner_id = ?, win_by_runs = ?, win_by_wickets = ?,
                        match_result = ?, player_of_match_id = ?
                    WHERE match_id = ?
                """, (winner_id, win_by_runs, win_by_wickets, match_result, pom_id, match_id))

        self.conn.commit()
        logger.info("Match results updated")

    def update_season_totals(self) -> None:
        """Update season aggregate totals."""
        logger.info("Updating season totals...")

        self.cursor.execute("""
            UPDATE seasons SET
                total_matches = (SELECT COUNT(*) FROM matches WHERE season_id = seasons.season_id),
                total_runs = (SELECT COALESCE(SUM(innings_total_runs), 0)
                              FROM innings i JOIN matches m ON i.match_id = m.match_id
                              WHERE m.season_id = seasons.season_id),
                total_wickets = (SELECT COALESCE(SUM(innings_wickets), 0)
                                 FROM innings i JOIN matches m ON i.match_id = m.match_id
                                 WHERE m.season_id = seasons.season_id)
        """)

        self.conn.commit()
        logger.info("Season totals updated")

    def run_full_seed(self, zip_path: str) -> None:
        """Run the complete seeding pipeline."""
        logger.info("=" * 60)
        logger.info("STARTING DATABASE SEEDING")
        logger.info("=" * 60)

        self.connect()

        try:
            # Create schema
            self.create_schema()

            # Load data using existing pipeline
            logger.info("Loading raw data...")
            with DataLoader(zip_path) as loader:
                raw_deliveries = list(loader.load_all_matches())
                # Get unique match IDs and load match info for each
                match_ids = loader.get_unique_match_ids()
                match_info_list = []
                for mid in match_ids:
                    info = loader.load_match_info(mid)
                    if info:
                        match_info_list.append(info)

            logger.info(f"Loaded {len(raw_deliveries)} raw deliveries")

            # Clean data
            logger.info("Cleaning data...")
            cleaner = DataCleaner()
            cleaned_deliveries = cleaner.clean_all(raw_deliveries)

            # Process aggregates
            logger.info("Processing aggregates...")
            processor = DataProcessor()
            processor.process_deliveries(cleaned_deliveries)

            # Seed reference data
            self.seed_reference_data(raw_deliveries)

            # Seed matches and innings
            self.seed_matches_and_innings(cleaned_deliveries, match_info_list)

            # Seed deliveries
            self.seed_deliveries(cleaned_deliveries)

            # Seed player innings
            self.seed_player_innings(processor)

            # Update derived data
            self.update_match_results()
            self.update_season_totals()

            # Final commit
            self.conn.commit()

            logger.info("=" * 60)
            logger.info("DATABASE SEEDING COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)

            # Print summary
            self.print_summary()

        except Exception as e:
            logger.error(f"Seeding failed: {e}")
            self.conn.rollback()
            raise
        finally:
            self.close()

    def print_summary(self) -> None:
        """Print database summary statistics."""
        tables = [
            'seasons', 'teams', 'venues', 'players',
            'matches', 'innings', 'deliveries', 'player_innings'
        ]

        print("\nDatabase Summary:")
        print("-" * 40)
        for table in tables:
            self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = self.cursor.fetchone()[0]
            print(f"  {table:20s}: {count:,}")


def main():
    """Main entry point."""
    zip_path = "C:/claudepro/Sports-Analytics/data/raw/ipl_csv2.zip"

    if not Path(zip_path).exists():
        logger.error(f"Zip file not found: {zip_path}")
        sys.exit(1)

    config = DatabaseConfig()
    seeder = DatabaseSeeder(config)
    seeder.run_full_seed(zip_path)


if __name__ == '__main__':
    main()