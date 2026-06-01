"""Broker registry — resolve a user to their broker's account/auth/resolver.

Adding a broker = build a ``BrokerBundle`` and call ``register_broker(...)``
once at import time. Nothing else in the codebase needs to know the broker's
name.

The user's broker is read from ``user.broker`` (a discriminator column added in
the Phase C migration). Until that column exists, ``getattr`` falls back to
``"upstox"`` so the whole app keeps working unchanged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from brokers.base import BrokerAccount, BrokerAuth, InstrumentResolver

DEFAULT_BROKER = "upstox"

# An async builder that, given a user_id, returns a ready BrokerAccount.
AccountBuilder = Callable[[int], Awaitable[BrokerAccount]]


@dataclass(frozen=True)
class BrokerBundle:
    """Everything the registry needs to serve one broker."""

    broker: str
    build_account: AccountBuilder
    auth: BrokerAuth
    resolver: InstrumentResolver


_BROKERS: dict[str, BrokerBundle] = {}


def register_broker(bundle: BrokerBundle) -> None:
    _BROKERS[bundle.broker] = bundle


def available_brokers() -> list[str]:
    return sorted(_BROKERS.keys())


def _bundle(broker: str) -> BrokerBundle:
    bundle = _BROKERS.get(broker)
    if bundle is None:
        raise KeyError(
            f"Unknown broker '{broker}'. Registered: {available_brokers()}"
        )
    return bundle


def _broker_and_user_id(user: Any, broker: Optional[str]) -> tuple[str, int]:
    """Accept either a User ORM object or a bare int user_id."""
    if isinstance(user, int):
        return (broker or DEFAULT_BROKER), user
    user_id = getattr(user, "id", None)
    if user_id is None:
        raise ValueError("user must be a User with .id or an int user_id")
    resolved = broker or getattr(user, "broker", None) or DEFAULT_BROKER
    return resolved, int(user_id)


async def get_broker_account(
    user: Any, *, broker: Optional[str] = None
) -> BrokerAccount:
    """Return the user's ``BrokerAccount`` for account-specific operations."""
    broker_id, user_id = _broker_and_user_id(user, broker)
    return await _bundle(broker_id).build_account(user_id)


def get_broker_auth(user: Any, *, broker: Optional[str] = None) -> BrokerAuth:
    broker_id, _ = _broker_and_user_id(user, broker)
    return _bundle(broker_id).auth


def get_instrument_resolver(broker: str = DEFAULT_BROKER) -> InstrumentResolver:
    return _bundle(broker).resolver


# ──────────────────────────────────────────────────────────────────────────
# Default registrations (Upstox + Paper)
# ──────────────────────────────────────────────────────────────────────────
def _register_defaults() -> None:
    from brokers.upstox.account import UpstoxBrokerAccount
    from brokers.upstox.auth import UpstoxAuth
    from brokers.upstox.instruments import UpstoxInstrumentResolver
    from brokers.paper.account import PaperBroker

    upstox_auth = UpstoxAuth()
    upstox_resolver = UpstoxInstrumentResolver()

    async def _build_upstox(user_id: int) -> BrokerAccount:
        from services.upstox_client import UpstoxClient

        token = await upstox_auth.get_access_token(user_id)
        client = UpstoxClient(
            access_token=token, paper_trading=False, user_id=user_id,
        )
        return UpstoxBrokerAccount(client, upstox_resolver)

    register_broker(
        BrokerBundle(
            broker="upstox",
            build_account=_build_upstox,
            auth=upstox_auth,
            resolver=upstox_resolver,
        )
    )

    async def _build_paper(user_id: int) -> BrokerAccount:
        return PaperBroker(user_id, price_provider=_default_price_provider)

    register_broker(
        BrokerBundle(
            broker="paper",
            build_account=_build_paper,
            auth=upstox_auth,            # paper reuses Upstox login for market data
            resolver=upstox_resolver,    # canonical mapping is shared (market data is Upstox)
        )
    )

    # Kotak Neo — pure REST (httpx + pyotp), no broker SDK. Registered
    # defensively so a Kotak import issue never breaks upstox/paper. Reachable
    # via get_broker_account(user, broker="kotak") until the Phase C `broker`
    # column routes real users.
    try:
        from brokers.kotak.account import KotakBrokerAccount
        from brokers.kotak.auth import KotakAuth
        from brokers.kotak.instruments import KotakInstrumentResolver

        kotak_auth = KotakAuth()
        kotak_resolver = KotakInstrumentResolver()

        async def _build_kotak(user_id: int) -> BrokerAccount:
            session = await kotak_auth.get_session(user_id)
            return KotakBrokerAccount(session, kotak_resolver)

        register_broker(
            BrokerBundle(
                broker="kotak",
                build_account=_build_kotak,
                auth=kotak_auth,
                resolver=kotak_resolver,
            )
        )
    except Exception as e:  # pragma: no cover - defensive
        import logging

        logging.getLogger(__name__).warning("Kotak broker not registered: %s", e)


async def _default_price_provider(symbol: str) -> float:
    """Live LTP from the shared market-data feed (analytics token)."""
    from services.upstox_client import UpstoxClient

    token = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "").strip() or os.environ.get(
        "UPSTOX_ACCESS_TOKEN", ""
    )
    client = UpstoxClient(access_token=token, paper_trading=False, user_id=1)
    quote = await client.get_quote(symbol)
    return float(quote.get("last_price") or quote.get("ltp") or 0)


_register_defaults()
