-- Migration 018: Thread embeddings for cross-thread awareness
-- Enables semantic search across recent conversations.
-- Uses pplx-embed-context-v1-0.6b (1024 dims) via Perplexity API.

-- Track embedding freshness on conversations
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS needs_processing_since TIMESTAMP;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS last_embedded_at TIMESTAMP;

-- Thread turn embeddings
CREATE TABLE IF NOT EXISTS thread_embeddings (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id VARCHAR NOT NULL,
    turn_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding halfvec(1024) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    UNIQUE(conversation_id, turn_index)
);

CREATE INDEX IF NOT EXISTS idx_thread_emb_user ON thread_embeddings(user_id);
CREATE INDEX IF NOT EXISTS idx_thread_emb_conv ON thread_embeddings(conversation_id);
