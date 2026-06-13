-- db/schema.sql
-- Актуальная базовая схема БД проекта «Отец прогнозов».
--
-- Схема подготовлена по текущим SQLAlchemy-моделям из app/models.py.
-- Это bootstrap-скрипт для создания БД с нуля, а не полноценная система миграций.
--
-- Для уже существующей production-БД в Railway не применяйте файл целиком без проверки:
-- часть таблиц и колонок уже может существовать.
--
-- Рекомендуемый безопасный порядок:
-- 1. Сделать backup production-БД.
-- 2. Проверить текущую схему: python scripts/check_db_schema.py
-- 3. Для новой пустой БД можно применить этот файл целиком.

BEGIN;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL UNIQUE,
    username VARCHAR,
    display_name VARCHAR NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_telegram_id ON users (telegram_id);


CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    tournament_code VARCHAR NOT NULL DEFAULT 'wc2026',

    home_team VARCHAR NOT NULL,
    away_team VARCHAR NOT NULL,

    stage VARCHAR NOT NULL DEFAULT 'group',
    starts_at TIMESTAMPTZ NOT NULL,

    score_home INTEGER,
    score_away INTEGER,
    winner_side VARCHAR,

    is_finished BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    fifa_match_no INTEGER,
    match_round VARCHAR,
    group_code VARCHAR,

    venue VARCHAR,
    city VARCHAR,

    external_provider VARCHAR,
    external_fixture_id VARCHAR,

    home_external_team_id INTEGER,
    away_external_team_id INTEGER,
    home_team_api_name VARCHAR,
    away_team_api_name VARCHAR,

    api_league_round VARCHAR,

    status_short VARCHAR,
    status_long VARCHAR,

    synced_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_matches_tournament_code ON matches (tournament_code);
CREATE INDEX IF NOT EXISTS ix_matches_starts_at ON matches (starts_at);
CREATE INDEX IF NOT EXISTS ix_matches_tournament_starts_at ON matches (tournament_code, starts_at);
CREATE INDEX IF NOT EXISTS ix_matches_external_fixture_id ON matches (external_fixture_id);
CREATE INDEX IF NOT EXISTS ix_matches_fifa_match_no ON matches (fifa_match_no);

CREATE TABLE IF NOT EXISTS match_videos (
    id SERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,

    source VARCHAR NOT NULL DEFAULT 'matchtv',
    video_type VARCHAR NOT NULL DEFAULT 'highlights',
    title VARCHAR NOT NULL,
    url TEXT NOT NULL,

    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 100,

    discovery_status VARCHAR NOT NULL DEFAULT 'manual',
    confidence INTEGER DEFAULT 100,
    external_id VARCHAR,

    available_from TIMESTAMPTZ,
    discovered_at TIMESTAMPTZ,
    notification_sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_match_videos_match_id ON match_videos (match_id);
CREATE INDEX IF NOT EXISTS ix_match_videos_is_active ON match_videos (is_active);
CREATE INDEX IF NOT EXISTS ix_match_videos_match_active_priority ON match_videos (match_id, is_active, priority);
CREATE INDEX IF NOT EXISTS ix_match_videos_discovery_status ON match_videos (discovery_status);
CREATE INDEX IF NOT EXISTS ix_match_videos_external_id ON match_videos (external_id);



CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,

    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,

    pred_home INTEGER NOT NULL,
    pred_away INTEGER NOT NULL,

    advancement_bet_enabled BOOLEAN DEFAULT FALSE,
    predicted_advancing_side VARCHAR,

    score_points INTEGER DEFAULT 0,
    advancement_points INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_user_match_prediction UNIQUE (user_id, match_id)
);

CREATE INDEX IF NOT EXISTS ix_predictions_user_id ON predictions (user_id);
CREATE INDEX IF NOT EXISTS ix_predictions_match_id ON predictions (match_id);


CREATE TABLE IF NOT EXISTS tournament_predictions (
    id SERIAL PRIMARY KEY,

    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tournament_code VARCHAR NOT NULL DEFAULT 'wc2026',

    champion VARCHAR NOT NULL,
    runner_up VARCHAR NOT NULL,
    third_place VARCHAR NOT NULL,
    top_scorer VARCHAR NOT NULL,

    champion_points INTEGER DEFAULT 0,
    runner_up_points INTEGER DEFAULT 0,
    third_place_points INTEGER DEFAULT 0,
    top_scorer_points INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_user_tournament_prediction UNIQUE (user_id, tournament_code)
);

