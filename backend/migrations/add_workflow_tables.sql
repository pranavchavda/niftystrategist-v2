-- Migration: Add workflow automation tables
-- Date: 2024-12-19
-- Description: Tables for scheduling and tracking automated workflows

-- Workflow configuration per user
CREATE TABLE IF NOT EXISTS workflow_configs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    workflow_type VARCHAR(50) NOT NULL,  -- 'email_autolabel', 'daily_sales_report', etc.

    -- Status
    enabled BOOLEAN DEFAULT false,

    -- Schedule settings
    frequency VARCHAR(20) DEFAULT 'daily',  -- 'hourly', '6hours', 'daily', 'weekly', 'manual'
    cron_expression VARCHAR(100),  -- For custom schedules (optional)

    -- Workflow-specific config (JSON)
    config JSONB DEFAULT '{}'::jsonb,
    -- Examples:
    -- email_autolabel: {"email_count": 50, "skip_labeled": true, "max_age_days": 7}
    -- daily_sales_report: {"format": "markdown", "send_email": true}

    -- Tracking
    last_run_at TIMESTAMP WITH TIME ZONE,
    next_run_at TIMESTAMP WITH TIME ZONE,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Each user can only have one config per workflow type
    UNIQUE(user_id, workflow_type)
);

-- Workflow execution history
CREATE TABLE IF NOT EXISTS workflow_runs (
    id SERIAL PRIMARY KEY,
    workflow_config_id INTEGER REFERENCES workflow_configs(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    workflow_type VARCHAR(50) NOT NULL,  -- Denormalized for easy querying

    -- Execution details
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'running', 'completed', 'failed'
    trigger_type VARCHAR(20) NOT NULL,  -- 'manual', 'scheduled'

    -- Timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,  -- Execution time in milliseconds

    -- Results (JSON)
    result JSONB,
    -- Examples:
    -- email_autolabel: {"emails_processed": 50, "labels_applied": {"To Respond": 5, "FYI": 20}, "skipped": 3}
    -- daily_sales_report: {"total_sales": "$5,234.00", "orders": 42, "report_url": "..."}

    error_message TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_workflow_configs_user ON workflow_configs(user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_configs_enabled ON workflow_configs(enabled) WHERE enabled = true;
CREATE INDEX IF NOT EXISTS idx_workflow_configs_next_run ON workflow_configs(next_run_at) WHERE enabled = true;

CREATE INDEX IF NOT EXISTS idx_workflow_runs_user ON workflow_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_config ON workflow_runs(workflow_config_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_started ON workflow_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status) WHERE status = 'running';

-- Trigger to update updated_at on workflow_configs
CREATE OR REPLACE FUNCTION update_workflow_configs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_workflow_configs_updated_at ON workflow_configs;
CREATE TRIGGER trigger_workflow_configs_updated_at
    BEFORE UPDATE ON workflow_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_workflow_configs_updated_at();
