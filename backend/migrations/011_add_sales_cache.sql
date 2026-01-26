-- Migration: Add Sales Cache for Inventory Prediction
-- Date: 2025-12-31
-- Description: Caches daily sales data from SkuVault to avoid repeated API calls

-- Daily sales cache (one row per SKU per day per warehouse)
CREATE TABLE IF NOT EXISTS skuvault_sales_cache (
    id SERIAL PRIMARY KEY,

    -- Identifiers
    sku VARCHAR(255) NOT NULL,
    sale_date DATE NOT NULL,
    warehouse_id VARCHAR(255),  -- NULL means aggregate across all warehouses

    -- Sales data
    units_sold INT NOT NULL DEFAULT 0,
    revenue DECIMAL(12, 2) NOT NULL DEFAULT 0,
    order_count INT NOT NULL DEFAULT 0,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint to prevent duplicates
    UNIQUE(sku, sale_date, warehouse_id)
);

-- Sync status tracking
CREATE TABLE IF NOT EXISTS skuvault_sync_status (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50) NOT NULL,  -- 'sales', 'inventory', 'products'

    -- Date range synced
    last_sync_date DATE,  -- Last date we have data for
    oldest_sync_date DATE,  -- Earliest date we have data for

    -- Status
    status VARCHAR(20) DEFAULT 'idle',  -- idle, running, completed, failed
    last_run_at TIMESTAMP,
    last_error TEXT,

    -- Stats
    total_records INT DEFAULT 0,
    records_synced_last_run INT DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_sales_cache_sku_date ON skuvault_sales_cache(sku, sale_date DESC);
CREATE INDEX IF NOT EXISTS idx_sales_cache_date ON skuvault_sales_cache(sale_date DESC);
CREATE INDEX IF NOT EXISTS idx_sales_cache_warehouse ON skuvault_sales_cache(warehouse_id, sale_date DESC);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_skuvault_sales_cache_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_sales_cache_updated_at ON skuvault_sales_cache;
CREATE TRIGGER trigger_sales_cache_updated_at
    BEFORE UPDATE ON skuvault_sales_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_skuvault_sales_cache_updated_at();

DROP TRIGGER IF EXISTS trigger_sync_status_updated_at ON skuvault_sync_status;
CREATE TRIGGER trigger_sync_status_updated_at
    BEFORE UPDATE ON skuvault_sync_status
    FOR EACH ROW
    EXECUTE FUNCTION update_skuvault_sales_cache_updated_at();

-- Initialize sync status record
INSERT INTO skuvault_sync_status (sync_type, status)
VALUES ('sales', 'idle')
ON CONFLICT DO NOTHING;

-- Comments
COMMENT ON TABLE skuvault_sales_cache IS 'Cached daily sales data from SkuVault for Prophet forecasting';
COMMENT ON TABLE skuvault_sync_status IS 'Tracks sync status for SkuVault data caching';
