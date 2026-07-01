-- v3.4.2 — quiz-readiness layer: content metadata/validation, scoped roles,
-- repeat protection and isolated host-only test runs. Apply after 001–029.

BEGIN;

ALTER TABLE league_members
    ADD COLUMN IF NOT EXISTS quiz_roles JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE league_quiz_questions
    ADD COLUMN IF NOT EXISTS topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS difficulty VARCHAR(16),
    ADD COLUMN IF NOT EXISTS repeat_after_days INTEGER NOT NULL DEFAULT 14;

ALTER TABLE league_quiz_questions
    DROP CONSTRAINT IF EXISTS chk_league_quiz_question_repeat_after_days;
ALTER TABLE league_quiz_questions
    ADD CONSTRAINT chk_league_quiz_question_repeat_after_days
    CHECK (repeat_after_days BETWEEN 0 AND 365);

ALTER TABLE league_quiz_sessions
    ADD COLUMN IF NOT EXISTS is_test_run BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS test_host_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS test_chat_id VARCHAR(80);

CREATE INDEX IF NOT EXISTS ix_league_quiz_sessions_test_host
    ON league_quiz_sessions (test_host_user_id, is_test_run);
CREATE INDEX IF NOT EXISTS ix_league_quiz_questions_difficulty
    ON league_quiz_questions (league_id, difficulty);

-- Existing approved questions remain usable. Mark the supplied WC-2026 test bank
-- so it is immediately useful for topic analytics and ready for future reuse rules.
UPDATE league_quiz_questions
SET
    topics = CASE WHEN COALESCE(topics, '[]'::jsonb) = '[]'::jsonb THEN '["ЧМ-2026"]'::jsonb ELSE topics END,
    difficulty = COALESCE(NULLIF(difficulty, ''), 'medium'),
    repeat_after_days = COALESCE(repeat_after_days, 14)
WHERE tags LIKE 'seed:wc2026-%';

COMMENT ON COLUMN league_members.quiz_roles IS
    'Scoped quiz roles: host, editor, moderator. League owner/admin has all quiz permissions.';
COMMENT ON COLUMN league_quiz_questions.topics IS
    'Question topics used for content governance and quiz analytics.';
COMMENT ON COLUMN league_quiz_questions.difficulty IS
    'Question difficulty: easy, medium or hard.';
COMMENT ON COLUMN league_quiz_questions.repeat_after_days IS
    'Minimum interval before a live quiz may reuse the question; 0 disables the protection.';
COMMENT ON COLUMN league_quiz_sessions.is_test_run IS
    'Host-only rehearsal. Does not send league broadcasts or increment bank usage statistics.';

COMMIT;
