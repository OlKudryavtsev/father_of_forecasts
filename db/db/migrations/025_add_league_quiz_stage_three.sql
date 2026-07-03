-- v3.2.0 — Stage 3: text rounds, Jeopardy board, countdown hints and «Сто к одному».
-- Content snapshots remain immutable per session; runtime_state stores only the
-- active hint stage for a live question and is safe to change during a game.

BEGIN;

ALTER TABLE league_quiz_questions
    ADD COLUMN IF NOT EXISTS question_payload JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE league_quiz_session_questions
    ADD COLUMN IF NOT EXISTS payload_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE league_quiz_session_questions
    ADD COLUMN IF NOT EXISTS runtime_state JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS ix_league_quiz_questions_type_status
    ON league_quiz_questions (league_id, question_type, status);

COMMIT;
