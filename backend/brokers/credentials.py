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
    """Backs onto the shared ``broker_accounts`` JSONB table (migration 046).

    One row per ``(user_id, broker)``. ``credentials`` holds the broker's
    credential fields Fernet-encrypted **per value**; ``session`` holds the
    broker-minted session blob (multi-field for Kotak), encrypted as a whole
    under ``{"_enc": <fernet>}`` since session tokens grant account access.
    """

    def __init__(self, broker: str):
        self.broker = broker

    async def _get_row(self, session, user_id: int, *, create: bool = False):
        from sqlalchemy import select

        from database.models import UserBrokerAccount

        row = (
            await session.execute(
                select(UserBrokerAccount).where(
                    UserBrokerAccount.user_id == user_id,
                    UserBrokerAccount.broker == self.broker,
                )
            )
        ).scalar_one_or_none()
        if row is None and create:
            row = UserBrokerAccount(user_id=user_id, broker=self.broker,
                                    credentials={}, status="connected")
            session.add(row)
        return row

    async def get_credentials(self, user_id: int) -> dict[str, Optional[str]]:
        from database.session import get_db_session

        async with get_db_session() as session:
            row = await self._get_row(session, user_id)
            if row is None or not row.credentials:
                return {}
            out: dict[str, Optional[str]] = {}
            for field, enc in (row.credentials or {}).items():
                out[field] = decrypt_token(enc) if enc else None
            return out

    async def set_credentials(self, user_id: int, values: dict[str, str]) -> None:
        from database.session import get_db_session

        async with get_db_session() as session:
            row = await self._get_row(session, user_id, create=True)
            # Partial update: merge into the existing (encrypted) credential map.
            creds = dict(row.credentials or {})
            for field, value in values.items():
                creds[field] = encrypt_token(value) if value else None
            row.credentials = creds
            # Reattach so SQLAlchemy tracks the JSON mutation.
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(row, "credentials")
            await session.commit()

    async def clear(self, user_id: int) -> None:
        from database.session import get_db_session

        async with get_db_session() as session:
            row = await self._get_row(session, user_id)
            if row is not None:
                await session.delete(row)
                await session.commit()

    # ── session blob (broker-minted, encrypted as a whole) ────────────────
    async def get_session(self, user_id: int) -> Optional[dict]:
        import json

        from database.session import get_db_session

        async with get_db_session() as session:
            row = await self._get_row(session, user_id)
            blob = row.session if row is not None else None
            if not blob:
                return None
            if isinstance(blob, dict) and "_enc" in blob:
                try:
                    return json.loads(decrypt_token(blob["_enc"]))
                except Exception:
                    logger.warning("GenericCredentialStore: failed to decrypt session for user %s", user_id)
                    return None
            return blob if isinstance(blob, dict) else None

    async def set_session(self, user_id: int, session_blob: dict,
                          *, token_expiry=None, broker_user_id: Optional[str] = None) -> None:
        import json

        from database.session import get_db_session

        async with get_db_session() as session:
            row = await self._get_row(session, user_id, create=True)
            row.session = {"_enc": encrypt_token(json.dumps(session_blob))}
            if token_expiry is not None:
                row.token_expiry = token_expiry
            if broker_user_id is not None:
                row.broker_user_id = broker_user_id
            row.status = "connected"
            await session.commit()


def get_credential_store(broker: str) -> BrokerCredentialStore:
    if broker == "upstox":
        return UpstoxCredentialStore()
    return GenericCredentialStore(broker)
