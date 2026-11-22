"""
Data Access Module for Statistics Engine.

Provides functions to query the IPL database for statistical analysis.
Uses the existing database views and tables.
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "C:/claudepro/Sports-Analytics/data/ipl_analytics.db"


def get_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_batter_career(min_balls: int = 200) -> pd.DataFrame:
    """Get career batting stats for all batters meeting minimum balls threshold."""
    conn = get_connection()
    query = """
        SELECT * FROM v_batter_career
        WHERE balls_faced >= ?
        ORDER BY runs DESC
    """
    df = pd.read_sql_query(query, conn, params=(min_balls,))
    conn.close()
    return df


def get_batter_season(min_balls: int = 100) -> pd.DataFrame:
    """Get season batting stats for all batters."""
    conn = get_connection()
    query = """
        SELECT * FROM v_batter_season
        WHERE balls_faced >= ?
        ORDER BY season_name, runs DESC
    """
    df = pd.read_sql_query(query, conn, params=(min_balls,))
    conn.close()
    return df


def get_bowler_career(min_balls: int = 100) -> pd.DataFrame:
    """Get career bowling stats for all bowlers."""
    conn = get_connection()
    query = """
        SELECT * FROM v_bowler_career
        WHERE balls_bowled >= ?
        ORDER BY wickets DESC
    """
    df = pd.read_sql_query(query, conn, params=(min_balls,))
    conn.close()
    return df


def get_bowler_season(min_balls: int = 50) -> pd.DataFrame:
    """Get season bowling stats for all bowlers."""
    conn = get_connection()
    query = """
        SELECT * FROM v_bowler_season
        WHERE balls_bowled >= ?
        ORDER BY season_name, wickets DESC
    """
    df = pd.read_sql_query(query, conn, params=(min_balls,))
    conn.close()
    return df


def get_player_innings(player_name: str) -> pd.DataFrame:
    """Get all innings for a specific player (batting and bowling)."""
    conn = get_connection()
    query = """
        SELECT
            pi.*,
            m.start_date,
            m.match_id,
            s.season_name,
            p.player_name,
            t.canonical_name as team_name,
            v.venue_name
        FROM player_innings pi
        JOIN players p ON pi.player_id = p.player_id
        JOIN matches m ON pi.match_id = m.match_id
        JOIN seasons s ON pi.season_id = s.season_id
        JOIN teams t ON pi.team_id = t.team_id
        JOIN venues v ON pi.venue_id = v.venue_id
        WHERE p.player_name = ?
        ORDER BY m.start_date, pi.innings_number
    """
    df = pd.read_sql_query(query, conn, params=(player_name,))
    conn.close()
    return df


def get_batter_innings(player_name: str, min_balls: int = 1) -> pd.DataFrame:
    """Get batting innings for a specific player."""
    conn = get_connection()
    query = """
        SELECT
            pi.*,
            m.start_date,
            m.match_id,
            s.season_name,
            p.player_name,
            t.canonical_name as team_name,
            v.venue_name
        FROM player_innings pi
        JOIN players p ON pi.player_id = p.player_id
        JOIN matches m ON pi.match_id = m.match_id
        JOIN seasons s ON pi.season_id = s.season_id
        JOIN teams t ON pi.team_id = t.team_id
        JOIN venues v ON pi.venue_id = v.venue_id
        WHERE p.player_name = ?
          AND pi.balls_faced >= ?
        ORDER BY m.start_date, pi.innings_number
    """
    df = pd.read_sql_query(query, conn, params=(player_name, min_balls))
    conn.close()
    return df


def get_bowler_innings(player_name: str, min_balls: int = 1) -> pd.DataFrame:
    """Get bowling innings for a specific player."""
    conn = get_connection()
    query = """
        SELECT
            pi.*,
            m.start_date,
            m.match_id,
            s.season_name,
            p.player_name,
            t.canonical_name as team_name,
            v.venue_name
        FROM player_innings pi
        JOIN players p ON pi.player_id = p.player_id
        JOIN matches m ON pi.match_id = m.match_id
        JOIN seasons s ON pi.season_id = s.season_id
        JOIN teams t ON pi.team_id = t.team_id
        JOIN venues v ON pi.venue_id = v.venue_id
        WHERE p.player_name = ?
          AND pi.balls_bowled >= ?
        ORDER BY m.start_date, pi.innings_number
    """
    df = pd.read_sql_query(query, conn, params=(player_name, min_balls))
    conn.close()
    return df


def get_league_boundary_stats(min_balls: int = 100) -> Tuple[float, float, int]:
    """Get league-wide boundary rate statistics for empirical Bayes prior.

    Returns:
        - total_boundaries: Total fours + sixes across all qualified batters
        - total_balls_faced: Total balls faced across all qualified batters
        - n_players: Number of qualified batters
    """
    conn = get_connection()
    query = """
        SELECT
            SUM(boundaries) as total_boundaries,
            SUM(balls_faced) as total_balls_faced,
            COUNT(*) as n_players
        FROM v_batter_career
        WHERE balls_faced >= ?
    """
    df = pd.read_sql_query(query, conn, params=(min_balls,))
    conn.close()
    total_boundaries = int(df.iloc[0]['total_boundaries'])
    total_balls_faced = int(df.iloc[0]['total_balls_faced'])
    n_players = int(df.iloc[0]['n_players'])
    return total_boundaries, total_balls_faced, n_players


def get_batter_career_balls_boundaries(player_name: str, min_balls: int = 0) -> Tuple[int, int]:
    """Get career balls faced and boundaries for a specific batter."""
    conn = get_connection()
    query = """
        SELECT balls_faced, boundaries
        FROM v_batter_career
        WHERE player_name = ?
    """
    params = [player_name]
    if min_balls > 0:
        query += " AND balls_faced >= ?"
        params.append(min_balls)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if df.empty:
        return 0, 0
    return int(df.iloc[0]['balls_faced']), int(df.iloc[0]['boundaries'])


def get_all_batter_innings_strike_rates(min_balls: int = 10) -> pd.DataFrame:
    """Get all batter innings strike rates for distribution analysis."""
    conn = get_connection()
    query = """
        SELECT
            pi.player_id,
            p.player_name,
            pi.runs_scored,
            pi.balls_faced,
            pi.strike_rate,
            m.start_date,
            s.season_name
        FROM player_innings pi
        JOIN players p ON pi.player_id = p.player_id
        JOIN matches m ON pi.match_id = m.match_id
        JOIN seasons s ON pi.season_id = s.season_id
        WHERE pi.balls_faced >= ?
        ORDER BY p.player_name, m.start_date
    """
    df = pd.read_sql_query(query, conn, params=(min_balls,))
    conn.close()
    return df


def get_career_halves_strike_rate(min_balls_per_half: int = 100) -> pd.DataFrame:
    """Get first-half vs second-half career strike rates for regression to mean analysis.

    Uses chronological splitting by start_date.
    """
    conn = get_connection()
    query = """
        WITH career_halves AS (
            SELECT
                pi.player_id,
                p.player_name,
                p.short_name,
                pi.player_innings_id,
                pi.runs_scored,
                pi.balls_faced,
                pi.strike_rate,
                m.start_date,
                -- Assign each innings to first or second half of career
                NTILE(2) OVER (PARTITION BY pi.player_id ORDER BY m.start_date) AS career_half
            FROM player_innings pi
            JOIN players p ON pi.player_id = p.player_id
            JOIN matches m ON pi.match_id = m.match_id
            WHERE pi.balls_faced >= 1
        ),
        half_stats AS (
            SELECT
                player_id,
                player_name,
                short_name,
                SUM(CASE WHEN career_half = 1 THEN runs_scored ELSE 0 END) AS first_half_runs,
                SUM(CASE WHEN career_half = 1 THEN balls_faced ELSE 0 END) AS first_half_balls,
                SUM(CASE WHEN career_half = 2 THEN runs_scored ELSE 0 END) AS second_half_runs,
                SUM(CASE WHEN career_half = 2 THEN balls_faced ELSE 0 END) AS second_half_balls,
                COUNT(CASE WHEN career_half = 1 THEN 1 END) AS first_half_innings,
                COUNT(CASE WHEN career_half = 2 THEN 1 END) AS second_half_innings
            FROM career_halves
            GROUP BY player_id, player_name, short_name
        )
        SELECT
            player_id,
            player_name,
            short_name,
            first_half_runs,
            first_half_balls,
            second_half_runs,
            second_half_balls,
            first_half_innings,
            second_half_innings,
            CASE WHEN first_half_balls > 0
                 THEN ROUND(1.0 * first_half_runs / first_half_balls * 100, 2)
                 ELSE NULL END AS first_half_strike_rate,
            CASE WHEN second_half_balls > 0
                 THEN ROUND(1.0 * second_half_runs / second_half_balls * 100, 2)
                 ELSE NULL END AS second_half_strike_rate
        FROM half_stats
        WHERE first_half_balls >= ? AND second_half_balls >= ?
        ORDER BY first_half_strike_rate DESC
    """
    df = pd.read_sql_query(query, conn, params=(min_balls_per_half, min_balls_per_half))
    conn.close()
    return df


def get_player_comparison_data(player_names: List[str], min_balls: int = 10) -> pd.DataFrame:
    """Get innings data for multiple players for comparison."""
    conn = get_connection()
    placeholders = ','.join(['?'] * len(player_names))
    query = f"""
        SELECT
            pi.player_id,
            p.player_name,
            pi.runs_scored,
            pi.balls_faced,
            pi.strike_rate,
            pi.fours,
            pi.sixes,
            pi.boundaries,
            pi.dismissed,
            m.start_date,
            s.season_name
        FROM player_innings pi
        JOIN players p ON pi.player_id = p.player_id
        JOIN matches m ON pi.match_id = m.match_id
        JOIN seasons s ON pi.season_id = s.season_id
        WHERE p.player_name IN ({placeholders})
          AND pi.balls_faced >= ?
        ORDER BY p.player_name, m.start_date
    """
    params = player_names + [min_balls]
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_league_strike_rate_distribution(min_balls: int = 10) -> pd.DataFrame:
    """Get league-wide innings strike rate distribution for reference."""
    conn = get_connection()
    query = """
        SELECT
            pi.strike_rate,
            pi.balls_faced,
            p.player_name
        FROM player_innings pi
        JOIN players p ON pi.player_id = p.player_id
        WHERE pi.balls_faced >= ?
        ORDER BY pi.strike_rate
    """
    df = pd.read_sql_query(query, conn, params=(min_balls,))
    conn.close()
    return df


def get_top_batters_by_strike_rate(min_balls: int = 500, limit: int = 50) -> pd.DataFrame:
    """Get top batters by career strike rate with qualification."""
    conn = get_connection()
    query = """
        SELECT * FROM v_batter_career
        WHERE balls_faced >= ?
        ORDER BY strike_rate DESC
        LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=(min_balls, limit))
    conn.close()
    return df


def get_boundary_rate_by_player(min_balls: int = 200) -> pd.DataFrame:
    """Get boundary rate by player for beta-binomial analysis."""
    conn = get_connection()
    query = """
        SELECT
            player_id,
            player_name,
            short_name,
            balls_faced,
            boundaries,
            strike_rate,
            boundary_rate,
            fours,
            sixes
        FROM v_batter_career
        WHERE balls_faced >= ?
        ORDER BY boundary_rate DESC
    """
    df = pd.read_sql_query(query, conn, params=(min_balls,))
    conn.close()
    return df


# For testing and validation
def validate_database():
    """Validate database has required data."""
    conn = get_connection()
    tables = ['seasons', 'teams', 'venues', 'players', 'matches', 'innings', 'deliveries', 'player_innings']
    results = {}
    for table in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        results[table] = count
        logger.info(f"Table {table}: {count} rows")
    conn.close()
    return results


if __name__ == '__main__':
    validate_database()
    print("\nTesting data access...")
    df = get_batter_career(200)
    print(f"Batters with 200+ balls: {len(df)}")
    print(df.head())