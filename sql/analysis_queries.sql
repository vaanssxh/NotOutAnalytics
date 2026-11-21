-- IPL Cricket Analytics - Analytical Queries
-- These queries demonstrate SQL aggregation, window functions, and advanced analytics
-- Run against the populated database

-- ============================================
-- QUERY 1: Career Batting Aggregates
-- ============================================
-- Full career batting statistics for all players
-- Uses: SUM, COUNT, AVG, MAX, CASE, GROUP BY, HAVING
SELECT
    p.player_id,
    p.player_name,
    p.short_name,
    p.batting_style,
    p.playing_role,
    COUNT(DISTINCT pi.match_id) AS matches,
    COUNT(pi.player_innings_id) AS innings,
    SUM(pi.runs_scored) AS total_runs,
    SUM(pi.balls_faced) AS balls_faced,
    SUM(pi.fours) AS fours,
    SUM(pi.sixes) AS sixes,
    SUM(pi.boundaries) AS boundaries,
    SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END) AS dismissals,
    SUM(CASE WHEN pi.dismissed = 0 AND pi.balls_faced > 0 THEN 1 ELSE 0 END) AS not_outs,
    MAX(pi.runs_scored) AS highest_score,
    SUM(CASE WHEN pi.runs_scored >= 100 THEN 1 ELSE 0 END) AS centuries,
    SUM(CASE WHEN pi.runs_scored >= 50 AND pi.runs_scored < 100 THEN 1 ELSE 0 END) AS fifties,
    SUM(CASE WHEN pi.runs_scored = 0 AND pi.balls_faced > 0 THEN 1 ELSE 0 END) AS ducks,
    ROUND(
        CASE WHEN SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END) > 0
             THEN 1.0 * SUM(pi.runs_scored) / SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END)
             ELSE NULL END, 2
    ) AS batting_average,
    ROUND(
        CASE WHEN SUM(pi.balls_faced) > 0
             THEN 1.0 * SUM(pi.runs_scored) / SUM(pi.balls_faced) * 100
             ELSE NULL END, 2
    ) AS strike_rate,
    ROUND(
        CASE WHEN SUM(pi.balls_faced) > 0
             THEN 1.0 * SUM(pi.boundaries) / SUM(pi.balls_faced)
             ELSE NULL END, 4
    ) AS boundary_percentage,
    MIN(m.start_date) AS debut_date,
    MAX(m.start_date) AS last_match_date
FROM player_innings pi
JOIN players p ON pi.player_id = p.player_id
JOIN matches m ON pi.match_id = m.match_id
WHERE pi.balls_faced > 0 OR pi.runs_scored > 0
GROUP BY p.player_id, p.player_name, p.short_name, p.batting_style, p.playing_role
HAVING SUM(pi.balls_faced) >= 200  -- Minimum qualification
ORDER BY total_runs DESC;


-- ============================================
-- QUERY 2: Season-wise Batting Aggregates
-- ============================================
-- Batting performance per player per season
-- Uses: SUM, COUNT, AVG, MAX, GROUP BY, JOIN
SELECT
    s.season_name,
    p.player_id,
    p.player_name,
    p.short_name,
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
    MAX(pi.runs_scored) AS highest_score,
    SUM(CASE WHEN pi.runs_scored >= 100 THEN 1 ELSE 0 END) AS centuries,
    SUM(CASE WHEN pi.runs_scored >= 50 AND pi.runs_scored < 100 THEN 1 ELSE 0 END) AS fifties,
    SUM(CASE WHEN pi.runs_scored = 0 AND pi.balls_faced > 0 THEN 1 ELSE 0 END) AS ducks,
    ROUND(
        CASE WHEN SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END) > 0
             THEN 1.0 * SUM(pi.runs_scored) / SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END)
             ELSE NULL END, 2
    ) AS average,
    ROUND(
        CASE WHEN SUM(pi.balls_faced) > 0
             THEN 1.0 * SUM(pi.runs_scored) / SUM(pi.balls_faced) * 100
             ELSE NULL END, 2
    ) AS strike_rate,
    ROUND(
        CASE WHEN SUM(pi.balls_faced) > 0
             THEN 1.0 * SUM(pi.boundaries) / SUM(pi.balls_faced)
             ELSE NULL END, 4
    ) AS boundary_rate
