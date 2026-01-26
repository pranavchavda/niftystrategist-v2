-- EspressoBot Complete Database Schema
-- PostgreSQL 14+ with asyncpg compatibility
-- Generated: 2025-09-29
--
-- This schema includes:
-- - User authentication (Google OAuth)
-- - Conversation persistence
-- - Memory/embedding system
-- - Analytics caching (Shopify, GA4, Google Workspace)
-- - Price monitoring system (competitors, products, violations)
--
-- Total: 18 tables with proper relationships, indexes, and constraints

-- ============================================================================
-- SECTION 1: USER AUTHENTICATION & MANAGEMENT
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    bio TEXT,
    password_hash VARCHAR(255),
    is_whitelisted BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),

    -- Google Workspace OAuth tokens
    google_id VARCHAR(255) UNIQUE,
    profile_picture TEXT,
    google_access_token TEXT,
    google_refresh_token TEXT,
    google_token_expiry TIMESTAMP WITHOUT TIME ZONE,

    -- GA4 Analytics configuration
    ga4_property_id VARCHAR(255) DEFAULT '325181275',
    ga4_enabled BOOLEAN DEFAULT TRUE,

    -- Google Ads configuration
    google_ads_customer_id VARCHAR(255),
    google_ads_enabled BOOLEAN DEFAULT FALSE
);

-- Indexes for user table
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);

-- ============================================================================
-- SECTION 2: CONVERSATION PERSISTENCE SYSTEM
-- ============================================================================

CREATE TABLE IF NOT EXISTS conversations (
    id VARCHAR(255) PRIMARY KEY,  -- thread_id from frontend
    user_id VARCHAR(255) NOT NULL,
    title VARCHAR(255),  -- Auto-generated from first message
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,

    -- Metadata
    agent_used VARCHAR(255),  -- Primary agent used (products, orders, etc)
    tags JSONB DEFAULT '[]'::jsonb,  -- User or auto-generated tags
    is_archived BOOLEAN DEFAULT FALSE,
    is_starred BOOLEAN DEFAULT FALSE,

    -- AI-generated summary for search
    summary TEXT
);

-- Indexes for conversations
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated ON conversations(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_user_starred ON conversations(user_id, is_starred);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    message_id VARCHAR(255) UNIQUE NOT NULL,  -- Unique ID from frontend

    role VARCHAR(50) NOT NULL,  -- user, assistant, system
    content TEXT NOT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,

    -- Optional metadata
    attachments JSONB DEFAULT '[]'::jsonb,  -- File/image attachments
    tool_calls JSONB DEFAULT '[]'::jsonb,  -- Tool calls made by agent
    extra_metadata JSONB DEFAULT '{}'::jsonb,  -- Additional metadata

    -- Token counts for cost analytics
    input_tokens INTEGER,
    output_tokens INTEGER
);

