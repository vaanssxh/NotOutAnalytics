# IPL Analytics Database - Entity Relationship Diagram

```mermaid
erDiagram
    SEASONS ||--o{ MATCHES : "contains"
    TEAMS ||--o{ MATCHES : "team1"
    TEAMS ||--o{ MATCHES : "team2"
    TEAMS ||--o{ MATCHES : "toss_winner"
    TEAMS ||--o{ MATCHES : "winner"
    TEAMS ||--o{ MATCHES : "team_a"
    TEAMS ||--o{ MATCHES : "team_b"
    VENUES ||--o{ MATCHES : "hosted_at"
    MATCHES ||--o{ INNINGS : "has"
    INNINGS ||--o{ DELIVERIES : "contains"
    TEAMS ||--o{ INNINGS : "batting_team"
    TEAMS ||--o{ INNINGS : "bowling_team"
    PLAYERS ||--o{ DELIVERIES : "striker"
    PLAYERS ||--o{ DELIVERIES : "non_striker"
    PLAYERS ||--o{ DELIVERIES : "bowler"
    PLAYERS ||--o{ DELIVERIES : "player_dismissed"
    PLAYERS ||--o{ DELIVERIES : "fielder"
    PLAYERS ||--o{ DELIVERIES : "fielder_2"
    PLAYERS ||--o{ DELIVERIES : "fielder_3"
    INNINGS ||--o{ PLAYER_INNINGS : "tracks"
    PLAYERS ||--o{ PLAYER_INNINGS : "performed_in"
    TEAMS ||--o{ PLAYER_INNINGS : "for_team"
    MATCHES ||--o{ PLAYER_INNINGS : "in_match"
    SEASONS ||--o{ PLAYER_SEASONS : "has"
    TEAMS ||--o{ PLAYER_SEASONS : "for_team"
    PLAYERS ||--o{ PLAYER_SEASONS : "player"
    TEAMS ||--o{ TEAM_ALIASES : "has_aliases"
    PLAYERS ||--o{ PLAYER_ALIASES : "has_aliases"

    SEASONS {
        int season_id PK
        int start_year
        int end_year
        text name
        date start_date
        date end_date
        text notes
    }

    TEAMS {
        int team_id PK
        text canonical_name UK
        text short_name
        text city
        boolean is_active
        date first_season
        date last_season
    }

    TEAM_ALIASES {
        int alias_id PK
        int team_id FK
        text alias_name
        date valid_from
        date valid_to
        boolean is_primary
    }

    VENUES {
        int venue_id PK
        text name UK
        text city
        text country
        text timezone
        int capacity
    }

    PLAYERS {
        int player_id PK
        text registry_id UK
        text full_name
        text short_name
        date dob
        text batting_style
        text bowling_style
        text playing_role
        text country
    }

    PLAYER_ALIASES {
        int alias_id PK
        int player_id FK
        text alias_name
        text source
    }

    MATCHES {
        int match_id PK
        text cricsheet_id UK
        int season_id FK
        int team_a_id FK
        int team_b_id FK
        int venue_id FK
        date match_date
        text match_type
        text gender
        int overs_per_innings
        int toss_winner_id FK
        text toss_decision
        int winner_id FK
        text win_type
        int win_margin
        text outcome_method
        text player_of_match_ids
        text cricsheet_info_json
    }

    INNINGS {
        int innings_id PK
        int match_id FK
        int innings_number
        int batting_team_id FK
        int bowling_team_id FK
        int runs
        int wickets
        int overs
        int balls
        text target_overs
        int target_runs
        text declaration
        text follow_on
    }

    DELIVERIES {
        int delivery_id PK
        int innings_id FK
        int match_id FK
        int over_number
        int ball_in_over
        int actual_delivery_seq
        int striker_id FK
        int non_striker_id FK
        int bowler_id FK
        int runs_off_bat
        int extras_wides
        int extras_noballs
        int extras_byes
        int extras_legbyes
        int extras_penalty
        int total_runs
        int batter_runs
        int bowler_conceded_runs
        int player_dismissed_id FK
        text wicket_type
        int fielder_id FK
        int fielder_2_id FK
        int fielder_3_id FK
        boolean is_legal_delivery
        boolean is_wide
        boolean is_noball
        boolean is_boundary
        boolean is_four
        boolean is_six
        boolean is_wicket
        boolean is_bowler_wicket
        boolean is_byes
        boolean is_legbyes
        text other_wicket_type
        text other_player_dismissed
        text notes
    }

    PLAYER_INNINGS {
        int player_innings_id PK
        int innings_id FK
        int match_id FK
        int player_id FK
        int team_id FK
        boolean is_batter
        boolean is_bowler
        int runs_scored
        int balls_faced
        int fours
        int sixes
        int balls_bowled
        int runs_conceded
        int wickets
        int maidens
        boolean is_dismissed
        text dismissal_type
        int dismissal_fielder_id FK
        text batting_position
    }

    PLAYER_SEASONS {
        int player_season_id PK
        int player_id FK
        int season_id FK
        int team_id FK
        int matches_played
        int innings_batted
        int innings_bowled
        int runs
        int balls_faced
        int fours
        int sixes
        int wickets
        int balls_bowled
        int runs_conceded
        int catches
        int stumpings
        int run_outs
        real batting_avg
        real batting_sr
        real bowling_avg
        real bowling_econ
        real bowling_sr
    }
```

