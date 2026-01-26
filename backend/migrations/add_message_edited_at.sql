-- Migration: Add edited_at column to messages table
-- Date: 2025-11-22
-- Purpose: Track when messages are edited by users

-- Add edited_at column to track message edits
ALTER TABLE messages ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;

-- Add comment for documentation
COMMENT ON COLUMN messages.edited_at IS 'Timestamp when message was last edited by user';