-- Indexes for messages
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_conv_timestamp ON messages(conversation_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_message_id ON messages(message_id);

CREATE TABLE IF NOT EXISTS memories (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,

    -- Memory content
    fact TEXT NOT NULL,  -- Extracted fact/memory
    category VARCHAR(100),  -- preference, fact, instruction, etc.
    confidence REAL DEFAULT 1.0,  -- Confidence score 0.0-1.0

    -- Vector embedding for semantic search (stored as JSON array)
    embedding JSONB,

    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    last_accessed TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    access_count INTEGER DEFAULT 0
);

-- Indexes for memories
CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_user_category ON memories(user_id, category);
CREATE INDEX IF NOT EXISTS idx_memories_user_accessed ON memories(user_id, last_accessed DESC);
CREATE INDEX IF NOT EXISTS idx_memories_conversation_id ON memories(conversation_id);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id VARCHAR(255) PRIMARY KEY,
    preferences JSONB DEFAULT '{}'::jsonb,  -- General preferences

    -- UI preferences
    theme VARCHAR(50) DEFAULT 'light',
    sidebar_collapsed BOOLEAN DEFAULT FALSE,

    -- Agent preferences
    default_model VARCHAR(100),
    temperature REAL DEFAULT 0.7,

    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

-- ============================================================================
-- SECTION 3: ANALYTICS CACHING SYSTEM
-- ============================================================================

CREATE TABLE IF NOT EXISTS daily_analytics_cache (
    id SERIAL PRIMARY KEY,
    date TIMESTAMP WITHOUT TIME ZONE UNIQUE NOT NULL,

    -- Shopify data
    shopify_revenue DOUBLE PRECISION,
    shopify_orders INTEGER,
    shopify_aov DOUBLE PRECISION,  -- Average Order Value
    shopify_top_products JSONB,
    shopify_raw_data JSONB,

    -- GA4 data
    ga4_revenue DOUBLE PRECISION,
    ga4_transactions INTEGER,
    ga4_users INTEGER,
    ga4_conversion_rate DOUBLE PRECISION,
    ga4_traffic_sources JSONB,
    ga4_ads_performance JSONB,
    ga4_raw_data JSONB,

    -- Google Workspace data
    workspace_data JSONB,

    -- Metadata
    is_complete BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- Indexes for daily analytics
CREATE INDEX IF NOT EXISTS idx_daily_analytics_date ON daily_analytics_cache(date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_analytics_complete ON daily_analytics_cache(is_complete, date DESC);

CREATE TABLE IF NOT EXISTS hourly_analytics_cache (
    id SERIAL PRIMARY KEY,
    date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    hour INTEGER NOT NULL,  -- 0-23

    -- Hourly metrics
    revenue DOUBLE PRECISION,
    orders INTEGER,

    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),

    -- Unique constraint on date+hour combination
    CONSTRAINT unique_date_hour UNIQUE (date, hour)
);

-- Indexes for hourly analytics
CREATE INDEX IF NOT EXISTS idx_hourly_analytics_date ON hourly_analytics_cache(date DESC, hour DESC);

CREATE TABLE IF NOT EXISTS analytics_sync_status (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50) NOT NULL,  -- 'shopify', 'ga4', 'workspace'
    start_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    end_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,

    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, failed
    total_days INTEGER,
    processed_days INTEGER DEFAULT 0,
    failed_days INTEGER DEFAULT 0,

    -- Timing
    started_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE
);

-- Indexes for sync status
CREATE INDEX IF NOT EXISTS idx_sync_status_type ON analytics_sync_status(sync_type, status);
CREATE INDEX IF NOT EXISTS idx_sync_status_dates ON analytics_sync_status(start_date, end_date);

-- ============================================================================
-- SECTION 4: PRICE MONITORING SYSTEM
-- ============================================================================

-- 4.1: Brand and Collection Configuration

CREATE TABLE IF NOT EXISTS monitored_brands (
    id VARCHAR(255) PRIMARY KEY,
    brand_name VARCHAR(255) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_monitored_brands_active ON monitored_brands(is_active, brand_name);

CREATE TABLE IF NOT EXISTS monitored_collections (
    id VARCHAR(255) PRIMARY KEY,
    collection_name VARCHAR(255) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_monitored_collections_active ON monitored_collections(is_active);

-- 4.2: Competitor Configuration

CREATE TABLE IF NOT EXISTS competitors (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) UNIQUE NOT NULL,
    collections TEXT[],  -- Array of collection URLs to scrape
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    scrape_schedule VARCHAR(100),  -- Cron expression
    rate_limit_ms INTEGER DEFAULT 2000 NOT NULL,
    last_scraped_at TIMESTAMP WITHOUT TIME ZONE,
    total_products INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,

    -- Scraping configuration
    exclude_patterns TEXT[] DEFAULT ARRAY[]::TEXT[],
    scraping_strategy VARCHAR(50) DEFAULT 'collections' NOT NULL,  -- collections, search, sitemap
    search_terms TEXT[] DEFAULT ARRAY[]::TEXT[],
    url_patterns TEXT[] DEFAULT ARRAY[]::TEXT[]
);

CREATE INDEX IF NOT EXISTS idx_competitors_active ON competitors(is_active);
CREATE INDEX IF NOT EXISTS idx_competitors_domain ON competitors(domain);
CREATE INDEX IF NOT EXISTS idx_competitors_last_scraped ON competitors(last_scraped_at);

-- 4.3: Product Catalogs

CREATE TABLE IF NOT EXISTS idc_products (
    id VARCHAR(255) PRIMARY KEY,
    shopify_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    vendor VARCHAR(255) NOT NULL,
    product_type VARCHAR(255),
    handle VARCHAR(255),
    sku VARCHAR(255),
    price DECIMAL(10, 2),
    compare_at_price DECIMAL(10, 2),
    available BOOLEAN DEFAULT TRUE NOT NULL,
    image_url TEXT,
    description TEXT,
    features TEXT,
    embedding TEXT,  -- Vector embedding as string
    last_synced_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    brand_id VARCHAR(255) NOT NULL REFERENCES monitored_brands(id) ON DELETE CASCADE,
    inventory_quantity INTEGER
);

CREATE INDEX IF NOT EXISTS idx_idc_products_shopify_id ON idc_products(shopify_id);
CREATE INDEX IF NOT EXISTS idx_idc_products_brand_id ON idc_products(brand_id);
CREATE INDEX IF NOT EXISTS idx_idc_products_vendor ON idc_products(vendor);
CREATE INDEX IF NOT EXISTS idx_idc_products_available ON idc_products(available);
CREATE INDEX IF NOT EXISTS idx_idc_products_last_synced ON idc_products(last_synced_at DESC);

CREATE TABLE IF NOT EXISTS competitor_products (
    id VARCHAR(255) PRIMARY KEY,
    external_id VARCHAR(255) NOT NULL,  -- Product ID from competitor site
    competitor_id VARCHAR(255) NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    vendor VARCHAR(255),
    product_type VARCHAR(255),
    handle VARCHAR(255),
    sku VARCHAR(255),
    price DECIMAL(10, 2),
    compare_at_price DECIMAL(10, 2),
    available BOOLEAN DEFAULT TRUE NOT NULL,
    image_url TEXT,
    product_url TEXT,
    description TEXT,
    features TEXT,
    embedding TEXT,  -- Vector embedding as string
    scraped_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,

    -- Unique constraint on competitor + external_id
    CONSTRAINT unique_competitor_external_id UNIQUE (competitor_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_competitor_products_competitor_id ON competitor_products(competitor_id);
CREATE INDEX IF NOT EXISTS idx_competitor_products_vendor ON competitor_products(vendor);
CREATE INDEX IF NOT EXISTS idx_competitor_products_available ON competitor_products(available);
CREATE INDEX IF NOT EXISTS idx_competitor_products_scraped_at ON competitor_products(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_competitor_products_price ON competitor_products(price);

-- 4.4: Product Matching

CREATE TABLE IF NOT EXISTS product_matches (
    id VARCHAR(255) PRIMARY KEY,
    idc_product_id VARCHAR(255) NOT NULL REFERENCES idc_products(id) ON DELETE CASCADE,
    competitor_product_id VARCHAR(255) NOT NULL REFERENCES competitor_products(id) ON DELETE CASCADE,

    -- Similarity scores
    overall_score DOUBLE PRECISION NOT NULL,
    brand_similarity DOUBLE PRECISION,
    title_similarity DOUBLE PRECISION,
    embedding_similarity DOUBLE PRECISION,
    price_similarity DOUBLE PRECISION,

    -- Price comparison
    price_difference DECIMAL(10, 2),
    price_difference_percent DOUBLE PRECISION,

    -- MAP violation tracking
    is_map_violation BOOLEAN DEFAULT FALSE NOT NULL,
    violation_amount DECIMAL(10, 2),
    violation_percentage DOUBLE PRECISION,
    first_violation_date TIMESTAMP WITHOUT TIME ZONE,
    last_checked_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,

    -- Match metadata
    is_manual_match BOOLEAN DEFAULT FALSE NOT NULL,
    is_rejected BOOLEAN DEFAULT FALSE NOT NULL,
    confidence_level VARCHAR(20) DEFAULT 'low' NOT NULL,  -- low, medium, high

    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,

    -- Unique constraint to prevent duplicate matches
    CONSTRAINT unique_product_match UNIQUE (idc_product_id, competitor_product_id)
);

CREATE INDEX IF NOT EXISTS idx_product_matches_idc_product ON product_matches(idc_product_id);
CREATE INDEX IF NOT EXISTS idx_product_matches_competitor_product ON product_matches(competitor_product_id);
CREATE INDEX IF NOT EXISTS idx_product_matches_violations ON product_matches(is_map_violation, last_checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_product_matches_confidence ON product_matches(confidence_level);
CREATE INDEX IF NOT EXISTS idx_product_matches_score ON product_matches(overall_score DESC);

-- 4.5: Price History

CREATE TABLE IF NOT EXISTS price_history (
    id VARCHAR(255) PRIMARY KEY,
    competitor_product_id VARCHAR(255) NOT NULL REFERENCES competitor_products(id) ON DELETE CASCADE,
    price DECIMAL(10, 2) NOT NULL,
    compare_at_price DECIMAL(10, 2),
    available BOOLEAN DEFAULT TRUE NOT NULL,
    recorded_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_price_history_competitor_product ON price_history(competitor_product_id);
CREATE INDEX IF NOT EXISTS idx_price_history_recorded_at ON price_history(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_price_history_product_date ON price_history(competitor_product_id, recorded_at DESC);

-- 4.6: Price Alerts

CREATE TABLE IF NOT EXISTS price_alerts (
    id VARCHAR(255) PRIMARY KEY,
    product_match_id VARCHAR(255) NOT NULL REFERENCES product_matches(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL,  -- price_drop, price_increase, map_violation, availability_change
    title VARCHAR(500) NOT NULL,
    message TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'medium' NOT NULL,  -- low, medium, high, critical

    -- Price change details
    old_price DECIMAL(10, 2),
    new_price DECIMAL(10, 2),
    price_change DECIMAL(10, 2),

    -- Alert status
    status VARCHAR(20) DEFAULT 'unread' NOT NULL,  -- unread, read, dismissed, actioned
    is_read BOOLEAN DEFAULT FALSE NOT NULL,

    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_price_alerts_product_match ON price_alerts(product_match_id);
CREATE INDEX IF NOT EXISTS idx_price_alerts_status ON price_alerts(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_price_alerts_severity ON price_alerts(severity, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_price_alerts_type ON price_alerts(alert_type);

-- 4.7: Violation History

CREATE TABLE IF NOT EXISTS violation_history (
    id VARCHAR(255) PRIMARY KEY,
    product_match_id VARCHAR(255) NOT NULL REFERENCES product_matches(id) ON DELETE CASCADE,
    violation_type VARCHAR(50) NOT NULL,  -- map_violation, price_undercut, etc.

    -- Price details
    competitor_price DECIMAL(10, 2) NOT NULL,
    idc_price DECIMAL(10, 2) NOT NULL,
    violation_amount DECIMAL(10, 2) NOT NULL,
    violation_percent DOUBLE PRECISION NOT NULL,
    previous_price DECIMAL(10, 2),
    price_change DECIMAL(10, 2),

    -- Evidence
    screenshot_url TEXT,
    competitor_url TEXT,
    notes TEXT,

    detected_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_violation_history_product_match ON violation_history(product_match_id);
CREATE INDEX IF NOT EXISTS idx_violation_history_detected_at ON violation_history(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_violation_history_type ON violation_history(violation_type);
CREATE INDEX IF NOT EXISTS idx_violation_history_amount ON violation_history(violation_amount DESC);

-- 4.8: Scraping Job Tracking

CREATE TABLE IF NOT EXISTS scrape_jobs (
    id VARCHAR(255) PRIMARY KEY,
    competitor_id VARCHAR(255) NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,  -- pending, running, completed, failed
    collections TEXT[],  -- Collections scraped in this job

    -- Job results
    products_found INTEGER,
    products_updated INTEGER,
    products_created INTEGER,
    errors TEXT,

    -- Timing
    started_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    duration_seconds INTEGER,

    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc') NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scrape_jobs_competitor ON scrape_jobs(competitor_id);
CREATE INDEX IF NOT EXISTS idx_scrape_jobs_status ON scrape_jobs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scrape_jobs_completed_at ON scrape_jobs(completed_at DESC);

-- ============================================================================
-- TRIGGERS FOR AUTOMATIC TIMESTAMP UPDATES
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW() AT TIME ZONE 'utc';
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all tables with updated_at column
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_preferences_updated_at BEFORE UPDATE ON user_preferences FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_daily_analytics_updated_at BEFORE UPDATE ON daily_analytics_cache FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_monitored_brands_updated_at BEFORE UPDATE ON monitored_brands FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_monitored_collections_updated_at BEFORE UPDATE ON monitored_collections FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_competitors_updated_at BEFORE UPDATE ON competitors FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_idc_products_updated_at BEFORE UPDATE ON idc_products FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_competitor_products_updated_at BEFORE UPDATE ON competitor_products FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_product_matches_updated_at BEFORE UPDATE ON product_matches FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_price_history_updated_at BEFORE UPDATE ON price_history FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_price_alerts_updated_at BEFORE UPDATE ON price_alerts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_violation_history_updated_at BEFORE UPDATE ON violation_history FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_scrape_jobs_updated_at BEFORE UPDATE ON scrape_jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE users IS 'User authentication with Google OAuth and analytics configuration';
COMMENT ON TABLE conversations IS 'Conversation threads with metadata and AI-generated summaries';
COMMENT ON TABLE messages IS 'Individual messages within conversations with tool call tracking';
COMMENT ON TABLE memories IS 'Extracted facts and preferences from conversations with embeddings';
COMMENT ON TABLE user_preferences IS 'User UI and agent preferences';

COMMENT ON TABLE daily_analytics_cache IS 'Daily aggregated analytics from Shopify, GA4, and Google Workspace';
COMMENT ON TABLE hourly_analytics_cache IS 'Hourly metrics for real-time analytics';
COMMENT ON TABLE analytics_sync_status IS 'Track bulk data synchronization jobs';

COMMENT ON TABLE monitored_brands IS 'Brands to monitor for price violations';
COMMENT ON TABLE monitored_collections IS 'Product collections to track';
COMMENT ON TABLE competitors IS 'Competitor stores with scraping configuration';
COMMENT ON TABLE idc_products IS 'IDC (iDrinkCoffee) product catalog from Shopify';
COMMENT ON TABLE competitor_products IS 'Products scraped from competitor sites';
COMMENT ON TABLE product_matches IS 'Matched products between IDC and competitors with similarity scores';
COMMENT ON TABLE price_history IS 'Historical price tracking for competitor products';
COMMENT ON TABLE price_alerts IS 'Alert notifications for price changes and violations';
COMMENT ON TABLE violation_history IS 'Record of MAP and pricing policy violations';
COMMENT ON TABLE scrape_jobs IS 'Track scraping job status and results';

-- ============================================================================
-- INITIAL DATA (Optional)
-- ============================================================================

-- Insert default analytics sync status if needed
-- INSERT INTO analytics_sync_status (sync_type, start_date, end_date, status, total_days)
-- VALUES ('shopify', NOW() - INTERVAL '30 days', NOW(), 'pending', 30)
-- ON CONFLICT DO NOTHING;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================