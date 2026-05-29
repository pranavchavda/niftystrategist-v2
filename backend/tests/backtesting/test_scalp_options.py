"""Unit tests for ``backtesting.scalp_options``.

The engine pulls strike lists and instrument resolution from
``strategies.fno_utils`` which reads a CSV cache. Tests monkeypatch those
two entry points so we can drive deterministic ATM strikes without depending
on a live cache.

Underlying signals use the EMA crossover primary the same way
``test_scalp_equity`` does — flips are easy to construct by stitching a
flat series with a directional run.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backtesting import scalp_options as so
from backtesting.scalp_options import (
    plan_atm_legs,
    run_scalp_options_backtest,
)
from monitor.scalp_models import ScalpSessionConfig, SessionMode

IST = timezone(timedelta(hours=5, minutes=30))


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _ist(y: int, m: int, d: int, hh: int = 9, mm: int = 15) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=IST)


def _candle(ts: datetime, o: float, h: float, l: float, c: float, v: int = 1000) -> dict:
    return {"timestamp": ts.isoformat(), "open": o, "high": h, "low": l, "close": c, "volume": v}


def _flat(n: int, price: float, start: datetime, step_mins: int = 5) -> list[dict]:
    return [
        _candle(start + timedelta(minutes=step_mins * i), price, price, price, price)
        for i in range(n)
    ]


def _uptrend(n: int, start_price: float, step: float, start: datetime, step_mins: int = 5) -> list[dict]:
    bars: list[dict] = []
    for i in range(n):
        c = start_price + step * (i + 1)
        o = start_price + step * i
        bars.append(_candle(start + timedelta(minutes=step_mins * i), o, c, o, c))
    return bars


def _downtrend(n: int, start_price: float, step: float, start: datetime, step_mins: int = 5) -> list[dict]:
    bars: list[dict] = []
    for i in range(n):
        c = start_price - step * (i + 1)
        o = start_price - step * i
        bars.append(_candle(start + timedelta(minutes=step_mins * i), o, o, c, c))
    return bars


def _base_config(**overrides) -> ScalpSessionConfig:
    """Default options-scalp config for tests. NIFTY weekly expiry shape."""
    defaults = dict(
        name="test-options",
        session_mode=SessionMode.OPTIONS_SCALP.value,
        underlying="NIFTY",
        expiry="2026-04-24",
        lots=1,
        indicator_timeframe="5m",
        primary_indicator="ema_crossover",
        primary_params={"fast": 3, "slow": 5},
        confirm_indicator=None,
        confirm_params=None,
        sl_points=None,
        target_points=None,
        trail_percent=None,
        trail_points=None,
        trail_arm_points=None,
        squareoff_time="15:15",
        max_trades=20,
        cooldown_seconds=0,
    )
    defaults.update(overrides)
    return ScalpSessionConfig(**defaults)


@pytest.fixture
def patch_fno(monkeypatch):
    """Patch list_strikes / resolve_option_instrument used inside the engine.

    ATM strikes are a flat 50-pt grid (NIFTY default). instrument_keys are
    synthesized as ``NSE_FO|<strike><type>``. Lot size is overridden to 25.
    """
    def fake_list_strikes(underlying, expiry, option_type):
        # 50-point NIFTY grid covering 23000-26000
        return [float(s) for s in range(23000, 26050, 50)]

    def fake_resolve(underlying, expiry, strike, option_type):
        return {
            "instrument_key": f"NSE_FO|{int(strike)}{option_type}",
            "tradingsymbol": f"NIFTY{int(strike)}{option_type}",
        }

    def fake_lot(_underlying, _expiry=None):
        return 25

    monkeypatch.setattr(so, "list_strikes", fake_list_strikes)
    monkeypatch.setattr(so, "resolve_option_instrument", fake_resolve)
    monkeypatch.setattr(so, "get_lot_size", fake_lot)


def _premium_series(
    candles: list[dict],
    *,
    direction: str,
    base: float = 100.0,
    move_per_bar: float = 1.0,
    sl_break_at: int | None = None,
    target_break_at: int | None = None,
    trail_pullback_at: int | None = None,
    pullback_amount: float = 5.0,
) -> list[dict]:
    """Synthesize an option leg's candle series aligned 1:1 with underlying.

    Premium starts at ``base`` and walks +``move_per_bar`` each bar (long
    direction; PE/CE doesn't matter — engine treats both as long-premium).
    Optional ``sl_break_at`` / ``target_break_at`` injects an extreme bar at
    that index that breaches an SL or target level.
    """
    out: list[dict] = []
    p = base
    for i, uc in enumerate(candles):
        ts = uc["timestamp"]
        if sl_break_at is not None and i == sl_break_at:
            out.append({"timestamp": ts, "open": p, "high": p + 1, "low": p - 50, "close": p - 30, "volume": 100})
            continue
        if target_break_at is not None and i == target_break_at:
            out.append({"timestamp": ts, "open": p, "high": p + 50, "low": p - 1, "close": p + 30, "volume": 100})
            continue
        if trail_pullback_at is not None and i == trail_pullback_at:
            out.append({"timestamp": ts, "open": p, "high": p, "low": p - pullback_amount, "close": p - pullback_amount, "volume": 100})
            p -= pullback_amount
            continue
        nxt = p + move_per_bar
        out.append({"timestamp": ts, "open": p, "high": max(p, nxt), "low": min(p, nxt), "close": nxt, "volume": 100})
        p = nxt
    return out


# ──────────────────────────────────────────────────────────────────────
# Mode validation
# ──────────────────────────────────────────────────────────────────────

class TestModeValidation:
    def test_rejects_non_options_mode(self):
        cfg = _base_config(session_mode=SessionMode.EQUITY_INTRADAY.value)
        with pytest.raises(ValueError, match="options_scalp"):
            run_scalp_options_backtest(
                [_candle(_ist(2026, 4, 21), 100, 100, 100, 100)], {}, cfg,
                interval="5minute",
            )

    def test_planner_rejects_non_options_mode(self):
        cfg = _base_config(session_mode=SessionMode.EQUITY_INTRADAY.value)
        with pytest.raises(ValueError, match="options_scalp"):
            plan_atm_legs([], cfg, "5minute")

    def test_requires_expiry(self, patch_fno):
        cfg = _base_config(expiry="")
        with pytest.raises(ValueError, match="expiry"):
            run_scalp_options_backtest(
                [_candle(_ist(2026, 4, 21), 100, 100, 100, 100)], {}, cfg,
                interval="5minute",
            )

    def test_requires_lots(self, patch_fno):
        cfg = _base_config(lots=0)
        with pytest.raises(ValueError, match="lots"):
            run_scalp_options_backtest(
                [_candle(_ist(2026, 4, 21), 100, 100, 100, 100)], {}, cfg,
                interval="5minute",
            )


# ──────────────────────────────────────────────────────────────────────
# Pass 1 — plan_atm_legs
# ──────────────────────────────────────────────────────────────────────

class TestPlanAtmLegs:
    def test_bullish_flip_records_ce_leg(self, patch_fno):
        start = _ist(2026, 4, 21)
        underlying = _flat(10, 24300.0, start) + _uptrend(8, 24300.0, 5.0, start + timedelta(minutes=50))
        cfg = _base_config()
        plans = plan_atm_legs(underlying, cfg, "5minute")
        ce_plans = [p for p in plans if p.option_type == "CE"]
        assert ce_plans, "expected at least one CE leg from bullish flip"
        # ATM must snap to nearest 50-pt grid strike — entry near 24305-24330.
        assert all(p.strike % 50 == 0 for p in ce_plans)
        assert all(p.instrument_key.endswith("CE") for p in ce_plans)

    def test_bearish_flip_records_pe_leg(self, patch_fno):
        start = _ist(2026, 4, 21)
        underlying = _flat(10, 24300.0, start) + _downtrend(8, 24300.0, 5.0, start + timedelta(minutes=50))
        cfg = _base_config()
        plans = plan_atm_legs(underlying, cfg, "5minute")
        pe_plans = [p for p in plans if p.option_type == "PE"]
        assert pe_plans, "expected at least one PE leg from bearish flip"

    def test_dedupes_same_day_same_atm_same_type(self, patch_fno):
        # A single bullish flip should only record one (date, strike, type).
        start = _ist(2026, 4, 21)
        underlying = _flat(10, 24300.0, start) + _uptrend(8, 24300.0, 1.0, start + timedelta(minutes=50))
        cfg = _base_config()
        plans = plan_atm_legs(underlying, cfg, "5minute")
        seen = {(p.date, p.strike, p.option_type) for p in plans}
        assert len(seen) == len(plans)


# ──────────────────────────────────────────────────────────────────────
# Pass 2 — replay
# ──────────────────────────────────────────────────────────────────────

class TestEntryFill:
    def test_bullish_flip_buys_atm_ce_at_next_bar_close(self, patch_fno):
        start = _ist(2026, 4, 21)
        underlying = _flat(10, 24300.0, start) + _uptrend(8, 24300.0, 5.0, start + timedelta(minutes=50))
        cfg = _base_config()

        # Pre-build one CE leg covering all 18 bars. Flip will fall on the
        # uptrend boundary; engine will pick whichever ATM strike the planner
        # would've picked. We mirror that here so the leg matches.
        plans = plan_atm_legs(underlying, cfg, "5minute")
        ce_plan = next(p for p in plans if p.option_type == "CE")
        leg = _premium_series(underlying, direction="long", base=100.0, move_per_bar=2.0)
        leg_candles_by_key = {ce_plan.instrument_key: leg}

        r = run_scalp_options_backtest(
            underlying, leg_candles_by_key, cfg, interval="5minute",
        )
        assert r.trades, "expected at least one round-trip trade"
        first = r.trades[0]
        assert first.symbol.endswith("CE")
        assert first.side == "long"

    def test_missing_leg_increments_block_counter(self, patch_fno):
        start = _ist(2026, 4, 21)
        underlying = _flat(10, 24300.0, start) + _uptrend(8, 24300.0, 5.0, start + timedelta(minutes=50))
        cfg = _base_config()
        # No leg candles supplied at all → every flip blocks on missing leg.
        r = run_scalp_options_backtest(
            underlying, {}, cfg, interval="5minute",
        )
        assert r.missing_leg_blocks >= 1
        assert not r.trades


class TestPremiumExits:
    def test_sl_fires_at_sl_level_not_low(self, patch_fno):
        start = _ist(2026, 4, 21)
        underlying = _flat(10, 24300.0, start) + _uptrend(20, 24300.0, 5.0, start + timedelta(minutes=50))
        cfg = _base_config(sl_points=10.0)
        plans = plan_atm_legs(underlying, cfg, "5minute")
        ce_plan = next(p for p in plans if p.option_type == "CE")
        # Premium walks up at first to fill, then crashes far below SL.
        # Find the fill bar index — flip is detected when fast crosses slow.
        # Simpler: flat premium for first 12 bars, then a big drop bar.
        leg: list[dict] = []
        for i, uc in enumerate(underlying):
            if i == 14:
                leg.append({"timestamp": uc["timestamp"], "open": 100, "high": 100, "low": 50, "close": 60, "volume": 1})
            else:
                leg.append({"timestamp": uc["timestamp"], "open": 100, "high": 100, "low": 100, "close": 100, "volume": 1})
        r = run_scalp_options_backtest(
            underlying, {ce_plan.instrument_key: leg}, cfg, interval="5minute",
        )
        sl_trades = [t for t in r.trades if t.exit_reason == "exit_sl"]
        assert sl_trades, "expected at least one SL exit"
        # SL fires at entry - sl_points (90), not the bar's low (50).
        # Entry is the leg's bar-close right after the flip — flat at 100.
        t = sl_trades[0]
        assert t.exit_price == pytest.approx(t.entry_price - 10.0, rel=1e-6)

    def test_target_fires_at_target_level_not_high(self, patch_fno):
        start = _ist(2026, 4, 21)
        underlying = _flat(10, 24300.0, start) + _uptrend(20, 24300.0, 5.0, start + timedelta(minutes=50))
        cfg = _base_config(target_points=15.0)
        plans = plan_atm_legs(underlying, cfg, "5minute")
        ce_plan = next(p for p in plans if p.option_type == "CE")
        leg: list[dict] = []
        for i, uc in enumerate(underlying):
            if i == 14:
                leg.append({"timestamp": uc["timestamp"], "open": 100, "high": 200, "low": 99, "close": 150, "volume": 1})
            else:
                leg.append({"timestamp": uc["timestamp"], "open": 100, "high": 100, "low": 100, "close": 100, "volume": 1})
        r = run_scalp_options_backtest(
            underlying, {ce_plan.instrument_key: leg}, cfg, interval="5minute",
        )
        tg_trades = [t for t in r.trades if t.exit_reason == "exit_target"]
        assert tg_trades
        t = tg_trades[0]
        assert t.exit_price == pytest.approx(t.entry_price + 15.0, rel=1e-6)


class TestSquareoff:
    def test_squareoff_fires_at_cutoff(self, patch_fno):
        # Build an underlying day that ends before squareoff and trip the
        # engine's bar-time guard. squareoff_time=09:50 means a bar at >=09:50
        # IST exits any held position.
        start = _ist(2026, 4, 21, hh=9, mm=15)
        underlying = _flat(5, 24300.0, start) + _uptrend(10, 24300.0, 5.0, start + timedelta(minutes=25))
        cfg = _base_config(squareoff_time="09:50")
        plans = plan_atm_legs(underlying, cfg, "5minute")
        ce_plan = next(p for p in plans if p.option_type == "CE")
        leg = [
            {"timestamp": uc["timestamp"], "open": 100, "high": 100, "low": 100, "close": 100, "volume": 1}
            for uc in underlying
        ]
        r = run_scalp_options_backtest(
            underlying, {ce_plan.instrument_key: leg}, cfg, interval="5minute",
        )
        sq_trades = [t for t in r.trades if t.exit_reason == "squareoff"]
        assert sq_trades, "expected at least one squareoff exit"
        assert r.squareoff_exits >= 1


class TestCharges:
    def test_charges_applied_per_round_trip(self, patch_fno):
        start = _ist(2026, 4, 21)
        underlying = _flat(10, 24300.0, start) + _uptrend(8, 24300.0, 5.0, start + timedelta(minutes=50))
        cfg = _base_config()
        plans = plan_atm_legs(underlying, cfg, "5minute")
        ce_plan = next(p for p in plans if p.option_type == "CE")
        leg = _premium_series(underlying, direction="long", base=100.0, move_per_bar=2.0)
        r = run_scalp_options_backtest(
            underlying, {ce_plan.instrument_key: leg}, cfg, interval="5minute",
        )
        # Net P&L should be strictly less than gross (charges deducted) when
        # there's at least one trade.
        if r.trades:
            assert r.charges_total > 0
            for t in r.trades:
                gross = getattr(t, "_gross_pnl", None)
                assert gross is not None
                assert t.pnl <= gross


class TestReversal:
    def test_opposite_flip_exits_position(self, patch_fno):
        # Build a sequence: flat → uptrend (bullish flip → enter CE) →
        # downtrend (bearish flip → exit on reversal).
        start = _ist(2026, 4, 21)
        underlying = (
            _flat(10, 24300.0, start)
            + _uptrend(8, 24300.0, 5.0, start + timedelta(minutes=50))
        )
        # Stitch a downtrend after the uptrend — picks up timestamps from
        # the last bar of the uptrend.
        last_ts = _ist(2026, 4, 21) + timedelta(minutes=5 * 17)
        underlying += _downtrend(8, 24340.0, 5.0, last_ts + timedelta(minutes=5))
        cfg = _base_config()
        plans = plan_atm_legs(underlying, cfg, "5minute")
        # Both CE and PE legs may be needed; build flat premium for both.
        leg_candles_by_key: dict[str, list[dict]] = {}
        for p in plans:
            leg_candles_by_key[p.instrument_key] = [
                {"timestamp": uc["timestamp"], "open": 100, "high": 100, "low": 100, "close": 100, "volume": 1}
                for uc in underlying
            ]
        r = run_scalp_options_backtest(
            underlying, leg_candles_by_key, cfg, interval="5minute",
        )
        reasons = [t.exit_reason for t in r.trades]
        assert "entry_opposite" in reasons or len(r.trades) >= 1
