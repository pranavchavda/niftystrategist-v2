-- Migration: Add Notes System (Second Brain)
-- Date: 2025-01-12
-- Description: Creates notes table with pgvector embeddings for AI-first note-taking

-- Create notes table
CREATE TABLE IF NOT EXISTS notes (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR,
    user_id VARCHAR NOT NULL,

    -- Core content
    title TEXT NOT NULL,
    content TEXT NOT NULL,

    -- Organization
    category VARCHAR DEFAULT 'personal',
    tags TEXT[] DEFAULT '{}',
    is_starred BOOLEAN DEFAULT FALSE,

    -- Semantic search (pgvector)
    embedding_halfvec halfvec(3072),

    -- Obsidian sync support
    obsidian_vault_id VARCHAR,
    obsidian_file_path TEXT,
    obsidian_content_hash VARCHAR,
    obsidian_last_synced TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraints
    CONSTRAINT fk_conversation
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE SET NULL,

    -- Unique constraint for Obsidian files
    CONSTRAINT unique_obsidian_file
        UNIQUE (user_id, obsidian_vault_id, obsidian_file_path)
);

-- Create indexes for performance
CREATE INDEX idx_notes_user_id ON notes(user_id);
CREATE INDEX idx_notes_user_starred ON notes(user_id, is_starred);
-- HNSW index for fast semantic search (OpenAI text-embedding-3-large = 3072 dims)
CREATE INDEX idx_notes_embedding ON notes USING hnsw (embedding_halfvec halfvec_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_notes_obsidian_vault ON notes(obsidian_vault_id);
CREATE INDEX idx_notes_user_category ON notes(user_id, category);
CREATE INDEX idx_notes_created_at ON notes(created_at DESC);

-- Create full-text search index
CREATE INDEX idx_notes_content_fts ON notes USING GIN (to_tsvector('english', content));
CREATE INDEX idx_notes_title_fts ON notes USING GIN (to_tsvector('english', title));

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_notes_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER notes_updated_at_trigger
    BEFORE UPDATE ON notes
    FOR EACH ROW
    EXECUTE FUNCTION update_notes_updated_at();

-- Add comments for documentation
COMMENT ON TABLE notes IS 'User notes for second brain / personal knowledge management';
COMMENT ON COLUMN notes.embedding_halfvec IS 'OpenAI text-embedding-3-large (3072 dims, halfvec for 50% memory savings)';
COMMENT ON COLUMN notes.obsidian_vault_id IS 'Unique identifier for Obsidian vault (for multi-vault support)';
COMMENT ON COLUMN notes.obsidian_file_path IS 'Path of file within Obsidian vault (e.g., "Projects/EspressoBot.md")';
COMMENT ON COLUMN notes.obsidian_content_hash IS 'SHA256 hash for change detection and sync';
