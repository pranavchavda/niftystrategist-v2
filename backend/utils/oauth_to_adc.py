"""
OAuth to ADC (Application Default Credentials) Converter

Converts user OAuth tokens from database to ADC format for MCP servers.
This allows MCP server subprocesses to use per-user credentials instead of
system-wide ADC.
"""

import os
import json
import tempfile
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class OAuthToADC:
    """Helper class to convert OAuth tokens to ADC format for MCP servers"""

    @staticmethod
    def create_adc_file(
        user_id: str,
        access_token: str,
        refresh_token: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ) -> str:
        """
        Create a temporary ADC credentials file from OAuth tokens.

        Args:
            user_id: User identifier (for temp file naming)
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            client_id: Google OAuth client ID (defaults to env var)
            client_secret: Google OAuth client secret (defaults to env var)

        Returns:
            Path to the temporary ADC credentials file

        Raises:
            ValueError: If client_id or client_secret not provided and not in env
        """
        # Use environment variables if not provided
        if not client_id:
            client_id = os.getenv("GOOGLE_CLIENT_ID")
        if not client_secret:
            client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise ValueError(
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in environment "
                "or passed as parameters"
            )

        # Create ADC-format credentials
        # Format: https://cloud.google.com/docs/authentication/application-default-credentials
        adc_credentials = {
            "type": "authorized_user",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "token_uri": "https://oauth2.googleapis.com/token"  # Required for token refresh
            # Note: access_token is optional in ADC format
            # The refresh_token is what's important for long-lived credentials
        }

        # Create temporary file in /tmp with user-specific name
        # Use a secure temp file to avoid race conditions
        safe_user_id = user_id.replace("@", "_at_").replace(".", "_")
        temp_dir = Path("/tmp/espressobot_adc")
        temp_dir.mkdir(exist_ok=True, mode=0o700)  # Only owner can access

        temp_file_path = temp_dir / f"adc_{safe_user_id}.json"

        # Write credentials to file with secure permissions
        with open(temp_file_path, 'w') as f:
            json.dump(adc_credentials, f, indent=2)

        # Set file permissions to read/write for owner only
        os.chmod(temp_file_path, 0o600)

        logger.info(f"Created ADC credentials file for user {user_id}: {temp_file_path}")

        return str(temp_file_path)

    @staticmethod
    def cleanup_adc_file(adc_file_path: str) -> None:
        """
        Clean up temporary ADC credentials file.

        Args:
            adc_file_path: Path to the ADC credentials file to delete
        """
        try:
            if os.path.exists(adc_file_path):
                os.remove(adc_file_path)
                logger.info(f"Cleaned up ADC credentials file: {adc_file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up ADC file {adc_file_path}: {e}")

    @staticmethod
    def get_adc_env(adc_file_path: str) -> Dict[str, str]:
        """
        Get environment variables dict with GOOGLE_APPLICATION_CREDENTIALS set.

        Args:
            adc_file_path: Path to the ADC credentials file

        Returns:
            Dict with current environment plus GOOGLE_APPLICATION_CREDENTIALS
        """
        env = os.environ.copy()
        env['GOOGLE_APPLICATION_CREDENTIALS'] = adc_file_path
        return env


# Convenience function for quick usage
def create_adc_from_oauth(
    user_id: str,
    access_token: str,
    refresh_token: str
) -> tuple[str, Dict[str, str]]:
    """
    Create ADC file and return both path and env vars.

    Returns:
        Tuple of (adc_file_path, env_dict)
    """
    converter = OAuthToADC()
    adc_file = converter.create_adc_file(user_id, access_token, refresh_token)
    env = converter.get_adc_env(adc_file)
    return adc_file, env
