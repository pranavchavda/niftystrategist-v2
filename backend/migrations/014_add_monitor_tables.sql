-- Migration: Add monitor_rules and monitor_logs tables
-- Description: IFTTT-style trade monitoring rules and firing audit log
-- Date: 2026-02-18

-- Monitor Rules: user-defined trigger → action rules
CREATE TABLE IF NOT EXISTS monitor_rules (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,

    trigger_type VARCHAR(20) NOT NULL,
    trigger_config JSONB NOT NULL,

    action_type VARCHAR(20) NOT NULL,
    action_config JSONB NOT NULL,

    instrument_token VARCHAR(50),
    symbol VARCHAR(50),
    linked_trade_id INTEGER REFERENCES trades(id) ON DELETE SET NULL,
    linked_order_id VARCHAR(100),

    fire_count INTEGER NOT NULL DEFAULT 0,
    max_fires INTEGER,
    expires_at TIMESTAMP,
    fired_at TIMESTAMP,

    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- Indexes for daemon polling and user queries
CREATE INDEX idx_monitor_rules_user_enabled ON monitor_rules(user_id, enabled);
CREATE INDEX idx_monitor_rules_instrument ON monitor_rules(instrument_token);
CREATE INDEX idx_monitor_rules_symbol ON monitor_rules(symbol);

-- Monitor Logs: audit trail of rule firings
CREATE TABLE IF NOT EXISTS monitor_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rule_id INTEGER REFERENCES monitor_rules(id) ON DELETE SET NULL,

    trigger_snapshot JSONB,
    action_taken VARCHAR(50) NOT NULL,
    action_result JSONB,

    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- Indexes for log queries
CREATE INDEX idx_monitor_logs_user ON monitor_logs(user_id, created_at);
CREATE INDEX idx_monitor_logs_rule ON monitor_logs(rule_id, created_at);

-- Auto-update updated_at on monitor_rules
CREATE OR REPLACE FUNCTION update_monitor_rules_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW() AT TIME ZONE 'utc';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER monitor_rules_updated_at
    BEFORE UPDATE ON monitor_rules
    FOR EACH ROW
    EXECUTE FUNCTION update_monitor_rules_updated_at();

-- Comments
COMMENT ON TABLE monitor_rules IS 'IFTTT-style trade monitoring rules evaluated by nf-monitor daemon';
COMMENT ON TABLE monitor_logs IS 'Audit log of monitor rule firings with trigger snapshots and action results';
