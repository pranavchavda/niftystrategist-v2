-- Migration: Convert memories table embeddings to pgvector
-- Date: 2025-11-06
-- Description: Migrates memories table to use pgvector halfvec(3072) for fast semantic search

-- Ensure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- PART 1: Add pgvector column to memories table
-- ============================================================================

-- Step 1: Add halfvec column (3072 dimensions for OpenAI text-embedding-3-large)
-- Using halfvec for memory efficiency (50% smaller than vector, minimal accuracy loss)
ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding_halfvec halfvec(3072);

-- Step 2: Convert existing JSON embeddings to halfvec
-- This handles existing memories that already have embeddings
UPDATE memories
SET embedding_halfvec = (
    SELECT ('[' || array_to_string(
        ARRAY(
            SELECT jsonb_array_elements_text(embedding::jsonb)
        ), ','
    ) || ']')::halfvec(3072)
)
WHERE embedding IS NOT NULL
  AND embedding_halfvec IS NULL;

-- ============================================================================
-- PART 2: Create HNSW index for fast similarity search
-- ============================================================================

-- Create HNSW index (much faster than IVFFlat for <2000 dims)
-- halfvec supports HNSW up to 4000 dimensions in pgvector 0.7.4+
-- Parameters:
--   m=16: Number of connections per layer (default, good balance)
--   ef_construction=64: Size of dynamic candidate list (default, good quality)
CREATE INDEX IF NOT EXISTS memories_embedding_hnsw_idx
ON memories
USING hnsw (embedding_halfvec halfvec_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- PART 3: Add index for user-specific searches
-- ============================================================================

-- Create compound index for user filtering + vector search
-- This speeds up: WHERE user_id = X ORDER BY embedding_halfvec <=> query
CREATE INDEX IF NOT EXISTS memories_user_embedding_idx
ON memories (user_id)
INCLUDE (embedding_halfvec)
WHERE embedding_halfvec IS NOT NULL;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check migration status
SELECT
    COUNT(*) as total_memories,
    COUNT(embedding) as json_embeddings,
    COUNT(embedding_halfvec) as halfvec_embeddings,
    COUNT(*) FILTER (WHERE embedding IS NOT NULL AND embedding_halfvec IS NULL) as need_conversion
FROM memories;

-- Show index status
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'memories'
  AND indexname LIKE '%vector%';

-- Test query performance (example)
-- EXPLAIN ANALYZE
-- SELECT fact, (1 - (embedding_halfvec <=> '[0.1,0.2,...]'::halfvec(3072))) AS similarity
-- FROM memories
-- WHERE user_id = 'test_user'
-- ORDER BY embedding_halfvec <=> '[0.1,0.2,...]'::halfvec(3072)
-- LIMIT 10;

-- ============================================================================
-- NOTES
-- ============================================================================

-- Performance Benefits:
-- 1. HNSW index provides O(log n) search vs O(n) full table scan
-- 2. halfvec uses 50% less memory than vector (6KB vs 12KB per embedding)
-- 3. Native pgvector operators are highly optimized (SIMD, etc.)
-- 4. Expected speedup: 10-100x for semantic search queries

-- Memory Usage:
-- - halfvec(3072): 3072 * 2 bytes = 6KB per memory
-- - HNSW index overhead: ~20-30% of data size
-- - For 10,000 memories: ~60MB + ~12-18MB index = ~72-78MB total

-- Next Steps:
-- 1. Run this migration
-- 2. Update database/operations.py to use embedding_halfvec
-- 3. Test semantic search performance
-- 4. (Optional) Drop old embedding JSON column after verification

-- ============================================================================
-- ROLLBACK PLAN (if needed)
-- ============================================================================

-- To rollback this migration:
-- DROP INDEX IF EXISTS memories_embedding_hnsw_idx;
-- DROP INDEX IF EXISTS memories_user_embedding_idx;
-- ALTER TABLE memories DROP COLUMN IF EXISTS embedding_halfvec;

DO $$
BEGIN
    RAISE NOTICE '✅ Migration to pgvector completed for memories table!';
    RAISE NOTICE '📊 Using halfvec(3072) for OpenAI text-embedding-3-large';
    RAISE NOTICE '🚀 HNSW index created for fast semantic search';
    RAISE NOTICE '⚡ Expected 10-100x speedup for memory searches';
    RAISE NOTICE '💾 50%% memory savings vs full vector type';
END $$;
