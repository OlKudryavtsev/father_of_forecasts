-- v2.8.16 — User access requests and admin approval
-- Adds pending access-request metadata used by /start approval flow.

BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS access_requested_at TIMESTAMPTZ;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS pending_invite_code VARCHAR;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS rejected_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_users_pending_invite_code ON users (pending_invite_code);

UPDATE users
SET access_requested_at = COALESCE(access_requested_at, created_at, NOW())
WHERE access_requested_at IS NULL;

-- Existing users stay approved. New users created after this release are pending by application logic.
UPDATE users
SET access_status = 'approved',
    approved_at = COALESCE(approved_at, NOW())
WHERE access_status IS NULL;

COMMIT;
