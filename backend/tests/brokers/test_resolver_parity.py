"""Parity: the relocated resolver must match the OLD logic byte-for-byte.

This runs the *real* ``UpstoxClient._get_instrument_key`` against the *real*
``UpstoxInstrumentResolver`` over a spread of symbol kinds. Unlike the
fake-based conformance suite, this proves the relocation is a faithful
passthrough — it would have caught a dropped resolution step or a changed
ordering. Fully offline (dict + CSV cache only, no token, no network).
"""

import pytest

from brokers.base import InstrumentDescriptor
from brokers.upstox.instruments import UpstoxInstrumentResolver

_SENTINEL = "‹unresolved›"

# Spread: Nifty-50 constants (incl. special chars), indices (constant + cache),
# non-Nifty-50 (cache-dependent), and a guaranteed-unknown.
SYMBOLS = [
    "RELIANCE", "TCS", "INFY", "M&M", "BAJAJ-AUTO",   # hardcoded ISIN map
    "NIFTY 50", "BANK NIFTY", "SENSEX", "INDIA VIX",  # INDEX_KEYS
    "NIFTY", "BANKNIFTY", "FINNIFTY",                  # index-cache lookup
    "IRCTC", "ZOMATO", "DMART", "TATAPOWER",           # cache-dependent equities
    "NOTAREALSYMBOL_XYZ",                               # both must raise
]


def _old(client, symbol):
    try:
        return client._get_instrument_key(symbol)
    except ValueError:
        return _SENTINEL


def _new(resolver, symbol):
    try:
        return resolver.resolve_order_instrument(InstrumentDescriptor(symbol=symbol))
    except ValueError:
        return _SENTINEL


@pytest.fixture(scope="module")
def old_client():
    from services.upstox_client import UpstoxClient

    # No token needed: _get_instrument_key only touches dicts + the CSV cache.
    return UpstoxClient(access_token=None, paper_trading=True, user_id=1)


@pytest.mark.parametrize("symbol", SYMBOLS)
def test_resolution_parity(old_client, symbol):
    resolver = UpstoxInstrumentResolver()
    old = _old(old_client, symbol)
    new = _new(resolver, symbol)
    assert old == new, f"{symbol}: old={old!r} new={new!r}"


def test_dynamic_holdings_cache_parity(old_client):
    """When seeded with the same holdings token, both resolve a CSV-absent symbol
    identically — proving the dynamic-cache step was preserved, not silently
    dropped."""
    sym = "ZZSMECO"  # deliberately not in the CSV cache
    token = "NSE_EQ|INE000SME0001"

    # Old: populate the instance dynamic cache like a portfolio fetch would.
    old_client._dynamic_symbols[sym] = token
    try:
        old = _old(old_client, sym)
    finally:
        old_client._dynamic_symbols.pop(sym, None)

    new = _new(UpstoxInstrumentResolver(dynamic_symbols={sym: token}), sym)

    assert old == token
    assert new == token

    # And without the seed, BOTH fall through identically (to ValueError here).
    assert _old(old_client, sym) == _new(UpstoxInstrumentResolver(), sym)