## Table Relationships Summary

| Parent Table | Child Table | Relationship | Foreign Key |
|--------------|-------------|--------------|-------------|
| seasons | matches | 1:N | season_id |
| teams | matches (team_a) | 1:N | team_a_id |
| teams | matches (team_b) | 1:N | team_b_id |
| teams | matches (toss_winner) | 1:N | toss_winner_id |
| teams | matches (winner) | 1:N | winner_id |
| venues | matches | 1:N | venue_id |
| matches | innings | 1:N | match_id |
| teams | innings (batting) | 1:N | batting_team_id |
| teams | innings (bowling) | 1:N | bowling_team_id |
| innings | deliveries | 1:N | innings_id |
| matches | deliveries | 1:N | match_id |
| players | deliveries (striker) | 1:N | striker_id |
| players | deliveries (non_striker) | 1:N | non_striker_id |
| players | deliveries (bowler) | 1:N | bowler_id |
| players | deliveries (dismissed) | 1:N | player_dismissed_id |
| players | deliveries (fielder) | 1:N | fielder_id |
| innings | player_innings | 1:N | innings_id |
| matches | player_innings | 1:N | match_id |
| players | player_innings | 1:N | player_id |
| teams | player_innings | 1:N | team_id |
| seasons | player_seasons | 1:N | season_id |
| teams | player_seasons | 1:N | team_id |
| players | player_seasons | 1:N | player_id |
| teams | team_aliases | 1:N | team_id |
| players | player_aliases | 1:N | player_id |

## Key Design Decisions

1. **Canonical Team Names**: Teams table stores canonical names (e.g., "Mumbai Indians") while team_aliases handles historical names ("Mumbai Indians" vs "Mumbai" in early seasons)

2. **Player Registry ID**: Uses Cricsheet's unique registry_id as natural key, with auto-increment player_id as surrogate PK

3. **Deliveries Table**: Contains both raw fields (runs_off_bat, extras_*) and derived cricket-specific fields (is_legal_delivery, batter_runs, bowler_conceded_runs, is_boundary, etc.)

4. **Innings Numbering**: innings_number 1-2 = regular innings, 3+ = super overs

5. **Player Innings**: Single row per player per innings, with boolean flags (is_batter, is_bowler) to track dual roles

6. **Indexes**: All foreign keys indexed; composite indexes on (match_id, innings_number), (player_id, season_id), (innings_id, over_number, ball_in_over)

7. **Views**: Four analytical views (v_batter_career, v_bowler_career, v_batter_season, v_bowler_season) pre-compute career/season aggregates