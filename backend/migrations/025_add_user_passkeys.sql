-- Migration: Add user_passkeys table for WebAuthn passkey authentication
-- Date: 2026-04-12

CREATE TABLE IF NOT EXISTS user_passkeys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    credential_id BYTEA NOT NULL UNIQUE,
    public_key BYTEA NOT NULL,
    sign_count INTEGER NOT NULL DEFAULT 0,
    device_name VARCHAR(255),
    transports JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    last_used_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_user_passkeys_user_id ON user_passkeys(user_id);
CREATE INDEX IF NOT EXISTS ix_user_passkeys_credential_id ON user_passkeys(credential_id);
