-- v3.4.0 — deterministic league-quiz delivery flow and per-format timers.
-- Apply after migrations 023–027.

ALTER TABLE league_quiz_sessions
    ADD COLUMN IF NOT EXISTS timer_settings JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN league_quiz_sessions.timer_settings IS
    'Per-format answer timers in seconds. Empty object uses application defaults.';

-- The unique constraint was already introduced in migration 024. Recreate it
-- defensively in case an environment was upgraded from a partial deployment.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_league_quiz_telegram_event_destination'
    ) THEN
        ALTER TABLE league_quiz_telegram_deliveries
            ADD CONSTRAINT uq_league_quiz_telegram_event_destination
            UNIQUE (event_id, destination_key);
    END IF;
END $$;
