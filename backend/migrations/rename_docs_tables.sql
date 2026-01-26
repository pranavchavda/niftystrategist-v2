-- Migration: Rename Documentation Tables to Generic Names
-- Purpose: Rename shopify_docs -> docs, documentation_chunks -> doc_chunks
-- This supports the DB-primary architecture where documentation is stored in DB
-- Created: 2025-12-22

-- ============================================================================
-- STEP 1: Rename main tables
-- ============================================================================

-- Rename shopify_docs to docs (source of truth for full document content)
ALTER TABLE IF EXISTS shopify_docs RENAME TO docs;

-- Rename shopify_docs_metadata to docs_metadata
ALTER TABLE IF EXISTS shopify_docs_metadata RENAME TO docs_metadata;

-- Rename documentation_chunks to doc_chunks (derived chunks for semantic search)
ALTER TABLE IF EXISTS documentation_chunks RENAME TO doc_chunks;

-- ============================================================================
-- STEP 2: Rename indexes for docs table
-- ============================================================================

ALTER INDEX IF EXISTS idx_shopify_docs_category RENAME TO idx_docs_category;
ALTER INDEX IF EXISTS idx_shopify_docs_api_version RENAME TO idx_docs_api_version;
ALTER INDEX IF EXISTS idx_shopify_docs_title RENAME TO idx_docs_title;
ALTER INDEX IF EXISTS idx_shopify_docs_content RENAME TO idx_docs_content;

-- ============================================================================
-- STEP 3: Rename indexes for docs_metadata table
-- ============================================================================

ALTER INDEX IF EXISTS idx_shopify_docs_metadata_api RENAME TO idx_docs_metadata_api;

-- ============================================================================
-- STEP 4: Rename indexes for doc_chunks table
-- ============================================================================

ALTER INDEX IF EXISTS idx_file_path RENAME TO idx_doc_chunks_file_path;
ALTER INDEX IF EXISTS idx_file_chunk RENAME TO idx_doc_chunks_file_chunk;

-- ============================================================================
-- STEP 5: Add source column to track document origin
-- ============================================================================

-- Add source column to docs table
-- Values: 'disk' (imported from file), 'manual' (created in UI), 'api' (from external API)
ALTER TABLE docs ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'disk';

-- ============================================================================
-- STEP 6: Update table comments
-- ============================================================================

COMMENT ON TABLE docs IS 'Source of truth for all EspressoBot documentation. Stores full document content.';
COMMENT ON COLUMN docs.doc_path IS 'Relative path (e.g., graphql-operations/products/search.md)';
COMMENT ON COLUMN docs.source IS 'Origin: disk (imported), manual (UI), api (external)';

COMMENT ON TABLE docs_metadata IS 'Tracks documentation versions and update status';

COMMENT ON TABLE doc_chunks IS 'Derived chunks from docs table for semantic search. Regenerated when docs change.';
COMMENT ON COLUMN doc_chunks.file_path IS 'References docs.doc_path';
COMMENT ON COLUMN doc_chunks.heading_context IS 'Parent heading hierarchy for context in search results';

-- ============================================================================
-- VERIFICATION QUERIES (run after migration to verify)
-- ============================================================================

-- Check table exists and has data:
-- SELECT COUNT(*) as doc_count FROM docs;
-- SELECT COUNT(*) as chunk_count FROM doc_chunks;
-- SELECT COUNT(*) as metadata_count FROM docs_metadata;

-- Check source column:
-- SELECT source, COUNT(*) FROM docs GROUP BY source;
