-- v2.8.24: league-specific Telegram chat notifications

ALTER TABLE leagues
    ADD COLUMN IF NOT EXISTS chat_id TEXT;

COMMENT ON COLUMN leagues.chat_id IS 'Optional Telegram group/chat id for league-scoped notifications';