FROM player_innings pi
JOIN players p ON pi.player_id = p.player_id
JOIN seasons s ON pi.season_id = s.season_id
JOIN teams t ON pi.team_id = t.team_id
JOIN matches m ON pi.match_id = m.match_id
WHERE pi.balls_faced > 0 OR pi.runs_scored > 0
GROUP BY s.season_id, s.season_name, p.player_id, p.player_name, p.short_name, t.canonical_name
ORDER BY s.season_name, runs DESC;


-- ============================================
-- QUERY 3: Innings-level Batting Statistics
-- ============================================
-- Detailed innings-by-innings batting performance
-- Uses: JOIN, window functions (ROW_NUMBER), CASE
SELECT
    pi.player_innings_id,
    m.match_id,
    s.season_name,
    m.start_date,
    v.venue_name,
    t1.canonical_name AS batting_team,
    t2.canonical_name AS bowling_team,
    p.player_name,
    p.short_name,
    pi.batting_position,
    pi.runs_scored,
    pi.balls_faced,
    pi.fours,
    pi.sixes,
    pi.boundaries,
    pi.strike_rate,
    pi.dismissed,
    pi.dismissal_kind,
    CASE WHEN pi.dismissed THEN 'Out' ELSE 'Not Out' END AS dismissal_status,
    pi.match_result,
    CASE
        WHEN pi.runs_scored >= 100 THEN 'Century'
        WHEN pi.runs_scored >= 50 THEN 'Fifty'
        WHEN pi.runs_scored = 0 AND pi.balls_faced > 0 THEN 'Duck'
        ELSE 'Other'
    END AS innings_category,
    -- Window function: innings number for this player in this season
    ROW_NUMBER() OVER (PARTITION BY pi.player_id, pi.season_id ORDER BY m.start_date) AS season_innings_number,
    -- Window function: career innings number
    ROW_NUMBER() OVER (PARTITION BY pi.player_id ORDER BY m.start_date) AS career_innings_number,
    -- Window function: running career average up to this innings
    ROUND(
        1.0 * SUM(pi.runs_scored) OVER (PARTITION BY pi.player_id ORDER BY m.start_date
            ROWS UNBOUNDED PRECEDING) /
        NULLIF(SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END) OVER (PARTITION BY pi.player_id ORDER BY m.start_date
            ROWS UNBOUNDED PRECEDING), 0), 2
    ) AS running_career_average
FROM player_innings pi
JOIN players p ON pi.player_id = p.player_id
JOIN matches m ON pi.match_id = m.match_id
JOIN seasons s ON pi.season_id = s.season_id
JOIN venues v ON pi.venue_id = v.venue_id
JOIN teams t1 ON pi.team_id = t1.team_id
JOIN teams t2 ON pi.opponent_team_id = t2.team_id
WHERE pi.balls_faced > 0 OR pi.runs_scored > 0
ORDER BY pi.player_id, m.start_date, pi.innings_number;


-- ============================================
-- QUERY 4: Player Boundary Percentages
-- ============================================
-- Boundary hitting analysis (4s and 6s as % of balls faced and % of runs)
-- Uses: SUM, AVG, CASE, GROUP BY, HAVING, window functions
SELECT
    p.player_id,
    p.player_name,
    p.short_name,
    SUM(pi.balls_faced) AS total_balls_faced,
    SUM(pi.runs_scored) AS total_runs,
    SUM(pi.fours) AS total_fours,
    SUM(pi.sixes) AS total_sixes,
    SUM(pi.boundaries) AS total_boundaries,
    SUM(pi.fours * 4 + pi.sixes * 6) AS boundary_runs,
    ROUND(1.0 * SUM(pi.boundaries) / NULLIF(SUM(pi.balls_faced), 0) * 100, 2) AS boundary_pct_balls,
    ROUND(1.0 * SUM(pi.fours) / NULLIF(SUM(pi.balls_faced), 0) * 100, 2) AS four_pct_balls,
    ROUND(1.0 * SUM(pi.sixes) / NULLIF(SUM(pi.balls_faced), 0) * 100, 2) AS six_pct_balls,
    ROUND(1.0 * SUM(pi.fours * 4 + pi.sixes * 6) / NULLIF(SUM(pi.runs_scored), 0) * 100, 2) AS boundary_pct_runs,
    ROUND(1.0 * SUM(pi.sixes * 6) / NULLIF(SUM(pi.runs_scored), 0) * 100, 2) AS six_pct_runs,
    -- Balls per boundary
    ROUND(1.0 * SUM(pi.balls_faced) / NULLIF(SUM(pi.boundaries), 0), 2) AS balls_per_boundary,
    -- Balls per six
    ROUND(1.0 * SUM(pi.balls_faced) / NULLIF(SUM(pi.sixes), 0), 2) AS balls_per_six,
    -- Percentile rank for boundary rate
    ROUND(
        PERCENT_RANK() OVER (ORDER BY 1.0 * SUM(pi.boundaries) / NULLIF(SUM(pi.balls_faced), 0)) * 100, 1
    ) AS boundary_rate_percentile
