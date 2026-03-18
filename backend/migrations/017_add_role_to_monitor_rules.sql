-- Add role column to monitor_rules for strategy template cross-referencing.
-- Used by activates_roles / kills_roles to resolve role names → rule IDs at deploy time.
ALTER TABLE monitor_rules ADD COLUMN IF NOT EXISTS role VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_monitor_rules_group_role ON monitor_rules(group_id, role) WHERE role IS NOT NULL;
