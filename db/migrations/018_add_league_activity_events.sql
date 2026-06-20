-- Participant action feed for league screens (Mini App v2.8.37).
CREATE TABLE IF NOT EXISTS league_activity_events (
    id SERIAL PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    actor_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_type VARCHAR NOT NULL,
    event_key VARCHAR NOT NULL UNIQUE,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_league_activity_events_league_created
    ON league_activity_events (league_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_league_activity_events_actor_created
    ON league_activity_events (actor_user_id, created_at DESC);

-- First launch should not show an empty feed. Backfill only stable, meaningful
-- historical facts. Every INSERT has a deterministic key, so the migration may
-- be safely re-run.
INSERT INTO league_activity_events (league_id, actor_user_id, action_type, event_key, payload, created_at)
SELECT
    lm.league_id,
    lm.user_id,
    'member_joined',
    'seed:member_joined:' || lm.league_id || ':' || lm.user_id,
    jsonb_build_object('league_name', l.name),
    COALESCE(lm.joined_at, l.created_at, NOW())
FROM league_members lm
JOIN leagues l ON l.id = lm.league_id
ON CONFLICT (event_key) DO NOTHING;

INSERT INTO league_activity_events (league_id, actor_user_id, action_type, event_key, payload, created_at)
SELECT
    lm.league_id,
    p.user_id,
    'match_prediction_created',
    'seed:prediction:' || lm.league_id || ':' || p.id,
    jsonb_build_object(
        'match_id', m.id,
        'match_label', m.home_team || ' — ' || m.away_team,
        'prediction', p.pred_home::text || ':' || p.pred_away::text
    ),
    COALESCE(p.updated_at, p.created_at, NOW())
FROM predictions p
JOIN league_members lm ON lm.user_id = p.user_id AND lm.status = 'active'
JOIN matches m ON m.id = p.match_id
ON CONFLICT (event_key) DO NOTHING;

INSERT INTO league_activity_events (league_id, actor_user_id, action_type, event_key, payload, created_at)
SELECT
    lm.league_id,
    tp.user_id,
    'tournament_prediction_created',
    'seed:tournament_prediction:' || lm.league_id || ':' || tp.id,
    jsonb_build_object(
        'champion', tp.champion,
        'runner_up', tp.runner_up,
        'third_place', tp.third_place,
        'top_scorer', tp.top_scorer
    ),
    COALESCE(tp.updated_at, tp.created_at, NOW())
FROM tournament_predictions tp
JOIN league_members lm ON lm.user_id = tp.user_id AND lm.status = 'active'
ON CONFLICT (event_key) DO NOTHING;
