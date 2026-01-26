-- Boxing Week Tracker Dashboard - Database Migration
-- Created: 2025-12-14
-- Purpose: Add tables for Boxing Week analytics caching and milestone tracking

-- Boxing Week analytics cache (multi-year, hourly granularity)
CREATE TABLE IF NOT EXISTS boxing_week_analytics_cache (
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
CREATE INDEX IF NOT EXISTS idx_bw_cache_year_date ON boxing_week_analytics_cache(year, date);
CREATE INDEX IF NOT EXISTS idx_bw_cache_year ON boxing_week_analytics_cache(year);
CREATE INDEX IF NOT EXISTS idx_bw_cache_is_live ON boxing_week_analytics_cache(is_live) WHERE is_live = TRUE;

-- Milestone tracking table
CREATE TABLE IF NOT EXISTS boxing_week_milestones (
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
CREATE INDEX IF NOT EXISTS idx_bw_milestones_year ON boxing_week_milestones(year);
CREATE INDEX IF NOT EXISTS idx_bw_milestones_achieved ON boxing_week_milestones(year, achieved);

-- Seed 2025 milestones ($50K, $100K, $250K, $400K)
INSERT INTO boxing_week_milestones (year, threshold) VALUES
    (2025, 50000),
    (2025, 100000),
    (2025, 250000),
    (2025, 400000),
    (2025, 500000),
    (2025, 750000),
    (2025, 1000000)
ON CONFLICT (year, threshold) DO NOTHING;

-- Function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_bw_cache_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at on boxing_week_analytics_cache
DROP TRIGGER IF EXISTS trigger_bw_cache_updated_at ON boxing_week_analytics_cache;
CREATE TRIGGER trigger_bw_cache_updated_at
    BEFORE UPDATE ON boxing_week_analytics_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_bw_cache_updated_at();
