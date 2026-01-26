-- Add fork tracking fields to conversations table
-- Run this migration to add conversation forking support

-- Add forked_from_id column (references parent conversation)
ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS forked_from_id VARCHAR,
ADD CONSTRAINT fk_forked_from FOREIGN KEY (forked_from_id)
  REFERENCES conversations(id) ON DELETE SET NULL;

-- Add fork_summary column (stores the comprehensive summary)
ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS fork_summary TEXT;

-- Create index for forked conversations lookup
CREATE INDEX IF NOT EXISTS idx_forked_from ON conversations(forked_from_id);

-- Show updated schema
\d conversations;