FROM player_innings pi
JOIN players p ON pi.player_id = p.player_id
WHERE pi.balls_faced > 0
GROUP BY p.player_id, p.player_name, p.short_name
HAVING SUM(pi.balls_faced) >= 300
ORDER BY boundary_pct_balls DESC;


-- ============================================
-- QUERY 5: Top Players by Strike Rate (Min Sample Size)
-- ============================================
-- Strike rate leaders with minimum qualification
-- Uses: HAVING, window functions (ROW_NUMBER, NTILE)
WITH qualified_batters AS (
    SELECT
        p.player_id,
        p.player_name,
        p.short_name,
        p.batting_style,
        p.playing_role,
        SUM(pi.runs_scored) AS runs,
        SUM(pi.balls_faced) AS balls_faced,
        SUM(pi.fours) AS fours,
        SUM(pi.sixes) AS sixes,
        SUM(pi.boundaries) AS boundaries,
        ROUND(1.0 * SUM(pi.runs_scored) / SUM(pi.balls_faced) * 100, 2) AS strike_rate,
        ROUND(1.0 * SUM(pi.boundaries) / SUM(pi.balls_faced), 4) AS boundary_rate,
        COUNT(DISTINCT pi.match_id) AS matches,
        COUNT(pi.player_innings_id) AS innings,
        SUM(CASE WHEN pi.runs_scored >= 50 THEN 1 ELSE 0 END) AS fifty_plus,
        -- Career span
        MIN(m.start_date) AS debut,
        MAX(m.start_date) AS last_match
    FROM player_innings pi
    JOIN players p ON pi.player_id = p.player_id
    JOIN matches m ON pi.match_id = m.match_id
    WHERE pi.balls_faced > 0
    GROUP BY p.player_id, p.player_name, p.short_name, p.batting_style, p.playing_role
    HAVING SUM(pi.balls_faced) >= 500  -- Minimum 500 balls faced
)
SELECT
    *,
    ROW_NUMBER() OVER (ORDER BY strike_rate DESC) AS sr_rank,
    NTILE(4) OVER (ORDER BY strike_rate DESC) AS sr_quartile,
    ROUND(strike_rate - AVG(strike_rate) OVER (), 2) AS sr_vs_avg,
    ROUND((strike_rate - AVG(strike_rate) OVER ()) / STDDEV(strike_rate) OVER (), 2) AS sr_zscore
FROM qualified_batters
ORDER BY strike_rate DESC
LIMIT 50;


