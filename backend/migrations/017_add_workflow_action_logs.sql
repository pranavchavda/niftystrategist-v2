-- Log tool calls and actions executed during workflows
-- Purpose: Track what the agent actually did during scheduled events (awakenings, automations)

CREATE TABLE workflow_action_logs (
    id SERIAL PRIMARY KEY,
    workflow_run_id INTEGER NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Tool invocation details
    tool_name VARCHAR(50) NOT NULL,  -- e.g., 'nf-order', 'nf-portfolio', 'nf-monitor'
    tool_args JSONB NOT NULL,         -- Command + args, e.g., {"command": "buy ADANIPOWER 487 --product I"}

    -- Execution result
    tool_result JSONB,                -- Result/output from the tool
    execution_status VARCHAR(20),     -- 'success', 'failed', 'pending'
    error_message TEXT,

    -- Timing
    started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    duration_ms INTEGER,

    -- Metadata for later analysis
    sequence_order INTEGER NOT NULL,  -- Order within the workflow
    agent_reasoning TEXT,             -- Why agent called this tool
    market_context JSONB,             -- Market state at time of execution (quotes, positions, etc.)

    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Indexes for efficient querying
    CONSTRAINT idx_workflow_action_logs_workflow UNIQUE (workflow_run_id, sequence_order)
);

CREATE INDEX idx_workflow_action_logs_user ON workflow_action_logs(user_id);
CREATE INDEX idx_workflow_action_logs_tool ON workflow_action_logs(tool_name);
CREATE INDEX idx_workflow_action_logs_status ON workflow_action_logs(execution_status);
CREATE INDEX idx_workflow_action_logs_started ON workflow_action_logs(started_at);
