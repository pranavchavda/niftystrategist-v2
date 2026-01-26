-- Migration: Add Shopify Documentation Index Tables
-- Purpose: Store locally downloaded Shopify API documentation with semantic search capability
-- Created: 2025-11-06

-- Main documentation storage table
CREATE TABLE IF NOT EXISTS shopify_docs (
    id SERIAL PRIMARY KEY,
    doc_path TEXT NOT NULL UNIQUE,
    category VARCHAR(100),
    title TEXT,
    content TEXT NOT NULL,
    embedding JSON,  -- 384-dimensional sentence-transformers embedding for semantic search
    api_version VARCHAR(50),
    last_updated TIMESTAMP DEFAULT NOW(),
    metadata JSON
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_shopify_docs_category ON shopify_docs(category);
CREATE INDEX IF NOT EXISTS idx_shopify_docs_api_version ON shopify_docs(api_version);
CREATE INDEX IF NOT EXISTS idx_shopify_docs_title ON shopify_docs USING gin(to_tsvector('english', title));
CREATE INDEX IF NOT EXISTS idx_shopify_docs_content ON shopify_docs USING gin(to_tsvector('english', content));

-- Metadata table for tracking documentation versions and updates
CREATE TABLE IF NOT EXISTS shopify_docs_metadata (
    id SERIAL PRIMARY KEY,
    api_name VARCHAR(100) UNIQUE NOT NULL,
    version VARCHAR(50),
    last_checked TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP,
    content_hash TEXT,
    total_docs INTEGER DEFAULT 0,
    metadata JSON
);

-- Index for fast metadata lookups
CREATE INDEX IF NOT EXISTS idx_shopify_docs_metadata_api ON shopify_docs_metadata(api_name);

-- Comments for documentation
COMMENT ON TABLE shopify_docs IS 'Stores locally indexed Shopify API documentation for fast search and retrieval';
COMMENT ON COLUMN shopify_docs.doc_path IS 'Relative path within backend/docs/shopify-api/ directory';
COMMENT ON COLUMN shopify_docs.category IS 'Documentation category (schema, operation, liquid, etc.)';
COMMENT ON COLUMN shopify_docs.embedding IS 'JSON array of 384-dim embedding vector for semantic search';
COMMENT ON COLUMN shopify_docs.metadata IS 'Additional metadata (source_url, tags, related_docs, etc.)';

COMMENT ON TABLE shopify_docs_metadata IS 'Tracks documentation versions and update status for each Shopify API';
COMMENT ON COLUMN shopify_docs_metadata.content_hash IS 'SHA256 hash of all documentation content for change detection';
