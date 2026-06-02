-- Fantasy MVP tables for WC2026.
-- Run once after deploying the code:
--   psql "$DATABASE_URL" -f db/migrations/002_add_fantasy.sql

CREATE TABLE IF NOT EXISTS fantasy_players (
    id SERIAL PRIMARY KEY,
    tournament_code VARCHAR NOT NULL DEFAULT 'wc2026',
    external_player_id INTEGER NOT NULL,
    external_team_id INTEGER NOT NULL,
    team_name VARCHAR NOT NULL,
    team_display_name VARCHAR NOT NULL,
    team_flag VARCHAR,
    player_name VARCHAR NOT NULL,
    age INTEGER,
    number INTEGER,
    position VARCHAR NOT NULL,
    photo TEXT,
    fifa_rank INTEGER,
    fifa_category INTEGER NOT NULL DEFAULT 4,
    is_active BOOLEAN DEFAULT TRUE,
    source_updated_at TIMESTAMPTZ,
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_fantasy_player_tournament_external_player_team
        UNIQUE (tournament_code, external_player_id, external_team_id)
);

CREATE INDEX IF NOT EXISTS ix_fantasy_players_tournament_code ON fantasy_players (tournament_code);
CREATE INDEX IF NOT EXISTS ix_fantasy_players_external_player_id ON fantasy_players (external_player_id);
CREATE INDEX IF NOT EXISTS ix_fantasy_players_external_team_id ON fantasy_players (external_team_id);
CREATE INDEX IF NOT EXISTS ix_fantasy_players_team_name ON fantasy_players (team_name);
CREATE INDEX IF NOT EXISTS ix_fantasy_players_team_display_name ON fantasy_players (team_display_name);
CREATE INDEX IF NOT EXISTS ix_fantasy_players_player_name ON fantasy_players (player_name);
CREATE INDEX IF NOT EXISTS ix_fantasy_players_position ON fantasy_players (position);
CREATE INDEX IF NOT EXISTS ix_fantasy_players_fifa_category ON fantasy_players (fifa_category);
CREATE INDEX IF NOT EXISTS ix_fantasy_players_is_active ON fantasy_players (is_active);

CREATE TABLE IF NOT EXISTS fantasy_teams (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tournament_code VARCHAR NOT NULL DEFAULT 'wc2026',
    formation VARCHAR NOT NULL DEFAULT '4-3-3',
    captain_player_id INTEGER REFERENCES fantasy_players(id) ON DELETE SET NULL,
    points INTEGER DEFAULT 0,
    is_locked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_fantasy_team_user_tournament UNIQUE (user_id, tournament_code)
);

CREATE INDEX IF NOT EXISTS ix_fantasy_teams_user_id ON fantasy_teams (user_id);
CREATE INDEX IF NOT EXISTS ix_fantasy_teams_tournament_code ON fantasy_teams (tournament_code);

CREATE TABLE IF NOT EXISTS fantasy_team_players (
    id SERIAL PRIMARY KEY,
    fantasy_team_id INTEGER NOT NULL REFERENCES fantasy_teams(id) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES fantasy_players(id) ON DELETE CASCADE,
    position_slot VARCHAR NOT NULL,
    position VARCHAR NOT NULL,
    is_captain BOOLEAN DEFAULT FALSE,
    points INTEGER DEFAULT 0,
    CONSTRAINT uq_fantasy_team_position_slot UNIQUE (fantasy_team_id, position_slot),
    CONSTRAINT uq_fantasy_team_player UNIQUE (fantasy_team_id, player_id)
);

CREATE INDEX IF NOT EXISTS ix_fantasy_team_players_fantasy_team_id ON fantasy_team_players (fantasy_team_id);
CREATE INDEX IF NOT EXISTS ix_fantasy_team_players_player_id ON fantasy_team_players (player_id);
CREATE INDEX IF NOT EXISTS ix_fantasy_team_players_position ON fantasy_team_players (position);

CREATE TABLE IF NOT EXISTS fantasy_player_match_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES fantasy_players(id) ON DELETE CASCADE,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    minutes INTEGER DEFAULT 0,
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    yellow_cards INTEGER DEFAULT 0,
    red_cards INTEGER DEFAULT 0,
    clean_sheet BOOLEAN DEFAULT FALSE,
    goals_conceded INTEGER DEFAULT 0,
    own_goals INTEGER DEFAULT 0,
    penalty_missed INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    source_updated_at TIMESTAMPTZ,
    CONSTRAINT uq_fantasy_player_match_stat UNIQUE (player_id, match_id)
);

CREATE INDEX IF NOT EXISTS ix_fantasy_player_match_stats_player_id ON fantasy_player_match_stats (player_id);
CREATE INDEX IF NOT EXISTS ix_fantasy_player_match_stats_match_id ON fantasy_player_match_stats (match_id);
