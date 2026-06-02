-- 046_add_broker_discriminator.sql
-- Phase C backbone of the broker-agnostic account layer.
--
-- Splits "broker" into two concepts:
--   * ACTIVE broker  — users.broker, ONE at a time. Governs where NS places
--     orders, the agent's account context, and monitor/scalp order routing
--     (SEBI static-IP + reconciliation safety). Defaults to 'upstox' so every
--     existing user is unchanged.
--   * CONNECTED brokers — broker_accounts rows (+ the legacy upstox_* columns on
--     users), MANY at once. What the Dashboard reads & consolidates so a user
--     sees a single picture across every broker they've linked.
--
-- ADDITIVE + backward-compatible: old application code (which doesn't reference
-- users.broker or broker_accounts) keeps working after this is applied, so this
-- can be applied to the shared Supabase BEFORE the Phase C code deploys.
--
-- NS conventions: TIMESTAMP WITHOUT TIME ZONE, naive UTC (utc_now()/datetime.utcnow()).

-- Active trading broker discriminator.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS broker VARCHAR(20) NOT NULL DEFAULT 'upstox';

-- Generic per-broker credential / session store. Every NON-Upstox broker backs
-- onto this (Upstox keeps using its dedicated upstox_* columns via
-- UpstoxCredentialStore — no token migration, lowest risk).
--
--   credentials  — Fernet-encrypted-per-value JSON of the broker's credential
--                  fields (api_key, mpin, totp_key, …). Driven by the broker's
--                  login_descriptor()/credential_fields().
--   session      — broker-minted session blob. Kotak Neo is multi-field
--                  (edit_token / edit_sid / serverId / base_url / …) with daily
--                  expiry, so this is JSON, not a single token string.
--   status       — 'connected' | 'disconnected' | 'error' (for the Dashboard's
--                  per-broker connection state).
CREATE TABLE IF NOT EXISTS broker_accounts (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    broker          VARCHAR(20) NOT NULL,
    credentials     JSONB NOT NULL DEFAULT '{}'::jsonb,   -- encrypted-per-value
    session         JSONB,                                -- broker-minted session (Kotak: multi-field)
    token_expiry    TIMESTAMP,                            -- naive UTC
    broker_user_id  TEXT,                                 -- broker's account identifier (e.g. Kotak UCC)
    status          VARCHAR(20) NOT NULL DEFAULT 'connected',
    created_at      TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at      TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    UNIQUE (user_id, broker)
);

CREATE INDEX IF NOT EXISTS idx_broker_accounts_user ON broker_accounts(user_id);
