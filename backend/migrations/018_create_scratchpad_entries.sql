-- Migration: Create scratchpad_entries table
-- Replaces file-based JSON scratchpad with PostgreSQL storage

CREATE TABLE IF NOT EXISTS scratchpad_entries (
    id SERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT 'agent',
    content TEXT NOT NULL,
    entry_type VARCHAR(50) NOT NULL DEFAULT 'note',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS idx_scratchpad_thread ON scratchpad_entries(thread_id);
CREATE INDEX IF NOT EXISTS idx_scratchpad_thread_type ON scratchpad_entries(thread_id, entry_type);
