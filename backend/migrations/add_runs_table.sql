-- Migration: Add runs table for async run completion
-- Date: 2025-11-09
-- Description: Tracks background agent runs that persist after browser closure

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    user_message TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    result JSONB,  -- Stores complete response: {text, tool_calls, reasoning, todos}
    error TEXT,
    run_metadata JSONB DEFAULT '{}'::jsonb  -- {model, tokens, duration_ms, etc.}
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_runs_thread_id ON runs(thread_id);
CREATE INDEX IF NOT EXISTS idx_runs_user_id ON runs(user_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);

-- Composite index for user's active runs
CREATE INDEX IF NOT EXISTS idx_runs_user_status ON runs(user_id, status) WHERE status IN ('pending', 'in_progress');

COMMENT ON TABLE runs IS 'Tracks async agent runs that persist after client disconnection';
COMMENT ON COLUMN runs.result IS 'Complete response data including text, tool_calls, reasoning, and todos';
COMMENT ON COLUMN runs.run_metadata IS 'Additional run metadata like model, token count, duration';
