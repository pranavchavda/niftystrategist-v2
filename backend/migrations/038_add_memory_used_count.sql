-- Migration 038: Add real-use signal columns to memories
-- The memory extractor now reports which pre-existing memories actually
-- shaped an assistant reply (used_memory_ids). The daily extraction job
-- bumps used_count and stamps last_used_at for those memories, so the
-- quality judge / cleanup pass can distinguish memories that earn their
-- keep from ones that are merely stored.
-- Ported from EspressoBot. Date: 2026-05-15

ALTER TABLE memories
    ADD COLUMN IF NOT EXISTS used_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE memories
    ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMP;

-- Index supports "least-recently-used" / "never-used" scans during cleanup.
CREATE INDEX IF NOT EXISTS idx_user_last_used
    ON memories (user_id, last_used_at);