-- ============================================
-- QUERY 6: First-Half vs Second-Half Career Performance
-- ============================================
-- Compare player performance in first vs second half of career
-- Uses: window functions (NTILE), CASE, GROUP BY, HAVING
WITH career_halves AS (
    SELECT
        pi.player_id,
        p.player_name,
        p.short_name,
        pi.player_innings_id,
        pi.runs_scored,
        pi.balls_faced,
        pi.dismissed,
        pi.fours,
        pi.sixes,
        pi.boundaries,
        m.start_date,
        -- Assign each innings to first or second half of career
        NTILE(2) OVER (PARTITION BY pi.player_id ORDER BY m.start_date) AS career_half
    FROM player_innings pi
    JOIN players p ON pi.player_id = p.player_id
    JOIN matches m ON pi.match_id = m.match_id
    WHERE pi.balls_faced > 0
)
SELECT
    player_id,
    player_name,
    short_name,
    -- First half stats
    SUM(CASE WHEN career_half = 1 THEN runs_scored ELSE 0 END) AS first_half_runs,
    SUM(CASE WHEN career_half = 1 THEN balls_faced ELSE 0 END) AS first_half_balls,
    SUM(CASE WHEN career_half = 1 THEN dismissed ELSE 0 END) AS first_half_dismissals,
    SUM(CASE WHEN career_half = 1 THEN fours ELSE 0 END) AS first_half_fours,
    SUM(CASE WHEN career_half = 1 THEN sixes ELSE 0 END) AS first_half_sixes,
    SUM(CASE WHEN career_half = 1 THEN boundaries ELSE 0 END) AS first_half_boundaries,
    COUNT(CASE WHEN career_half = 1 THEN 1 END) AS first_half_innings,
    ROUND(
        1.0 * SUM(CASE WHEN career_half = 1 THEN runs_scored ELSE 0 END) /
        NULLIF(SUM(CASE WHEN career_half = 1 THEN dismissed ELSE 0 END), 0), 2
    ) AS first_half_average,
    ROUND(
        1.0 * SUM(CASE WHEN career_half = 1 THEN runs_scored ELSE 0 END) /
        NULLIF(SUM(CASE WHEN career_half = 1 THEN balls_faced ELSE 0 END), 0) * 100, 2
    ) AS first_half_strike_rate,
    -- Second half stats
    SUM(CASE WHEN career_half = 2 THEN runs_scored ELSE 0 END) AS second_half_runs,
    SUM(CASE WHEN career_half = 2 THEN balls_faced ELSE 0 END) AS second_half_balls,
    SUM(CASE WHEN career_half = 2 THEN dismissed ELSE 0 END) AS second_half_dismissals,
    SUM(CASE WHEN career_half = 2 THEN fours ELSE 0 END) AS second_half_fours,
    SUM(CASE WHEN career_half = 2 THEN sixes ELSE 0 END) AS second_half_sixes,
    SUM(CASE WHEN career_half = 2 THEN boundaries ELSE 0 END) AS second_half_boundaries,
    COUNT(CASE WHEN career_half = 2 THEN 1 END) AS second_half_innings,
    ROUND(
        1.0 * SUM(CASE WHEN career_half = 2 THEN runs_scored ELSE 0 END) /
        NULLIF(SUM(CASE WHEN career_half = 2 THEN dismissed ELSE 0 END), 0), 2
    ) AS second_half_average,
    ROUND(
        1.0 * SUM(CASE WHEN career_half = 2 THEN runs_scored ELSE 0 END) /
        NULLIF(SUM(CASE WHEN career_half = 2 THEN balls_faced ELSE 0 END), 0) * 100, 2
    ) AS second_half_strike_rate,
    -- Difference (second - first)
    ROUND(
        1.0 * SUM(CASE WHEN career_half = 2 THEN runs_scored ELSE 0 END) /
        NULLIF(SUM(CASE WHEN career_half = 2 THEN dismissed ELSE 0 END), 0)
        -
        1.0 * SUM(CASE WHEN career_half = 1 THEN runs_scored ELSE 0 END) /
        NULLIF(SUM(CASE WHEN career_half = 1 THEN dismissed ELSE 0 END), 0), 2
    ) AS avg_improvement,
    ROUND(
        1.0 * SUM(CASE WHEN career_half = 2 THEN runs_scored ELSE 0 END) /
        NULLIF(SUM(CASE WHEN career_half = 2 THEN balls_faced ELSE 0 END), 0) * 100
        -
        1.0 * SUM(CASE WHEN career_half = 1 THEN runs_scored ELSE 0 END) /
        NULLIF(SUM(CASE WHEN career_half = 1 THEN balls_faced ELSE 0 END), 0) * 100, 2
    ) AS sr_improvement
FROM career_halves
GROUP BY player_id, player_name, short_name
HAVING SUM(CASE WHEN career_half = 1 THEN balls_faced ELSE 0 END) >= 200
   AND SUM(CASE WHEN career_half = 2 THEN balls_faced ELSE 0 END) >= 200
