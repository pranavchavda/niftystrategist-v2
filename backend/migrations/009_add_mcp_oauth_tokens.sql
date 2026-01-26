-- Migration: Add MCP OAuth tokens table for remote server authentication
-- Date: 2025-01-22
-- Description: Stores OAuth tokens for remote MCP servers that require authentication

-- Create the OAuth tokens table
CREATE TABLE IF NOT EXISTS user_mcp_oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mcp_server_id INTEGER NOT NULL REFERENCES user_mcp_servers(id) ON DELETE CASCADE,

    -- Token storage (encrypted at application level)
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type VARCHAR(50) DEFAULT 'Bearer',

    -- Token metadata
    expires_at TIMESTAMP WITH TIME ZONE,
    scopes TEXT[],

    -- OAuth state for PKCE flow
    -- Stored temporarily during auth flow, cleared after completion
    pkce_code_verifier TEXT,
    oauth_state TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure one token per user per server
    UNIQUE(user_id, mcp_server_id)
);

-- Add indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_mcp_oauth_user_id ON user_mcp_oauth_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_mcp_oauth_server_id ON user_mcp_oauth_tokens(mcp_server_id);
CREATE INDEX IF NOT EXISTS idx_mcp_oauth_expires ON user_mcp_oauth_tokens(expires_at);

-- Add auth_type column to user_mcp_servers if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_mcp_servers' AND column_name = 'auth_type'
    ) THEN
        ALTER TABLE user_mcp_servers ADD COLUMN auth_type VARCHAR(20) DEFAULT 'none';
    END IF;
END $$;

-- Add oauth_config column to user_mcp_servers if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_mcp_servers' AND column_name = 'oauth_config'
    ) THEN
        ALTER TABLE user_mcp_servers ADD COLUMN oauth_config JSONB;
    END IF;
END $$;

-- Add comment for documentation
COMMENT ON TABLE user_mcp_oauth_tokens IS 'Stores OAuth 2.1 tokens for remote MCP servers requiring authentication';
COMMENT ON COLUMN user_mcp_oauth_tokens.access_token IS 'Encrypted access token for MCP server authentication';
COMMENT ON COLUMN user_mcp_oauth_tokens.refresh_token IS 'Encrypted refresh token for token renewal';
COMMENT ON COLUMN user_mcp_oauth_tokens.pkce_code_verifier IS 'Temporary PKCE code verifier during OAuth flow';
COMMENT ON COLUMN user_mcp_oauth_tokens.oauth_state IS 'Temporary state parameter for CSRF protection during OAuth flow';
COMMENT ON COLUMN user_mcp_servers.auth_type IS 'Authentication type: none, api_key, or oauth';
COMMENT ON COLUMN user_mcp_servers.oauth_config IS 'OAuth configuration: {authorization_url, token_url, client_id, scopes}';
