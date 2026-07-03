-- v2.8.15 — League foundation
-- Добавляет фундамент лиг без изменения UX:
-- 1) таблицы leagues и league_members;
-- 2) статус доступа users.access_status;
-- 3) системную лигу «Отец прогнозов»;
-- 4) всех текущих пользователей переводит в approved и добавляет в лигу.

BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS access_status VARCHAR NOT NULL DEFAULT 'approved';

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS approved_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_users_access_status ON users (access_status);

UPDATE users
SET access_status = 'approved',
    approved_at = COALESCE(approved_at, NOW())
WHERE access_status IS NULL OR access_status <> 'approved';

CREATE TABLE IF NOT EXISTS leagues (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    description TEXT,
    league_type VARCHAR NOT NULL DEFAULT 'system',
    owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    invite_code VARCHAR UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_leagues_name ON leagues (name);
CREATE INDEX IF NOT EXISTS ix_leagues_league_type ON leagues (league_type);
CREATE INDEX IF NOT EXISTS ix_leagues_invite_code ON leagues (invite_code);
CREATE INDEX IF NOT EXISTS ix_leagues_is_active ON leagues (is_active);

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

WITH admin_owner AS (
    SELECT id
    FROM users
    WHERE is_admin = TRUE
    ORDER BY id
    LIMIT 1
), upsert_league AS (
    INSERT INTO leagues (name, description, league_type, owner_user_id, is_active, created_at, updated_at)
    VALUES (
        'Отец прогнозов',
        'Системная лига для текущих участников турнира',
        'system',
        (SELECT id FROM admin_owner),
        TRUE,
        NOW(),
        NOW()
    )
    ON CONFLICT (name) DO UPDATE
    SET description = EXCLUDED.description,
        league_type = EXCLUDED.league_type,
        owner_user_id = COALESCE(leagues.owner_user_id, EXCLUDED.owner_user_id),
        is_active = TRUE,
        updated_at = NOW()
    RETURNING id
)
INSERT INTO league_members (league_id, user_id, role, status, joined_at)
SELECT
    (SELECT id FROM upsert_league),
    u.id,
    CASE WHEN u.is_admin THEN 'admin' ELSE 'member' END,
    'active',
    NOW()
FROM users u
WHERE COALESCE(u.access_status, 'approved') = 'approved'
ON CONFLICT (league_id, user_id) DO UPDATE
SET status = 'active',
    role = CASE
        WHEN EXCLUDED.role = 'admin' THEN 'admin'
        ELSE league_members.role
    END;

COMMIT;