ORDER BY avg_improvement DESC;


-- ============================================
-- QUERY 7: Player Comparison Query
-- ============================================
-- Head-to-head comparison of multiple players
-- Uses: window functions, CASE, conditional aggregation
-- Replace player names in WHERE clause as needed
WITH player_stats AS (
    SELECT
        p.player_id,
        p.player_name,
        p.short_name,
        p.batting_style,
        p.bowling_style,
        p.playing_role,
        -- Batting
        SUM(pi.runs_scored) AS total_runs,
        SUM(pi.balls_faced) AS balls_faced,
        SUM(pi.fours) AS fours,
        SUM(pi.sixes) AS sixes,
        SUM(pi.boundaries) AS boundaries,
        SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END) AS dismissals,
        SUM(CASE WHEN pi.dismissed = 0 AND pi.balls_faced > 0 THEN 1 ELSE 0 END) AS not_outs,
        MAX(pi.runs_scored) AS highest_score,
        SUM(CASE WHEN pi.runs_scored >= 100 THEN 1 ELSE 0 END) AS centuries,
        SUM(CASE WHEN pi.runs_scored >= 50 AND pi.runs_scored < 100 THEN 1 ELSE 0 END) AS fifties,
        SUM(CASE WHEN pi.runs_scored = 0 AND pi.balls_faced > 0 THEN 1 ELSE 0 END) AS ducks,
        ROUND(1.0 * SUM(pi.runs_scored) / NULLIF(SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END), 0), 2) AS batting_avg,
        ROUND(1.0 * SUM(pi.runs_scored) / NULLIF(SUM(pi.balls_faced), 0) * 100, 2) AS strike_rate,
        ROUND(1.0 * SUM(pi.boundaries) / NULLIF(SUM(pi.balls_faced), 0), 4) AS boundary_rate,
        COUNT(DISTINCT pi.match_id) AS matches_batted,
        -- Bowling
        SUM(pi.balls_bowled) AS balls_bowled,
        SUM(pi.runs_conceded) AS runs_conceded,
        SUM(pi.wickets_taken) AS wickets,
        SUM(pi.wides_bowled) AS wides,
        SUM(pi.noballs_bowled) AS noballs,
        SUM(pi.maidens) AS maidens,
        SUM(pi.dot_balls) AS dot_balls,
        ROUND(1.0 * SUM(pi.runs_conceded) / NULLIF(SUM(pi.balls_bowled) / 6.0, 0), 2) AS economy,
        ROUND(1.0 * SUM(pi.balls_bowled) / NULLIF(SUM(pi.wickets_taken), 0), 2) AS bowling_sr,
        ROUND(1.0 * SUM(pi.runs_conceded) / NULLIF(SUM(pi.wickets_taken), 0), 2) AS bowling_avg,
        COUNT(DISTINCT CASE WHEN pi.balls_bowled > 0 THEN pi.match_id END) AS matches_bowled,
        MIN(m.start_date) AS debut,
        MAX(m.start_date) AS last_match
    FROM player_innings pi
    JOIN players p ON pi.player_id = p.player_id
    JOIN matches m ON pi.match_id = m.match_id
    WHERE p.player_name IN (
        'V Kohli', 'RG Sharma', 'S Dhawan', 'DA Warner', 'KL Rahul',
        'MS Dhoni', 'AB de Villiers', 'SK Raina', 'SV Samson', 'AM Rahane'
    )
    GROUP BY p.player_id, p.player_name, p.short_name, p.batting_style, p.bowling_style, p.playing_role
)
SELECT
    *,
    -- Percentile ranks
    ROUND(PERCENT_RANK() OVER (ORDER BY total_runs) * 100, 1) AS runs_percentile,
    ROUND(PERCENT_RANK() OVER (ORDER BY batting_avg) * 100, 1) AS avg_percentile,
    ROUND(PERCENT_RANK() OVER (ORDER BY strike_rate) * 100, 1) AS sr_percentile,
    ROUND(PERCENT_RANK() OVER (ORDER BY boundary_rate) * 100, 1) AS boundary_percentile,
    ROUND(PERCENT_RANK() OVER (ORDER BY wickets) * 100, 1) AS wickets_percentile,
    ROUND(PERCENT_RANK() OVER (ORDER BY economy) * 100, 1) AS economy_percentile,
    -- Z-scores
    ROUND((total_runs - AVG(total_runs) OVER ()) / STDDEV(total_runs) OVER (), 2) AS runs_zscore,
    ROUND((batting_avg - AVG(batting_avg) OVER ()) / STDDEV(batting_avg) OVER (), 2) AS avg_zscore,
    ROUND((strike_rate - AVG(strike_rate) OVER ()) / STDDEV(strike_rate) OVER (), 2) AS sr_zscore,
    ROUND((economy - AVG(economy) OVER ()) / STDDEV(economy) OVER (), 2) AS economy_zscore
