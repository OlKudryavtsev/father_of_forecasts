-- Add timed group quiz battle tables.
-- Safe to run on an existing PostgreSQL database.

BEGIN;

CREATE TABLE IF NOT EXISTS group_quiz_games (
    id SERIAL PRIMARY KEY,

    chat_id BIGINT NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'setup',

    questions_total INTEGER NOT NULL,
    current_question_index INTEGER DEFAULT 0,

    seconds_per_question INTEGER NOT NULL DEFAULT 60,

    started_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,

    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_group_quiz_games_chat_id ON group_quiz_games (chat_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_games_status ON group_quiz_games (status);

CREATE TABLE IF NOT EXISTS group_quiz_game_questions (
    id SERIAL PRIMARY KEY,

    game_id INTEGER NOT NULL REFERENCES group_quiz_games(id) ON DELETE CASCADE,
    quiz_question_id INTEGER NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,

    question_order INTEGER NOT NULL,

    message_id BIGINT,

    opened_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,

    status VARCHAR NOT NULL DEFAULT 'pending',

    CONSTRAINT uq_group_quiz_game_question_order UNIQUE (game_id, question_order)
);

CREATE INDEX IF NOT EXISTS ix_group_quiz_game_questions_game_id ON group_quiz_game_questions (game_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_game_questions_quiz_question_id ON group_quiz_game_questions (quiz_question_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_game_questions_status ON group_quiz_game_questions (status);

CREATE TABLE IF NOT EXISTS group_quiz_game_answers (
    id SERIAL PRIMARY KEY,

    game_id INTEGER NOT NULL REFERENCES group_quiz_games(id) ON DELETE CASCADE,
    game_question_id INTEGER NOT NULL REFERENCES group_quiz_game_questions(id) ON DELETE CASCADE,
    quiz_question_id INTEGER NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,

    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    telegram_id BIGINT,
    display_name VARCHAR,

    selected_option VARCHAR NOT NULL,
    is_correct BOOLEAN NOT NULL,

    answered_at TIMESTAMPTZ DEFAULT NOW(),
    answer_seconds INTEGER,

    CONSTRAINT uq_group_quiz_game_question_user UNIQUE (game_question_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_group_quiz_game_answers_game_id ON group_quiz_game_answers (game_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_game_answers_game_question_id ON group_quiz_game_answers (game_question_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_game_answers_quiz_question_id ON group_quiz_game_answers (quiz_question_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_game_answers_user_id ON group_quiz_game_answers (user_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_game_answers_telegram_id ON group_quiz_game_answers (telegram_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_game_answers_answered_at ON group_quiz_game_answers (answered_at);

COMMIT;
