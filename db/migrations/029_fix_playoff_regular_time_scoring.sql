-- v3.4.1 — playoff score/outcome points are calculated from regular time only.
-- Apply after migrations 001–028.

-- ``score_home`` / ``score_away`` retain the score after 90 minutes because
-- those are the values used by score_match_prediction().  Keep a separate
-- final score so extra-time results remain visible in the UI and Telegram.
ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS final_score_home INTEGER,
    ADD COLUMN IF NOT EXISTS final_score_away INTEGER;

COMMENT ON COLUMN matches.score_home IS
    'Score after regular time (90 minutes); used for exact-score and outcome prediction points.';
COMMENT ON COLUMN matches.score_away IS
    'Score after regular time (90 minutes); used for exact-score and outcome prediction points.';
COMMENT ON COLUMN matches.final_score_home IS
    'Final score after extra time, if different from regular time. Penalty shoot-out winner is winner_side.';
COMMENT ON COLUMN matches.final_score_away IS
    'Final score after extra time, if different from regular time. Penalty shoot-out winner is winner_side.';

-- All historical ordinary matches have the same score after 90 minutes and at
-- the end of the match. Preserve that display value before handling AET rows.
UPDATE matches
SET
    final_score_home = COALESCE(final_score_home, score_home),
    final_score_away = COALESCE(final_score_away, score_away)
WHERE final_score_home IS NULL OR final_score_away IS NULL;

-- Correct the already synced Belgium — Senegal Round-of-32 fixture. It was
-- 2:2 after 90 minutes and Belgium won 3:2 after extra time. This block is
-- deliberately idempotent and accepts Russian or API-English team names.
WITH corrected_match AS (
    UPDATE matches
    SET
        score_home = 2,
        score_away = 2,
        final_score_home = 3,
        final_score_away = 2,
        winner_side = 'home',
        is_finished = TRUE,
        status_short = 'AET'
    WHERE tournament_code = 'wc2026'
      AND lower(home_team) IN ('бельгия', 'belgium')
      AND lower(away_team) IN ('сенегал', 'senegal')
      AND COALESCE(final_score_home, score_home) = 3
      AND COALESCE(final_score_away, score_away) = 2
    RETURNING id, score_home, score_away, winner_side
), scored AS (
    SELECT
        p.id,
        CASE
            WHEN p.pred_home = m.score_home AND p.pred_away = m.score_away THEN 3
            WHEN (p.pred_home > p.pred_away AND m.score_home > m.score_away)
              OR (p.pred_home < p.pred_away AND m.score_home < m.score_away)
              OR (p.pred_home = p.pred_away AND m.score_home = m.score_away)
            THEN 1
            ELSE 0
        END AS score_points,
        CASE
            WHEN (COALESCE(p.advancement_bet_enabled, FALSE) OR p.predicted_advancing_side IN ('home', 'away'))
             AND p.predicted_advancing_side IN ('home', 'away')
             AND m.winner_side IN ('home', 'away')
            THEN CASE WHEN p.predicted_advancing_side = m.winner_side THEN 1 ELSE -1 END
            ELSE 0
        END AS advancement_points
    FROM predictions p
    JOIN corrected_match m ON m.id = p.match_id
)
UPDATE predictions p
SET
    score_points = s.score_points,
    advancement_points = s.advancement_points,
    points = s.score_points + s.advancement_points,
    updated_at = NOW()
FROM scored s
WHERE p.id = s.id;
