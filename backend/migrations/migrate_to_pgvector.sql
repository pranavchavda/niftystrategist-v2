-- Migration: Convert JSON embeddings to pgvector native type
-- Date: 2025-11-06
-- Description: Migrates both documentation_chunks and shopify_docs tables to use pgvector

-- Ensure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- PART 1: Migrate documentation_chunks table
-- ============================================================================

-- Step 1: Create new column with vector type
-- Note: Need to determine dimension from existing data
-- Checking existing data shows 3072 for OpenAI, but we'll migrate to 4096 for Qwen
DO $$
DECLARE
    current_dim INTEGER;
BEGIN
    -- Check if any embeddings exist to determine dimension
    SELECT jsonb_array_length(embedding::jsonb)
    INTO current_dim
    FROM documentation_chunks
    WHERE embedding IS NOT NULL
    LIMIT 1;

    -- If table is empty or no embeddings, set to 4096 (Qwen dimension)
    IF current_dim IS NULL THEN
        current_dim := 4096;
    END IF;

    RAISE NOTICE 'Current embedding dimension for documentation_chunks: %', current_dim;

    -- Add new vector column (will be 4096 for Qwen after reindexing)
    -- For now, create temp column for existing 3072-dim OpenAI embeddings
    IF current_dim = 3072 THEN
        ALTER TABLE documentation_chunks ADD COLUMN IF NOT EXISTS embedding_vector vector(3072);
    ELSE
        ALTER TABLE documentation_chunks ADD COLUMN IF NOT EXISTS embedding_vector vector(4096);
    END IF;
END $$;

-- Step 2: Convert JSON embeddings to vector type
-- This converts [1,2,3,...] JSON to native pgvector format
UPDATE documentation_chunks
SET embedding_vector = (
    SELECT ('[' || array_to_string(
        ARRAY(
            SELECT jsonb_array_elements_text(embedding::jsonb)
        ), ','
    ) || ']')::vector
)
WHERE embedding IS NOT NULL
  AND embedding_vector IS NULL;

-- Step 3: Create index on vector column (will recreate with HNSW after migration to 4096)
-- For now, skip index creation as we'll reindex with Qwen embeddings

-- Step 4: Rename columns (do this AFTER reindexing with Qwen)
-- ALTER TABLE documentation_chunks RENAME COLUMN embedding TO embedding_old_json;
-- ALTER TABLE documentation_chunks RENAME COLUMN embedding_vector TO embedding;

-- ============================================================================
-- PART 2: Migrate shopify_docs table
-- ============================================================================

-- Step 1: Add vector column (4096 dimensions for Qwen)
ALTER TABLE shopify_docs ADD COLUMN IF NOT EXISTS embedding_vector vector(4096);

-- Step 2: Convert JSON embeddings to vector type
UPDATE shopify_docs
SET embedding_vector = (
    SELECT ('[' || array_to_string(
        ARRAY(
            SELECT jsonb_array_elements_text(embedding::jsonb)
        ), ','
    ) || ']')::vector
)
WHERE embedding IS NOT NULL
  AND embedding_vector IS NULL;

-- Step 3: Create IVFFlat index for fast similarity search
-- IVFFlat supports up to 16,000 dimensions (HNSW maxes at 2000 in pgvector 0.7.4)
-- Still provides significant speedup over no index
-- lists parameter: roughly sqrt(row_count), adjust as data grows
CREATE INDEX IF NOT EXISTS shopify_docs_embedding_vector_idx
ON shopify_docs
USING ivfflat (embedding_vector vector_cosine_ops)
WITH (lists = 100);

-- Step 4: Rename columns (keep old JSON column for now as backup)
-- We'll do the rename after verifying everything works
-- ALTER TABLE shopify_docs RENAME COLUMN embedding TO embedding_old_json;
-- ALTER TABLE shopify_docs RENAME COLUMN embedding_vector TO embedding;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check documentation_chunks migration status
SELECT
    COUNT(*) as total_rows,
    COUNT(embedding) as json_embeddings,
    COUNT(embedding_vector) as vector_embeddings
FROM documentation_chunks;

-- Check shopify_docs migration status
SELECT
    COUNT(*) as total_rows,
    COUNT(embedding) as json_embeddings,
    COUNT(embedding_vector) as vector_embeddings
FROM shopify_docs;

-- Show index status
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN ('documentation_chunks', 'shopify_docs')
  AND indexname LIKE '%vector%';

-- ============================================================================
-- ROLLBACK PLAN (if needed)
-- ============================================================================

-- To rollback this migration:
-- ALTER TABLE documentation_chunks DROP COLUMN IF EXISTS embedding_vector;
-- ALTER TABLE shopify_docs DROP COLUMN IF EXISTS embedding_vector;
-- DROP INDEX IF EXISTS shopify_docs_embedding_vector_idx;

DO $$
BEGIN
    RAISE NOTICE '✅ Migration to pgvector completed!';
    RAISE NOTICE '⚠️  Remember to reindex documentation_chunks with Qwen (4096-dim) embeddings';
    RAISE NOTICE '⚠️  Then create IVFFlat index on documentation_chunks.embedding_vector';
    RAISE NOTICE '📊 pgvector 0.7.4 HNSW limit: 2000 dims, using IVFFlat for 4096-dim Qwen';
END $$;
