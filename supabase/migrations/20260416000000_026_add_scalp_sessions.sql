-- Migration 026: Add scalp_sessions and scalp_session_logs tables
-- Stateful options scalping session manager
-- Date: 2026-04-16

CREATE TABLE IF NOT EXISTS scalp_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Identity
    name VARCHAR(200) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,

    -- Underlying config (signal source)
    underlying VARCHAR(20) NOT NULL,
    underlying_instrument_token VARCHAR(50) NOT NULL,
    expiry VARCHAR(20) NOT NULL,
    lots INTEGER NOT NULL DEFAULT 1,
    product VARCHAR(2) NOT NULL DEFAULT 'I',

    -- UT Bot indicator params
    indicator_timeframe VARCHAR(5) NOT NULL DEFAULT '1m',
    utbot_period INTEGER NOT NULL DEFAULT 10,
    utbot_sensitivity REAL NOT NULL DEFAULT 1.0,

    -- Exit params
    sl_points REAL,
    target_points REAL,
    trail_percent REAL,
    squareoff_time VARCHAR(5) NOT NULL DEFAULT '15:15',

    -- Runtime state (daemon-authoritative, DB for crash recovery)
    state VARCHAR(15) NOT NULL DEFAULT 'IDLE',
    current_option_type VARCHAR(2),
    current_strike REAL,
    current_instrument_token VARCHAR(50),
    current_tradingsymbol VARCHAR(50),
    entry_price REAL,
    entry_time TIMESTAMP WITHOUT TIME ZONE,
    highest_premium REAL,
    trade_count INTEGER NOT NULL DEFAULT 0,
    max_trades INTEGER DEFAULT 20,
    cooldown_seconds INTEGER NOT NULL DEFAULT 60,
    last_exit_time TIMESTAMP WITHOUT TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS idx_scalp_sessions_user_enabled
    ON scalp_sessions(user_id, enabled);

CREATE INDEX IF NOT EXISTS idx_scalp_sessions_state
    ON scalp_sessions(state);


CREATE TABLE IF NOT EXISTS scalp_session_logs (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES scalp_sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    event_type VARCHAR(30) NOT NULL,

    -- Trade details
    option_type VARCHAR(2),
    strike REAL,
    instrument_token VARCHAR(50),
    entry_price REAL,
    exit_price REAL,
    quantity INTEGER,

    -- P&L (populated on exit events)
    pnl_points REAL,
    pnl_amount REAL,

    -- Order
    order_id VARCHAR(100),

    -- Context
    underlying_price REAL,
    trigger_snapshot JSONB,

    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS idx_scalp_session_logs_session
    ON scalp_session_logs(session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_scalp_session_logs_user
    ON scalp_session_logs(user_id, created_at);
