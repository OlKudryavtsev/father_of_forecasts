-- v2.8.58 — RSS-powered World Cup news with one shared AI curation call per scan.
-- Apply once in Railway PostgreSQL before deploying this release.

BEGIN;

CREATE TABLE IF NOT EXISTS world_cup_news_items (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(128) NOT NULL UNIQUE,
    source_name VARCHAR(160),
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    father_commentary TEXT,
    category VARCHAR(64),
    relevance_score INTEGER NOT NULL DEFAULT 0,
    published_at TIMESTAMPTZ,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    selected_at TIMESTAMPTZ,
    published_for_date DATE,
    selection_status VARCHAR(24) NOT NULL DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS ix_world_cup_news_items_published_at
    ON world_cup_news_items (published_at DESC);
CREATE INDEX IF NOT EXISTS ix_world_cup_news_items_selected_at
    ON world_cup_news_items (selected_at DESC);
CREATE INDEX IF NOT EXISTS ix_world_cup_news_items_published_for_date
    ON world_cup_news_items (published_for_date);
CREATE INDEX IF NOT EXISTS ix_world_cup_news_items_selection_status
    ON world_cup_news_items (selection_status);

CREATE TABLE IF NOT EXISTS league_news_deliveries (
    id SERIAL PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    news_item_id INTEGER NOT NULL REFERENCES world_cup_news_items(id) ON DELETE CASCADE,
    chat_id VARCHAR(80),
    delivered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_league_news_delivery UNIQUE (league_id, news_item_id)
);

CREATE INDEX IF NOT EXISTS ix_league_news_deliveries_league_id
    ON league_news_deliveries (league_id);
CREATE INDEX IF NOT EXISTS ix_league_news_deliveries_news_item_id
    ON league_news_deliveries (news_item_id);

CREATE TABLE IF NOT EXISTS ai_usage_logs (
    id SERIAL PRIMARY KEY,
    purpose VARCHAR(64) NOT NULL,
    model VARCHAR(96),
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd VARCHAR(32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ai_usage_logs_purpose_created
    ON ai_usage_logs (purpose, created_at DESC);

COMMIT;
