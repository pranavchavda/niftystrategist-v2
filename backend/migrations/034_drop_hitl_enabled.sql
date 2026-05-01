-- 034_drop_hitl_enabled.sql
-- Remove vestigial HITL approval column from user_preferences.
-- HITL infra removed in favor of render_ui confirmation cards (system-prompt SAFETY-1).

ALTER TABLE user_preferences DROP COLUMN IF EXISTS hitl_enabled;
