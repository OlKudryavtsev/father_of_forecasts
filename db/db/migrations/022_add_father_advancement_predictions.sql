-- v2.8.72: Father Predictions gets the same optional playoff advancement pick as users.

ALTER TABLE father_match_predictions
    ADD COLUMN IF NOT EXISTS advancement_bet_enabled BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE father_match_predictions
    ADD COLUMN IF NOT EXISTS predicted_advancing_side VARCHAR(8) NULL;

-- Backfill legacy Father forecasts only where a decisive 90-minute forecast gives
-- a clear advancing side. Draw forecasts deliberately remain without a pick.
UPDATE father_match_predictions AS father
SET
    advancement_bet_enabled = TRUE,
    predicted_advancing_side = CASE
        WHEN father.pred_home > father.pred_away THEN 'home'
        WHEN father.pred_away > father.pred_home THEN 'away'
        ELSE NULL
    END,
    updated_at = NOW()
FROM matches AS match
WHERE match.id = father.match_id
  AND match.stage IN ('round_of_32', 'round_of_16', 'quarterfinal', 'semifinal', 'third_place', 'final')
  AND father.pred_home <> father.pred_away
  AND COALESCE(father.advancement_bet_enabled, FALSE) = FALSE
  AND father.predicted_advancing_side IS NULL;

ALTER TABLE father_match_predictions
    DROP CONSTRAINT IF EXISTS chk_father_predicted_advancing_side;

ALTER TABLE father_match_predictions
    ADD CONSTRAINT chk_father_predicted_advancing_side
    CHECK (predicted_advancing_side IS NULL OR predicted_advancing_side IN ('home', 'away'));
