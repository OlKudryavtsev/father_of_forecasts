CREATE TABLE IF NOT EXISTS father_match_predictions (
    id SERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    pred_home INTEGER NOT NULL,
    pred_away INTEGER NOT NULL,
    outcome VARCHAR NOT NULL,
    confidence INTEGER NULL,
    source VARCHAR NOT NULL DEFAULT 'ai',
    forecast_text TEXT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_father_match_predictions_match_id
    ON father_match_predictions(match_id);
