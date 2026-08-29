-- v3.9.0: register UEFA Champions League 2026/27 as a selectable tournament.
-- Fixtures are loaded lazily from API-Football when the tournament is opened.

INSERT INTO tournaments (
    code,
    name,
    short_name,
    tournament_type,
    year,
    host,
    status,
    starts_at,
    prediction_deadline,
    has_third_place_match,
    scoring_rules,
    is_default,
    display_order
)
VALUES (
    'ucl_2026_2027',
    'Лига чемпионов 2026/27',
    'ЛЧ 2026/27',
    'champions_league',
    2026,
    'Европа',
    'active',
    TIMESTAMPTZ '2026-09-15 16:45:00+00',
    TIMESTAMPTZ '2026-09-15 16:45:00+00',
    FALSE,
    '{"exact_score":3,"outcome":1,"advancement_correct":1,"advancement_wrong":-1,"champion":15,"runner_up":10,"third_place":0,"top_scorer":15}'::jsonb,
    FALSE,
    20
)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    short_name = EXCLUDED.short_name,
    tournament_type = EXCLUDED.tournament_type,
    year = EXCLUDED.year,
    host = EXCLUDED.host,
    status = EXCLUDED.status,
    starts_at = COALESCE(tournaments.starts_at, EXCLUDED.starts_at),
    prediction_deadline = COALESCE(tournaments.prediction_deadline, EXCLUDED.prediction_deadline),
    has_third_place_match = EXCLUDED.has_third_place_match,
    scoring_rules = EXCLUDED.scoring_rules,
    is_default = FALSE,
    display_order = EXCLUDED.display_order;
