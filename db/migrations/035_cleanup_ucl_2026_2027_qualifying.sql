-- v3.9.1: remove UEFA Champions League 2026/27 qualifying/play-off qualification fixtures
-- The authoritative cleanup is performed by scripts/sync_ucl_2026_2027.py because it also
-- normalizes the official league-phase kickoff dates and Russian club names.
-- This migration is a safe DB-level cleanup for the already imported non-league fixtures.

DELETE FROM matches
WHERE tournament_code = 'ucl_2026_2027'
  AND (
    lower(coalesce(stage, '')) IN ('qualifying', 'playoff')
    OR lower(coalesce(match_round, '')) LIKE '%qualif%'
    OR lower(coalesce(match_round, '')) LIKE '%play-off%'
    OR lower(coalesce(match_round, '')) LIKE '%playoff%'
    OR lower(coalesce(api_league_round, '')) LIKE '%qualif%'
    OR lower(coalesce(api_league_round, '')) LIKE '%play-off%'
    OR lower(coalesce(api_league_round, '')) LIKE '%playoff%'
    OR starts_at < TIMESTAMPTZ '2026-09-08 00:00:00+00'
  );

UPDATE tournaments
SET starts_at = (
        SELECT min(starts_at)
        FROM matches
        WHERE tournament_code = 'ucl_2026_2027'
    ),
    prediction_deadline = (
        SELECT min(starts_at)
        FROM matches
        WHERE tournament_code = 'ucl_2026_2027'
    )
WHERE code = 'ucl_2026_2027'
  AND EXISTS (
      SELECT 1
      FROM matches
      WHERE tournament_code = 'ucl_2026_2027'
  );
