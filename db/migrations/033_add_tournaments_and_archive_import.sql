CREATE TABLE IF NOT EXISTS tournaments (
    code VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    short_name VARCHAR,
    tournament_type VARCHAR NOT NULL DEFAULT 'custom',
    year INTEGER,
    host VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'draft',
    starts_at TIMESTAMP WITH TIME ZONE,
    ends_at TIMESTAMP WITH TIME ZONE,
    prediction_deadline TIMESTAMP WITH TIME ZONE,
    has_third_place_match BOOLEAN NOT NULL DEFAULT TRUE,
    scoring_rules JSON NOT NULL DEFAULT '{}',
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    display_order INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_tournaments_status ON tournaments(status);
CREATE INDEX IF NOT EXISTS ix_tournaments_is_default ON tournaments(is_default);
CREATE INDEX IF NOT EXISTS ix_tournaments_display_order ON tournaments(display_order);

INSERT INTO tournaments (
    code, name, short_name, tournament_type, year, host, status,
    starts_at, ends_at, prediction_deadline, has_third_place_match,
    scoring_rules, is_default, display_order
)
VALUES (
    'wc2026', 'ЧМ-2026', 'ЧМ-2026', 'world_cup', 2026, 'США · Мексика · Канада', 'finished',
    '2026-06-11T22:00:00+03:00', NULL, '2026-06-11T22:00:00+03:00', TRUE,
    '{"exact_score":3,"outcome":1,"advancement_correct":1,"advancement_wrong":-1,"champion":15,"runner_up":10,"third_place":5,"top_scorer":15}',
    TRUE, 10
)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    short_name = EXCLUDED.short_name,
    tournament_type = EXCLUDED.tournament_type,
    year = EXCLUDED.year,
    host = EXCLUDED.host,
    starts_at = COALESCE(tournaments.starts_at, EXCLUDED.starts_at),
    prediction_deadline = COALESCE(tournaments.prediction_deadline, EXCLUDED.prediction_deadline),
    has_third_place_match = EXCLUDED.has_third_place_match,
    scoring_rules = EXCLUDED.scoring_rules,
    is_default = EXCLUDED.is_default,
    display_order = EXCLUDED.display_order,
    updated_at = now();

ALTER TABLE league_win_model_cache
    ADD COLUMN IF NOT EXISTS tournament_code VARCHAR NOT NULL DEFAULT 'wc2026';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'league_win_model_cache_league_id_key'
    ) THEN
        ALTER TABLE league_win_model_cache DROP CONSTRAINT league_win_model_cache_league_id_key;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_league_win_model_cache_league_tournament'
    ) THEN
        NULL;
    ELSE
        ALTER TABLE league_win_model_cache
            ADD CONSTRAINT uq_league_win_model_cache_league_tournament UNIQUE (league_id, tournament_code);
    END IF;
END $$;
