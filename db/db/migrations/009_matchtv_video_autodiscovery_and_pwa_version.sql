-- Adds Match TV video autodiscovery metadata and PWA update support.
-- Safe to run after migration 008.

BEGIN;

ALTER TABLE match_videos
    ADD COLUMN IF NOT EXISTS discovery_status VARCHAR NOT NULL DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS confidence INTEGER DEFAULT 100,
    ADD COLUMN IF NOT EXISTS external_id VARCHAR,
    ADD COLUMN IF NOT EXISTS discovered_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_match_videos_discovery_status ON match_videos (discovery_status);
CREATE INDEX IF NOT EXISTS ix_match_videos_external_id ON match_videos (external_id);

COMMIT;
