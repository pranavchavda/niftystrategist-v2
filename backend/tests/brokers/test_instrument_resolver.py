"""Instrument-identity round-trips for the Upstox resolver."""

import pytest

from brokers.base import InstrumentDescriptor, OptionType
from brokers.upstox.instruments import UpstoxInstrumentResolver

resolver = UpstoxInstrumentResolver()


def test_equity_resolves_to_isin_key():
    key = resolver.resolve_order_instrument(InstrumentDescriptor(symbol="RELIANCE"))
    assert key == "NSE_EQ|INE002A01018"


def test_equity_round_trip_preserves_native_id():
    key = resolver.resolve_order_instrument(InstrumentDescriptor(symbol="TCS"))
    back = resolver.to_canonical(key)
    assert back.native_id == key
    assert back.instrument_kind == "EQ"
    # Re-resolving the recovered descriptor returns the same native id.
    assert resolver.resolve_order_instrument(back) == key


def test_index_resolves_and_round_trips():
    key = resolver.resolve_order_instrument(InstrumentDescriptor(symbol="NIFTY 50"))
    assert key == "NSE_INDEX|Nifty 50"
    back = resolver.to_canonical(key)
    assert back.instrument_kind == "IDX"
    assert back.native_id == key


def test_native_id_escape_hatch():
    desc = InstrumentDescriptor(instrument_kind="OPT", native_id="NSE_FO|43885")
    assert resolver.resolve_order_instrument(desc) == "NSE_FO|43885"


def test_unknown_symbol_raises():
    with pytest.raises(ValueError):
        resolver.resolve_order_instrument(InstrumentDescriptor(symbol="NOTAREALSYMBOL_XYZ"))


def test_option_descriptor_requires_fields():
    # Missing strike/expiry/option_type must fail clearly, not silently mis-resolve.
    with pytest.raises(ValueError):
        resolver.resolve_order_instrument(
            InstrumentDescriptor(instrument_kind="OPT", underlying="NIFTY")
        )


def test_to_canonical_handles_bare_id():
    # No pipe separator -> degrade gracefully, never crash.
    back = resolver.to_canonical("WEIRD")
    assert back.native_id == "WEIRD"
