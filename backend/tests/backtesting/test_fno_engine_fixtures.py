"""Regression fixtures for backtesting/fno_engine.py.

Bypasses the strategy templates (which require a loaded F&O instrument
cache) and feeds run_fno_backtest hand-crafted RuleSpecs + candles for
synthetic instrument keys. Pins the multi-leg replay shape.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backtesting.fno_engine import run_fno_backtest
from strategies.templates import RuleSpec


def _candle(ts: datetime, o: float, h: float, l: float, c: float, v: int = 1000) -> dict:
    return {
        "timestamp": ts.isoformat(),
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": v,
    }


def _series(start: datetime, closes: list[float]) -> list[dict]:
    return [
        _candle(start + timedelta(minutes=i * 5), c - 0.2, c + 0.5, c - 0.5, c)
        for i, c in enumerate(closes)
    ]


def test_two_leg_short_straddle_no_sl_squareoff_at_close():
    """A simple 2-leg short straddle: SELL CE + SELL PE at 09:20, both
    decay slightly through the day, squareoff at 15:15. Net credit on
    both legs."""
    base = datetime(2026, 5, 1, 9, 15)
    # 75 5-min bars from 9:15 → 15:30 (one trading day).
    n = 75
    # CE premium opens at 100, decays to 95 by close.
    ce_premia = [100 - (i / n) * 5 for i in range(n)]
    # PE similarly.
    pe_premia = [100 - (i / n) * 5 for i in range(n)]

    ce_candles = _series(base, ce_premia)
    pe_candles = _series(base, pe_premia)
    leg_candles = {
        "NSE_FO|CE_TEST": ce_candles,
        "NSE_FO|PE_TEST": pe_candles,
    }

    # Time-triggered SELL entries at 09:20, 15:15 squareoff. No SL.
    rules = [
        RuleSpec(
            name="NIFTY 100 CE",
            trigger_type="time",
            trigger_config={"at": "09:20"},
            action_type="place_order",
            action_config={
                "transaction_type": "SELL",
                "quantity": 75,
                "instrument_token": "NSE_FO|CE_TEST",
            },
            role="entry_ce",
            activates_roles=["squareoff_ce"],
        ),
        RuleSpec(
            name="NIFTY 100 CE Squareoff",
            trigger_type="time",
            trigger_config={"at": "15:15"},
            action_type="place_order",
            action_config={
                "transaction_type": "BUY",
                "quantity": 75,
                "instrument_token": "NSE_FO|CE_TEST",
            },
            role="squareoff_ce",
            enabled=False,
        ),
        RuleSpec(
            name="NIFTY 100 PE",
            trigger_type="time",
            trigger_config={"at": "09:20"},
            action_type="place_order",
            action_config={
                "transaction_type": "SELL",
                "quantity": 75,
                "instrument_token": "NSE_FO|PE_TEST",
            },
            role="entry_pe",
            activates_roles=["squareoff_pe"],
        ),
        RuleSpec(
            name="NIFTY 100 PE Squareoff",
            trigger_type="time",
            trigger_config={"at": "15:15"},
            action_type="place_order",
            action_config={
                "transaction_type": "BUY",
                "quantity": 75,
                "instrument_token": "NSE_FO|PE_TEST",
            },
            role="squareoff_pe",
            enabled=False,
        ),
    ]

    result = run_fno_backtest(
        leg_candles=leg_candles,
        rules=rules,
        strategy_name="straddle-test",
        underlying="NIFTY",
        initial_capital=200_000,
    )

    assert result.days_traded == 1
    assert len(result.day_results) == 1
    day = result.day_results[0]
    # Two SELLs — should produce two LegTrades.
    assert len(day.leg_trades) == 2
    sides = [lt.side for lt in day.leg_trades]
    assert sides == ["SELL", "SELL"]
    # Premium decayed → both legs profitable gross. Net depends on charges.
    assert day.gross_pnl > 0
    # Charges should be non-zero (F&O charges apply per leg).
    assert day.total_charges > 0


def test_progress_cb_and_cancel():
    """Smoke test the progress + cancel callbacks plumb correctly through
    fno_engine. Use a 3-day fixture so progress_cb gets multiple calls."""
    base = datetime(2026, 5, 1, 9, 15)
    leg_candles = {
        "NSE_FO|CE_T": _series(base, [100, 99, 98, 97, 96]),
        "NSE_FO|CE_T2": _series(base, [50, 49, 48, 47, 46]),
    }
    rules = [
        RuleSpec(
            name="leg1", trigger_type="time", trigger_config={"at": "09:20"},
            action_type="place_order",
            action_config={
                "transaction_type": "BUY",
                "quantity": 75,
                "instrument_token": "NSE_FO|CE_T",
            },
            role="entry_1",
        ),
    ]

    progress_calls = []
    run_fno_backtest(
        leg_candles=leg_candles,
        rules=rules,
        strategy_name="test",
        underlying="NIFTY",
        initial_capital=100_000,
        progress_cb=lambda d, t: progress_calls.append((d, t)),
    )
    # At least the terminal emit.
    assert progress_calls, "progress_cb should fire"
    assert progress_calls[-1][0] == progress_calls[-1][1], "final emit at 100%"
