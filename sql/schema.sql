-- IPL Cricket Analytics Database Schema
-- SQLite implementation (PostgreSQL-compatible syntax where possible)
-- Normalized relational schema for ball-by-ball cricket data

-- ============================================
-- CORE REFERENCE TABLES
-- ============================================

-- Seasons table - stores IPL season metadata
CREATE TABLE seasons (
    season_id INTEGER PRIMARY KEY,
    season_name TEXT NOT NULL UNIQUE,           -- e.g., '2008/09', '2023'
    start_year INTEGER NOT NULL,                 -- e.g., 2008
    end_year INTEGER,                            -- e.g., 2009 (NULL for single-year seasons)
    start_date DATE,                             -- Season start date
    end_date DATE,                               -- Season end date
    winner_team_id INTEGER,                      -- FK to teams (champion)
    runner_up_team_id INTEGER,                   -- FK to teams
    total_matches INTEGER DEFAULT 0,
    total_runs INTEGER DEFAULT 0,
    total_wickets INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Teams table - canonical team names with historical mapping
CREATE TABLE teams (
    team_id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,         -- Current/official name (e.g., 'Chennai Super Kings')
    display_name TEXT NOT NULL,                  -- Display name
    short_name TEXT,                             -- 3-4 char abbreviation (CSK, MI, RCB)
    primary_color TEXT,                          -- Hex color for viz
    secondary_color TEXT,
    founded_year INTEGER,
    home_venue_id INTEGER,                       -- FK to venues
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Team aliases - historical name changes (e.g., Delhi Daredevils -> Delhi Capitals)
CREATE TABLE team_aliases (
    alias_id INTEGER PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    alias_name TEXT NOT NULL,                    -- Historical name
    season_from TEXT,                            -- Season when alias started
    season_to TEXT,                              -- Season when alias ended (NULL = current)
    UNIQUE(team_id, alias_name)
);

-- Venues table - cricket grounds
CREATE TABLE venues (
    venue_id INTEGER PRIMARY KEY,
    venue_name TEXT NOT NULL UNIQUE,
    city TEXT NOT NULL,
    state TEXT,
    country TEXT DEFAULT 'India',
    latitude REAL,
    longitude REAL,
    capacity INTEGER,
    established_year INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Players table - master player registry
CREATE TABLE players (
    player_id INTEGER PRIMARY KEY,
    player_name TEXT NOT NULL,                   -- Full name as appears in data
    short_name TEXT,                             -- Initials + surname (V Kohli)
    known_as TEXT,                               -- Common name (Virat Kohli)
    batting_style TEXT,                          -- Right-hand bat, Left-hand bat
    bowling_style TEXT,                          -- Right-arm fast, Left-arm orthodox
    playing_role TEXT,                           -- Batter, Bowler, All-rounder, Wicketkeeper
    date_of_birth DATE,
    country TEXT DEFAULT 'India',
    cricsheet_id TEXT,                           -- Original Cricsheet identifier
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Player name aliases (for handling name variations in data)
CREATE TABLE player_aliases (
    alias_id INTEGER PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    alias_name TEXT NOT NULL,                    -- Alternative spelling/name
    season_from TEXT,
    season_to TEXT,
    UNIQUE(player_id, alias_name)
);

-- ============================================
-- MATCH & INNINGS TABLES
-- ============================================

-- Matches table - one row per match
CREATE TABLE matches (
    match_id INTEGER PRIMARY KEY,                -- Cricsheet match ID
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    match_number INTEGER,                        -- Match number within season
    start_date DATE NOT NULL,
    end_date DATE,
    venue_id INTEGER NOT NULL REFERENCES venues(venue_id),
    team1_id INTEGER NOT NULL REFERENCES teams(team_id),
    team2_id INTEGER NOT NULL REFERENCES teams(team_id),
    toss_winner_id INTEGER REFERENCES teams(team_id),
    toss_decision TEXT,                          -- 'bat' or 'field'
    match_type TEXT DEFAULT 'T20',               -- T20, League, Playoff, Final
    gender TEXT DEFAULT 'male',
    match_result TEXT,                           -- 'normal', 'tie', 'no_result'
    winner_id INTEGER REFERENCES teams(team_id),
    win_by_runs INTEGER DEFAULT 0,
    win_by_wickets INTEGER DEFAULT 0,
    player_of_match_id INTEGER REFERENCES players(player_id),
    umpire1 TEXT,
    umpire2 TEXT,
    tv_umpire TEXT,
    match_referee TEXT,
    balls_per_over INTEGER DEFAULT 6,
    overs_per_innings INTEGER DEFAULT 20,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Innings table - one row per innings (1-2 for regular, 3+ for super overs)
CREATE TABLE innings (
    innings_id INTEGER PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(match_id),
    innings_number INTEGER NOT NULL,             -- 1, 2 (regular), 3, 4 (super overs)
    batting_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    bowling_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    innings_total_runs INTEGER DEFAULT 0,
    innings_wickets INTEGER DEFAULT 0,
    innings_overs REAL DEFAULT 0.0,
    innings_declared BOOLEAN DEFAULT 0,
    innings_forfeited BOOLEAN DEFAULT 0,
    target_runs INTEGER,                         -- For 2nd innings (target to chase)
    target_overs REAL,                           -- DLS target overs if applicable
    powerplay_overs INTEGER DEFAULT 6,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(match_id, innings_number)
);

-- ============================================
-- DELIVERIES TABLE (Core fact table)
-- ============================================

CREATE TABLE deliveries (
    delivery_id INTEGER PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(match_id),
    innings_id INTEGER NOT NULL REFERENCES innings(innings_id),
    innings_number INTEGER NOT NULL,             -- Denormalized for querying ease (1, 2, 3...)
    over_number INTEGER NOT NULL,                -- 1-20 (or more for super overs)
    ball_number INTEGER NOT NULL,                -- 1-6 (legal balls), can exceed 6 for wides/no-balls
    actual_delivery_number INTEGER NOT NULL,     -- Sequential count including wides/no-balls

    -- Players involved
    striker_id INTEGER NOT NULL REFERENCES players(player_id),
    non_striker_id INTEGER NOT NULL REFERENCES players(player_id),
    bowler_id INTEGER NOT NULL REFERENCES players(player_id),

    -- Runs breakdown
    runs_off_bat INTEGER DEFAULT 0,              -- 0,1,2,3,4,5,6
    extras_wides INTEGER DEFAULT 0,
    extras_noballs INTEGER DEFAULT 0,
    extras_byes INTEGER DEFAULT 0,
    extras_legbyes INTEGER DEFAULT 0,
    extras_penalty INTEGER DEFAULT 0,
    total_runs INTEGER DEFAULT 0,                -- Total runs from this delivery

    -- Derived run fields (for convenience)
    batter_runs INTEGER DEFAULT 0,               -- Runs credited to batter (excludes byes/legbyes)
    bowler_conceded_runs INTEGER DEFAULT 0,      -- Runs charged to bowler (excludes byes/legbyes)

    -- Extras flags
    is_wide BOOLEAN DEFAULT 0,
    is_noball BOOLEAN DEFAULT 0,
    is_bye BOOLEAN DEFAULT 0,
    is_legbye BOOLEAN DEFAULT 0,
    is_penalty BOOLEAN DEFAULT 0,

    -- Boundary flags
    is_boundary BOOLEAN DEFAULT 0,               -- 4 or 6 (including overthrows to boundary)
    is_four BOOLEAN DEFAULT 0,
    is_six BOOLEAN DEFAULT 0,

    -- Legal delivery flag
    is_legal_delivery BOOLEAN DEFAULT 1,         -- FALSE for wides, TRUE for no-balls

    -- Wicket info
    is_wicket BOOLEAN DEFAULT 0,
    player_dismissed_id INTEGER REFERENCES players(player_id),
    dismissal_kind TEXT,                         -- caught, bowled, lbw, run out, stumped, etc.
    fielder1_id INTEGER REFERENCES players(player_id),
    fielder2_id INTEGER REFERENCES players(player_id),
    fielder3_id INTEGER REFERENCES players(player_id),

    -- Context
    batting_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    bowling_team_id INTEGER NOT NULL REFERENCES teams(team_id),

    -- Over tracking
    is_over_start BOOLEAN DEFAULT 0,             -- First ball of over
    is_over_end BOOLEAN DEFAULT 0,               -- Last legal ball of over
    over_runs_so_far INTEGER DEFAULT 0,          -- Runs in over up to this ball
    over_wickets_so_far INTEGER DEFAULT 0,       -- Wickets in over up to this ball

    -- Match context
    innings_runs_at_start INTEGER DEFAULT 0,     -- Team total at start of delivery
    innings_wickets_at_start INTEGER DEFAULT 0,  -- Wickets fallen at start
    required_run_rate REAL,                      -- For 2nd innings
    balls_remaining INTEGER,                     -- For 2nd innings

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(match_id, innings_number, over_number, ball_number)
);

-- ============================================
-- PLAYER INNINGS TABLE (Aggregated per innings)
-- ============================================

CREATE TABLE player_innings (
    player_innings_id INTEGER PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(match_id),
    innings_id INTEGER NOT NULL REFERENCES innings(innings_id),
    innings_number INTEGER NOT NULL,             -- 1 or 2 (excludes super overs)
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    opponent_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    venue_id INTEGER NOT NULL REFERENCES venues(venue_id),
    season_id INTEGER NOT NULL REFERENCES seasons(season_id),
    start_date DATE NOT NULL,

    -- Batting stats (NULL if didn't bat)
    runs_scored INTEGER DEFAULT 0,
    balls_faced INTEGER DEFAULT 0,               -- Legal deliveries faced (excludes wides)
    fours INTEGER DEFAULT 0,
    sixes INTEGER DEFAULT 0,
    boundaries INTEGER DEFAULT 0,
    strike_rate REAL,                            -- runs/balls * 100
    batting_position INTEGER,                    -- 1-11
    dismissed BOOLEAN DEFAULT 0,
    dismissal_kind TEXT,
    fielder_id INTEGER REFERENCES players(player_id),
    dismissal_over REAL,                         -- Over when dismissed
    dismissal_ball INTEGER,

    -- Bowling stats (NULL if didn't bowl)
    overs_bowled REAL DEFAULT 0.0,
    balls_bowled INTEGER DEFAULT 0,              -- Legal deliveries bowled
    maidens INTEGER DEFAULT 0,
    runs_conceded INTEGER DEFAULT 0,             -- Excludes byes/legbyes
    wickets_taken INTEGER DEFAULT 0,
    wides_bowled INTEGER DEFAULT 0,
    noballs_bowled INTEGER DEFAULT 0,
    dot_balls INTEGER DEFAULT 0,
    economy_rate REAL,                           -- runs per over
    bowling_strike_rate REAL,                    -- balls per wicket
    bowling_average REAL,                        -- runs per wicket

    -- Match context
    match_result TEXT,                           -- 'won', 'lost', 'tied', 'no_result'
    team_innings_total INTEGER,                  -- Team total in this innings
    team_innings_wickets INTEGER,                -- Wickets fallen
    is_batting_first BOOLEAN,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(match_id, innings_number, player_id)
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

-- Matches indexes
CREATE INDEX idx_matches_season ON matches(season_id);
CREATE INDEX idx_matches_date ON matches(start_date);
CREATE INDEX idx_matches_venue ON matches(venue_id);
CREATE INDEX idx_matches_teams ON matches(team1_id, team2_id);
CREATE INDEX idx_matches_winner ON matches(winner_id);

-- Innings indexes
CREATE INDEX idx_innings_match ON innings(match_id);
CREATE INDEX idx_innings_batting_team ON innings(batting_team_id);
CREATE INDEX idx_innings_bowling_team ON innings(bowling_team_id);

-- Deliveries indexes (critical for performance)
CREATE INDEX idx_deliveries_match ON deliveries(match_id);
CREATE INDEX idx_deliveries_innings ON deliveries(innings_id);
CREATE INDEX idx_deliveries_striker ON deliveries(striker_id);
CREATE INDEX idx_deliveries_bowler ON deliveries(bowler_id);
CREATE INDEX idx_deliveries_batting_team ON deliveries(batting_team_id);
CREATE INDEX idx_deliveries_bowling_team ON deliveries(bowling_team_id);
CREATE INDEX idx_deliveries_wicket ON deliveries(is_wicket, player_dismissed_id);
CREATE INDEX idx_deliveries_boundary ON deliveries(is_boundary);
CREATE INDEX idx_deliveries_legal ON deliveries(is_legal_delivery);
CREATE INDEX idx_deliveries_over_ball ON deliveries(match_id, innings_number, over_number, ball_number);

-- Player innings indexes
CREATE INDEX idx_pi_player ON player_innings(player_id);
CREATE INDEX idx_pi_match ON player_innings(match_id);
CREATE INDEX idx_pi_season ON player_innings(season_id);
CREATE INDEX idx_pi_team ON player_innings(team_id);
CREATE INDEX idx_pi_batting ON player_innings(player_id) WHERE runs_scored > 0 OR balls_faced > 0;
CREATE INDEX idx_pi_bowling ON player_innings(player_id) WHERE balls_bowled > 0;

-- Players indexes
CREATE INDEX idx_players_name ON players(player_name);
CREATE INDEX idx_players_short ON players(short_name);
CREATE INDEX idx_players_country ON players(country);

-- ============================================
-- VIEWS FOR COMMON QUERIES
-- ============================================

-- Career batting summary view
CREATE VIEW v_batter_career AS
SELECT
    p.player_id,
    p.player_name,
    p.short_name,
    p.batting_style,
    p.playing_role,
    COUNT(DISTINCT pi.match_id) AS matches,
    COUNT(pi.player_innings_id) AS innings,
    SUM(pi.runs_scored) AS runs,
    SUM(pi.balls_faced) AS balls_faced,
    SUM(pi.fours) AS fours,
    SUM(pi.sixes) AS sixes,
    SUM(pi.boundaries) AS boundaries,
    SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END) AS dismissals,
    SUM(CASE WHEN pi.dismissed = 0 AND pi.balls_faced > 0 THEN 1 ELSE 0 END) AS not_outs,
    SUM(CASE WHEN pi.runs_scored >= 100 THEN 1 ELSE 0 END) AS hundreds,
    SUM(CASE WHEN pi.runs_scored >= 50 AND pi.runs_scored < 100 THEN 1 ELSE 0 END) AS fifties,
    SUM(CASE WHEN pi.runs_scored = 0 AND pi.balls_faced > 0 THEN 1 ELSE 0 END) AS ducks,
    MAX(pi.runs_scored) AS highest_score,
    CASE WHEN SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END) > 0
         THEN ROUND(1.0 * SUM(pi.runs_scored) / SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END), 2)
         ELSE NULL END AS average,
    CASE WHEN SUM(pi.balls_faced) > 0
         THEN ROUND(1.0 * SUM(pi.runs_scored) / SUM(pi.balls_faced) * 100, 2)
         ELSE NULL END AS strike_rate,
    CASE WHEN SUM(pi.balls_faced) > 0
         THEN ROUND(1.0 * SUM(pi.boundaries) / SUM(pi.balls_faced), 4)
         ELSE NULL END AS boundary_rate,
    MIN(m.start_date) AS debut_date,
    MAX(m.start_date) AS last_match_date
FROM player_innings pi
JOIN players p ON pi.player_id = p.player_id
JOIN matches m ON pi.match_id = m.match_id
WHERE pi.balls_faced > 0 OR pi.runs_scored > 0
GROUP BY p.player_id, p.player_name, p.short_name, p.batting_style, p.playing_role;

-- Career bowling summary view
CREATE VIEW v_bowler_career AS
SELECT
    p.player_id,
    p.player_name,
    p.short_name,
    p.bowling_style,
    p.playing_role,
    COUNT(DISTINCT pi.match_id) AS matches,
    COUNT(pi.player_innings_id) AS innings,
    SUM(pi.balls_bowled) AS balls_bowled,
    ROUND(SUM(pi.balls_bowled) / 6.0, 1) AS overs,
    SUM(pi.runs_conceded) AS runs_conceded,
    SUM(pi.wickets_taken) AS wickets,
    SUM(pi.wides_bowled) AS wides,
    SUM(pi.noballs_bowled) AS noballs,
    SUM(pi.maidens) AS maidens,
    SUM(pi.dot_balls) AS dot_balls,
    CASE WHEN SUM(pi.balls_bowled) > 0
         THEN ROUND(1.0 * SUM(pi.runs_conceded) / (SUM(pi.balls_bowled) / 6.0), 2)
         ELSE NULL END AS economy,
    CASE WHEN SUM(pi.wickets_taken) > 0
         THEN ROUND(1.0 * SUM(pi.balls_bowled) / SUM(pi.wickets_taken), 2)
         ELSE NULL END AS strike_rate,
    CASE WHEN SUM(pi.wickets_taken) > 0
         THEN ROUND(1.0 * SUM(pi.runs_conceded) / SUM(pi.wickets_taken), 2)
         ELSE NULL END AS average,
    MIN(m.start_date) AS debut_date,
    MAX(m.start_date) AS last_match_date
FROM player_innings pi
JOIN players p ON pi.player_id = p.player_id
JOIN matches m ON pi.match_id = m.match_id
WHERE pi.balls_bowled > 0
GROUP BY p.player_id, p.player_name, p.short_name, p.bowling_style, p.playing_role;

-- Season batting summary view
CREATE VIEW v_batter_season AS
SELECT
    pi.season_id,
    s.season_name,
    p.player_id,
    p.player_name,
    p.short_name,
    t.team_id,
    t.canonical_name AS team_name,
    COUNT(DISTINCT pi.match_id) AS matches,
    COUNT(pi.player_innings_id) AS innings,
    SUM(pi.runs_scored) AS runs,
    SUM(pi.balls_faced) AS balls_faced,
    SUM(pi.fours) AS fours,
    SUM(pi.sixes) AS sixes,
    SUM(pi.boundaries) AS boundaries,
    SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END) AS dismissals,
    SUM(CASE WHEN pi.dismissed = 0 AND pi.balls_faced > 0 THEN 1 ELSE 0 END) AS not_outs,
    SUM(CASE WHEN pi.runs_scored >= 100 THEN 1 ELSE 0 END) AS hundreds,
    SUM(CASE WHEN pi.runs_scored >= 50 AND pi.runs_scored < 100 THEN 1 ELSE 0 END) AS fifties,
    SUM(CASE WHEN pi.runs_scored = 0 AND pi.balls_faced > 0 THEN 1 ELSE 0 END) AS ducks,
    MAX(pi.runs_scored) AS highest_score,
    CASE WHEN SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END) > 0
         THEN ROUND(1.0 * SUM(pi.runs_scored) / SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END), 2)
         ELSE NULL END AS average,
    CASE WHEN SUM(pi.balls_faced) > 0
         THEN ROUND(1.0 * SUM(pi.runs_scored) / SUM(pi.balls_faced) * 100, 2)
         ELSE NULL END AS strike_rate,
    CASE WHEN SUM(pi.balls_faced) > 0
         THEN ROUND(1.0 * SUM(pi.boundaries) / SUM(pi.balls_faced), 4)
         ELSE NULL END AS boundary_rate
FROM player_innings pi
JOIN players p ON pi.player_id = p.player_id
JOIN seasons s ON pi.season_id = s.season_id
JOIN teams t ON pi.team_id = t.team_id
WHERE pi.balls_faced > 0 OR pi.runs_scored > 0
GROUP BY pi.season_id, p.player_id, p.player_name, p.short_name, t.team_id, t.canonical_name, s.season_name;

-- Season bowling summary view
CREATE VIEW v_bowler_season AS
SELECT
    pi.season_id,
    s.season_name,
    p.player_id,
    p.player_name,
    p.short_name,
    t.team_id,
    t.canonical_name AS team_name,
    COUNT(DISTINCT pi.match_id) AS matches,
    COUNT(pi.player_innings_id) AS innings,
    SUM(pi.balls_bowled) AS balls_bowled,
    ROUND(SUM(pi.balls_bowled) / 6.0, 1) AS overs,
    SUM(pi.runs_conceded) AS runs_conceded,
    SUM(pi.wickets_taken) AS wickets,
    SUM(pi.wides_bowled) AS wides,
    SUM(pi.noballs_bowled) AS noballs,
    SUM(pi.maidens) AS maidens,
    SUM(pi.dot_balls) AS dot_balls,
    CASE WHEN SUM(pi.balls_bowled) > 0
         THEN ROUND(1.0 * SUM(pi.runs_conceded) / (SUM(pi.balls_bowled) / 6.0), 2)
         ELSE NULL END AS economy,
    CASE WHEN SUM(pi.wickets_taken) > 0
         THEN ROUND(1.0 * SUM(pi.balls_bowled) / SUM(pi.wickets_taken), 2)
         ELSE NULL END AS strike_rate,
    CASE WHEN SUM(pi.wickets_taken) > 0
         THEN ROUND(1.0 * SUM(pi.runs_conceded) / SUM(pi.wickets_taken), 2)
         ELSE NULL END AS average
FROM player_innings pi
JOIN players p ON pi.player_id = p.player_id
JOIN seasons s ON pi.season_id = s.season_id
JOIN teams t ON pi.team_id = t.team_id
WHERE pi.balls_bowled > 0
GROUP BY pi.season_id, p.player_id, p.player_name, p.short_name, t.team_id, t.canonical_name, s.season_name;