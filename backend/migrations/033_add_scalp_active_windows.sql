-- 033_add_scalp_active_windows.sql
-- Optional time-window gating for scalp sessions. NULL = always active
-- (current behavior). When set, scalp engine blocks new entries outside
-- any window. Existing positions still managed (SL/target/trail/squareoff
-- continue to evaluate).
--
-- Format: JSON array of {"start": "HH:MM", "end": "HH:MM"} strings, IST.
--   Example: [{"start": "09:15", "end": "10:30"}, {"start": "13:30", "end": "15:00"}]
--
-- Why: 2026-04-28 chop day showed mid-day sideways markets eat round-trip
-- charges. Letting users gate entries to high-momentum windows reduces
-- "death by a thousand cuts" trades.

ALTER TABLE scalp_sessions
ADD COLUMN active_windows JSON;
