-- Adds manually managed official video links for matches.
-- Safe to run on an existing production database.

BEGIN;

CREATE TABLE IF NOT EXISTS match_videos (
    id SERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    source VARCHAR NOT NULL DEFAULT 'matchtv',
    video_type VARCHAR NOT NULL DEFAULT 'highlights',
    title VARCHAR NOT NULL,
    url TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 100,
    available_from TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_match_videos_match_id ON match_videos (match_id);
CREATE INDEX IF NOT EXISTS ix_match_videos_is_active ON match_videos (is_active);
CREATE INDEX IF NOT EXISTS ix_match_videos_match_active_priority ON match_videos (match_id, is_active, priority);

COMMIT;
