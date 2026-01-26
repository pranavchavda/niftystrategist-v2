-- Migration: Add user_mcp_servers table
-- Description: Store user-specific MCP server configurations
-- Date: 2025-01-07

CREATE TABLE IF NOT EXISTS user_mcp_servers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    transport_type VARCHAR(50) NOT NULL CHECK (transport_type IN ('stdio', 'sse', 'http')),
    config JSONB NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_server_name UNIQUE (user_id, name)
);

-- Create index for faster lookups
CREATE INDEX idx_user_mcp_servers_user_id ON user_mcp_servers(user_id);
CREATE INDEX idx_user_mcp_servers_enabled ON user_mcp_servers(enabled);

-- Add updated_at trigger
CREATE OR REPLACE FUNCTION update_user_mcp_servers_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_mcp_servers_updated_at
    BEFORE UPDATE ON user_mcp_servers
    FOR EACH ROW
    EXECUTE FUNCTION update_user_mcp_servers_updated_at();

-- Add comment
COMMENT ON TABLE user_mcp_servers IS 'Stores user-specific MCP server configurations for dynamic tool loading';
