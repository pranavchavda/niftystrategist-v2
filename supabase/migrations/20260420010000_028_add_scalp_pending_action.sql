-- Migration 028: pending_action signal for scalp sessions
-- Allows the API (web process) to request an exit-and-disable or
-- exit-and-delete of a HOLDING session; the daemon (separate process)
-- picks it up on the next load_sessions poll, places the SELL, logs
-- 'exit_disabled', then applies the disable or delete.
-- Date: 2026-04-20

ALTER TABLE scalp_sessions
    ADD COLUMN IF NOT EXISTS pending_action VARCHAR(20);
