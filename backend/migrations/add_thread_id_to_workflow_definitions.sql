-- Add thread_id to workflow_definitions for thread-bound follow-ups (Thread Awakening)
-- Run with: psql $DATABASE_URL -f migrations/add_thread_id_to_workflow_definitions.sql

ALTER TABLE workflow_definitions
ADD COLUMN IF NOT EXISTS thread_id VARCHAR REFERENCES conversations(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_workflow_defs_thread_id
ON workflow_definitions(thread_id)
WHERE thread_id IS NOT NULL;

COMMENT ON COLUMN workflow_definitions.thread_id IS
'Binds this workflow to a conversation thread. When set, the workflow awakens in that thread with full message history.';
