-- Migration: Convert to halfvec for 4096-dimensional embeddings
-- Date: 2025-11-06
-- Description: Migrates both documentation_chunks and shopify_docs to use halfvec(4096)
--              Enables HNSW indexing for Qwen 3 Embedding 8B (4096 dimensions)

-- Ensure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- PART 1: Migrate shopify_docs table to halfvec
-- ============================================================================

-- Step 1: Add halfvec column
ALTER TABLE shopify_docs ADD COLUMN IF NOT EXISTS embedding_halfvec halfvec(4096);

-- Step 2: Convert existing vector(4096) to halfvec(4096)
UPDATE shopify_docs
SET embedding_halfvec = embedding_vector::halfvec(4096)
WHERE embedding_vector IS NOT NULL
  AND embedding_halfvec IS NULL;

-- Step 3: Create HNSW index for blazing-fast similarity search
-- HNSW parameters:
--   m = 16: number of bidirectional links (higher = better recall, more memory)
--   ef_construction = 64: size of dynamic candidate list (higher = better quality, slower build)
CREATE INDEX IF NOT EXISTS shopify_docs_embedding_hnsw_idx
ON shopify_docs
USING hnsw (embedding_halfvec halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Step 4: Drop old vector column and rename
ALTER TABLE shopify_docs DROP COLUMN IF EXISTS embedding_vector;
-- ALTER TABLE shopify_docs RENAME COLUMN embedding TO embedding_json_backup;  -- Keep JSON as backup
-- ALTER TABLE shopify_docs RENAME COLUMN embedding_halfvec TO embedding;  -- Do after testing

-- ============================================================================
-- PART 2: Migrate documentation_chunks table to halfvec
-- ============================================================================

-- Step 1: Add halfvec column (4096 for Qwen, will be populated during reindexing)
ALTER TABLE documentation_chunks ADD COLUMN IF NOT EXISTS embedding_halfvec halfvec(4096);

-- Step 2: Convert existing 3072-dim OpenAI embeddings if any exist
-- Note: This is a temporary measure - we'll reindex with Qwen 4096-dim embeddings
DO $$
DECLARE
    current_dim INTEGER;
BEGIN
    -- Check dimension of existing embeddings
    SELECT jsonb_array_length(embedding::jsonb)
    INTO current_dim
    FROM documentation_chunks
    WHERE embedding IS NOT NULL
    LIMIT 1;

    IF current_dim = 3072 THEN
        -- Can't convert 3072 to 4096 directly, so we'll skip this
        -- The reindexing will populate with proper 4096-dim embeddings
        RAISE NOTICE 'Existing embeddings are 3072-dim (OpenAI). Will be replaced during reindexing with 4096-dim Qwen embeddings.';
    ELSIF current_dim = 4096 THEN
        -- Convert 4096-dim vector to halfvec
        UPDATE documentation_chunks
        SET embedding_halfvec = (
            SELECT ('[' || array_to_string(
                ARRAY(
                    SELECT jsonb_array_elements_text(embedding::jsonb)
                ), ','
            ) || ']')::halfvec(4096)
        )
        WHERE embedding IS NOT NULL
          AND embedding_halfvec IS NULL;

        RAISE NOTICE 'Converted existing 4096-dim embeddings to halfvec';
    END IF;
END $$;

-- Step 3: Create HNSW index (will be fast after reindexing populates data)
-- We'll create this after reindexing to avoid building on sparse data
-- CREATE INDEX IF NOT EXISTS documentation_chunks_embedding_hnsw_idx
-- ON documentation_chunks
-- USING hnsw (embedding_halfvec halfvec_cosine_ops)
-- WITH (m = 16, ef_construction = 64);

-- Step 4: Drop old vector column if it exists
ALTER TABLE documentation_chunks DROP COLUMN IF EXISTS embedding_vector;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check shopify_docs migration
SELECT
    COUNT(*) as total_rows,
    COUNT(embedding) as json_embeddings,
    COUNT(embedding_halfvec) as halfvec_embeddings,
    pg_size_pretty(pg_total_relation_size('shopify_docs')) as table_size
FROM shopify_docs;

-- Check documentation_chunks status
SELECT
    COUNT(*) as total_rows,
    COUNT(embedding) as json_embeddings,
    COUNT(embedding_halfvec) as halfvec_embeddings,
    pg_size_pretty(pg_total_relation_size('documentation_chunks')) as table_size
FROM documentation_chunks;

-- Show indexes
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN ('documentation_chunks', 'shopify_docs')
  AND indexname LIKE '%hnsw%';

-- Test HNSW search performance on shopify_docs
DO $$
DECLARE
    test_embedding halfvec(4096);
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
        -- Test search performance
        start_time := clock_timestamp();

        PERFORM *
        FROM shopify_docs
        ORDER BY embedding_halfvec <=> test_embedding
        LIMIT 5;

        end_time := clock_timestamp();
        duration := end_time - start_time;

        RAISE NOTICE 'HNSW search performance: % ms', EXTRACT(MILLISECONDS FROM duration);
    END IF;
END $$;

-- ============================================================================
-- ROLLBACK PLAN (if needed)
-- ============================================================================

-- To rollback:
-- ALTER TABLE shopify_docs DROP COLUMN IF EXISTS embedding_halfvec;
-- ALTER TABLE documentation_chunks DROP COLUMN IF EXISTS embedding_halfvec;
-- DROP INDEX IF EXISTS shopify_docs_embedding_hnsw_idx;
-- DROP INDEX IF EXISTS documentation_chunks_embedding_hnsw_idx;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ Migration to halfvec(4096) completed!';
    RAISE NOTICE '🚀 HNSW index created on shopify_docs';
    RAISE NOTICE '⚠️  Next step: Reindex documentation_chunks with Qwen embeddings';
    RAISE NOTICE '💾 Storage savings: ~50%% with halfvec vs full precision';
END $$;
