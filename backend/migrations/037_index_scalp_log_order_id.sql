-- 037_index_scalp_log_order_id.sql
--
-- Webhook backfill (services/webhook_processor.py) looks up scalp_session_logs
-- by order_id on every Upstox webhook delivery. Without an index this is a
-- full scan of the table (~tens of thousands of rows in steady state).
-- Partial index because most rows have order_id NULL (signal/error events).

CREATE INDEX IF NOT EXISTS idx_scalp_session_logs_order_id
    ON scalp_session_logs (order_id)
    WHERE order_id IS NOT NULL;
