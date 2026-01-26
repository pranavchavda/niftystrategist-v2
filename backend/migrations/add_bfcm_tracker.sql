-- BFCM Tracker Dashboard - Database Migration
-- Created: 2025-11-27
-- Purpose: Add tables for BFCM analytics caching and milestone tracking

-- BFCM analytics cache (multi-year, hourly granularity)
CREATE TABLE IF NOT EXISTS bfcm_analytics_cache (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    date DATE NOT NULL,
    hour INTEGER,  -- 0-23, NULL for daily aggregates

    -- Revenue metrics
    revenue DECIMAL(12, 2),
    order_count INTEGER,
    aov DECIMAL(10, 2),

    -- Top products (JSON array)
    top_products JSONB,

    -- Category breakdown (JSON object)
    category_breakdown JSONB,

    -- GA4 metrics (optional)
    ga4_users INTEGER,
    ga4_sessions INTEGER,
    ga4_conversion_rate DECIMAL(5, 2),

    -- Metadata
    is_live BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Unique constraint: one row per year/date/hour combination
    UNIQUE(year, date, hour)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_bfcm_cache_year_date ON bfcm_analytics_cache(year, date);
CREATE INDEX IF NOT EXISTS idx_bfcm_cache_year ON bfcm_analytics_cache(year);
CREATE INDEX IF NOT EXISTS idx_bfcm_cache_is_live ON bfcm_analytics_cache(is_live) WHERE is_live = TRUE;

-- Milestone tracking table
CREATE TABLE IF NOT EXISTS bfcm_milestones (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    threshold DECIMAL(12, 2) NOT NULL,
    achieved BOOLEAN DEFAULT FALSE,
    achieved_at TIMESTAMP,
    notified BOOLEAN DEFAULT FALSE,

    -- Unique constraint: one milestone per year/threshold combination
    UNIQUE(year, threshold)
);

-- Index for quick milestone lookups
CREATE INDEX IF NOT EXISTS idx_bfcm_milestones_year ON bfcm_milestones(year);
CREATE INDEX IF NOT EXISTS idx_bfcm_milestones_achieved ON bfcm_milestones(year, achieved);

-- Seed 2025 milestones ($50K, $100K, $250K, $400K)
INSERT INTO bfcm_milestones (year, threshold) VALUES
    (2025, 50000),
    (2025, 100000),
    (2025, 250000),
    (2025, 400000)
ON CONFLICT (year, threshold) DO NOTHING;

-- Seed historical milestones for comparison (optional - can be backfilled later)
INSERT INTO bfcm_milestones (year, threshold, achieved, achieved_at) VALUES
    (2024, 50000, TRUE, '2024-11-28 10:00:00'),
    (2024, 100000, TRUE, '2024-11-28 14:00:00'),
    (2024, 250000, TRUE, '2024-11-29 16:00:00'),
    (2024, 400000, FALSE, NULL)
ON CONFLICT (year, threshold) DO NOTHING;

-- Function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_bfcm_cache_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at on bfcm_analytics_cache
DROP TRIGGER IF EXISTS trigger_bfcm_cache_updated_at ON bfcm_analytics_cache;
CREATE TRIGGER trigger_bfcm_cache_updated_at
    BEFORE UPDATE ON bfcm_analytics_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_bfcm_cache_updated_at();

-- Grant permissions (if needed for your setup)
-- GRANT SELECT, INSERT, UPDATE ON bfcm_analytics_cache TO espressobot;
-- GRANT SELECT, INSERT, UPDATE ON bfcm_milestones TO espressobot;
-- GRANT USAGE, SELECT ON SEQUENCE bfcm_analytics_cache_id_seq TO espressobot;
-- GRANT USAGE, SELECT ON SEQUENCE bfcm_milestones_id_seq TO espressobot;
