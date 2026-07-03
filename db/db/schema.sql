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
    access_status VARCHAR NOT NULL DEFAULT 'approved',
    approved_at TIMESTAMPTZ,
    approved_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_telegram_id ON users (telegram_id);
CREATE INDEX IF NOT EXISTS ix_users_access_status ON users (access_status);


CREATE TABLE IF NOT EXISTS leagues (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    description TEXT,
    league_type VARCHAR NOT NULL DEFAULT 'system',
    owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    invite_code VARCHAR UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    scoring_start_at TIMESTAMPTZ,
    chat_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_leagues_name ON leagues (name);
CREATE INDEX IF NOT EXISTS ix_leagues_league_type ON leagues (league_type);
CREATE INDEX IF NOT EXISTS ix_leagues_invite_code ON leagues (invite_code);
CREATE INDEX IF NOT EXISTS ix_leagues_is_active ON leagues (is_active);
CREATE INDEX IF NOT EXISTS ix_leagues_scoring_start_at ON leagues (scoring_start_at);


CREATE TABLE IF NOT EXISTS league_members (
    id SERIAL PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR NOT NULL DEFAULT 'member',
    status VARCHAR NOT NULL DEFAULT 'active',
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_league_members_league_user UNIQUE (league_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_league_members_league_id ON league_members (league_id);
CREATE INDEX IF NOT EXISTS ix_league_members_user_id ON league_members (user_id);
CREATE INDEX IF NOT EXISTS ix_league_members_role ON league_members (role);
CREATE INDEX IF NOT EXISTS ix_league_members_status ON league_members (status);


CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    tournament_code VARCHAR NOT NULL DEFAULT 'wc2026',

    home_team VARCHAR NOT NULL,
    away_team VARCHAR NOT NULL,

    stage VARCHAR NOT NULL DEFAULT 'group',
    starts_at TIMESTAMPTZ NOT NULL,

    -- Score after regular time (90 minutes): used for prediction scoring.
    score_home INTEGER,
    score_away INTEGER,

    -- Final score after extra time, if it differs from the regular-time score.
    final_score_home INTEGER,
    final_score_away INTEGER,
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


-- Product analytics for the Mini App (v2.8.44)
-- Properties are intentionally limited by the application to non-personal values.
CREATE TABLE IF NOT EXISTS analytics_events (
    id SERIAL PRIMARY KEY,

    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id VARCHAR(96) NOT NULL,
    event_name VARCHAR(64) NOT NULL,
    screen VARCHAR(64),
    source VARCHAR(24) NOT NULL DEFAULT 'web',
    app_version VARCHAR(32),
    properties JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_analytics_events_user_id ON analytics_events (user_id);
CREATE INDEX IF NOT EXISTS ix_analytics_events_session_id ON analytics_events (session_id);
CREATE INDEX IF NOT EXISTS ix_analytics_events_event_name ON analytics_events (event_name);
CREATE INDEX IF NOT EXISTS ix_analytics_events_screen ON analytics_events (screen);
CREATE INDEX IF NOT EXISTS ix_analytics_events_source ON analytics_events (source);
CREATE INDEX IF NOT EXISTS ix_analytics_events_created_at ON analytics_events (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_analytics_events_event_created_at ON analytics_events (event_name, created_at DESC);

COMMIT;

-- v3.0.1 — league quiz core
-- v3.0.1 — core of the league-scoped synchronous quiz platform.
-- This is intentionally independent from legacy /quiz tables:
-- quiz_questions, quiz_answers, group_quiz_*.
-- Apply once in Railway PostgreSQL before deploying v3.0.1.

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


-- v3.4.2 quiz readiness extensions (also see migration 030).
ALTER TABLE league_members ADD COLUMN IF NOT EXISTS quiz_roles JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE league_quiz_questions ADD COLUMN IF NOT EXISTS topics JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE league_quiz_questions ADD COLUMN IF NOT EXISTS difficulty VARCHAR(16);
ALTER TABLE league_quiz_questions ADD COLUMN IF NOT EXISTS repeat_after_days INTEGER NOT NULL DEFAULT 14;
ALTER TABLE league_quiz_sessions ADD COLUMN IF NOT EXISTS is_test_run BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE league_quiz_sessions ADD COLUMN IF NOT EXISTS test_host_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE league_quiz_sessions ADD COLUMN IF NOT EXISTS test_chat_id VARCHAR(80);
