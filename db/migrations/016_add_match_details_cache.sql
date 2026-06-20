-- v2.8.31: unified backend cache for API-Football match details.
-- Run once after deploying the application code.

BEGIN;

CREATE TABLE IF NOT EXISTS match_details_cache (
    id SERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL UNIQUE REFERENCES matches(id) ON DELETE CASCADE,
    fixture_payload JSONB,
    events_payload JSONB,
    statistics_payload JSONB,
    lineups_payload JSONB,
    players_payload JSONB,
    sync_status TEXT NOT NULL DEFAULT 'pending',
    last_synced_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_match_details_cache_sync_status
    ON match_details_cache(sync_status);

CREATE INDEX IF NOT EXISTS ix_match_details_cache_last_success_at
    ON match_details_cache(last_success_at);

COMMIT;
