-- v2.8.21 — League scoring start
-- Добавляет точку старта подсчета очков для лиг.
-- Системная лига «Отец прогнозов» считается с начала турнира.
-- Частные лиги считаются с момента создания, если старт еще не задан.

BEGIN;

ALTER TABLE leagues
    ADD COLUMN IF NOT EXISTS scoring_start_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_leagues_scoring_start_at ON leagues (scoring_start_at);

UPDATE leagues
SET scoring_start_at = TIMESTAMPTZ '2026-06-11 19:00:00+00'
WHERE name = 'Отец прогнозов'
  AND (scoring_start_at IS NULL OR scoring_start_at > TIMESTAMPTZ '2026-06-11 19:00:00+00');

UPDATE leagues
SET scoring_start_at = COALESCE(created_at, NOW())
WHERE name <> 'Отец прогнозов'
  AND scoring_start_at IS NULL;


UPDATE league_members lm
SET joined_at = TIMESTAMPTZ '2026-06-11 19:00:00+00'
FROM leagues l
WHERE lm.league_id = l.id
  AND l.name = 'Отец прогнозов'
  AND (lm.joined_at IS NULL OR lm.joined_at > TIMESTAMPTZ '2026-06-11 19:00:00+00');

COMMIT;
