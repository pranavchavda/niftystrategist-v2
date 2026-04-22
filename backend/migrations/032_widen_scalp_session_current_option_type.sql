-- Widen scalp_sessions.current_option_type so equity sessions can persist state.
--
-- Mirror fix for migration 031. The logs-table column was widened to VARCHAR(10)
-- yesterday, but the same-named column on scalp_sessions was missed. Equity
-- sessions write "LONG"/"SHORT" into current_option_type when entering a
-- position, and Postgres rejects the UPDATE with
-- "value too long for type character varying(2)". The scalp_session.py
-- persist_state handler logs ERROR and returns — in-memory runtime is correct
-- but the DB row stays at state=IDLE, current_option_type=NULL.
--
-- If the daemon restarts before the position closes, it reloads IDLE from DB
-- and orphans the live broker position.
--
-- Observed 2026-04-22: Adaniensol session #19 entered SHORT @ ₹1284.55 after
-- the candle-buffer saturation fix (commit 5aa86e3) unblocked flip detection.
-- persist_state failed with VARCHAR(2) error; exit at 09:32:00 worked because
-- in-memory runtime carried the position through.

ALTER TABLE scalp_sessions ALTER COLUMN current_option_type TYPE VARCHAR(10);
