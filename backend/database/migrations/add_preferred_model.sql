-- Migration: Add preferred_model column to users table
-- Date: 2025-01-27
-- Description: Adds model preference setting for orchestrator selection

-- Add preferred_model column with default value
ALTER TABLE users
ADD COLUMN IF NOT EXISTS preferred_model VARCHAR(50) DEFAULT 'claude-haiku-4.5';

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_preferred_model ON users(preferred_model);

-- Update existing users to use default model
UPDATE users
SET preferred_model = 'claude-haiku-4.5'
WHERE preferred_model IS NULL;
