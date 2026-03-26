-- Migration: Create docs and docs_metadata tables
-- Purpose: Store documentation for semantic search by the orchestrator
-- The doc_chunks table already exists; this creates the parent tables
-- Created: 2026-03-26

-- Main documentation storage table (source of truth)
CREATE TABLE IF NOT EXISTS docs (
    id SERIAL PRIMARY KEY,
    doc_path TEXT NOT NULL UNIQUE,
    category VARCHAR(100),
    title TEXT,
    content TEXT NOT NULL,
    embedding JSON,
    embedding_halfvec halfvec(3072),
    api_version VARCHAR(50),
    source VARCHAR(50) DEFAULT 'disk',
    last_updated TIMESTAMP DEFAULT NOW(),
    metadata JSON
);

CREATE INDEX IF NOT EXISTS idx_docs_category ON docs(category);
CREATE INDEX IF NOT EXISTS idx_docs_title ON docs USING gin(to_tsvector('english', title));
CREATE INDEX IF NOT EXISTS idx_docs_content ON docs USING gin(to_tsvector('english', content));

-- Metadata table for tracking documentation versions
CREATE TABLE IF NOT EXISTS docs_metadata (
    id SERIAL PRIMARY KEY,
    api_name VARCHAR(100) UNIQUE NOT NULL,
    version VARCHAR(50),
    last_checked TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP,
    content_hash TEXT,
    total_docs INTEGER DEFAULT 0,
    metadata JSON
);

CREATE INDEX IF NOT EXISTS idx_docs_metadata_api ON docs_metadata(api_name);

COMMENT ON TABLE docs IS 'Source of truth for NiftyStrategist documentation. Stores full document content.';
COMMENT ON COLUMN docs.doc_path IS 'Relative path (e.g., cli-tools/nf-order.md)';
COMMENT ON COLUMN docs.source IS 'Origin: disk (imported), manual (UI), api (external)';
COMMENT ON TABLE docs_metadata IS 'Tracks documentation versions and update status';
