-- 043_add_memory_archived.sql
-- Non-lossy memory archiving. Fading + consolidation retire memories by setting
-- archived=TRUE (preserving their original category), instead of overwriting
-- category='_archived' (which lost the original and wasn't cleanly reversible).
-- Retrieval excludes archived=TRUE.

ALTER TABLE memories ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE memories ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_memories_user_archived ON memories (user_id, archived);

COMMENT ON COLUMN memories.archived IS
  'TRUE if faded out (jobs/memory_fade.py) or merged away (jobs/memory_consolidation.py). Excluded from retrieval. Reversible — category is preserved.';
