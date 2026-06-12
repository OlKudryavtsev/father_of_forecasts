-- Add user notification subscriptions and global app settings for Mini App admin panel.
-- Safe to run multiple times.

CREATE TABLE IF NOT EXISTS user_notification_settings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_key VARCHAR NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_user_notification_setting UNIQUE (user_id, notification_key)
);

CREATE INDEX IF NOT EXISTS ix_user_notification_settings_user_id
    ON user_notification_settings(user_id);

CREATE INDEX IF NOT EXISTS ix_user_notification_settings_notification_key
    ON user_notification_settings(notification_key);

CREATE TABLE IF NOT EXISTS app_settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR NOT NULL UNIQUE,
    setting_value TEXT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_app_settings_setting_key
    ON app_settings(setting_key);

INSERT INTO app_settings (setting_key, setting_value)
VALUES
    ('match_reminders_enabled', 'true'),
    ('group_activity_enabled', 'true'),
    ('match_started_enabled', 'true'),
    ('match_finished_enabled', 'true'),
    ('daily_facts_enabled', 'true')
ON CONFLICT (setting_key) DO NOTHING;
