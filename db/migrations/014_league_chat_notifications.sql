-- v2.8.24 — League chat notifications
-- Adds optional Telegram chat_id per league for league-scoped group notifications.

BEGIN;

ALTER TABLE leagues
    ADD COLUMN IF NOT EXISTS chat_id BIGINT;

CREATE INDEX IF NOT EXISTS ix_leagues_chat_id ON leagues (chat_id);

COMMIT;
