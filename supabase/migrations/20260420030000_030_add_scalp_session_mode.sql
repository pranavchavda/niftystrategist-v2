-- Migration 030: session_mode + equity fields on scalp_sessions
-- Generalizes the manager from options-only scalping to also handle
-- equity intraday and equity swing (multi-day delivery) sessions.
--   session_mode: 'options_scalp' (default), 'equity_intraday', 'equity_swing'
--   quantity: equity share count (replaces lots×lot_size for equity modes)
-- Equity sessions store the equity instrument key in the existing
-- underlying_instrument_token column, so no new symbol column is needed.
-- Date: 2026-04-20

ALTER TABLE scalp_sessions
    ADD COLUMN IF NOT EXISTS session_mode VARCHAR(20) NOT NULL DEFAULT 'options_scalp',
    ADD COLUMN IF NOT EXISTS quantity INTEGER;

CREATE INDEX IF NOT EXISTS idx_scalp_sessions_mode ON scalp_sessions(session_mode);
