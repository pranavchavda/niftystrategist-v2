-- Update default squareoff_time on scalp_sessions to 15:09 IST.
-- Upstox closes intraday positions at ~15:10 for retail accounts
-- (auto-squareoff window is 15:15+ but execution starts earlier),
-- so we must place our exit before 15:10 to avoid Upstox's auto-squareoff fee.
-- Supersedes prior 15:15 -> 15:14 migration (which Upstox still beat).

ALTER TABLE scalp_sessions
    ALTER COLUMN squareoff_time SET DEFAULT '15:09';

UPDATE scalp_sessions
SET squareoff_time = '15:09'
WHERE squareoff_time IN ('15:14', '15:15');
