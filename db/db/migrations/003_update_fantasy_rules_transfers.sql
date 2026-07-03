-- Fantasy Release 2: transfers, 15-player squad, captain x2 support metadata.
-- Run after 002_add_fantasy.sql:
--   psql "$DATABASE_URL" -f db/migrations/003_update_fantasy_rules_transfers.sql

ALTER TABLE fantasy_teams
    ADD COLUMN IF NOT EXISTS transfer_penalty_points INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS transfers_used INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS transfer_window_key VARCHAR,
    ADD COLUMN IF NOT EXISTS transfer_baseline_player_ids TEXT;

ALTER TABLE fantasy_team_players
    ADD COLUMN IF NOT EXISTS is_starter BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS bench_order INTEGER;

ALTER TABLE fantasy_player_match_stats
    ADD COLUMN IF NOT EXISTS starts BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS saves INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS penalties_saved INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS balls_recovered INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS shots_on_target INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS ix_fantasy_teams_transfer_window_key
    ON fantasy_teams (transfer_window_key);

CREATE INDEX IF NOT EXISTS ix_fantasy_team_players_is_starter
    ON fantasy_team_players (is_starter);
