-- Migration 029: Parametrize scalp session primary/confirm indicators
-- Replaces the hardcoded UT Bot signal with a config-driven primary
-- indicator plus an optional confirm filter. Existing utbot_period and
-- utbot_sensitivity columns stay for back-compat but primary_params is
-- authoritative when set. Backfills primary_params from legacy columns.
-- Date: 2026-04-20

ALTER TABLE scalp_sessions
    ADD COLUMN IF NOT EXISTS primary_indicator VARCHAR(30) NOT NULL DEFAULT 'utbot',
    ADD COLUMN IF NOT EXISTS primary_params JSONB,
    ADD COLUMN IF NOT EXISTS confirm_indicator VARCHAR(30),
    ADD COLUMN IF NOT EXISTS confirm_params JSONB;

UPDATE scalp_sessions
   SET primary_params = jsonb_build_object(
           'period', utbot_period,
           'sensitivity', utbot_sensitivity
       )
 WHERE primary_params IS NULL
   AND primary_indicator = 'utbot';
