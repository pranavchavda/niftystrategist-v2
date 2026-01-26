-- Migration: Add Inventory Prediction System
-- Date: 2025-12-31
-- Description: Creates tables for Prophet-based inventory forecasting with LLM demand sensing

-- 1. Forecast Models (configurations)
CREATE TABLE IF NOT EXISTS forecast_models (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Configuration
    method VARCHAR(50) DEFAULT 'prophet',  -- prophet, exp_smoothing, croston, ensemble
    forecast_horizon_days INT DEFAULT 30,
    seasonality_mode VARCHAR(20) DEFAULT 'multiplicative',
    include_holidays BOOLEAN DEFAULT TRUE,

    -- Warehouse scope
    warehouse_id VARCHAR(255),  -- NULL means aggregate across all warehouses

    -- Performance tracking
    last_mape DOUBLE PRECISION,  -- Mean Absolute Percentage Error
    last_trained_at TIMESTAMP,
    training_data_days INT DEFAULT 365,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Forecasts (predictions) - our computed output from SkuVault data
CREATE TABLE IF NOT EXISTS inventory_forecasts (
    id VARCHAR(255) PRIMARY KEY,
    model_id VARCHAR(255) REFERENCES forecast_models(id) ON DELETE CASCADE,
    sku VARCHAR(255) NOT NULL,  -- SkuVault SKU
    warehouse_id VARCHAR(255),  -- NULL means aggregate

    -- Prediction
    forecast_date DATE NOT NULL,
    predicted_units INT NOT NULL,
    confidence_low INT,
    confidence_high INT,

    -- Prophet components (for explainability)
    trend_component DOUBLE PRECISION,
    seasonal_component DOUBLE PRECISION,
    holiday_component DOUBLE PRECISION,

    -- LLM adjustments
    llm_multiplier DOUBLE PRECISION DEFAULT 1.0,
    llm_reasoning TEXT,

    -- Actuals (filled after period ends for accuracy tracking)
    actual_units INT,
    accuracy_score DOUBLE PRECISION,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Demand Signals (LLM-extracted external factors)
CREATE TABLE IF NOT EXISTS demand_signals (
    id VARCHAR(255) PRIMARY KEY,

    signal_type VARCHAR(50) NOT NULL,  -- trend, competitor, supply_chain, sentiment, seasonal
    category VARCHAR(255),  -- product category affected
    affected_skus TEXT[],  -- Array of SKUs

    multiplier DOUBLE PRECISION NOT NULL,  -- 0.5 = -50%, 1.5 = +50%
    confidence VARCHAR(20),  -- low, medium, high
    duration_days INT,

    source_query TEXT,  -- What search produced this
    source_content TEXT,  -- Raw content analyzed
    reasoning TEXT,  -- LLM explanation

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    applied_to_forecasts BOOLEAN DEFAULT FALSE,

    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Inventory Alerts
CREATE TABLE IF NOT EXISTS inventory_alerts (
    id VARCHAR(255) PRIMARY KEY,
    sku VARCHAR(255) NOT NULL,
    warehouse_id VARCHAR(255),  -- NULL means all warehouses
    forecast_id VARCHAR(255) REFERENCES inventory_forecasts(id) ON DELETE SET NULL,

    alert_type VARCHAR(50) NOT NULL,  -- stockout_risk, overstock_warning, accuracy_drift, demand_spike
    severity VARCHAR(20) DEFAULT 'medium',  -- low, medium, high, critical

    title VARCHAR(500) NOT NULL,
    message TEXT NOT NULL,
    recommended_action TEXT,

    -- Metadata
    days_until_stockout INT,
    days_of_overstock INT,
    current_quantity INT,
    predicted_quantity INT,

    -- Status
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP,
    acknowledged_by VARCHAR(255),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_forecast_models_user ON forecast_models(user_id);
CREATE INDEX IF NOT EXISTS idx_forecast_models_active ON forecast_models(is_active);

CREATE INDEX IF NOT EXISTS idx_forecasts_sku ON inventory_forecasts(sku, forecast_date DESC);
CREATE INDEX IF NOT EXISTS idx_forecasts_model ON inventory_forecasts(model_id);
CREATE INDEX IF NOT EXISTS idx_forecasts_warehouse ON inventory_forecasts(warehouse_id, forecast_date DESC);
CREATE INDEX IF NOT EXISTS idx_forecasts_date ON inventory_forecasts(forecast_date DESC);

CREATE INDEX IF NOT EXISTS idx_signals_active ON demand_signals(is_active, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_category ON demand_signals(category, is_active);
CREATE INDEX IF NOT EXISTS idx_signals_expires ON demand_signals(expires_at) WHERE expires_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_alerts_unack ON inventory_alerts(is_acknowledged, severity, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_sku ON inventory_alerts(sku, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON inventory_alerts(alert_type, created_at DESC);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_forecast_models_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_forecast_models_updated_at ON forecast_models;
CREATE TRIGGER trigger_forecast_models_updated_at
    BEFORE UPDATE ON forecast_models
    FOR EACH ROW
    EXECUTE FUNCTION update_forecast_models_updated_at();

-- Add comment for documentation
COMMENT ON TABLE forecast_models IS 'Prophet model configurations for inventory forecasting';
COMMENT ON TABLE inventory_forecasts IS 'Predicted inventory demand from Prophet models';
COMMENT ON TABLE demand_signals IS 'LLM-extracted demand signals from external sources';
COMMENT ON TABLE inventory_alerts IS 'Stockout/overstock alerts generated from forecasts';
