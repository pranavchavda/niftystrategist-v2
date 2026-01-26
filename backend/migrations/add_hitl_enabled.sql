-- Migration: Add HITL (Human-in-the-Loop) enabled field to user_preferences
-- Date: 2025-11-01
-- Description: Add hitl_enabled boolean field to user_preferences table to allow users to enable/disable approval mode

-- Add hitl_enabled column to user_preferences table (defaults to FALSE - disabled)
ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS hitl_enabled BOOLEAN DEFAULT FALSE;

-- Add comment for documentation
COMMENT ON COLUMN user_preferences.hitl_enabled IS 'Enable human-in-the-loop approval mode for tool executions';
