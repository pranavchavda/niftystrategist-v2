"""
MCP Server Management API Routes

Provides CRUD operations for user-specific MCP server configurations.
Users can add, edit, remove, and test MCP servers (stdio, SSE, HTTP).
Includes OAuth 2.1 authentication flow for remote MCP servers.
"""

import logging
import secrets
import hashlib
import base64
import os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, delete
from datetime import datetime, timedelta, timezone
from utils.datetime_utils import utc_now_naive
import httpx

from auth import User, get_current_user
from database.session import AsyncSessionLocal
from database.models import UserMCPServer, UserMCPOAuthToken
from services.mcp_manager import MCPManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Frontend URL for OAuth redirects
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


# ========================================
# Pydantic Models
# ========================================

class OAuthConfig(BaseModel):
    """OAuth configuration for MCP servers requiring authentication"""
    authorization_url: str  # OAuth authorization endpoint
    token_url: str  # OAuth token endpoint
    client_id: str  # OAuth client ID
    client_secret: Optional[str] = None  # OAuth client secret (optional for public clients)
    scopes: List[str] = []  # OAuth scopes to request


class MCPServerConfig(BaseModel):
    """MCP server configuration model"""
    name: str
    description: Optional[str] = None
    transport_type: str  # stdio, sse, or http
    config: Dict[str, Any]  # Flexible config based on transport type
    enabled: bool = True
    auth_type: str = "none"  # none, api_key, oauth
    oauth_config: Optional[OAuthConfig] = None


class OAuthStatus(BaseModel):
    """OAuth connection status"""
    connected: bool
    expires_at: Optional[datetime] = None
    scopes: Optional[List[str]] = None


class MCPServerResponse(BaseModel):
    """MCP server response model"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    description: Optional[str]
    transport_type: str
    config: Dict[str, Any]
    enabled: bool
    auth_type: str = "none"
    oauth_config: Optional[Dict[str, Any]] = None
    oauth_status: Optional[OAuthStatus] = None
    created_at: datetime
    updated_at: datetime


class MCPServerUpdate(BaseModel):
    """MCP server update model"""
    name: Optional[str] = None
    description: Optional[str] = None
    transport_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    auth_type: Optional[str] = None
    oauth_config: Optional[OAuthConfig] = None


class ValidationResponse(BaseModel):
    """Validation response model"""
    valid: bool
    error: Optional[str] = None


class TestConnectionResponse(BaseModel):
    """Test connection response model"""
    success: bool
    error: Optional[str] = None


# ========================================
# OAuth Helper Functions
# ========================================

def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge pair"""
    # Generate a cryptographically random code verifier (43-128 chars)
    code_verifier = secrets.token_urlsafe(64)

    # Create SHA256 hash of verifier, then base64url encode it
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")

    return code_verifier, code_challenge


def generate_state() -> str:
    """Generate a random state parameter for CSRF protection"""
    return secrets.token_urlsafe(32)


async def get_oauth_status(db, server: UserMCPServer) -> Optional[OAuthStatus]:
    """Get OAuth connection status for a server"""
    if server.auth_type != "oauth":
        return None

    result = await db.execute(
        select(UserMCPOAuthToken).where(
            UserMCPOAuthToken.mcp_server_id == server.id
        )
    )
    token = result.scalar_one_or_none()

    if not token:
        return OAuthStatus(connected=False)

    # Check if token is actually valid (not just "pending" from OAuth flow initiation)
    if token.access_token == "pending":
        return OAuthStatus(connected=False)

    return OAuthStatus(
        connected=True,
        expires_at=token.expires_at,
        scopes=token.scopes
    )


def build_server_response(server: UserMCPServer, oauth_status: Optional[OAuthStatus] = None) -> MCPServerResponse:
    """Build MCPServerResponse from database model"""
    # Sanitize oauth_config to remove client_secret from response
    oauth_config = None
    if server.oauth_config:
        oauth_config = {k: v for k, v in server.oauth_config.items() if k != "client_secret"}

    return MCPServerResponse(
        id=server.id,
        user_id=server.user_id,
        name=server.name,
        description=server.description,
        transport_type=server.transport_type,
        config=server.config,
        enabled=server.enabled,
        auth_type=server.auth_type or "none",
        oauth_config=oauth_config,
        oauth_status=oauth_status,
        created_at=server.created_at,
        updated_at=server.updated_at
    )


# ========================================
# MCP Server CRUD Endpoints
# ========================================

