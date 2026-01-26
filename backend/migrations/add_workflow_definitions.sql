-- Migration: Add workflow_definitions table for user-created prompt-based workflows
-- Date: 2024-12-20
-- Description: Allows users to create custom workflows by writing natural language prompts

CREATE TABLE IF NOT EXISTS workflow_definitions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE NOT NULL,

    -- Identity
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(10) DEFAULT '🤖',  -- Emoji for display

    -- The prompt to execute (this is what gets sent to the orchestrator)
    prompt TEXT NOT NULL,

    -- Optional: hint for which agent to use (NULL = orchestrator decides)
    agent_hint VARCHAR(50),  -- 'google_workspace', 'web_search', etc.

    -- Schedule settings
    enabled BOOLEAN DEFAULT false,
    frequency VARCHAR(20) DEFAULT 'daily',  -- 'hourly', '6hours', 'daily', 'weekly', 'manual'
    cron_expression VARCHAR(100),  -- For custom schedules

    -- Execution settings
    timeout_seconds INTEGER DEFAULT 120,
    notify_on_complete BOOLEAN DEFAULT false,
    notify_on_failure BOOLEAN DEFAULT true,

    -- Tracking
    last_run_at TIMESTAMP WITH TIME ZONE,
    next_run_at TIMESTAMP WITH TIME ZONE,
    run_count INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Each user can only have one workflow with a given name
    UNIQUE(user_id, name)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_workflow_defs_user ON workflow_definitions(user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_defs_enabled ON workflow_definitions(enabled) WHERE enabled = true;
CREATE INDEX IF NOT EXISTS idx_workflow_defs_next_run ON workflow_definitions(next_run_at) WHERE enabled = true;

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_workflow_definitions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_workflow_definitions_updated_at ON workflow_definitions;
CREATE TRIGGER trigger_workflow_definitions_updated_at
    BEFORE UPDATE ON workflow_definitions
    FOR EACH ROW
    EXECUTE FUNCTION update_workflow_definitions_updated_at();
