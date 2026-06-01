"""Canonical instrument descriptor <-> Kotak Neo (exchange_segment, trading_symbol).

Kotak's order API identifies an instrument by TWO fields — ``es`` (exchange
segment, e.g. ``nse_cm``) and ``ts`` (trading symbol, e.g. ``RELIANCE-EQ``) —
unlike Upstox's single ``instrument_token``. The ``InstrumentResolver`` contract
returns a single string, so we encode the Kotak identity as ``"es:ts"`` and
provide ``resolve_pair()`` for the account to get the two fields back.

Equity resolution is exact (``{SYMBOL}-EQ`` on ``nse_cm``/``bse_cm``). F&O
resolution needs Kotak's scrip master (``search_scrip``) — deferred; it raises a
clear error so callers fail loudly rather than mis-resolving. hf-tools never did
canonical resolution at all (the user typed the full Kotak symbol), so this is
net-new on top of the repo.
"""

from __future__ import annotations

from typing import Tuple

from brokers.base import InstrumentDescriptor, InstrumentResolver

# Canonical exchange + segment -> Kotak exchange-segment code.
_EQ_SEGMENT = {"NSE": "nse_cm", "BSE": "bse_cm"}
_FO_SEGMENT = {"NSE": "nse_fo", "BSE": "bse_fo"}
# Reverse, for to_canonical.
_SEGMENT_EXCHANGE = {
    "nse_cm": ("NSE", "EQ"), "bse_cm": ("BSE", "EQ"),
    "nse_fo": ("NSE", "OPT"), "bse_fo": ("BSE", "OPT"),
}


class KotakInstrumentResolver(InstrumentResolver):
    """Resolve canonical descriptors to Kotak ``es:ts`` identifiers and back."""

    def resolve_pair(self, descriptor: InstrumentDescriptor) -> Tuple[str, str]:
        """Return ``(exchange_segment, trading_symbol)`` for an order."""
        if descriptor.native_id and ":" in descriptor.native_id:
            es, _, ts = descriptor.native_id.partition(":")
            return es, ts

        exchange = (descriptor.exchange or "NSE").upper()

        if descriptor.instrument_kind in ("OPT", "FUT"):
            # Kotak F&O trading symbols (e.g. "BANKNIFTY2526400CE") come from its
            # scrip master, not derivable here. Deferred to the F&O slice.
            raise ValueError(
                "Kotak F&O instrument resolution not yet supported "
                "(needs Kotak scrip master / search_scrip). "
                f"descriptor={descriptor.describe()}"
            )

        symbol = (descriptor.symbol or "").upper()
        if not symbol:
            raise ValueError("Cannot resolve an empty symbol for Kotak")
        es = _EQ_SEGMENT.get(exchange)
        if not es:
            raise ValueError(f"Unsupported exchange '{exchange}' for Kotak equity")
        # Kotak cash-market equity trading symbols are suffixed "-EQ".
        ts = symbol if symbol.endswith("-EQ") else f"{symbol}-EQ"
        return es, ts

    def resolve_order_instrument(self, descriptor: InstrumentDescriptor) -> str:
        es, ts = self.resolve_pair(descriptor)
        return f"{es}:{ts}"

    def to_canonical(self, native_id: str) -> InstrumentDescriptor:
        if not native_id or ":" not in native_id:
            return InstrumentDescriptor(symbol=native_id, native_id=native_id)
        es, _, ts = native_id.partition(":")
        exchange, kind = _SEGMENT_EXCHANGE.get(es, ("NSE", "EQ"))
        if kind == "EQ":
            symbol = ts[:-3] if ts.upper().endswith("-EQ") else ts
            return InstrumentDescriptor(
                exchange=exchange, symbol=symbol, instrument_kind="EQ",
                native_id=native_id,
            )
        # F&O: keep native_id authoritative; symbol parsing deferred.
        return InstrumentDescriptor(
            exchange=exchange, instrument_kind="OPT", native_id=native_id,
        )
