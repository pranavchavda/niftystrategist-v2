-- Migration 027: Armed trailing stop fields on scalp_sessions
-- Adds:
--   trail_arm_points — points of profit required before the trail activates
--                      (NULL = arm immediately, same as pre-027 behavior)
--   trail_points     — absolute trail distance in premium points. Preferred
--                      over trail_percent when both are set. Keeps
--                      trail_percent around for back-compat.
-- Date: 2026-04-20

ALTER TABLE scalp_sessions
    ADD COLUMN IF NOT EXISTS trail_arm_points REAL,
    ADD COLUMN IF NOT EXISTS trail_points REAL;
