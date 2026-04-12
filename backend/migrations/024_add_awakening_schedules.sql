-- Migration: Add recurring awakening schedules and daily trading threads
-- Description: User-configurable recurring awakenings with trading mandates and daily thread lifecycle
-- Date: 2026-04-11

-- ============================================================================
-- 1. Awakening schedules — per-user recurring awakening configuration
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_awakening_schedules (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Schedule identity
    name VARCHAR(100) NOT NULL,           -- e.g., "Morning Scan", "Mid-Day Check"
    enabled BOOLEAN NOT NULL DEFAULT true,

    -- Timing (stored as IST hours/minutes, converted to UTC at scheduler load)
    cron_hour INTEGER NOT NULL,           -- IST hour (0-23)
    cron_minute INTEGER NOT NULL DEFAULT 0,  -- IST minute (0-59)
    weekdays_only BOOLEAN NOT NULL DEFAULT true,   -- Skip weekends (Sat/Sun)

    -- What to do
    prompt TEXT NOT NULL,                 -- Task prompt for the orchestrator

    -- Execution config
    timeout_seconds INTEGER NOT NULL DEFAULT 600,
    model_override VARCHAR(100),          -- Optional: override user's preferred model

    -- Tracking
    last_run_at TIMESTAMP,
    last_error TEXT,
    run_count INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),

    UNIQUE(user_id, name)
);

CREATE INDEX idx_awakening_schedules_user ON user_awakening_schedules(user_id);
CREATE INDEX idx_awakening_schedules_enabled ON user_awakening_schedules(enabled);

-- ============================================================================
-- 2. Trading mandate — per-user risk parameters for autonomous trading
-- ============================================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS trading_mandate JSONB;

COMMENT ON COLUMN users.trading_mandate IS 'Standing trading mandate for autonomous awakenings. JSON: {risk_per_trade, daily_loss_cap, allowed_instruments, cutoff_time, auto_squareoff_time, approved_at}';

-- ============================================================================
-- 3. Daily thread tracking on conversations
-- ============================================================================

ALTER TABLE conversations ADD COLUMN IF NOT EXISTS is_daily_thread BOOLEAN DEFAULT false;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS daily_thread_date DATE;

-- Only one daily thread per user per date
CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_thread_user_date
    ON conversations(user_id, daily_thread_date) WHERE is_daily_thread = true;
