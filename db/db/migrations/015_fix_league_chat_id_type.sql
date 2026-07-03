-- v2.8.26: make league chat_id type consistent and safe

-- Some production databases may already have leagues.chat_id as BIGINT from an
-- earlier rollout. The application treats it as optional text input, so align
-- the database type with the model and preserve existing numeric ids.
ALTER TABLE leagues
    ADD COLUMN IF NOT EXISTS chat_id TEXT;

ALTER TABLE leagues
    ALTER COLUMN chat_id TYPE TEXT USING NULLIF(chat_id::text, '');

UPDATE leagues
SET chat_id = NULL
WHERE chat_id IS NOT NULL AND btrim(chat_id) = '';

COMMENT ON COLUMN leagues.chat_id IS 'Optional Telegram group/chat id for league-scoped notifications';
