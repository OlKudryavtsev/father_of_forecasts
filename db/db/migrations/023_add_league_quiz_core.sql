-- v3.0.1 — core of the league-scoped synchronous quiz platform.
-- This is intentionally independent from legacy /quiz tables:
-- quiz_questions, quiz_answers, group_quiz_*.
-- Apply once in Railway PostgreSQL before deploying v3.0.1.

BEGIN;

CREATE TABLE IF NOT EXISTS league_quiz_questions (
    id SERIAL PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    question_type VARCHAR(40) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'draft',
    question_text TEXT NOT NULL,
    explanation TEXT,
    default_points INTEGER NOT NULL DEFAULT 100 CHECK (default_points >= 0),
    tags VARCHAR(500),
    times_used INTEGER NOT NULL DEFAULT 0 CHECK (times_used >= 0),
    last_used_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_league_quiz_question_type CHECK (question_type IN (
        'choice_2', 'choice_4', 'jeopardy', 'one_of_two',
        'what_where_when', 'countdown', 'one_hundred_to_one'
    )),
    CONSTRAINT chk_league_quiz_question_status CHECK (status IN ('draft', 'approved', 'archived'))
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_questions_league_status
    ON league_quiz_questions (league_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_league_quiz_questions_type
    ON league_quiz_questions (question_type);

CREATE TABLE IF NOT EXISTS league_quiz_question_options (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES league_quiz_questions(id) ON DELETE CASCADE,
    option_key VARCHAR(12) NOT NULL,
    option_text TEXT NOT NULL,
    position INTEGER NOT NULL,
    is_correct BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_league_quiz_question_option_key UNIQUE (question_id, option_key),
    CONSTRAINT uq_league_quiz_question_option_position UNIQUE (question_id, position)
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_question_options_question
    ON league_quiz_question_options (question_id);

CREATE TABLE IF NOT EXISTS league_quiz_question_aliases (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES league_quiz_questions(id) ON DELETE CASCADE,
    alias_text VARCHAR(500) NOT NULL,
    normalized_alias VARCHAR(500) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_league_quiz_question_alias UNIQUE (question_id, normalized_alias)
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_question_aliases_normalized
    ON league_quiz_question_aliases (normalized_alias);

CREATE TABLE IF NOT EXISTS league_quiz_question_sources (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES league_quiz_questions(id) ON DELETE CASCADE,
    source_title VARCHAR(500),
    source_url TEXT,
    source_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_question_sources_question
    ON league_quiz_question_sources (question_id);

CREATE TABLE IF NOT EXISTS league_quiz_sessions (
    id SERIAL PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    title VARCHAR(160) NOT NULL,
    description TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'registration_open',
    scheduled_start_at TIMESTAMPTZ,
    registration_opened_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    paused_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    seconds_per_question INTEGER NOT NULL DEFAULT 30 CHECK (seconds_per_question BETWEEN 10 AND 300),
    reveal_seconds INTEGER NOT NULL DEFAULT 12 CHECK (reveal_seconds BETWEEN 3 AND 90),
    allow_late_registration BOOLEAN NOT NULL DEFAULT FALSE,
    rounds_total INTEGER NOT NULL DEFAULT 1 CHECK (rounds_total >= 1),
    current_round_order INTEGER,
    current_question_order INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_league_quiz_session_status CHECK (status IN (
        'draft', 'registration_open', 'running', 'paused', 'finished', 'cancelled', 'archived'
    ))
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_sessions_league_status
    ON league_quiz_sessions (league_id, status, scheduled_start_at DESC);
CREATE INDEX IF NOT EXISTS ix_league_quiz_sessions_active
    ON league_quiz_sessions (status, scheduled_start_at)
    WHERE status IN ('registration_open', 'running', 'paused');

CREATE TABLE IF NOT EXISTS league_quiz_session_rounds (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES league_quiz_sessions(id) ON DELETE CASCADE,
    round_order INTEGER NOT NULL,
    round_type VARCHAR(40) NOT NULL,
    title VARCHAR(160) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'pending',
    points_mode VARCHAR(24) NOT NULL DEFAULT 'positive',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_league_quiz_session_round_order UNIQUE (session_id, round_order),
    CONSTRAINT chk_league_quiz_round_status CHECK (status IN ('pending', 'running', 'finished', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_session_rounds_session
    ON league_quiz_session_rounds (session_id, round_order);

CREATE TABLE IF NOT EXISTS league_quiz_session_questions (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL REFERENCES league_quiz_session_rounds(id) ON DELETE CASCADE,
    bank_question_id INTEGER REFERENCES league_quiz_questions(id) ON DELETE SET NULL,
    question_order INTEGER NOT NULL,
    question_type VARCHAR(40) NOT NULL,
    question_text_snapshot TEXT NOT NULL,
    explanation_snapshot TEXT,
    options_snapshot JSONB NOT NULL,
    points INTEGER NOT NULL DEFAULT 0,
    negative_on_wrong BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(24) NOT NULL DEFAULT 'pending',
    opened_at TIMESTAMPTZ,
    closes_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    revealed_at TIMESTAMPTZ,
    revealed_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_league_quiz_session_question_order UNIQUE (round_id, question_order),
    CONSTRAINT chk_league_quiz_session_question_status CHECK (status IN ('pending', 'open', 'revealed', 'closed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_session_questions_round_status
    ON league_quiz_session_questions (round_id, status, question_order);
CREATE INDEX IF NOT EXISTS ix_league_quiz_session_questions_closes_at
    ON league_quiz_session_questions (closes_at)
    WHERE status = 'open';

CREATE TABLE IF NOT EXISTS league_quiz_session_participants (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES league_quiz_sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(24) NOT NULL DEFAULT 'registered',
    score_total INTEGER NOT NULL DEFAULT 0,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_league_quiz_session_participant UNIQUE (session_id, user_id),
    CONSTRAINT chk_league_quiz_participant_status CHECK (status IN ('registered', 'left', 'disqualified'))
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_session_participants_session_score
    ON league_quiz_session_participants (session_id, status, score_total DESC);

CREATE TABLE IF NOT EXISTS league_quiz_session_answers (
    id SERIAL PRIMARY KEY,
    session_question_id INTEGER NOT NULL REFERENCES league_quiz_session_questions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    selected_option_key VARCHAR(12),
    answer_text TEXT,
    answer_payload JSONB,
    is_correct BOOLEAN,
    points_awarded INTEGER,
    answered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scored_at TIMESTAMPTZ,
    CONSTRAINT uq_league_quiz_session_question_answer UNIQUE (session_question_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_session_answers_question
    ON league_quiz_session_answers (session_question_id);
CREATE INDEX IF NOT EXISTS ix_league_quiz_session_answers_user
    ON league_quiz_session_answers (user_id);

CREATE TABLE IF NOT EXISTS league_quiz_score_events (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES league_quiz_sessions(id) ON DELETE CASCADE,
    round_id INTEGER REFERENCES league_quiz_session_rounds(id) ON DELETE SET NULL,
    session_question_id INTEGER REFERENCES league_quiz_session_questions(id) ON DELETE SET NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type VARCHAR(40) NOT NULL,
    delta_points INTEGER NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_score_events_session_user
    ON league_quiz_score_events (session_id, user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_league_quiz_score_events_question
    ON league_quiz_score_events (session_question_id);

CREATE TABLE IF NOT EXISTS league_quiz_events (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES league_quiz_sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_events_session_created
    ON league_quiz_events (session_id, created_at DESC);

CREATE TABLE IF NOT EXISTS league_quiz_admin_actions (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES league_quiz_sessions(id) ON DELETE CASCADE,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action_type VARCHAR(64) NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_league_quiz_admin_actions_session_created
    ON league_quiz_admin_actions (session_id, created_at DESC);

COMMIT;
