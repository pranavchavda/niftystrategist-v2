-- Migration: Add price forecast storage for TimesFM predictions
-- Description: Stores ML-based price forecasts for watchlist symbols
-- Date: 2026-04-05

CREATE TABLE IF NOT EXISTS price_forecasts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- What was forecasted
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(10) NOT NULL DEFAULT 'NSE',
    horizon_days INTEGER NOT NULL,  -- 5, 10, 20, or 60

    -- Current state at forecast time
    current_price DOUBLE PRECISION NOT NULL,
    data_points_used INTEGER NOT NULL,

    -- Aggregate signal
    signal VARCHAR(10) NOT NULL,  -- 'bullish', 'bearish', 'neutral'
    confidence DOUBLE PRECISION NOT NULL,  -- 0.0 to 1.0
    predicted_change_pct DOUBLE PRECISION NOT NULL,

    -- Detailed predictions (JSONB array of {date, price, lower, upper})
    predictions JSONB NOT NULL,

    -- Model metadata
    model_version VARCHAR(100) NOT NULL DEFAULT 'google/timesfm-2.5-200m-pytorch',
    inference_time_ms INTEGER,

    -- Accuracy tracking (filled after the forecast period ends)
    actual_prices JSONB,  -- filled later for backtesting accuracy
    mape DOUBLE PRECISION,  -- mean absolute percentage error

    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- Indexes for common queries
CREATE INDEX idx_forecasts_user_symbol ON price_forecasts(user_id, symbol, created_at DESC);
CREATE INDEX idx_forecasts_user_latest ON price_forecasts(user_id, created_at DESC);

COMMENT ON TABLE price_forecasts IS 'TimesFM ML price forecasts for watchlist symbols';
