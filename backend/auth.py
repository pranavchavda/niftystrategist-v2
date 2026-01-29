"""
Authentication module for Nifty Strategist
Provides JWT token authentication for the trading platform
"""

import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Security, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-jwt-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 7

# Security
security = HTTPBearer(auto_error=False)


class User(BaseModel):
    """User model for authentication"""
    id: int
    email: str
    name: str
    bio: Optional[str] = None
    picture: Optional[str] = None
    permissions: List[str] = []


class TokenData(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str = "bearer"
    user: User


def create_access_token(user_data: Dict[str, Any]) -> str:
    """Create JWT access token with permissions"""
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRATION_DAYS)

    to_encode = {
        "sub": str(user_data.get("id", 1)),
        "email": user_data.get("email"),
        "name": user_data.get("name"),
        "picture": user_data.get("picture"),
        "bio": user_data.get("bio"),
        "permissions": user_data.get("permissions", []),
        "exp": expire
    }

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials) -> User:
    """Verify JWT token and return user with permissions"""
    if not credentials:
        raise HTTPException(status_code=401, detail="No authorization credentials")

    token = credentials.credentials

    # Handle dev tokens (not JWT format)
    if token.startswith("dev-token-"):
        return User(
            id=999,
            email="dev@localhost",
            name="Dev User",
            permissions=[
                "chat.access",
                "dashboard.access",
                "trading.access",
                "portfolio.access",
                "memory.access",
                "settings.access",
            ]
        )

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        user = User(
            id=int(payload.get("sub", 1)),
            email=payload.get("email", ""),
            name=payload.get("name", ""),
            picture=payload.get("picture"),
            bio=payload.get("bio"),
            permissions=payload.get("permissions", [])
        )

        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except (jwt.InvalidSignatureError, jwt.DecodeError, jwt.PyJWTError) as e:
        logger.error(f"JWT verification failed: {e}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> User:
    """
    Get current authenticated user.
    In development mode, returns a default user if no auth is provided.
    """

    # Check for development mode bypass
    if os.getenv("ENVIRONMENT") == "development" or os.getenv("ALLOW_UNAUTHENTICATED") == "true":
        if not credentials:
            return User(
                id=999,
                email="dev@localhost",
                name="Dev User",
                permissions=[
                    "chat.access",
                    "dashboard.access",
                    "trading.access",
                    "portfolio.access",
                    "memory.access",
                    "settings.access",
                ]
            )

    # Check for terminal/CLI requests
    is_localhost = request.client.host in ["127.0.0.1", "localhost", "::1"]
    is_terminal = request.headers.get("x-terminal-request") == "true"

    if is_localhost and is_terminal and not credentials:
        return User(
            id=2,
            email="terminal@localhost",
            name="Terminal User",
            permissions=["chat.access", "dashboard.access", "trading.access"]
        )

    # Verify JWT token
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    return verify_token(credentials)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Optional[User]:
    """
    Optional authentication - returns None if no valid auth.
    Useful for endpoints that work with or without auth.
    """
    if not credentials:
        return None

    try:
        return verify_token(credentials)
    except HTTPException:
        return None


def check_permission(user: User, permission: str) -> bool:
    """Check if user has a specific permission."""
    return permission in user.permissions


def requires_permission(permission: str):
    """
    Dependency to check if user has required permission.

    Usage:
        @router.get("/api/trading/...", dependencies=[Depends(requires_permission("trading.access"))])
        async def trading_endpoint():
            ...
    """
    async def permission_checker(user: User = Depends(get_current_user)):
        if not check_permission(user, permission):
            logger.warning(f"Permission denied: {user.email} attempted to access {permission}")
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {permission}"
            )
        return user

    return permission_checker


# Keep for backward compatibility but not used
class GoogleOAuthMock:
    """Deprecated - kept for import compatibility"""
    @staticmethod
    def generate_mock_user(email: str = None) -> User:
        return User(
            id=999,
            email=email or "dev@localhost",
            name="Dev User",
            permissions=["chat.access", "dashboard.access", "trading.access"]
        )
