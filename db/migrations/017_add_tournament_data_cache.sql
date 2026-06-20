-- Shared cache for tournament-level API-Football payloads used by Mini App 2.0.
CREATE TABLE IF NOT EXISTS tournament_data_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR NOT NULL UNIQUE,
    payload JSONB,
    sync_status VARCHAR NOT NULL DEFAULT 'pending',
    last_synced_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_tournament_data_cache_cache_key
    ON tournament_data_cache (cache_key);
CREATE INDEX IF NOT EXISTS ix_tournament_data_cache_sync_status
    ON tournament_data_cache (sync_status);
