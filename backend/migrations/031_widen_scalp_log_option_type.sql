-- Widen scalp_session_logs.option_type so equity sessions can record direction.
--
-- Original sizing was VARCHAR(2) for CE/PE. Equity sessions (added in migration
-- 030) pass "LONG"/"SHORT" into the same column, which Postgres rejects with
-- "value too long for type character varying(2)". _log_event catches the
-- exception silently, leaving the state mutations persisted but no log row —
-- so UI stats (P&L, wins/losses) look empty even when trades ran end-to-end.
--
-- Observed 2026-04-21: BIOCON session #15 placed SELL+BUY 1000 shares via the
-- order node, trade_count/last_exit_time updated, zero log rows.

ALTER TABLE scalp_session_logs ALTER COLUMN option_type TYPE VARCHAR(10);
