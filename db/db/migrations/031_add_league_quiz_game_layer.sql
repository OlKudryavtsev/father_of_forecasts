-- v3.5.0 — quiz game layer: result cards, achievements, recap cache and analytics.
-- Apply after migrations 023–030.

BEGIN;

CREATE TABLE IF NOT EXISTS league_quiz_round_results (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES league_quiz_sessions(id) ON DELETE CASCADE,
    round_id INTEGER NOT NULL REFERENCES league_quiz_session_rounds(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    round_order INTEGER NOT NULL,
    round_score INTEGER NOT NULL DEFAULT 0,
    score_total INTEGER NOT NULL DEFAULT 0,
    place INTEGER NOT NULL,
    previous_place INTEGER,
    place_change INTEGER NOT NULL DEFAULT 0,
    best_question_id INTEGER REFERENCES league_quiz_session_questions(id) ON DELETE SET NULL,
    best_answer_label VARCHAR(240),
    best_answer_points INTEGER NOT NULL DEFAULT 0,
    correct_answers INTEGER NOT NULL DEFAULT 0,
    answered_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_league_quiz_round_result UNIQUE (session_id, round_id, user_id)
);
CREATE INDEX IF NOT EXISTS ix_league_quiz_round_results_session_round
    ON league_quiz_round_results (session_id, round_order, user_id);
CREATE INDEX IF NOT EXISTS ix_league_quiz_round_results_user
    ON league_quiz_round_results (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS league_quiz_achievements (
    id SERIAL PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    achievement_code VARCHAR(64) NOT NULL,
    unlocked_in_session_id INTEGER REFERENCES league_quiz_sessions(id) ON DELETE SET NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    unlocked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_league_quiz_achievement UNIQUE (league_id, user_id, achievement_code)
);
CREATE INDEX IF NOT EXISTS ix_league_quiz_achievements_user_league
    ON league_quiz_achievements (user_id, league_id, unlocked_at DESC);

CREATE TABLE IF NOT EXISTS league_quiz_recaps (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES league_quiz_sessions(id) ON DELETE CASCADE,
    round_id INTEGER REFERENCES league_quiz_session_rounds(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    scope_key VARCHAR(160) NOT NULL,
    recap_text TEXT NOT NULL,
    source VARCHAR(24) NOT NULL DEFAULT 'template',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_league_quiz_recap_scope UNIQUE (session_id, scope_key)
);
CREATE INDEX IF NOT EXISTS ix_league_quiz_recaps_session ON league_quiz_recaps (session_id, created_at DESC);

COMMENT ON TABLE league_quiz_round_results IS
    'Frozen per-player quiz state after every completed live round. Test runs are excluded.';
COMMENT ON TABLE league_quiz_achievements IS
    'One-time quiz achievements only; unrelated to football forecast badges.';
COMMENT ON TABLE league_quiz_recaps IS
    'Cached factual/template or OpenAI wording for round and quiz result cards.';

COMMIT;
