-- Migration: Add strategy group tracking to monitor_rules
-- Allows grouping rules created by nf-strategy templates

ALTER TABLE monitor_rules
ADD COLUMN IF NOT EXISTS group_id VARCHAR(50) DEFAULT NULL;

ALTER TABLE monitor_rules
ADD COLUMN IF NOT EXISTS strategy_name VARCHAR(50) DEFAULT NULL;

-- Index for fast group lookups (teardown, listing by strategy)
CREATE INDEX IF NOT EXISTS idx_monitor_rules_group_id
ON monitor_rules (group_id)
WHERE group_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_monitor_rules_strategy_name
ON monitor_rules (strategy_name)
WHERE strategy_name IS NOT NULL;
