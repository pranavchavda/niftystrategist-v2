-- Set HITL (Human-in-the-Loop) approval mode as the default
-- This makes approval mode the default behavior for all users

-- Update NULL values to TRUE (approval mode)
UPDATE user_preferences
SET hitl_enabled = TRUE
WHERE hitl_enabled IS NULL;

-- Change column default to TRUE
ALTER TABLE user_preferences
ALTER COLUMN hitl_enabled SET DEFAULT TRUE;

-- Add comment
COMMENT ON COLUMN user_preferences.hitl_enabled IS 'Enable human-in-the-loop approval mode for tool executions (default: TRUE for safety)';
