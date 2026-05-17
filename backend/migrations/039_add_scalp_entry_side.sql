-- 039_add_scalp_entry_side.sql
-- Optional direction gate for scalp signal sessions. 'both' = current
-- behavior (enter on either a bullish or bearish signal flip). 'long'
-- restricts entries to bullish flips only (CE for options, LONG for
-- equity); 'short' restricts to bearish flips only (PE / SHORT).
--
-- Exit handling is unaffected — a held position still exits on a reversal
-- flip regardless of entry_side. The gate only blocks new entries.
--
-- Why: users running directional bias (e.g. only buying calls in an
-- uptrend) previously had to work around the both-sided default with
-- separate strategy templates. One flag covers options + equity modes.
--
-- equity_swing cannot short (no SLBM in delivery), so the API rejects
-- entry_side='short' for that mode.

ALTER TABLE scalp_sessions
ADD COLUMN entry_side VARCHAR(5) NOT NULL DEFAULT 'both';
