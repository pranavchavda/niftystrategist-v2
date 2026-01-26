-- Migration: Add supports_vision column to ai_models table
-- Date: 2025-11-01
-- Purpose: Enable vision capability tracking for orchestrator models

-- Add supports_vision column
ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS supports_vision BOOLEAN DEFAULT FALSE;

-- Update existing models with vision capabilities
-- Claude models (Haiku 4.5, Sonnet 4.5) support vision
UPDATE ai_models SET supports_vision = TRUE WHERE model_id IN ('claude-haiku-4.5', 'claude-sonnet-4.5');

-- GPT-5 models support vision
UPDATE ai_models SET supports_vision = TRUE WHERE model_id IN ('gpt-5', 'gpt-5-mini');

-- Other models don't support vision (DeepSeek, GLM, Grok)
UPDATE ai_models SET supports_vision = FALSE WHERE model_id IN ('deepseek-v3.1', 'glm-4.6', 'grok-4-fast');

-- Add index for efficient vision capability queries
CREATE INDEX IF NOT EXISTS idx_ai_models_vision ON ai_models(supports_vision);

-- Verify migration
SELECT model_id, name, supports_vision FROM ai_models ORDER BY model_id;
