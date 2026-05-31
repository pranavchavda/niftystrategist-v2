"""BrokerCredentialStore — where a user's per-broker credentials live.

This abstracts *storage* so brokers don't all have to add their own columns:

* ``UpstoxCredentialStore`` backs onto the existing ``upstox_*`` columns on the
  User row (no migration, no token move — lowest risk).
* ``GenericCredentialStore`` backs onto a single ``broker_accounts`` JSONB table
  (added in the Phase C migration) that every *future* broker shares.

Both encrypt secret values at rest with the existing Fernet helper
(``utils.encryption``), so the encryption story is identical across brokers.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from utils.encryption import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)


class BrokerCredentialStore(ABC):
    """Read/write a user's credentials + token state for one broker."""

    broker: str = "unknown"

    @abstractmethod
    async def get_credentials(self, user_id: int) -> dict[str, Optional[str]]:
        """Return decrypted credential fields (api_key, api_secret, …)."""

    @abstractmethod
    async def set_credentials(self, user_id: int, values: dict[str, str]) -> None:
        """Encrypt + persist the supplied credential fields (partial update)."""

    @abstractmethod
    async def clear(self, user_id: int) -> None:
        """Remove all stored credentials/tokens for this broker."""


class UpstoxCredentialStore(BrokerCredentialStore):
    """Backs onto the legacy ``upstox_*`` columns on ``users``.

    Field keys map to columns:
        api_key      -> upstox_api_key
        api_secret   -> upstox_api_secret
        mobile       -> upstox_mobile
        pin          -> upstox_pin
        totp_secret  -> upstox_totp_secret
    """

    broker = "upstox"

    _FIELD_COLUMNS = {
        "api_key": "upstox_api_key",
        "api_secret": "upstox_api_secret",
        "mobile": "upstox_mobile",
        "pin": "upstox_pin",
        "totp_secret": "upstox_totp_secret",
    }

    async def get_credentials(self, user_id: int) -> dict[str, Optional[str]]:
        from sqlalchemy import select

        from database.models import User
        from database.session import get_db_session

        async with get_db_session() as session:
            user = (
                await session.execute(select(User).where(User.id == user_id))
            ).scalar_one_or_none()
            if user is None:
                return {}
            out: dict[str, Optional[str]] = {}
            for field, column in self._FIELD_COLUMNS.items():
                raw = getattr(user, column, None)
                out[field] = decrypt_token(raw) if raw else None
            return out

    async def set_credentials(self, user_id: int, values: dict[str, str]) -> None:
        from sqlalchemy import select

        from database.models import User
        from database.session import get_db_session

        async with get_db_session() as session:
            user = (
                await session.execute(select(User).where(User.id == user_id))
            ).scalar_one_or_none()
            if user is None:
                raise ValueError(f"User {user_id} not found")
            for field, value in values.items():
                column = self._FIELD_COLUMNS.get(field)
                if column is None:
                    logger.warning("UpstoxCredentialStore: ignoring unknown field %r", field)
                    continue
                setattr(user, column, encrypt_token(value) if value else None)
            await session.commit()

    async def clear(self, user_id: int) -> None:
        from sqlalchemy import select

        from database.models import User
        from database.session import get_db_session

        async with get_db_session() as session:
            user = (
                await session.execute(select(User).where(User.id == user_id))
            ).scalar_one_or_none()
            if user is None:
                return
            for column in self._FIELD_COLUMNS.values():
                setattr(user, column, None)
            # Also clear OAuth token state.
            for column in ("upstox_access_token", "upstox_refresh_token",
                           "upstox_token_expiry", "upstox_user_id"):
                setattr(user, column, None)
            await session.commit()


class GenericCredentialStore(BrokerCredentialStore):
    """Backs onto the shared ``broker_accounts`` JSONB table.

    The table is introduced by the Phase C migration
    (``0NN_add_broker_discriminator.sql``). Until that lands these methods raise
    a clear error, so wiring a new broker fails loudly rather than silently.
    Schema (planned):
        broker_accounts(user_id, broker, credentials JSONB, access_token TEXT,
                        token_expiry TIMESTAMP, broker_user_id TEXT, status TEXT)
    Secret values inside ``credentials`` are Fernet-encrypted per-value.
    """

    def __init__(self, broker: str):
        self.broker = broker

    async def get_credentials(self, user_id: int) -> dict[str, Optional[str]]:
        raise NotImplementedError(
            "GenericCredentialStore requires the broker_accounts table "
            "(Phase C migration). Not yet available."
        )

    async def set_credentials(self, user_id: int, values: dict[str, str]) -> None:
        raise NotImplementedError(
            "GenericCredentialStore requires the broker_accounts table "
            "(Phase C migration). Not yet available."
        )

    async def clear(self, user_id: int) -> None:
        raise NotImplementedError(
            "GenericCredentialStore requires the broker_accounts table "
            "(Phase C migration). Not yet available."
        )


def get_credential_store(broker: str) -> BrokerCredentialStore:
    if broker == "upstox":
        return UpstoxCredentialStore()
    return GenericCredentialStore(broker)
