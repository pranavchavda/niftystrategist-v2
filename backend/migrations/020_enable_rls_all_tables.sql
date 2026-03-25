-- Migration 020: Enable Row Level Security on ALL tables
--
-- Supabase exposes all public-schema tables via PostgREST (REST API).
-- Without RLS, anyone with the anon key can read/write all data.
-- This app uses direct asyncpg connections (not PostgREST), so we enable
-- RLS with NO policies — effectively blocking all REST API access while
-- direct DB connections continue working unaffected.
--
-- CRITICAL: This fixes two Supabase security advisories:
--   1. "Table publicly accessible" (rls_disabled_in_public)
--   2. "Sensitive data publicly accessible" (sensitive_columns_exposed)

-- Core tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;

-- Auth / RBAC
ALTER TABLE ai_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;

-- User settings / integrations
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_mcp_servers ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_mcp_oauth_tokens ENABLE ROW LEVEL SECURITY;

-- Notes
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE published_notes ENABLE ROW LEVEL SECURITY;

-- Trading
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist_items ENABLE ROW LEVEL SECURITY;

-- Monitor
ALTER TABLE monitor_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitor_logs ENABLE ROW LEVEL SECURITY;

-- Workflows / Awakenings
ALTER TABLE workflow_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_action_logs ENABLE ROW LEVEL SECURITY;

-- Documents
ALTER TABLE doc_chunks ENABLE ROW LEVEL SECURITY;

-- Legacy EspressoBot tables (if they still exist, ignore errors)
DO $$ BEGIN
  EXECUTE 'ALTER TABLE scratchpad_entries ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE skuvault_sales_cache ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE skuvault_sync_status ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE skuvault_inventory_cache ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE forecast_models ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE inventory_forecasts ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE demand_signals ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE inventory_alerts ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE shopify_docs ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE shopify_docs_metadata ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE boxing_week_analytics_cache ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE boxing_week_milestones ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE bfcm_analytics_cache ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
  EXECUTE 'ALTER TABLE bfcm_milestones ENABLE ROW LEVEL SECURITY';
EXCEPTION WHEN undefined_table THEN NULL;
END $$;
