-- Migration: Default trading mode to 'live' instead of 'paper'
-- All existing users with 'paper' mode get switched to 'live'
-- Paper trading UI has been removed; live is now the default.

UPDATE users SET trading_mode = 'live' WHERE trading_mode = 'paper';
ALTER TABLE users ALTER COLUMN trading_mode SET DEFAULT 'live';
