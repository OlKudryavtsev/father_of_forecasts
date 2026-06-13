-- Adds notification tracking for newly discovered match videos.
-- Safe to run after migration 009.

BEGIN;

ALTER TABLE match_videos
    ADD COLUMN IF NOT EXISTS notification_sent_at TIMESTAMPTZ;

COMMIT;