FROM player_stats
ORDER BY total_runs DESC;


-- ============================================
-- BONUS QUERY 8: Venue-wise Batting Analysis
-- ============================================
-- How batters perform at different venues
SELECT
    v.venue_name,
    v.city,
    p.player_name,
    p.short_name,
    COUNT(DISTINCT pi.match_id) AS matches,
    SUM(pi.runs_scored) AS runs,
    SUM(pi.balls_faced) AS balls_faced,
    SUM(pi.fours) AS fours,
    SUM(pi.sixes) AS sixes,
    ROUND(1.0 * SUM(pi.runs_scored) / NULLIF(SUM(CASE WHEN pi.dismissed THEN 1 ELSE 0 END), 0), 2) AS average,
    ROUND(1.0 * SUM(pi.runs_scored) / NULLIF(SUM(pi.balls_faced), 0) * 100, 2) AS strike_rate,
    ROUND(1.0 * SUM(pi.boundaries) / NULLIF(SUM(pi.balls_faced), 0), 4) AS boundary_rate
FROM player_innings pi
JOIN players p ON pi.player_id = p.player_id
JOIN venues v ON pi.venue_id = v.venue_id
JOIN matches m ON pi.match_id = m.match_id
WHERE pi.balls_faced > 0
GROUP BY v.venue_id, v.venue_name, v.city, p.player_id, p.player_name, p.short_name
HAVING SUM(pi.balls_faced) >= 100
ORDER BY v.venue_name, strike_rate DESC;


-- ============================================
-- BONUS QUERY 9: Powerplay vs Death Overs Performance
-- ============================================
-- Batter performance in different phases (requires deliveries table)
SELECT
    p.player_name,
    p.short_name,
    -- Powerplay (overs 1-6)
    SUM(CASE WHEN d.over_number BETWEEN 1 AND 6 THEN d.batter_runs ELSE 0 END) AS pp_runs,
    SUM(CASE WHEN d.over_number BETWEEN 1 AND 6 AND d.is_legal_delivery THEN 1 ELSE 0 END) AS pp_balls,
    SUM(CASE WHEN d.over_number BETWEEN 1 AND 6 AND d.is_wicket AND d.player_dismissed_id = p.player_id THEN 1 ELSE 0 END) AS pp_dismissals,
    SUM(CASE WHEN d.over_number BETWEEN 1 AND 6 THEN d.is_four::INTEGER ELSE 0 END) AS pp_fours,
    SUM(CASE WHEN d.over_number BETWEEN 1 AND 6 THEN d.is_six::INTEGER ELSE 0 END) AS pp_sixes,
    ROUND(
        1.0 * SUM(CASE WHEN d.over_number BETWEEN 1 AND 6 THEN d.batter_runs ELSE 0 END) /
        NULLIF(SUM(CASE WHEN d.over_number BETWEEN 1 AND 6 AND d.is_legal_delivery THEN 1 ELSE 0 END), 0) * 100, 2
    ) AS pp_strike_rate,
    -- Middle overs (7-15)
    SUM(CASE WHEN d.over_number BETWEEN 7 AND 15 THEN d.batter_runs ELSE 0 END) AS mid_runs,
    SUM(CASE WHEN d.over_number BETWEEN 7 AND 15 AND d.is_legal_delivery THEN 1 ELSE 0 END) AS mid_balls,
    SUM(CASE WHEN d.over_number BETWEEN 7 AND 15 AND d.is_wicket AND d.player_dismissed_id = p.player_id THEN 1 ELSE 0 END) AS mid_dismissals,
    ROUND(
        1.0 * SUM(CASE WHEN d.over_number BETWEEN 7 AND 15 THEN d.batter_runs ELSE 0 END) /
        NULLIF(SUM(CASE WHEN d.over_number BETWEEN 7 AND 15 AND d.is_legal_delivery THEN 1 ELSE 0 END), 0) * 100, 2
    ) AS mid_strike_rate,
    -- Death overs (16-20)
    SUM(CASE WHEN d.over_number BETWEEN 16 AND 20 THEN d.batter_runs ELSE 0 END) AS death_runs,
    SUM(CASE WHEN d.over_number BETWEEN 16 AND 20 AND d.is_legal_delivery THEN 1 ELSE 0 END) AS death_balls,
    SUM(CASE WHEN d.over_number BETWEEN 16 AND 20 AND d.is_wicket AND d.player_dismissed_id = p.player_id THEN 1 ELSE 0 END) AS death_dismissals,
    SUM(CASE WHEN d.over_number BETWEEN 16 AND 20 THEN d.is_four::INTEGER ELSE 0 END) AS death_fours,
    SUM(CASE WHEN d.over_number BETWEEN 16 AND 20 THEN d.is_six::INTEGER ELSE 0 END) AS death_sixes,
    ROUND(
        1.0 * SUM(CASE WHEN d.over_number BETWEEN 16 AND 20 THEN d.batter_runs ELSE 0 END) /
        NULLIF(SUM(CASE WHEN d.over_number BETWEEN 16 AND 20 AND d.is_legal_delivery THEN 1 ELSE 0 END), 0) * 100, 2
    ) AS death_strike_rate
