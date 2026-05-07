-- Migration 035: Add backtest_jobs table
-- Backtest runs converted from blocking HTTP calls to background jobs with
-- SSE-streamed progress. Each job persists across server restarts; partial
-- progress and full result are stored as JSONB for easy reload into the UI.
-- Date: 2026-05-06

CREATE TABLE IF NOT EXISTS backtest_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- What kind of backtest. One of: equity, fno, scalp.
    -- The handler dispatches on this; engines are not interchangeable.
    kind VARCHAR(20) NOT NULL,

    -- Free-form name the user gave the run (defaults to "<kind> <symbol> <timestamp>"
    -- if blank). Shown in the run-history list.
    name VARCHAR(200) NOT NULL DEFAULT '',

    -- The full request body as the engine received it (symbol, days, interval,
    -- params, indicator config, etc.). Frozen so a re-run uses the same inputs.
    config JSONB NOT NULL,

    -- queued | running | completed | failed | cancelled
    status VARCHAR(15) NOT NULL DEFAULT 'queued',

    -- Bars processed / total bars (when known). Reported by the engine via
    -- progress callback every N bars. Either may be NULL until candles fetch
    -- completes.
    progress_done INTEGER,
    progress_total INTEGER,

    -- Free-form progress message ("fetching candles", "evaluating bars", etc.)
    -- Surfaces stages that aren't well represented by bar count.
    progress_message VARCHAR(200),

    -- Final result (same shape today's endpoints return). NULL until status =
    -- completed. Stored as JSONB so the UI can pull historic runs straight
    -- back into the result panel.
    result JSONB,

    -- On failure, the message and (optionally) traceback.
    error_message TEXT,
    error_traceback TEXT,

    -- Lifecycle timestamps. created_at = enqueue, started_at = worker pick-up,
    -- completed_at = terminal status reached. Use TIMESTAMP WITHOUT TIME ZONE
    -- consistent with the rest of the codebase (Supabase).
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    started_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE,

    -- Soft cancel: when the user hits cancel, we flip this. The engine's
    -- cancel-check callback reads it and exits cleanly. Daemon-style hard
    -- termination isn't needed since each job runs in a worker thread that
    -- voluntarily yields between bars.
    cancel_requested BOOLEAN NOT NULL DEFAULT false
);

-- List a user's run history newest first.
CREATE INDEX IF NOT EXISTS idx_backtest_jobs_user_created
    ON backtest_jobs(user_id, created_at DESC);

-- Worker uses this to pick up the next queued job (status='queued' is the hot
-- path; the partial index keeps it tiny).
CREATE INDEX IF NOT EXISTS idx_backtest_jobs_queued
    ON backtest_jobs(created_at)
    WHERE status = 'queued';
