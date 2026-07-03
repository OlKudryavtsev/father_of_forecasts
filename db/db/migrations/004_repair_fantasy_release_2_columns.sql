-- Hotfix: repair Fantasy Release 2 DB columns if 003 migration was not applied
-- or was applied against a different database.
-- Safe to run multiple times.

BEGIN;

-- 1) Ensure base Fantasy tables exist. If this block fails, run 002_add_fantasy.sql first.
DO $$
BEGIN
    IF to_regclass('public.fantasy_teams') IS NULL THEN
        RAISE EXCEPTION 'Table fantasy_teams does not exist. Run db/migrations/002_add_fantasy.sql first.';
    END IF;

    IF to_regclass('public.fantasy_team_players') IS NULL THEN
        RAISE EXCEPTION 'Table fantasy_team_players does not exist. Run db/migrations/002_add_fantasy.sql first.';
    END IF;

    IF to_regclass('public.fantasy_player_match_stats') IS NULL THEN
        RAISE EXCEPTION 'Table fantasy_player_match_stats does not exist. Run db/migrations/002_add_fantasy.sql first.';
    END IF;
END $$;

-- 2) Fantasy team transfer metadata.
ALTER TABLE public.fantasy_teams
    ADD COLUMN IF NOT EXISTS transfer_penalty_points INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS transfers_used INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS transfer_window_key VARCHAR,
    ADD COLUMN IF NOT EXISTS transfer_baseline_player_ids TEXT;

-- 3) Starter/bench metadata.
ALTER TABLE public.fantasy_team_players
    ADD COLUMN IF NOT EXISTS is_starter BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS bench_order INTEGER;

-- 4) Additional player match stats for Fantasy scoring.
ALTER TABLE public.fantasy_player_match_stats
    ADD COLUMN IF NOT EXISTS starts BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS saves INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS penalties_saved INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS balls_recovered INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS shots_on_target INTEGER NOT NULL DEFAULT 0;

-- 5) Backfill NULL values in case columns were created earlier without defaults.
UPDATE public.fantasy_teams
SET
    transfer_penalty_points = COALESCE(transfer_penalty_points, 0),
    transfers_used = COALESCE(transfers_used, 0);

UPDATE public.fantasy_team_players
SET
    is_starter = COALESCE(is_starter, TRUE);

UPDATE public.fantasy_player_match_stats
SET
    starts = COALESCE(starts, FALSE),
    saves = COALESCE(saves, 0),
    penalties_saved = COALESCE(penalties_saved, 0),
    balls_recovered = COALESCE(balls_recovered, 0),
    shots_on_target = COALESCE(shots_on_target, 0);

-- 6) Indexes.
CREATE INDEX IF NOT EXISTS ix_fantasy_teams_transfer_window_key
    ON public.fantasy_teams (transfer_window_key);

CREATE INDEX IF NOT EXISTS ix_fantasy_team_players_is_starter
    ON public.fantasy_team_players (is_starter);

COMMIT;

-- 7) Verification: should return all required columns.
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('fantasy_teams', 'fantasy_team_players', 'fantasy_player_match_stats')
  AND column_name IN (
      'transfer_penalty_points',
      'transfers_used',
      'transfer_window_key',
      'transfer_baseline_player_ids',
      'is_starter',
      'bench_order',
      'starts',
      'saves',
      'penalties_saved',
      'balls_recovered',
      'shots_on_target'
  )
ORDER BY table_name, column_name;
