-- v3.3.0 — Stage 4: question-editor audit history and manual adjudication.
-- Question media remain in question_payload JSONB because session snapshots already
-- copy that payload into the live quiz and therefore preserve past games.

BEGIN;

CREATE TABLE IF NOT EXISTS league_quiz_question_audits (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES league_quiz_questions(id) ON DELETE CASCADE,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action_type VARCHAR(64) NOT NULL,
    before_snapshot JSONB,
    after_snapshot JSONB,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_question_audits_question_created
    ON league_quiz_question_audits (question_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_league_quiz_question_audits_league_created
    ON league_quiz_question_audits (league_id, created_at DESC);

CREATE TABLE IF NOT EXISTS league_quiz_answer_reviews (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES league_quiz_sessions(id) ON DELETE CASCADE,
    session_question_id INTEGER NOT NULL REFERENCES league_quiz_session_questions(id) ON DELETE CASCADE,
    answer_id INTEGER NOT NULL REFERENCES league_quiz_session_answers(id) ON DELETE CASCADE,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    decision VARCHAR(24) NOT NULL CHECK (decision IN ('accepted', 'rejected')),
    previous_is_correct BOOLEAN,
    previous_points INTEGER NOT NULL DEFAULT 0,
    new_is_correct BOOLEAN NOT NULL,
    new_points INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_answer_reviews_question_created
    ON league_quiz_answer_reviews (session_question_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_league_quiz_answer_reviews_answer_created
    ON league_quiz_answer_reviews (answer_id, created_at DESC);

COMMIT;
