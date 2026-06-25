-- v2.8.55 — gamification, personal delivery tone and durable achievement levels.
-- Apply once in Railway PostgreSQL before deploying the application.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS personal_humor_mode VARCHAR(24) NOT NULL DEFAULT 'ruthless';

ALTER TABLE leagues
    ADD COLUMN IF NOT EXISTS humor_mode VARCHAR(24) NOT NULL DEFAULT 'ruthless';

ALTER TABLE leagues
    ADD COLUMN IF NOT EXISTS gamification_started_at TIMESTAMPTZ;

-- Existing tournament results stay visible in ratings/titles. Achievements begin
-- from the moment this migration is applied, so users do not instantly receive
-- the whole new collection from historical matches.
UPDATE leagues
SET gamification_started_at = CURRENT_TIMESTAMP
WHERE gamification_started_at IS NULL;

ALTER TABLE leagues
    ALTER COLUMN gamification_started_at SET DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS user_achievements (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    achievement_code VARCHAR(64) NOT NULL,
    level INTEGER NOT NULL DEFAULT 0,
    earned_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_league_achievement UNIQUE (user_id, league_id, achievement_code)
);

CREATE INDEX IF NOT EXISTS ix_user_achievements_user_id ON user_achievements(user_id);
CREATE INDEX IF NOT EXISTS ix_user_achievements_league_id ON user_achievements(league_id);
CREATE INDEX IF NOT EXISTS ix_user_achievements_code ON user_achievements(achievement_code);
