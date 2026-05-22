-- 042_add_memory_consolidation.sql
-- Memory consolidation (Part A of EspressoBot's memory_distillation, adapted).
-- The nightly job clusters near-duplicate memories and merges each cluster into
-- one comprehensive memory via an LLM, archiving the sources.
--
--   is_consolidated   — TRUE for a memory produced by merging a cluster.
--   consolidated_from — JSON array of the source memory ids it was merged from.

ALTER TABLE memories ADD COLUMN IF NOT EXISTS is_consolidated BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE memories ADD COLUMN IF NOT EXISTS consolidated_from JSON;

COMMENT ON COLUMN memories.is_consolidated IS
  'TRUE if this memory was produced by merging a cluster (jobs/memory_consolidation.py).';
COMMENT ON COLUMN memories.consolidated_from IS
  'JSON array of source memory ids merged into this consolidated memory.';
