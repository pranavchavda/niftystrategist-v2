-- 041_add_memory_importance.sql
-- Memory fading (Part 0 of EspressoBot's memory_distillation, adapted to NS).
-- importance_score drives retrieval ranking (similarity * importance) and the
-- nightly auto-archive of stale, unused memories.
--
-- NULL = unscored: retrieval treats it as 1.0 (no penalty) until the nightly
-- job (jobs/memory_fade.py) scores it. Safe additive change.

ALTER TABLE memories ADD COLUMN IF NOT EXISTS importance_score DOUBLE PRECISION;

COMMENT ON COLUMN memories.importance_score IS
  'Recency+frequency+confidence importance (0-1), recomputed nightly by jobs/memory_fade.py. NULL = unscored, treated as 1.0 in retrieval.';
