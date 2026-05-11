-- 036_add_upstox_webhook_events.sql
--
-- Stores every order-update webhook payload Upstox pushes to our public endpoint.
-- Phase 1 is passive: persist the event, return 200, don't update other tables.
-- Phases 2+ (state updates) will read from here.
--
-- Origin: 2026-05-11 TATACONSUM multi-fill incident — needed a definitive push
-- signal to resolve ambiguous SDK timeouts. See docs/plans/2026-05-11-upstox-webhook-design.md.

CREATE TABLE IF NOT EXISTS upstox_webhook_events (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    upstox_user_id VARCHAR(100) NOT NULL,
    update_type VARCHAR(32) NOT NULL,            -- 'order' | 'gtt_order'
    order_id VARCHAR(64),                         -- null for gtt updates
    gtt_order_id VARCHAR(64),                     -- null for order updates
    status VARCHAR(64) NOT NULL,
    tag VARCHAR(64),                              -- our client_request_id (Upstox V3 cap is 40)
    instrument_key VARCHAR(64),
    trading_symbol VARCHAR(64),
    transaction_type VARCHAR(8),
    quantity INTEGER,
    filled_quantity INTEGER,
    pending_quantity INTEGER,
    average_price NUMERIC(18, 4),
    price NUMERIC(18, 4),
    trigger_price NUMERIC(18, 4),
    order_timestamp TIMESTAMP,                    -- Upstox's clock (no tz per project convention)
    exchange_timestamp TIMESTAMP,
    status_message TEXT,
    raw_payload JSONB NOT NULL,                   -- full payload for forensics
    received_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    processed_at TIMESTAMP,
    processed_outcome VARCHAR(32),                -- 'applied' | 'duplicate' | 'unknown_order' | 'mismatch' | 'error' | 'observed'
    processed_error TEXT
);

-- Dedup: Upstox may retry deliveries. (order_id, status, order_timestamp) is the
-- natural key for an order state transition. NULLs in order_timestamp are
-- permitted (some statuses don't carry one).
CREATE UNIQUE INDEX IF NOT EXISTS idx_uwe_dedup
    ON upstox_webhook_events (order_id, status, order_timestamp)
    WHERE order_id IS NOT NULL AND order_timestamp IS NOT NULL;

-- For UI / debugging — most-recent-events-per-user view.
CREATE INDEX IF NOT EXISTS idx_uwe_user_received
    ON upstox_webhook_events (user_id, received_at DESC);

-- For state-update lookups by our tag pattern (rule:N:fire:K, scalp:U:UUID).
CREATE INDEX IF NOT EXISTS idx_uwe_tag
    ON upstox_webhook_events (tag)
    WHERE tag IS NOT NULL;

-- For correlating to monitor_logs.action_result.order_id / scalp_session_logs.order_id.
CREATE INDEX IF NOT EXISTS idx_uwe_order_id
    ON upstox_webhook_events (order_id)
    WHERE order_id IS NOT NULL;

COMMENT ON TABLE upstox_webhook_events IS
    'Raw Upstox order-update webhook payloads. Phase 1 = passive store only.';
