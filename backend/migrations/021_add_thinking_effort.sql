-- Add thinking_effort column to ai_models table
-- Replaces the boolean supports_thinking with a configurable effort level
-- Values: 'high', 'medium', 'low', or NULL (no thinking)

ALTER TABLE ai_models
ADD COLUMN IF NOT EXISTS thinking_effort VARCHAR(20) DEFAULT NULL;

-- Backfill: existing models with supports_thinking=true get 'high' effort
UPDATE ai_models
SET thinking_effort = 'high'
WHERE supports_thinking = true AND thinking_effort IS NULL;
