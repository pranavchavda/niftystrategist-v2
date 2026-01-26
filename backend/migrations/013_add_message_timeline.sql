-- Migration: Add timeline column to messages table
-- This stores the temporal order of events (text, reasoning, tool_calls) during streaming

ALTER TABLE messages
ADD COLUMN IF NOT EXISTS timeline JSONB DEFAULT '[]'::jsonb;

-- Add comment for documentation
COMMENT ON COLUMN messages.timeline IS 'Temporal order of events during streaming. Each entry has type (text/reasoning/tool), content/data, timestamp, id';
