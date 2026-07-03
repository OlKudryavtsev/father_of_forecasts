-- v2.8 Web/PWA mode: browser sessions and push subscriptions

CREATE TABLE IF NOT EXISTS web_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR NOT NULL UNIQUE,
    title VARCHAR NULL,
    user_agent TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_used_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_web_sessions_user_id ON web_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_web_sessions_token_hash ON web_sessions(token_hash);
CREATE INDEX IF NOT EXISTS ix_web_sessions_is_active ON web_sessions(is_active);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    user_agent TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    last_success_at TIMESTAMPTZ NULL,
    last_error TEXT NULL,
    CONSTRAINT uq_push_subscription_endpoint UNIQUE (endpoint)
);

CREATE INDEX IF NOT EXISTS ix_push_subscriptions_user_id ON push_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS ix_push_subscriptions_is_active ON push_subscriptions(is_active);