CREATE INDEX IF NOT EXISTS ix_tournament_predictions_user_id ON tournament_predictions (user_id);
CREATE INDEX IF NOT EXISTS ix_tournament_predictions_tournament_code ON tournament_predictions (tournament_code);


CREATE TABLE IF NOT EXISTS tournament_results (
    id SERIAL PRIMARY KEY,

    tournament_code VARCHAR NOT NULL UNIQUE DEFAULT 'wc2026',

    champion VARCHAR NOT NULL,
    runner_up VARCHAR NOT NULL,
    third_place VARCHAR NOT NULL,
    top_scorer VARCHAR NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS reminder_logs (
    id SERIAL PRIMARY KEY,

    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,

    reminder_type VARCHAR NOT NULL,
    reminder_key VARCHAR NOT NULL,

    sent_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_reminder_user_match_type_key UNIQUE (
        user_id,
        match_id,
        reminder_type,
        reminder_key
    )
);

CREATE INDEX IF NOT EXISTS ix_reminder_logs_user_id ON reminder_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_reminder_logs_match_id ON reminder_logs (match_id);


CREATE TABLE IF NOT EXISTS command_logs (
    id SERIAL PRIMARY KEY,

    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    telegram_id BIGINT,
    display_name VARCHAR,

    command VARCHAR NOT NULL,
    full_text TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_command_logs_user_id ON command_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_command_logs_telegram_id ON command_logs (telegram_id);
CREATE INDEX IF NOT EXISTS ix_command_logs_command ON command_logs (command);
CREATE INDEX IF NOT EXISTS ix_command_logs_created_at ON command_logs (created_at);


CREATE TABLE IF NOT EXISTS world_cup_facts (
    id SERIAL PRIMARY KEY,

    external_id VARCHAR UNIQUE,

    title VARCHAR NOT NULL,
    fact_text TEXT NOT NULL,

    category VARCHAR,
    tournament_year INTEGER,

    source_text VARCHAR,
    source_url TEXT,

    spicy_comment TEXT,

    needs_verification BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_world_cup_facts_category ON world_cup_facts (category);
CREATE INDEX IF NOT EXISTS ix_world_cup_facts_tournament_year ON world_cup_facts (tournament_year);
CREATE INDEX IF NOT EXISTS ix_world_cup_facts_is_active ON world_cup_facts (is_active);


CREATE TABLE IF NOT EXISTS fact_delivery_logs (
    id SERIAL PRIMARY KEY,

    fact_id INTEGER NOT NULL REFERENCES world_cup_facts(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    telegram_id BIGINT,
    chat_id BIGINT,

    delivery_type VARCHAR NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_fact_delivery_logs_fact_id ON fact_delivery_logs (fact_id);
CREATE INDEX IF NOT EXISTS ix_fact_delivery_logs_user_id ON fact_delivery_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_fact_delivery_logs_telegram_id ON fact_delivery_logs (telegram_id);
CREATE INDEX IF NOT EXISTS ix_fact_delivery_logs_chat_id ON fact_delivery_logs (chat_id);
CREATE INDEX IF NOT EXISTS ix_fact_delivery_logs_sent_at ON fact_delivery_logs (sent_at);


CREATE TABLE IF NOT EXISTS quiz_questions (
    id SERIAL PRIMARY KEY,

    external_id VARCHAR UNIQUE,

    question_text TEXT NOT NULL,

    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,

    correct_option VARCHAR NOT NULL,

    explanation TEXT,

    category VARCHAR,
    tournament_year INTEGER,

    source_fact_id INTEGER REFERENCES world_cup_facts(id) ON DELETE SET NULL,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_quiz_questions_category ON quiz_questions (category);
CREATE INDEX IF NOT EXISTS ix_quiz_questions_tournament_year ON quiz_questions (tournament_year);
CREATE INDEX IF NOT EXISTS ix_quiz_questions_is_active ON quiz_questions (is_active);
CREATE INDEX IF NOT EXISTS ix_quiz_questions_source_fact_id ON quiz_questions (source_fact_id);


CREATE TABLE IF NOT EXISTS quiz_answers (
    id SERIAL PRIMARY KEY,

    quiz_question_id INTEGER NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    telegram_id BIGINT,

    selected_option VARCHAR NOT NULL,
    is_correct BOOLEAN NOT NULL,

    answered_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_quiz_answers_question_id ON quiz_answers (quiz_question_id);
CREATE INDEX IF NOT EXISTS ix_quiz_answers_user_id ON quiz_answers (user_id);
CREATE INDEX IF NOT EXISTS ix_quiz_answers_telegram_id ON quiz_answers (telegram_id);
CREATE INDEX IF NOT EXISTS ix_quiz_answers_answered_at ON quiz_answers (answered_at);


CREATE TABLE IF NOT EXISTS historical_archive_cards (
    id SERIAL PRIMARY KEY,

    external_id VARCHAR NOT NULL UNIQUE,

    title VARCHAR NOT NULL,
    text TEXT NOT NULL,

    card_type VARCHAR,
    tournament_code VARCHAR,

    related_name VARCHAR,
    related_telegram_id BIGINT,

    is_public BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_historical_archive_cards_card_type ON historical_archive_cards (card_type);
CREATE INDEX IF NOT EXISTS ix_historical_archive_cards_tournament_code ON historical_archive_cards (tournament_code);
CREATE INDEX IF NOT EXISTS ix_historical_archive_cards_related_telegram_id ON historical_archive_cards (related_telegram_id);
CREATE INDEX IF NOT EXISTS ix_historical_archive_cards_is_active ON historical_archive_cards (is_active);


CREATE TABLE IF NOT EXISTS historical_archive_delivery_logs (
    id SERIAL PRIMARY KEY,

    archive_card_id INTEGER NOT NULL REFERENCES historical_archive_cards(id) ON DELETE CASCADE,

    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    telegram_id BIGINT,
    chat_id BIGINT,

    delivery_type VARCHAR NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_archive_delivery_logs_card_id ON historical_archive_delivery_logs (archive_card_id);
CREATE INDEX IF NOT EXISTS ix_archive_delivery_logs_user_id ON historical_archive_delivery_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_archive_delivery_logs_telegram_id ON historical_archive_delivery_logs (telegram_id);
CREATE INDEX IF NOT EXISTS ix_archive_delivery_logs_chat_id ON historical_archive_delivery_logs (chat_id);
CREATE INDEX IF NOT EXISTS ix_archive_delivery_logs_sent_at ON historical_archive_delivery_logs (sent_at);


CREATE TABLE IF NOT EXISTS group_quiz_sessions (
    id SERIAL PRIMARY KEY,

    chat_id BIGINT NOT NULL,
    quiz_question_id INTEGER NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,

    status VARCHAR NOT NULL DEFAULT 'open',

    started_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,

    message_id BIGINT,

    category VARCHAR
);

CREATE INDEX IF NOT EXISTS ix_group_quiz_sessions_chat_id ON group_quiz_sessions (chat_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_sessions_question_id ON group_quiz_sessions (quiz_question_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_sessions_status ON group_quiz_sessions (status);
CREATE INDEX IF NOT EXISTS ix_group_quiz_sessions_started_at ON group_quiz_sessions (started_at);


CREATE TABLE IF NOT EXISTS group_quiz_answers (
    id SERIAL PRIMARY KEY,

    session_id INTEGER NOT NULL REFERENCES group_quiz_sessions(id) ON DELETE CASCADE,
    quiz_question_id INTEGER NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,

    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    telegram_id BIGINT,
    display_name VARCHAR,

    selected_option VARCHAR NOT NULL,
    is_correct BOOLEAN NOT NULL,

    answered_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_group_quiz_session_user UNIQUE (session_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_group_quiz_answers_session_id ON group_quiz_answers (session_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_answers_question_id ON group_quiz_answers (quiz_question_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_answers_user_id ON group_quiz_answers (user_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_answers_telegram_id ON group_quiz_answers (telegram_id);
CREATE INDEX IF NOT EXISTS ix_group_quiz_answers_answered_at ON group_quiz_answers (answered_at);


-- Timed group quiz battle series
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
