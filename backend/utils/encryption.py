"""Encryption utilities for sensitive data like OAuth tokens."""

import os
import logging
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Global Fernet instance
_fernet: Optional[Fernet] = None


def get_fernet() -> Fernet:
    """Get or create the Fernet encryption instance."""
    global _fernet
    if _fernet is None:
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            # Generate a key for development (not for production!)
            logger.warning(
                "ENCRYPTION_KEY not set - generating temporary key. "
                "Set ENCRYPTION_KEY in .env for production!"
            )
            key = Fernet.generate_key().decode()

        # Ensure key is bytes
        if isinstance(key, str):
            key = key.encode()

        _fernet = Fernet(key)

    return _fernet


def encrypt_token(token: str) -> str:
    """
    Encrypt a token for secure storage.

    Args:
        token: Plain text token

    Returns:
        Base64-encoded encrypted token
    """
    if not token:
        return ""

    fernet = get_fernet()
    encrypted = fernet.encrypt(token.encode())
    return encrypted.decode()


def decrypt_token(encrypted_token: str) -> Optional[str]:
    """
    Decrypt a stored token.

    Args:
        encrypted_token: Base64-encoded encrypted token

    Returns:
        Plain text token, or None if decryption fails
    """
    if not encrypted_token:
        return None

    try:
        fernet = get_fernet()
        decrypted = fernet.decrypt(encrypted_token.encode())
        return decrypted.decode()
    except InvalidToken:
        logger.error("Failed to decrypt token - invalid or corrupted")
        return None
    except Exception as e:
        logger.error(f"Token decryption error: {e}")
        return None


def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key for .env file."""
    return Fernet.generate_key().decode()