@router.get("/api/mcp-servers", response_model=List[MCPServerResponse])
async def list_mcp_servers(
    current_user: User = Depends(get_current_user)
):
    """
    List all MCP servers for the current user.
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserMCPServer).where(UserMCPServer.user_id == current_user.id)
            )
            servers = result.scalars().all()

            responses = []
            for server in servers:
                oauth_status = await get_oauth_status(db, server)
                responses.append(build_server_response(server, oauth_status))

            return responses

    except Exception as e:
        logger.error(f"Error listing MCP servers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/mcp-servers", response_model=MCPServerResponse)
async def create_mcp_server(
    server_config: MCPServerConfig,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new MCP server configuration.
    """
    logger.info(f"Creating MCP server: {server_config.name}, auth_type={server_config.auth_type}, transport={server_config.transport_type}")
    try:
        async with AsyncSessionLocal() as db:
            # Initialize MCP manager
            mcp_manager = MCPManager(db)

            # Validate configuration
            is_valid, error = await mcp_manager.validate_server_config(
                server_config.transport_type,
                server_config.config
            )

            if not is_valid:
                raise HTTPException(status_code=400, detail=error)

            # Check for duplicate name
            existing = await db.execute(
                select(UserMCPServer).where(
                    UserMCPServer.user_id == current_user.id,
                    UserMCPServer.name == server_config.name
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail=f"MCP server with name '{server_config.name}' already exists"
                )

            # Validate OAuth config if auth_type is oauth
            if server_config.auth_type == "oauth":
                if not server_config.oauth_config:
                    raise HTTPException(
                        status_code=400,
                        detail="oauth_config is required when auth_type is 'oauth'"
                    )
                if server_config.transport_type == "stdio":
                    raise HTTPException(
                        status_code=400,
                        detail="OAuth authentication is not supported for stdio transport"
                    )

            # Create new server
            new_server = UserMCPServer(
                user_id=current_user.id,
                name=server_config.name,
                description=server_config.description,
                transport_type=server_config.transport_type,
                config=server_config.config,
                enabled=server_config.enabled,
                auth_type=server_config.auth_type,
                oauth_config=server_config.oauth_config.model_dump() if server_config.oauth_config else None
            )

            db.add(new_server)
            await db.commit()
            await db.refresh(new_server)

            logger.info(f"Created MCP server '{server_config.name}' for user {current_user.id}")

            oauth_status = await get_oauth_status(db, new_server)
            return build_server_response(new_server, oauth_status)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/mcp-servers/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    server_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific MCP server by ID.
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserMCPServer).where(
                    UserMCPServer.id == server_id,
                    UserMCPServer.user_id == current_user.id
                )
            )
            server = result.scalar_one_or_none()

            if not server:
                raise HTTPException(status_code=404, detail="MCP server not found")

            oauth_status = await get_oauth_status(db, server)
            return build_server_response(server, oauth_status)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/mcp-servers/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: int,
    server_update: MCPServerUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing MCP server configuration.
    """
    try:
        async with AsyncSessionLocal() as db:
            # Get existing server
            result = await db.execute(
                select(UserMCPServer).where(
                    UserMCPServer.id == server_id,
                    UserMCPServer.user_id == current_user.id
                )
            )
            server = result.scalar_one_or_none()

            if not server:
                raise HTTPException(status_code=404, detail="MCP server not found")

            # Validate new config if provided
            if server_update.config and server_update.transport_type:
                mcp_manager = MCPManager(db)
                is_valid, error = await mcp_manager.validate_server_config(
                    server_update.transport_type,
                    server_update.config
                )
                if not is_valid:
                    raise HTTPException(status_code=400, detail=error)

            # Check for duplicate name if name is being changed
            if server_update.name and server_update.name != server.name:
                existing = await db.execute(
                    select(UserMCPServer).where(
                        UserMCPServer.user_id == current_user.id,
                        UserMCPServer.name == server_update.name
                    )
                )
                if existing.scalar_one_or_none():
                    raise HTTPException(
                        status_code=400,
                        detail=f"MCP server with name '{server_update.name}' already exists"
                    )

            # Update fields
            if server_update.name is not None:
                server.name = server_update.name
            if server_update.description is not None:
                server.description = server_update.description
            if server_update.transport_type is not None:
                server.transport_type = server_update.transport_type
            if server_update.config is not None:
                server.config = server_update.config
            if server_update.enabled is not None:
                server.enabled = server_update.enabled
            if server_update.auth_type is not None:
                server.auth_type = server_update.auth_type
            if server_update.oauth_config is not None:
                server.oauth_config = server_update.oauth_config.model_dump()

            await db.commit()
            await db.refresh(server)

            logger.info(f"Updated MCP server {server_id} for user {current_user.id}")

            oauth_status = await get_oauth_status(db, server)
            return build_server_response(server, oauth_status)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/mcp-servers/{server_id}")
async def delete_mcp_server(
    server_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Delete an MCP server configuration.
    """
    try:
        async with AsyncSessionLocal() as db:
            # Verify ownership
            result = await db.execute(
                select(UserMCPServer).where(
                    UserMCPServer.id == server_id,
                    UserMCPServer.user_id == current_user.id
                )
            )
            server = result.scalar_one_or_none()

            if not server:
                raise HTTPException(status_code=404, detail="MCP server not found")

            # Delete server
            await db.execute(
                delete(UserMCPServer).where(UserMCPServer.id == server_id)
            )
            await db.commit()

            logger.info(f"Deleted MCP server {server_id} for user {current_user.id}")

            return {"success": True, "message": "MCP server deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# Validation & Testing Endpoints
# ========================================

@router.post("/api/mcp-servers/validate", response_model=ValidationResponse)
async def validate_config(
    transport_type: str,
    config: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """
    Validate an MCP server configuration without saving it.
    """
    try:
        async with AsyncSessionLocal() as db:
            mcp_manager = MCPManager(db)
            is_valid, error = await mcp_manager.validate_server_config(transport_type, config)

            return ValidationResponse(valid=is_valid, error=error)

    except Exception as e:
        logger.error(f"Error validating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/mcp-servers/{server_id}/test", response_model=TestConnectionResponse)
async def test_connection(
    server_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Test connection to an MCP server.
    """
    try:
        async with AsyncSessionLocal() as db:
            # Get server
            result = await db.execute(
                select(UserMCPServer).where(
                    UserMCPServer.id == server_id,
                    UserMCPServer.user_id == current_user.id
                )
            )
            server = result.scalar_one_or_none()

            if not server:
                raise HTTPException(status_code=404, detail="MCP server not found")

            # Test connection
            mcp_manager = MCPManager(db)
            success, error = await mcp_manager.test_connection(server)

            return TestConnectionResponse(success=success, error=error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/mcp-servers/{server_id}/toggle")
async def toggle_server(
    server_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Toggle MCP server enabled status.
    """
    try:
        async with AsyncSessionLocal() as db:
            # Get server
            result = await db.execute(
                select(UserMCPServer).where(
                    UserMCPServer.id == server_id,
                    UserMCPServer.user_id == current_user.id
                )
            )
            server = result.scalar_one_or_none()

            if not server:
                raise HTTPException(status_code=404, detail="MCP server not found")

            # Toggle enabled status
            server.enabled = not server.enabled
            await db.commit()

            logger.info(f"Toggled MCP server {server_id} to {server.enabled} for user {current_user.id}")

            return {
                "success": True,
                "enabled": server.enabled,
                "message": f"MCP server {'enabled' if server.enabled else 'disabled'}"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# OAuth 2.1 Authentication Endpoints
# ========================================

@router.get("/api/mcp-servers/{server_id}/oauth/authorize")
async def oauth_authorize(
    server_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Initiate OAuth 2.1 authorization flow for an MCP server.
    Redirects to the authorization server with PKCE parameters.
    """
    try:
        async with AsyncSessionLocal() as db:
            # Get server
            result = await db.execute(
                select(UserMCPServer).where(
                    UserMCPServer.id == server_id,
                    UserMCPServer.user_id == current_user.id
                )
            )
            server = result.scalar_one_or_none()

            if not server:
                raise HTTPException(status_code=404, detail="MCP server not found")

            if server.auth_type != "oauth":
                raise HTTPException(
                    status_code=400,
                    detail="This server is not configured for OAuth authentication"
                )

            if not server.oauth_config:
                raise HTTPException(
                    status_code=400,
                    detail="OAuth configuration is missing"
                )

            oauth_config = server.oauth_config

            # Generate PKCE pair and state
            code_verifier, code_challenge = generate_pkce_pair()
            state = generate_state()

            # Store PKCE verifier and state in database for callback validation
            # Check if token record exists
            token_result = await db.execute(
                select(UserMCPOAuthToken).where(
                    UserMCPOAuthToken.user_id == current_user.id,
                    UserMCPOAuthToken.mcp_server_id == server_id
                )
            )
            token_record = token_result.scalar_one_or_none()

            if token_record:
                # Update existing record with new PKCE state
                logger.info(f"Updating existing token record {token_record.id} with new state: {state}")
                token_record.pkce_code_verifier = code_verifier
                token_record.oauth_state = state
            else:
                # Create new record to store PKCE state
                logger.info(f"Creating new token record with state: {state}")
                token_record = UserMCPOAuthToken(
                    user_id=current_user.id,
                    mcp_server_id=server_id,
                    access_token="pending",  # Placeholder until we get real token
                    pkce_code_verifier=code_verifier,
                    oauth_state=state
                )
                db.add(token_record)

            await db.commit()
            logger.info(f"Token record saved with state: {token_record.oauth_state}")

            # Build authorization URL
            # Use a generic callback URL - server_id is encoded in the state parameter
            callback_url = f"{FRONTEND_URL}/api/mcp-oauth/callback"
            scopes = " ".join(oauth_config.get("scopes", []))

            # Encode server_id in state (format: "server_id:random_state")
            state_with_server = f"{server_id}:{state}"

            auth_params = {
                "response_type": "code",
                "client_id": oauth_config["client_id"],
                "redirect_uri": callback_url,
                "state": state_with_server,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
            if scopes:
                auth_params["scope"] = scopes

            # Build query string - URL encode values
            from urllib.parse import urlencode
            query_string = urlencode(auth_params)
            auth_url = f"{oauth_config['authorization_url']}?{query_string}"

            logger.info(f"Initiating OAuth flow for server {server_id}, user {current_user.id}")

            # Return the auth URL as JSON so frontend can redirect
            # This allows the frontend to make an authenticated request first
            return {
                "auth_url": auth_url,
                "message": "Redirect to this URL to complete OAuth authorization"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/mcp-oauth/callback")
async def oauth_callback(
    code: str = Query(..., description="Authorization code from OAuth provider"),
    state: str = Query(..., description="State parameter containing server_id and CSRF token"),
):
    """
    Generic OAuth callback endpoint. Exchanges authorization code for tokens.
    Note: This endpoint doesn't require authentication because it's called by
    the OAuth provider redirect. We validate using the state parameter instead.

    The state parameter format is: "server_id:random_state"
    """
    try:
        # Parse server_id from state
        if ":" not in state:
            logger.warning(f"OAuth callback with malformed state: {state}")
            return RedirectResponse(
                url=f"{FRONTEND_URL}/settings/mcp?error=invalid_state"
            )

        server_id_str, original_state = state.split(":", 1)
        logger.info(f"OAuth callback: server_id_str={server_id_str}, original_state={original_state}")
        try:
            server_id = int(server_id_str)
        except ValueError:
            logger.warning(f"OAuth callback with invalid server_id in state: {state}")
            return RedirectResponse(
                url=f"{FRONTEND_URL}/settings/mcp?error=invalid_state"
            )

        async with AsyncSessionLocal() as db:
            # Find the token record with matching state
            logger.info(f"Looking for token record with server_id={server_id}, state={original_state}")
            result = await db.execute(
                select(UserMCPOAuthToken).where(
                    UserMCPOAuthToken.mcp_server_id == server_id,
                    UserMCPOAuthToken.oauth_state == original_state
                )
            )
            token_record = result.scalar_one_or_none()
            logger.info(f"Token record found: {token_record is not None}")

            if not token_record:
                logger.warning(f"OAuth callback with invalid state for server {server_id}")
                return RedirectResponse(
                    url=f"{FRONTEND_URL}/settings/mcp?error=invalid_state"
                )

            # Get the server config
            server_result = await db.execute(
                select(UserMCPServer).where(UserMCPServer.id == server_id)
            )
            server = server_result.scalar_one_or_none()

            if not server or not server.oauth_config:
                return RedirectResponse(
                    url=f"{FRONTEND_URL}/settings/mcp?error=server_not_found"
                )

            oauth_config = server.oauth_config
            # Use the same generic callback URL
            callback_url = f"{FRONTEND_URL}/api/mcp-oauth/callback"

            # Exchange code for tokens
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": callback_url,
                "code_verifier": token_record.pkce_code_verifier,
            }

            # Build headers - some providers require Basic Auth for client credentials
            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            # If we have a client secret, use Basic Auth (required by some providers like Klaviyo)
            # Otherwise, include client_id in the body (for public clients)
            if oauth_config.get("client_secret"):
                import base64
                credentials = f"{oauth_config['client_id']}:{oauth_config['client_secret']}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                headers["Authorization"] = f"Basic {encoded_credentials}"
            else:
                # Public client - include client_id in body
                token_data["client_id"] = oauth_config["client_id"]

            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"Exchanging code for tokens at {oauth_config['token_url']}")
                response = await client.post(
                    oauth_config["token_url"],
                    data=token_data,
                    headers=headers
                )

            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                return RedirectResponse(
                    url=f"{FRONTEND_URL}/settings/mcp?error=token_exchange_failed"
                )

            tokens = response.json()
            logger.info(f"Token exchange response for server {server_id}: {list(tokens.keys())}")

            # Validate token response
            access_token = tokens.get("access_token")
            if not access_token:
                logger.error(f"Token exchange response missing access_token: {tokens}")
                return RedirectResponse(
                    url=f"{FRONTEND_URL}/settings/mcp?error=no_access_token"
                )

            # Update token record with real tokens
            token_record.access_token = access_token
            token_record.refresh_token = tokens.get("refresh_token")
            token_record.token_type = tokens.get("token_type", "Bearer")

            # Calculate expiration
            expires_in = tokens.get("expires_in")
            if expires_in:
                token_record.expires_at = utc_now_naive() + timedelta(seconds=expires_in)

            # Store scopes
            scope_str = tokens.get("scope", "")
            if scope_str:
                token_record.scopes = scope_str.split(" ")

            # Clear PKCE state
            token_record.pkce_code_verifier = None
            token_record.oauth_state = None

            await db.commit()

            logger.info(f"OAuth flow completed for server {server_id}")

            return RedirectResponse(
                url=f"{FRONTEND_URL}/settings/mcp?success=connected&server={server_id}"
            )

    except Exception as e:
        import traceback
        logger.error(f"Error in OAuth callback: {type(e).__name__}: {e}")
        logger.error(f"OAuth callback traceback: {traceback.format_exc()}")
        return RedirectResponse(
            url=f"{FRONTEND_URL}/settings/mcp?error=callback_failed"
        )


@router.delete("/api/mcp-servers/{server_id}/oauth")
async def oauth_revoke(
    server_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Revoke OAuth connection for an MCP server.
    Deletes stored tokens.
    """
    try:
        async with AsyncSessionLocal() as db:
            # Verify server ownership
            server_result = await db.execute(
                select(UserMCPServer).where(
                    UserMCPServer.id == server_id,
                    UserMCPServer.user_id == current_user.id
                )
            )
            server = server_result.scalar_one_or_none()

            if not server:
                raise HTTPException(status_code=404, detail="MCP server not found")

            # Delete token record
            await db.execute(
                delete(UserMCPOAuthToken).where(
                    UserMCPOAuthToken.user_id == current_user.id,
                    UserMCPOAuthToken.mcp_server_id == server_id
                )
            )
            await db.commit()

            logger.info(f"OAuth revoked for server {server_id}, user {current_user.id}")

            return {"success": True, "message": "OAuth connection revoked"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/mcp-servers/{server_id}/oauth/refresh")
async def oauth_refresh(
    server_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Manually refresh OAuth token for an MCP server.
    """
    try:
        async with AsyncSessionLocal() as db:
            # Verify server ownership
            server_result = await db.execute(
                select(UserMCPServer).where(
                    UserMCPServer.id == server_id,
                    UserMCPServer.user_id == current_user.id
                )
            )
            server = server_result.scalar_one_or_none()

            if not server:
                raise HTTPException(status_code=404, detail="MCP server not found")

            if not server.oauth_config:
                raise HTTPException(status_code=400, detail="Server not configured for OAuth")

            # Get token record
            token_result = await db.execute(
                select(UserMCPOAuthToken).where(
                    UserMCPOAuthToken.user_id == current_user.id,
                    UserMCPOAuthToken.mcp_server_id == server_id
                )
            )
            token_record = token_result.scalar_one_or_none()

            if not token_record or not token_record.refresh_token:
                raise HTTPException(
                    status_code=400,
                    detail="No refresh token available. Re-authenticate required."
                )

            oauth_config = server.oauth_config

            # Refresh token request
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
                logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=400,
                    detail="Token refresh failed. Re-authentication required."
                )

            tokens = response.json()

            # Update tokens
            token_record.access_token = tokens.get("access_token")
            if tokens.get("refresh_token"):
                token_record.refresh_token = tokens.get("refresh_token")

            expires_in = tokens.get("expires_in")
            if expires_in:
                token_record.expires_at = utc_now_naive() + timedelta(seconds=expires_in)

            await db.commit()

            logger.info(f"OAuth token refreshed for server {server_id}, user {current_user.id}")

            return {
                "success": True,
                "message": "Token refreshed successfully",
                "expires_at": token_record.expires_at.isoformat() if token_record.expires_at else None
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing OAuth token: {e}")
        raise HTTPException(status_code=500, detail=str(e))