FROM deliveries d
JOIN players p ON d.striker_id = p.player_id
JOIN matches m ON d.match_id = m.match_id
JOIN innings i ON d.innings_id = i.innings_id
WHERE i.innings_number <= 2  -- Regular innings only
  AND d.is_legal_delivery = 1
GROUP BY p.player_id, p.player_name, p.short_name
HAVING SUM(CASE WHEN d.over_number BETWEEN 1 AND 6 AND d.is_legal_delivery THEN 1 ELSE 0 END) >= 50
   AND SUM(CASE WHEN d.over_number BETWEEN 16 AND 20 AND d.is_legal_delivery THEN 1 ELSE 0 END) >= 50
ORDER BY death_strike_rate DESC;


-- ============================================
-- BONUS QUERY 10: Partnership Analysis
-- ============================================
-- Top batting partnerships (requires deliveries table)
SELECT
    p1.player_name AS batter1,
    p1.short_name AS b1_short,
    p2.player_name AS batter2,
    p2.short_name AS b2_short,
    COUNT(DISTINCT d.match_id) AS innings_together,
    SUM(d.batter_runs) AS partnership_runs,
    SUM(CASE WHEN d.is_legal_delivery THEN 1 ELSE 0 END) AS balls_faced,
    ROUND(1.0 * SUM(d.batter_runs) / SUM(CASE WHEN d.is_legal_delivery THEN 1 ELSE 0 END) * 100, 2) AS partnership_sr,
    SUM(CASE WHEN d.is_four THEN 1 ELSE 0 END) AS fours,
    SUM(CASE WHEN d.is_six THEN 1 ELSE 0 END) AS sixes,
    MAX(d.innings_runs_at_start + d.batter_runs - d.innings_runs_at_start) AS max_partnership -- Simplified
FROM deliveries d
JOIN players p1 ON d.striker_id = p1.player_id
JOIN players p2 ON d.non_striker_id = p2.player_id
JOIN innings i ON d.innings_id = i.innings_id
WHERE i.innings_number <= 2
  AND d.is_legal_delivery = 1
  AND p1.player_id < p2.player_id  -- Avoid duplicate pairs
GROUP BY p1.player_id, p1.player_name, p1.short_name, p2.player_id, p2.player_name, p2.short_name
HAVING COUNT(DISTINCT d.match_id) >= 5
   AND SUM(CASE WHEN d.is_legal_delivery THEN 1 ELSE 0 END) >= 100
ORDER BY partnership_runs DESC
LIMIT 20;