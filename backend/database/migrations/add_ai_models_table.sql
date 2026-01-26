-- Migration: Add ai_models table for dynamic model management
-- Date: 2025-01-27
-- Description: Creates table for storing AI model configurations and populates with defaults

-- Create ai_models table
CREATE TABLE IF NOT EXISTS ai_models (
    id SERIAL PRIMARY KEY,
    model_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(200) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    description TEXT,
    context_window INTEGER NOT NULL,
    max_output INTEGER NOT NULL,
    cost_input VARCHAR(50),
    cost_output VARCHAR(50),
    supports_thinking BOOLEAN DEFAULT FALSE,
    speed VARCHAR(20),
    intelligence VARCHAR(20),
    recommended_for JSON,
    is_enabled BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_ai_models_model_id ON ai_models(model_id);
CREATE INDEX IF NOT EXISTS idx_ai_models_provider ON ai_models(provider);
CREATE INDEX IF NOT EXISTS idx_ai_models_enabled ON ai_models(is_enabled);
CREATE INDEX IF NOT EXISTS idx_ai_models_default ON ai_models(is_default);

-- Populate with default models from config/models.py
INSERT INTO ai_models (model_id, name, slug, provider, description, context_window, max_output, cost_input, cost_output, supports_thinking, speed, intelligence, recommended_for, is_enabled, is_default)
VALUES
    -- Claude Haiku 4.5 (default)
    ('claude-haiku-4.5', 'Claude Haiku 4.5', 'claude-haiku-4-5-20251001', 'anthropic',
     'Lightning-fast with extended thinking. Near-frontier performance at 2.5x lower cost than GPT-5. Direct Anthropic API with prompt caching support.',
     200000, 64000, '$1/1M tokens', '$5/1M tokens', TRUE, 'fast', 'very-high',
     '["General orchestration", "Fast responses", "Cost-effective"]'::json, TRUE, TRUE),

    -- Claude Sonnet 4.5
    ('claude-sonnet-4.5', 'Claude Sonnet 4.5', 'claude-sonnet-4-5-20251001', 'anthropic',
     'Highest intelligence for complex reasoning. Frontier model with extended thinking capabilities. 3x cost of Haiku but unmatched performance.',
     200000, 64000, '$3/1M tokens', '$15/1M tokens', TRUE, 'medium', 'frontier',
     '["Complex analysis", "Critical decisions", "Detailed reasoning"]'::json, TRUE, FALSE),

    -- DeepSeek V3.1 Terminus
    ('deepseek-v3.1', 'DeepSeek V3.1 Terminus', 'deepseek/deepseek-v3.1-terminus', 'openrouter',
     'Ultra-cheap model with solid performance. 18x cheaper than Haiku (1/71 cost of GPT-5). Great for high-volume operations.',
     64000, 8000, '$0.14/1M tokens', '$0.14/1M tokens', FALSE, 'fast', 'high',
     '["High-volume tasks", "Cost-sensitive", "Batch operations"]'::json, TRUE, FALSE),

    -- GLM 4.6
    ('glm-4.6', 'GLM 4.6', 'z-ai/glm-4.6', 'openrouter',
     'Best value proposition - 1/5 cost of GPT-5 with strong reasoning. 200K context window and competitive performance.',
     200000, 8000, '$0.50/1M tokens', '$2.00/1M tokens', FALSE, 'medium', 'very-high',
     '["Value option", "Long context", "Cost-effective reasoning"]'::json, TRUE, FALSE),

    -- GPT-5
    ('gpt-5', 'GPT-5', 'openai/gpt-5', 'openrouter',
     'OpenAI''s frontier model with advanced reasoning. Excellent for complex analysis and decision-making.',
     128000, 16000, '$2.50/1M tokens', '$10.00/1M tokens', FALSE, 'slow', 'frontier',
     '["Complex reasoning", "Critical analysis", "OpenAI ecosystem"]'::json, TRUE, FALSE),

    -- GPT-5-mini
    ('gpt-5-mini', 'GPT-5-mini', 'openai/gpt-5-mini', 'openrouter',
     'Medium reasoning at 10x lower cost than GPT-5. Great balance of performance and value.',
     128000, 16000, '$0.25/1M tokens', '$2.00/1M tokens', FALSE, 'fast', 'very-high',
     '["Documentation", "Medium complexity", "Cost-effective"]'::json, TRUE, FALSE),

    -- Grok-4-Fast
    ('grok-4-fast', 'Grok-4-Fast', 'x-ai/grok-4-fast', 'openrouter',
     'Blazing fast with 2M context. Perfect for memory extraction and large document processing.',
     2000000, 16000, '$0.10/1M tokens', '$0.40/1M tokens', FALSE, 'fast', 'high',
     '["Memory extraction", "Large documents", "High-speed processing"]'::json, TRUE, FALSE)
ON CONFLICT (model_id) DO NOTHING;
