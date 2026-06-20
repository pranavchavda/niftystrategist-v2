"""Tests for same-day delivery (intraday→delivery conversion) visibility.

Root cause (fixed 2026-06-21): get_portfolio() reconciled delivery SELLS
(product=D, qty<0 → subtract from holdings) and intraday positions (product=I),
but silently dropped delivery BUYS (product=D, qty>0). A same-day I→D conversion
like COFORGE — invisible in the holdings API until T+1 settlement — therefore
vanished from the portfolio entirely during the intraday window it was being
actively carried under a trailing stop.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import services.upstox_client as uc_mod
from services.upstox_client import UpstoxClient


def _holding(sym, qty, avg=100.0, ltp=110.0, close=105.0, token=None):
    return SimpleNamespace(
        tradingsymbol=sym, trading_symbol=sym, quantity=qty,
        average_price=avg, last_price=ltp, close_price=close,
        instrument_token=token or f"NSE_EQ|{sym}",
    )


def _position(sym, qty, product, avg=100.0, ltp=110.0, close=105.0,
              pnl=None, exchange="NSE_EQ", instrument_type="EQ"):
    return SimpleNamespace(
        tradingsymbol=sym, trading_symbol=sym, quantity=qty, product=product,
        average_price=avg, last_price=ltp, close_price=close, pnl=pnl,
        exchange=exchange, instrument_type=instrument_type,
        instrument_token=f"{exchange}|{sym}", buy_price=avg,
    )


def _make_client_with(holdings, positions):
    client = UpstoxClient(access_token="tok", user_id=1, paper_trading=False)

    class _FakePortfolioApi:
        def __init__(self, *_a, **_k):
            pass

        def get_holdings(self, *_a, **_k):
            return SimpleNamespace(data=holdings)

        def get_positions(self, *_a, **_k):
            return SimpleNamespace(data=positions)

    class _FakeUserApi:
        def __init__(self, *_a, **_k):
            pass

        def get_user_fund_margin(self, *_a, **_k):
            raise RuntimeError("funds API unavailable in test")  # falls back to cache

    async def _passthrough(fn):
        return fn()

    p_api = patch.object(uc_mod.upstox_client, "PortfolioApi", _FakePortfolioApi)
    u_api = patch.object(uc_mod.upstox_client, "UserApi", _FakeUserApi)
    a_cli = patch.object(uc_mod.upstox_client, "ApiClient", lambda *_a, **_k: object())
    retry = patch.object(client, "_call_with_token_retry", new=AsyncMock(side_effect=_passthrough))
    return client, (p_api, u_api, a_cli, retry)


async def _run(client, patches):
    for p in patches:
        p.start()
    try:
        return await client.get_portfolio()
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_same_day_conversion_surfaces():
    # COFORGE converted I→D today: present in positions (D, +174), absent from holdings.
    client, patches = _make_client_with(
        holdings=[_holding("ITC", 122)],
        positions=[_position("COFORGE", 174, "D", avg=1440.0, ltp=1450.0, pnl=1740.0)],
    )
    pf = await _run(client, patches)
    syms = {p.symbol: p for p in pf.positions}
    assert "COFORGE" in syms, "converted delivery position must be visible"
    assert syms["COFORGE"].quantity == 174
    assert syms["COFORGE"].product == "D"
    assert syms["COFORGE"].pnl == 1740.0  # uses Upstox native pnl


@pytest.mark.asyncio
async def test_fresh_delivery_buy_already_in_holdings_not_double_counted():
    # A fresh same-day delivery buy appears in BOTH holdings (pre-settlement) and
    # positions (D, qty>0). It must be counted once (from holdings), not twice.
    client, patches = _make_client_with(
        holdings=[_holding("RELIANCE", 100, avg=1300.0)],
        positions=[_position("RELIANCE", 100, "D", avg=1300.0)],
    )
    pf = await _run(client, patches)
    rel = [p for p in pf.positions if p.symbol == "RELIANCE"]
    assert len(rel) == 1, "must not double-count a buy present in holdings"
    assert rel[0].quantity == 100


@pytest.mark.asyncio
async def test_delivery_sell_still_subtracts():
    # Regression: a delivery SELL today (D, qty<0) still reduces the holding.
    client, patches = _make_client_with(
        holdings=[_holding("TCS", 50)],
        positions=[_position("TCS", -20, "D")],
    )
    pf = await _run(client, patches)
    tcs = [p for p in pf.positions if p.symbol == "TCS"]
    assert len(tcs) == 1
    assert tcs[0].quantity == 30  # 50 held - 20 sold


@pytest.mark.asyncio
async def test_fno_legs_not_misbucketed_as_delivery():
    # An options leg (D product on FO exchange) must go to fno_positions, never
    # into the new delivery-conversion branch.
    client, patches = _make_client_with(
        holdings=[],
        positions=[_position("NIFTY2662324100CE", 130, "D",
                             exchange="NSE_FO", instrument_type="OPTIDX")],
    )
    pf = await _run(client, patches)
    assert pf.positions == [] or all(p.symbol != "NIFTY2662324100CE" for p in pf.positions)
    assert len(pf.fno_positions) == 1


# ── Snapshot delivery-carry classification ───────────────────────────────────

def _rule(rule_id, symbol, enabled=True):
    return SimpleNamespace(
        id=rule_id, symbol=symbol, enabled=enabled, action_config={},
        trigger_type="trailing_stop", trigger_config={},
    )


def _pos(symbol):
    return SimpleNamespace(symbol=symbol, quantity=10, average_price=100.0,
                           current_price=110.0, pnl=100.0, pnl_percentage=10.0,
                           product="D")


def test_classify_managed_vs_untracked():
    from services.trading_snapshot import _classify_delivery_carries
    delivery = [_pos("COFORGE"), _pos("HCLTECH"), _pos("RANDOMINV")]
    rules = [_rule(4547, "COFORGE"), _rule(4523, "HCLTECH")]
    managed, untracked = _classify_delivery_carries(delivery, rules)
    assert {p.symbol for p, _ in managed} == {"COFORGE", "HCLTECH"}
    assert {p.symbol for p, _ in untracked} == {"RANDOMINV"}
    # the protecting rule travels with the position
    cof = next(prot for p, prot in managed if p.symbol == "COFORGE")
    assert cof[0].id == 4547


def test_classify_disabled_rule_is_untracked():
    from services.trading_snapshot import _classify_delivery_carries
    managed, untracked = _classify_delivery_carries(
        [_pos("ITC")], [_rule(1, "ITC", enabled=False)]
    )
    assert managed == []
    assert untracked[0][0].symbol == "ITC"


def test_classify_normalizes_eq_suffix():
    from services.trading_snapshot import _classify_delivery_carries
    # rule symbol carries the -EQ series suffix; position does not
    managed, _ = _classify_delivery_carries([_pos("HCLTECH")], [_rule(1, "HCLTECH-EQ")])
    assert managed and managed[0][0].symbol == "HCLTECH"
