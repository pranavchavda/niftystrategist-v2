-- Add thread compaction support
-- Tracks when a conversation was last compacted in-place

ALTER TABLE conversations ADD COLUMN IF NOT EXISTS last_compacted_at TIMESTAMP WITHOUT TIME ZONE;
