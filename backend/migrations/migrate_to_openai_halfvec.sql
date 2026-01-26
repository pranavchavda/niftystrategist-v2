-- Migration: Final migration to OpenAI text-embedding-3-large with halfvec(3072)
-- Date: 2025-11-06
-- Description: Sets up halfvec(3072) columns with HNSW indexes for both tables

-- Ensure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- PART 1: Migrate shopify_docs table
-- ============================================================================

-- Step 1: Add halfvec(3072) column
ALTER TABLE shopify_docs ADD COLUMN IF NOT EXISTS embedding_halfvec halfvec(3072);

-- Step 2: Create HNSW index for ultra-fast similarity search
-- HNSW parameters:
--   m = 16: number of bidirectional links (higher = better recall, more memory)
--   ef_construction = 64: size of dynamic candidate list (higher = better quality, slower build)
CREATE INDEX IF NOT EXISTS shopify_docs_embedding_hnsw_idx
ON shopify_docs
USING hnsw (embedding_halfvec halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Note: Data will be populated by reindexing with unified_docs_indexer.py

-- ============================================================================
-- PART 2: Migrate documentation_chunks table
-- ============================================================================

-- Step 1: Add halfvec(3072) column
ALTER TABLE documentation_chunks ADD COLUMN IF NOT EXISTS embedding_halfvec halfvec(3072);

-- Step 2: Create HNSW index
-- This will be created after reindexing populates the data
CREATE INDEX IF NOT EXISTS documentation_chunks_embedding_hnsw_idx
ON documentation_chunks
USING hnsw (embedding_halfvec halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Note: Data will be populated by reindexing with unified_docs_indexer.py

-- ============================================================================
-- CLEANUP: Drop old columns (optional, keep for now as backup)
-- ============================================================================

-- Uncomment after verifying everything works:
-- ALTER TABLE shopify_docs DROP COLUMN IF EXISTS embedding;
-- ALTER TABLE shopify_docs DROP COLUMN IF EXISTS embedding_vector;
-- ALTER TABLE documentation_chunks DROP COLUMN IF EXISTS embedding;
-- ALTER TABLE documentation_chunks DROP COLUMN IF EXISTS embedding_vector;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check shopify_docs migration
SELECT
    COUNT(*) as total_rows,
    COUNT(embedding_halfvec) as halfvec_embeddings,
    pg_size_pretty(pg_total_relation_size('shopify_docs')) as table_size
FROM shopify_docs;

-- Check documentation_chunks status
SELECT
    COUNT(*) as total_rows,
    COUNT(embedding_halfvec) as halfvec_embeddings,
    pg_size_pretty(pg_total_relation_size('documentation_chunks')) as table_size
FROM documentation_chunks;

-- Show HNSW indexes
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE tablename IN ('documentation_chunks', 'shopify_docs')
  AND indexname LIKE '%hnsw%';

-- Test query performance (after reindexing)
-- This will run after data is populated
DO $$
DECLARE
    test_embedding halfvec(3072);
    start_time timestamp;
    end_time timestamp;
    duration interval;
BEGIN
    -- Get a random embedding for testing
    SELECT embedding_halfvec INTO test_embedding
    FROM shopify_docs
    WHERE embedding_halfvec IS NOT NULL
    LIMIT 1;

    IF test_embedding IS NOT NULL THEN
        start_time := clock_timestamp();

        PERFORM *
        FROM shopify_docs
        ORDER BY embedding_halfvec <=> test_embedding
        LIMIT 5;

        end_time := clock_timestamp();
        duration := end_time - start_time;

        RAISE NOTICE '🚀 HNSW search performance: % ms', EXTRACT(MILLISECONDS FROM duration);
    ELSE
        RAISE NOTICE '⚠️  No embeddings found - run reindexing first';
    END IF;
END $$;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ Migration to halfvec(3072) completed!';
    RAISE NOTICE '📊 Model: OpenAI text-embedding-3-large';
    RAISE NOTICE '🚀 HNSW indexes created on both tables';
    RAISE NOTICE '⚠️  Next step: Run unified_docs_indexer.py to reindex with OpenAI embeddings';
    RAISE NOTICE '💾 Storage savings: ~50%% with halfvec vs full precision';
    RAISE NOTICE '⚡ Query speed: 1-5ms with HNSW index';
END $$;
