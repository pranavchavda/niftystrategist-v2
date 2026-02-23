-- Add TOTP auto-login credentials for Upstox token refresh
-- All credential columns are encrypted at application level (Fernet)

ALTER TABLE users ADD COLUMN IF NOT EXISTS upstox_mobile TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS upstox_password TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS upstox_pin TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS upstox_totp_secret TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS upstox_totp_last_failed_at TIMESTAMP;
