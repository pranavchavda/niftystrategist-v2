"""Canonical instrument descriptor <-> Upstox instrument_key.

This is the *relocation* of the Upstox-specific identity logic that used to be
hidden inside ``UpstoxClient._get_instrument_key`` (equity/index) and
``strategies.fno_utils.resolve_option_instrument`` (F&O). No behavior change —
it just lives behind the broker-neutral ``InstrumentResolver`` protocol now, so
a future broker plugs in its own mapping without touching callers.

Upstox native id formats:
    equity   NSE_EQ|INE002A01018        (exchange_EQ | ISIN)
    index    NSE_INDEX|Nifty 50         (exchange_INDEX | name)
    f&o      NSE_FO|43885               (exchange_FO | exchange_token)
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from brokers.base import (
    InstrumentDescriptor,
    InstrumentResolver,
    OptionType,
)

logger = logging.getLogger(__name__)


class UpstoxInstrumentResolver(InstrumentResolver):
    """Resolve canonical descriptors to Upstox instrument_keys and back.

    ``dynamic_symbols`` optionally seeds the resolver with live, holdings-derived
    symbol->native_id pairs. The old ``UpstoxClient`` built this map lazily from
    a user's positions (``services/upstox_client.py`` ~L1078/L1145) and consulted
    it ahead of the CSV cache. A stateless resolver cannot rebuild it on its own,
    so callers that hold live position tokens (Phase B: portfolio/position flows)
    should either seed it here or pass the token via ``descriptor.native_id``.
    Left empty it matches a *fresh* client, whose dynamic cache is also empty
    until the first portfolio fetch — i.e. the common order-placement path.
    """

    def __init__(self, dynamic_symbols: Optional[dict[str, str]] = None):
        self._dynamic_symbols = {k.upper(): v for k, v in (dynamic_symbols or {}).items()}

    def resolve_order_instrument(self, descriptor: InstrumentDescriptor) -> str:
        # Escape hatch: caller already holds the native key (e.g. resolved from
        # an F&O cache earlier in the same flow).
        if descriptor.native_id:
            return descriptor.native_id

        if descriptor.instrument_kind in ("OPT", "FUT"):
            return self._resolve_fno(descriptor)
        return self._resolve_equity_or_index(descriptor.symbol or descriptor.underlying or "")

    # ── equity / index ───────────────────────────────────────────────────
    def _resolve_equity_or_index(self, symbol: str) -> str:
        """Faithful relocation of ``UpstoxClient._get_instrument_key``.

        Resolution order is identical to the old method:
        index keys -> hardcoded ISIN map -> seeded dynamic (holdings) map ->
        NSE instruments cache -> index-cache lookup.
        """
        if not symbol:
            raise ValueError("Cannot resolve an empty symbol")
        sym = symbol.upper()

        # Pull the canonical constant tables from the existing client so there
        # is a single source of truth (no copy of the ISIN/index dicts).
        from services.upstox_client import UpstoxClient

        if sym in UpstoxClient.INDEX_KEYS:
            return UpstoxClient.INDEX_KEYS[sym]

        isin = UpstoxClient.SYMBOL_TO_ISIN.get(sym)
        if isin:
            return f"NSE_EQ|{isin}"

        # Live, holdings-derived shortcut (matches old _dynamic_symbols step).
        if sym in self._dynamic_symbols:
            return self._dynamic_symbols[sym]

        from services.instruments_cache import (
            get_instrument_key as cache_get_key,
            get_index_key,
        )

        cached_key = cache_get_key(sym)
        if cached_key:
            return cached_key

        index_key = get_index_key(symbol)
        if index_key:
            return index_key

        raise ValueError(
            f"No instrument mapping for symbol '{symbol}'. "
            f"Use nf-quote --search to find valid NSE symbols."
        )

    # ── F&O ──────────────────────────────────────────────────────────────
    def _resolve_fno(self, descriptor: InstrumentDescriptor) -> str:
        underlying = descriptor.underlying or descriptor.symbol
        if not underlying:
            raise ValueError("F&O descriptor requires an underlying")
        if descriptor.instrument_kind != "OPT":
            raise ValueError(
                f"Only option (OPT) F&O resolution is supported here, got "
                f"{descriptor.instrument_kind}"
            )
        if descriptor.expiry is None or descriptor.strike is None or descriptor.option_type is None:
            raise ValueError(
                "Option descriptor requires expiry, strike and option_type"
            )

        from strategies.fno_utils import resolve_option_instrument

        info = resolve_option_instrument(
            underlying=underlying,
            expiry=descriptor.expiry.isoformat(),
            strike=descriptor.strike,
            option_type=descriptor.option_type.value,
        )
        key = info.get("instrument_key")
        if not key:
            raise ValueError(
                f"Resolved option for {descriptor.describe()} has no instrument_key"
            )
        return key

    # ── reverse ──────────────────────────────────────────────────────────
    def to_canonical(self, native_id: str) -> InstrumentDescriptor:
        """Best-effort reverse mapping. Always preserves ``native_id`` so the
        descriptor round-trips back to the same key even when we can't fully
        reconstruct symbol/strike/expiry."""
        if not native_id or "|" not in native_id:
            return InstrumentDescriptor(symbol=native_id, native_id=native_id)

        prefix, _, rhs = native_id.partition("|")
        exchange = prefix.split("_")[0] if "_" in prefix else "NSE"

        if prefix.endswith("_INDEX"):
            return InstrumentDescriptor(
                exchange=exchange, symbol=rhs, instrument_kind="IDX",
                native_id=native_id,
            )

        if prefix.endswith("_EQ"):
            # symbol may be None (cache has no ISIN->symbol reverse); native_id
            # stays authoritative so the descriptor still round-trips.
            return InstrumentDescriptor(
                exchange=exchange, symbol=self._symbol_from_isin(rhs),
                instrument_kind="EQ", native_id=native_id,
            )

        if prefix.endswith("_FO"):
            return self._fno_from_native(native_id, exchange)

        return InstrumentDescriptor(symbol=rhs, native_id=native_id)

    def _symbol_from_isin(self, isin: str) -> Optional[str]:
        """Reverse ISIN -> human symbol, best-effort.

        Only the hardcoded Nifty-50 map is reliably reversible; the instruments
        cache exposes symbol->ISIN (``get_isin``) but no reverse index. When the
        symbol can't be recovered we return None (honest) rather than echoing the
        ISIN — ``native_id`` on the descriptor remains authoritative, so the key
        still round-trips regardless.
        """
        from services.upstox_client import UpstoxClient

        for sym, mapped in UpstoxClient.SYMBOL_TO_ISIN.items():
            if mapped == isin:
                return sym
        return None

    def _fno_from_native(self, native_id: str, exchange: str) -> InstrumentDescriptor:
        """Look the F&O contract up in the options cache by instrument_key."""
        try:
            from strategies.fno_utils import _load_cache  # type: ignore

            cache = _load_cache()
            for data in cache.values():
                if data.get("instrument_key") == native_id:
                    expiry = _parse_expiry(data.get("expiry"))
                    opt = data.get("option_type")
                    return InstrumentDescriptor(
                        exchange=exchange,
                        instrument_kind="OPT",
                        underlying=data.get("name"),
                        expiry=expiry,
                        strike=float(data["strike"]) if data.get("strike") else None,
                        option_type=OptionType(opt) if opt in ("CE", "PE") else None,
                        native_id=native_id,
                    )
        except Exception as e:  # pragma: no cover - cache best-effort
            logger.debug("F&O reverse lookup failed for %s: %s", native_id, e)
        return InstrumentDescriptor(
            exchange=exchange, instrument_kind="OPT", native_id=native_id,
        )


def _parse_expiry(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d%b%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None
