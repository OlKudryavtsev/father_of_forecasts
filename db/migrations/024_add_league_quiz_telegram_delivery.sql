-- v3.1.0 — durable Telegram delivery ledger for league quizzes.
-- Existing v3.0.x quiz events are intentionally marked as historical so that
-- deploying this migration does not resend old test-game announcements.

CREATE TABLE IF NOT EXISTS league_quiz_telegram_deliveries (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES league_quiz_events(id) ON DELETE CASCADE,
    destination_key VARCHAR(160) NOT NULL,
    recipient_user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    chat_id VARCHAR(80) NULL,
    message_kind VARCHAR(64) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'sent',
    error_text TEXT NULL,
    delivered_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_league_quiz_telegram_event_destination UNIQUE (event_id, destination_key)
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_telegram_deliveries_event_id
    ON league_quiz_telegram_deliveries(event_id);
CREATE INDEX IF NOT EXISTS ix_league_quiz_telegram_deliveries_recipient_user_id
    ON league_quiz_telegram_deliveries(recipient_user_id);

-- Historical Stage 1 events must remain in the audit log but must not trigger a
-- burst of announcements immediately after upgrading to Stage 2.
UPDATE league_quiz_events
SET payload = COALESCE(payload, '{}'::jsonb) || jsonb_build_object('telegram_skip', true)
WHERE created_at < NOW()
  AND COALESCE(payload, '{}'::jsonb)->>'telegram_skip' IS DISTINCT FROM 'true';
