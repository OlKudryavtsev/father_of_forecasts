-- v3.7.5 — durable background cache for league win probabilities and scenarios.
-- The cache is safe to delete/rebuild; it contains no source-of-truth scores.

BEGIN;

CREATE TABLE IF NOT EXISTS league_win_model_cache (
    id SERIAL PRIMARY KEY,
    league_id INTEGER NOT NULL UNIQUE REFERENCES leagues(id) ON DELETE CASCADE,
    source_signature VARCHAR(96),
    payload JSONB,
    sync_status VARCHAR(24) NOT NULL DEFAULT 'pending',
    last_synced_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_league_win_model_cache_sync_status
    ON league_win_model_cache (sync_status);
CREATE INDEX IF NOT EXISTS ix_league_win_model_cache_source_signature
    ON league_win_model_cache (source_signature);

COMMENT ON TABLE league_win_model_cache IS
    'Precomputed Monte-Carlo probabilities and likely strict-first-place paths per league. Rebuilt in the bot background.';

COMMIT;
