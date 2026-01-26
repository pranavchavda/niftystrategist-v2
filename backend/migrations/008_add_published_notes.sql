-- Migration: Add Published Notes System
-- Date: 2025-01-15
-- Description: Enable public web publishing of notes with optional password protection and expiry

-- Create published_notes table
CREATE TABLE IF NOT EXISTS published_notes (
    id SERIAL PRIMARY KEY,
    note_id INTEGER NOT NULL,
    user_id VARCHAR NOT NULL,

    -- Public access
    public_id VARCHAR(32) UNIQUE NOT NULL,  -- Random URL-safe identifier

    -- Security options
    password_hash VARCHAR,  -- Optional password protection (bcrypt)
    expires_at TIMESTAMP,   -- Optional expiration date

    -- Metadata
    view_count INTEGER DEFAULT 0,
    last_viewed_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraints
    CONSTRAINT fk_note
        FOREIGN KEY (note_id)
        REFERENCES notes(id)
        ON DELETE CASCADE,

    -- Ensure one publication per note
    CONSTRAINT unique_note_publication
        UNIQUE (note_id)
);

-- Create indexes for performance
CREATE INDEX idx_published_notes_public_id ON published_notes(public_id);
CREATE INDEX idx_published_notes_note_id ON published_notes(note_id);
CREATE INDEX idx_published_notes_user_id ON published_notes(user_id);
CREATE INDEX idx_published_notes_expires_at ON published_notes(expires_at) WHERE expires_at IS NOT NULL;

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_published_notes_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER published_notes_updated_at_trigger
    BEFORE UPDATE ON published_notes
    FOR EACH ROW
    EXECUTE FUNCTION update_published_notes_updated_at();

-- Add comments for documentation
COMMENT ON TABLE published_notes IS 'Publicly accessible notes with optional security';
COMMENT ON COLUMN published_notes.public_id IS 'URL-safe random identifier for public access (e.g., "a3k9mz2")';
COMMENT ON COLUMN published_notes.password_hash IS 'Bcrypt hash if password protection is enabled';
COMMENT ON COLUMN published_notes.expires_at IS 'Automatic unpublish date (NULL = never expires)';
COMMENT ON COLUMN published_notes.view_count IS 'Total number of times this public note has been viewed';
