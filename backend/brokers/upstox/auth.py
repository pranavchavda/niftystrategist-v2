"""UpstoxAuth — Upstox token lifecycle behind the broker-neutral ``BrokerAuth``.

Wraps the existing, battle-tested ``api.upstox_oauth`` helpers
(``get_user_upstox_token`` with TOTP auto-refresh, ``_build_upstox_auth_url``).
Reads the existing ``upstox_*`` columns on the User row — no token migration.

Upstox uses an OAuth (+ optional TOTP daily refresh) flow, so its
``login_descriptor`` returns ``flow="oauth"`` with a redirect URL. The
``credential_fields`` describe the per-user API key/secret + optional TOTP
inputs that the Settings form already collects.
"""

from __future__ import annotations

import logging
from typing import Optional

from brokers.base import BrokerAuth, CredentialField, LoginDescriptor

logger = logging.getLogger(__name__)


_CREDENTIAL_FIELDS: tuple[CredentialField, ...] = (
    CredentialField("api_key", "API Key", secret=True, required=True,
                    help_text="From the Upstox Developer Console."),
    CredentialField("api_secret", "API Secret", secret=True, required=True,
                    help_text="From the Upstox Developer Console."),
    # Optional TOTP auto-login — enables silent daily token refresh.
    CredentialField("mobile", "Mobile Number", secret=True, required=False,
                    help_text="Upstox login mobile (for TOTP auto-refresh)."),
    CredentialField("pin", "PIN", secret=True, required=False,
                    help_text="Upstox login PIN (for TOTP auto-refresh)."),
    CredentialField("totp_secret", "TOTP Secret", secret=True, required=False,
                    help_text="Authenticator secret (for TOTP auto-refresh)."),
)


class UpstoxAuth(BrokerAuth):
    broker = "upstox"

    async def get_access_token(self, user_id: int, *, force_refresh: bool = False) -> Optional[str]:
        # Single source of truth for decrypt + expiry detection + TOTP refresh.
        from api.upstox_oauth import get_user_upstox_token

        return await get_user_upstox_token(user_id, force_refresh=force_refresh)

    def credential_fields(self) -> tuple[CredentialField, ...]:
        return _CREDENTIAL_FIELDS

    async def login_descriptor(self, user_id: int) -> LoginDescriptor:
        auth_url: Optional[str] = None
        try:
            from api.upstox_oauth import _build_upstox_auth_url

            auth_url = await _build_upstox_auth_url(user_id)
        except Exception as e:
            # Missing per-user API key etc. — the form still needs to render so
            # the user can supply credentials; surface the reason in notes.
            logger.debug("Could not build Upstox auth url for user %s: %s", user_id, e)

        return LoginDescriptor(
            broker="upstox",
            flow="oauth",
            credential_fields=_CREDENTIAL_FIELDS,
            auth_url=auth_url,
            notes=(
                "Connect via Upstox OAuth. Optionally add TOTP credentials for "
                "automatic daily token refresh (~3:30 AM IST)."
            ),
        )
