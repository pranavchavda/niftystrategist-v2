-- Add TOTP auto-login credentials for Upstox token refresh
-- All credential columns are encrypted at application level (Fernet)
-- Upstox TOTP login requires: mobile, PIN, and TOTP secret (no password)

ALTER TABLE users ADD COLUMN IF NOT EXISTS upstox_mobile TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS upstox_pin TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS upstox_totp_secret TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS upstox_totp_last_failed_at TIMESTAMP;

-- Drop password column if it was added by a previous version of this migration
ALTER TABLE users DROP COLUMN IF EXISTS upstox_password;
