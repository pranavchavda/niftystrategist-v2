-- Add scheduled_at column to workflow_definitions for one-time scheduled runs
-- Run with: psql $DATABASE_URL -f migrations/add_scheduled_at_to_workflow_definitions.sql

ALTER TABLE workflow_definitions
ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMP;

-- Add index for efficient scheduling queries
CREATE INDEX IF NOT EXISTS idx_workflow_defs_scheduled_at
ON workflow_definitions(scheduled_at)
WHERE scheduled_at IS NOT NULL AND enabled = true;

COMMENT ON COLUMN workflow_definitions.scheduled_at IS 'For one-time runs (frequency=once), the datetime to execute';
