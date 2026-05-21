-- Per-user Telegram integration.
-- Each user creates their own bot via BotFather and pastes the token here.
-- The bot token is Fernet-encrypted at the application level (same ENCRYPTION_KEY
-- used for Upstox creds). See docs/plans/2026-05-20-telegram-integration.md.

ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_bot_token TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_bot_username VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_pending_chat_id BIGINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_paired_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notification_prefs JSONB NOT NULL DEFAULT '{}'::jsonb;
