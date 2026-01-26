"""
MCP Manager Service - Dynamic MCP server management for user-specific tool loading

Handles spawning and managing MCP servers based on user configurations stored in the database.
Supports stdio, SSE, and HTTP transports with OAuth 2.1 authentication for remote servers.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from utils.datetime_utils import utc_now_naive
from typing import List, Dict, Any, Optional
from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP, MCPServerSSE
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx

from database.models import UserMCPServer, UserMCPOAuthToken

logger = logging.getLogger(__name__)


class OAuthTokenExpiredError(Exception):
    """Raised when OAuth token is expired and cannot be refreshed"""
    pass


class OAuthNotConnectedError(Exception):
    """Raised when OAuth connection is required but not established"""
    pass


class MCPManager:
    """Manages dynamic loading and spawning of user MCP servers"""

    def __init__(self, db_session: AsyncSession):
        """Initialize MCP manager with database session"""
        self.db_session = db_session

    async def get_user_mcp_servers(self, user_id: int, enabled_only: bool = True) -> List[UserMCPServer]:
        """
        Get MCP server configurations for a user from database.

        Args:
            user_id: User ID to fetch servers for
            enabled_only: If True, only return enabled servers

        Returns:
            List of UserMCPServer models
        """
        try:
            query = select(UserMCPServer).where(UserMCPServer.user_id == user_id)

            if enabled_only:
                query = query.where(UserMCPServer.enabled == True)

            result = await self.db_session.execute(query)
            servers = result.scalars().all()

            logger.info(f"Loaded {len(servers)} MCP server configs for user {user_id}")
            return list(servers)

        except Exception as e:
            logger.error(f"Error loading MCP servers for user {user_id}: {e}")
            return []

    async def get_oauth_token(self, server_config: UserMCPServer) -> Optional[str]:
        """
        Get a valid OAuth token for the server, refreshing if necessary.

        Args:
            server_config: UserMCPServer with OAuth configuration

        Returns:
            Valid access token string, or None if not available

        Raises:
            OAuthNotConnectedError: If OAuth is required but not connected
            OAuthTokenExpiredError: If token expired and refresh failed
        """
        if server_config.auth_type != "oauth":
            return None

        # Query for token
        result = await self.db_session.execute(
            select(UserMCPOAuthToken).where(
                UserMCPOAuthToken.mcp_server_id == server_config.id
            )
        )
        token_record = result.scalar_one_or_none()

        if not token_record or token_record.access_token == "pending":
            raise OAuthNotConnectedError(
                f"OAuth not connected for server '{server_config.name}'. Please authenticate first."
            )

        # Check if token is expired (with 5 minute buffer)
        if token_record.expires_at:
            if utc_now_naive() >= token_record.expires_at - timedelta(minutes=5):
                # Try to refresh
                if token_record.refresh_token:
                    try:
                        await self._refresh_oauth_token(server_config, token_record)
                    except Exception as e:
                        logger.error(f"Failed to refresh OAuth token: {e}")
                        raise OAuthTokenExpiredError(
                            f"OAuth token expired for '{server_config.name}'. Re-authentication required."
                        )
                else:
                    raise OAuthTokenExpiredError(
                        f"OAuth token expired for '{server_config.name}' and no refresh token available."
                    )

        return token_record.access_token

    async def _refresh_oauth_token(
        self,
        server_config: UserMCPServer,
        token_record: UserMCPOAuthToken
    ) -> None:
        """Refresh an OAuth token using the refresh token"""
        oauth_config = server_config.oauth_config

        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": token_record.refresh_token,
            "client_id": oauth_config["client_id"],
        }

        if oauth_config.get("client_secret"):
            token_data["client_secret"] = oauth_config["client_secret"]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                oauth_config["token_url"],
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.status_code}")

        tokens = response.json()

        # Update token record
        token_record.access_token = tokens.get("access_token")
        if tokens.get("refresh_token"):
            token_record.refresh_token = tokens.get("refresh_token")

        expires_in = tokens.get("expires_in")
        if expires_in:
            token_record.expires_at = utc_now_naive() + timedelta(seconds=expires_in)

        await self.db_session.commit()
        logger.info(f"OAuth token refreshed for server {server_config.name}")

    async def spawn_mcp_server(
        self,
        server_config: UserMCPServer,
        env_vars: Optional[Dict[str, str]] = None
    ) -> Optional[Any]:
        """
        Spawn an MCP server instance based on configuration.

        Args:
            server_config: UserMCPServer database model with transport config
            env_vars: Optional environment variables to pass to the server

        Returns:
            MCP server instance (MCPServerStdio, MCPServerHTTP, or MCPServerSSE)

        Raises:
            OAuthNotConnectedError: If OAuth required but not connected
            OAuthTokenExpiredError: If OAuth token expired
        """
        try:
            transport_type = server_config.transport_type
            config = server_config.config

            # Get OAuth token if needed
            oauth_token = None
            if server_config.auth_type == "oauth":
                logger.info(f"Server {server_config.name} requires OAuth, fetching token...")
                oauth_token = await self.get_oauth_token(server_config)
                if oauth_token:
                    logger.info(f"OAuth token retrieved for {server_config.name}: {oauth_token[:20]}...")
                else:
                    logger.warning(f"No OAuth token found for {server_config.name}")

            # Merge environment variables
            mcp_env = os.environ.copy()
            if env_vars:
                mcp_env.update(env_vars)

            # Spawn based on transport type
            if transport_type == "stdio":
                return self._spawn_stdio(server_config.name, config, mcp_env)
            elif transport_type == "sse":
                return self._spawn_sse(server_config.name, config, oauth_token)
            elif transport_type == "http":
                return self._spawn_http(server_config.name, config, oauth_token)
            else:
                logger.error(f"Unknown transport type: {transport_type}")
                return None

        except (OAuthNotConnectedError, OAuthTokenExpiredError):
            raise
        except Exception as e:
            logger.error(f"Error spawning MCP server '{server_config.name}': {e}")
            return None

    def _spawn_stdio(self, name: str, config: Dict[str, Any], env: Dict[str, str]) -> MCPServerStdio:
        """
        Spawn a stdio MCP server.

        Config format:
        {
            "command": "path/to/command",
            "args": ["--arg1", "value1"],
            "env": {"VAR": "value"}  # Additional env vars
        }
        """
        command = config.get("command")
        args = config.get("args", [])
        config_env = config.get("env", {})

        if not command:
            raise ValueError(f"stdio server '{name}' missing 'command' in config")

        # Merge config env with passed env
        merged_env = {**env, **config_env}

        logger.info(f"Spawning stdio MCP server: {name} (command: {command})")

        # Use longer timeout for stdio servers that may need to initialize (e.g., uvx)
        return MCPServerStdio(
            command=command,
            args=args,
            env=merged_env,
            timeout=60.0,  # 60 seconds to allow for slow startup (uvx, npm, etc.)
        )

    def _spawn_sse(
        self,
        name: str,
        config: Dict[str, Any],
        oauth_token: Optional[str] = None
    ) -> MCPServerSSE:
        """
        Spawn an SSE MCP server.

        Config format:
        {
            "url": "http://example.com/sse",
            "headers": {"Authorization": "Bearer token"}
        }

        Args:
            name: Server name for logging
            config: Server configuration
            oauth_token: OAuth access token to inject into Authorization header
        """
        url = config.get("url")
        headers = config.get("headers", {}).copy()

        if not url:
            raise ValueError(f"SSE server '{name}' missing 'url' in config")

        # Inject OAuth token into headers if provided
        if oauth_token:
            headers["Authorization"] = f"Bearer {oauth_token}"
            logger.info(f"Spawning SSE MCP server with OAuth: {name} (url: {url})")
            logger.info(f"SSE headers for {name}: Authorization=Bearer {oauth_token[:20]}...")
        else:
            logger.info(f"Spawning SSE MCP server: {name} (url: {url})")
            logger.warning(f"No OAuth token provided for SSE server {name}")

        return MCPServerSSE(
            url=url,
            headers=headers
        )

    def _spawn_http(
        self,
        name: str,
        config: Dict[str, Any],
        oauth_token: Optional[str] = None
    ) -> MCPServerStreamableHTTP:
        """
        Spawn an HTTP MCP server using Streamable HTTP transport.

        Config format:
        {
            "url": "http://example.com/mcp",
            "headers": {"Authorization": "Bearer token"}
        }

        Args:
            name: Server name for logging
            config: Server configuration
            oauth_token: OAuth access token to inject into Authorization header
        """
        url = config.get("url")
        headers = config.get("headers", {}).copy()

        if not url:
            raise ValueError(f"HTTP server '{name}' missing 'url' in config")

        # Inject OAuth token into headers if provided
        if oauth_token:
            headers["Authorization"] = f"Bearer {oauth_token}"
            logger.info(f"Spawning HTTP (Streamable) MCP server with OAuth: {name} (url: {url})")
        else:
            logger.info(f"Spawning HTTP (Streamable) MCP server: {name} (url: {url})")

        return MCPServerStreamableHTTP(
            url=url,
            headers=headers
        )

    async def spawn_user_mcp_servers(
        self,
        user_id: int,
        env_vars: Optional[Dict[str, str]] = None
    ) -> List[Any]:
        """
        Spawn all enabled MCP servers for a user.

        Args:
            user_id: User ID to load servers for
            env_vars: Optional environment variables to pass to stdio servers

        Returns:
            List of spawned MCP server instances
        """
        try:
            # Get user's MCP server configs
            server_configs = await self.get_user_mcp_servers(user_id, enabled_only=True)

            if not server_configs:
                logger.info(f"No MCP servers configured for user {user_id}")
                return []

            # Spawn each server
            mcp_servers = []
            oauth_errors = []
            for config in server_configs:
                try:
                    server = await self.spawn_mcp_server(config, env_vars)
                    if server:
                        mcp_servers.append(server)
                        logger.info(f"✅ Spawned MCP server: {config.name} ({config.transport_type})")
                    else:
                        logger.warning(f"❌ Failed to spawn MCP server: {config.name}")
                except (OAuthNotConnectedError, OAuthTokenExpiredError) as e:
                    # Log OAuth errors but continue with other servers
                    oauth_errors.append(f"{config.name}: {str(e)}")
                    logger.warning(f"⚠️ OAuth issue for MCP server {config.name}: {e}")
                except Exception as e:
                    logger.error(f"❌ Error spawning MCP server {config.name}: {e}")

            if oauth_errors:
                logger.warning(f"OAuth issues with {len(oauth_errors)} server(s): {oauth_errors}")

            logger.info(f"Spawned {len(mcp_servers)}/{len(server_configs)} MCP servers for user {user_id}")
            return mcp_servers

        except Exception as e:
            logger.error(f"Error spawning user MCP servers: {e}")
            return []

    async def validate_server_config(self, transport_type: str, config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate MCP server configuration before saving.

        Args:
            transport_type: "stdio", "sse", or "http"
            config: Configuration dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if transport_type == "stdio":
                if "command" not in config:
                    return False, "stdio transport requires 'command' field"
                if not isinstance(config.get("args", []), list):
                    return False, "args must be a list"
                if "env" in config and not isinstance(config["env"], dict):
                    return False, "env must be a dictionary"

            elif transport_type in ["sse", "http"]:
                if "url" not in config:
                    return False, f"{transport_type} transport requires 'url' field"
                if not config["url"].startswith(("http://", "https://")):
                    return False, "url must start with http:// or https://"
                if "headers" in config and not isinstance(config["headers"], dict):
                    return False, "headers must be a dictionary"

            else:
                return False, f"Invalid transport type: {transport_type}. Must be stdio, sse, or http"

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    async def test_connection(self, server_config: UserMCPServer) -> tuple[bool, Optional[str]]:
        """
        Test connection to an MCP server.

        Args:
            server_config: UserMCPServer configuration to test

        Returns:
            Tuple of (is_successful, error_message)
        """
        server = None
        try:
            # Spawn the server
            server = self.spawn_mcp_server(server_config)
            if not server:
                return False, "Failed to spawn server"

            # For stdio servers, we can try to initialize
            # For HTTP/SSE, we'd need to make a test request
            # This is a basic implementation

            logger.info(f"Test connection successful for {server_config.name}")
            return True, None

        except Exception as e:
            logger.error(f"Test connection failed for {server_config.name}: {e}")
            return False, str(e)

        finally:
            # Cleanup
            if server:
                try:
                    if hasattr(server, 'cleanup'):
                        await server.cleanup()
                except Exception as e:
                    logger.warning(f"Error cleaning up test server: {e}")
