-- Migration: Add inventory cache table
-- Date: 2026-01-02
-- Description: Cache inventory levels from SkuVault for offline forecasting

CREATE TABLE IF NOT EXISTS skuvault_inventory_cache (
    id SERIAL PRIMARY KEY,

    -- Identifiers
    sku VARCHAR(255) NOT NULL,
    warehouse_id VARCHAR(255),  -- NULL = aggregate total
    warehouse_name VARCHAR(255),

    -- Inventory levels
    quantity_on_hand INTEGER NOT NULL DEFAULT 0,
    quantity_available INTEGER NOT NULL DEFAULT 0,
    quantity_committed INTEGER NOT NULL DEFAULT 0,

    -- Metadata
    snapshot_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Unique constraint for upsert
ALTER TABLE skuvault_inventory_cache
ADD CONSTRAINT unique_sku_warehouse_inventory UNIQUE (sku, warehouse_id);

-- Index for lookups
CREATE INDEX IF NOT EXISTS idx_inventory_cache_sku ON skuvault_inventory_cache(sku);
