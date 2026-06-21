-- v2.8.44 — Product analytics for the Mini App
-- Stores only internal user IDs and allowlisted event properties.
-- No Telegram IDs, usernames, prediction scores or free text are collected.

BEGIN;

CREATE TABLE IF NOT EXISTS analytics_events (
    id SERIAL PRIMARY KEY,

    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id VARCHAR(96) NOT NULL,
    event_name VARCHAR(64) NOT NULL,
    screen VARCHAR(64),
    source VARCHAR(24) NOT NULL DEFAULT 'web',
    app_version VARCHAR(32),
    properties JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_analytics_events_user_id ON analytics_events (user_id);
CREATE INDEX IF NOT EXISTS ix_analytics_events_session_id ON analytics_events (session_id);
CREATE INDEX IF NOT EXISTS ix_analytics_events_event_name ON analytics_events (event_name);
CREATE INDEX IF NOT EXISTS ix_analytics_events_screen ON analytics_events (screen);
CREATE INDEX IF NOT EXISTS ix_analytics_events_source ON analytics_events (source);
CREATE INDEX IF NOT EXISTS ix_analytics_events_created_at ON analytics_events (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_analytics_events_event_created_at ON analytics_events (event_name, created_at DESC);

COMMIT;
