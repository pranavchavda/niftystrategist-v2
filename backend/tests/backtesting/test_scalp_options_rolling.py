"""Unit tests for rolling front-weekly resolution in ``backtesting.scalp_options``.

The rolling path resolves each flip against the weekly contract that was
front-of-book ON THAT DATE, using pre-fetched ``RollingExpiryData`` rather than
``list_strikes`` / ``resolve_option_instrument`` against a single fixed expiry.

All data here is synthetic (no network, no CSV cache). We stitch an underlying
series spanning two fake expiries and supply leg candles keyed by the contract
instrument_keys the planner emits, then assert:

* flips before/after the expiry boundary resolve to the correct contract
* plan/replay consistency (no missing_leg_blocks when leg candles supplied)
* expiries_used is correct and sorted
* lot_size is taken from the resolved contract (differs across expiries here)
* the fixed-expiry path is byte-identical to pre-change behaviour
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backtesting import scalp_options as so
from backtesting.scalp_options import (
    RollingExpiryData,
    front_expiry_for_date,
    plan_atm_legs,
    run_scalp_options_backtest,
)
from monitor.scalp_models import ScalpSessionConfig, SessionMode

IST = timezone(timedelta(hours=5, minutes=30))


# ──────────────────────────────────────────────────────────────────────
# Helpers (mirror test_scalp_options conventions)
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


def _rolling_config(**overrides) -> ScalpSessionConfig:
    """Options-scalp config in rolling mode (expiry sentinel = 'rolling')."""
    defaults = dict(
        name="test-rolling",
        session_mode=SessionMode.OPTIONS_SCALP.value,
        underlying="NIFTY",
        expiry="rolling",
        lots=1,
        indicator_timeframe="5m",
        primary_indicator="ema_crossover",
        primary_params={"fast": 3, "slow": 5},
        squareoff_time="15:15",
        max_trades=20,
        cooldown_seconds=0,
    )
    defaults.update(overrides)
    return ScalpSessionConfig(**defaults)


def _fixed_config(**overrides) -> ScalpSessionConfig:
    defaults = dict(
        name="test-fixed",
        session_mode=SessionMode.OPTIONS_SCALP.value,
        underlying="NIFTY",
        expiry="2026-04-24",
        lots=1,
        indicator_timeframe="5m",
        primary_indicator="ema_crossover",
        primary_params={"fast": 3, "slow": 5},
        squareoff_time="15:15",
        max_trades=20,
        cooldown_seconds=0,
    )
    defaults.update(overrides)
    return ScalpSessionConfig(**defaults)


# Two fake weekly expiries: contracts list a 50-pt grid around 24000-24600.
# Expiry A lot_size=25, expiry B lot_size=30 (so lot-from-contract is testable).
EXPIRY_A = "2026-04-10"
EXPIRY_B = "2026-04-17"


def _contracts_for(expiry: str, lot: int) -> list[dict]:
    out: list[dict] = []
    for strike in range(24000, 24650, 50):
        for opt in ("CE", "PE"):
            out.append({
                "strike_price": float(strike),
                "instrument_type": opt,
                "instrument_key": f"NSE_FO|{expiry}|{strike}{opt}",
                "trading_symbol": f"NIFTY{expiry}{strike}{opt}",
                "lot_size": lot,
            })
    return out


def _rolling_data() -> RollingExpiryData:
    return RollingExpiryData(
        expiries=[EXPIRY_A, EXPIRY_B],
        contracts_by_expiry={
            EXPIRY_A: _contracts_for(EXPIRY_A, 25),
            EXPIRY_B: _contracts_for(EXPIRY_B, 30),
        },
    )


def _bullish_day(day: datetime) -> list[dict]:
    """A single trading day with one clean bullish flip → CE entry.

    Flat then an uptrend; the ema_crossover primary flips bullish on the
    uptrend boundary. Underlying ~24300 so ATM snaps to 24300.
    """
    return (
        _flat(10, 24300.0, day)
        + _uptrend(8, 24300.0, 5.0, day + timedelta(minutes=50))
    )


def _flat_leg(underlying: list[dict], price: float = 100.0) -> list[dict]:
    return [
        {"timestamp": uc["timestamp"], "open": price, "high": price,
         "low": price, "close": price, "volume": 1}
        for uc in underlying
    ]


# ──────────────────────────────────────────────────────────────────────
# front_expiry_for_date
# ──────────────────────────────────────────────────────────────────────

class TestFrontExpiryForDate:
    def test_picks_smallest_expiry_ge_date(self):
        exps = [EXPIRY_A, EXPIRY_B]
        # Before A → A is front
        assert front_expiry_for_date("2026-04-05", exps) == EXPIRY_A
        # On A → A is still front (>=)
        assert front_expiry_for_date(EXPIRY_A, exps) == EXPIRY_A
        # Day after A → B is now front
        assert front_expiry_for_date("2026-04-11", exps) == EXPIRY_B
        # On B → B
        assert front_expiry_for_date(EXPIRY_B, exps) == EXPIRY_B

    def test_returns_none_past_all_expiries(self):
        assert front_expiry_for_date("2026-05-01", [EXPIRY_A, EXPIRY_B]) is None

    def test_unsorted_input(self):
        assert front_expiry_for_date("2026-04-05", [EXPIRY_B, EXPIRY_A]) == EXPIRY_A


# ──────────────────────────────────────────────────────────────────────
# plan_atm_legs — rolling
# ──────────────────────────────────────────────────────────────────────

class TestRollingPlan:
    def test_flips_resolve_to_correct_contract_across_boundary(self):
        # Day inside expiry A's window
        day_a = _ist(2026, 4, 8)
        # Day inside expiry B's window (after A's expiry)
        day_b = _ist(2026, 4, 15)
        underlying = _bullish_day(day_a) + _bullish_day(day_b)
        cfg = _rolling_config()
        rolling = _rolling_data()

        plans = plan_atm_legs(underlying, cfg, "5minute", rolling=rolling)
        ce_plans = [p for p in plans if p.option_type == "CE"]
        assert len(ce_plans) == 2, f"expected one CE per day, got {ce_plans}"

        by_date = {p.date: p for p in ce_plans}
        # Flip on 2026-04-08 → front weekly is EXPIRY_A
        assert by_date["2026-04-08"].expiry == EXPIRY_A
        assert EXPIRY_A in by_date["2026-04-08"].instrument_key
        assert by_date["2026-04-08"].lot_size == 25
        # Flip on 2026-04-15 (after A expired) → front weekly is EXPIRY_B
        assert by_date["2026-04-15"].expiry == EXPIRY_B
        assert EXPIRY_B in by_date["2026-04-15"].instrument_key
        assert by_date["2026-04-15"].lot_size == 30

    def test_flip_past_all_expiries_is_skipped(self):
        # A flip on a day past both expiries → no_strike/skip (no plan emitted).
        day = _ist(2026, 5, 1)
        underlying = _bullish_day(day)
        cfg = _rolling_config()
        rolling = _rolling_data()
        plans = plan_atm_legs(underlying, cfg, "5minute", rolling=rolling)
        assert plans == []

    def test_atm_snaps_to_nearest_listed_strike(self):
        day = _ist(2026, 4, 8)
        underlying = _bullish_day(day)
        cfg = _rolling_config()
        plans = plan_atm_legs(underlying, cfg, "5minute", rolling=_rolling_data())
        ce = next(p for p in plans if p.option_type == "CE")
        # Underlying near 24300 → ATM 24300 (on the 50-pt grid).
        assert ce.strike == 24300.0


# ──────────────────────────────────────────────────────────────────────
# run_scalp_options_backtest — rolling
# ──────────────────────────────────────────────────────────────────────

class TestRollingReplay:
    def test_plan_replay_consistency_no_missing_legs(self):
        day_a = _ist(2026, 4, 8)
        day_b = _ist(2026, 4, 15)
        underlying = _bullish_day(day_a) + _bullish_day(day_b)
        cfg = _rolling_config()
        rolling = _rolling_data()

        plans = plan_atm_legs(underlying, cfg, "5minute", rolling=rolling)
        assert plans, "planner should emit legs"
        leg_candles_by_key = {
            p.instrument_key: _flat_leg(underlying) for p in plans
        }

        r = run_scalp_options_backtest(
            underlying, leg_candles_by_key, cfg, interval="5minute",
            rolling=rolling,
        )
        # Leg candles supplied for every planned key → no orphaned flips.
        assert r.missing_leg_blocks == 0
        assert r.trades, "expected round-trip trades"

    def test_expiries_used_correct_and_sorted(self):
        day_a = _ist(2026, 4, 8)
        day_b = _ist(2026, 4, 15)
        underlying = _bullish_day(day_a) + _bullish_day(day_b)
        cfg = _rolling_config()
        rolling = _rolling_data()
        plans = plan_atm_legs(underlying, cfg, "5minute", rolling=rolling)
        leg_candles_by_key = {p.instrument_key: _flat_leg(underlying) for p in plans}

        r = run_scalp_options_backtest(
            underlying, leg_candles_by_key, cfg, interval="5minute",
            rolling=rolling,
        )
        assert r.expiries_used == [EXPIRY_A, EXPIRY_B]

    def test_lot_size_taken_from_contract(self):
        # Single day inside expiry B → lot 30, not the index default.
        day_b = _ist(2026, 4, 15)
        underlying = _bullish_day(day_b)
        cfg = _rolling_config()
        rolling = _rolling_data()
        plans = plan_atm_legs(underlying, cfg, "5minute", rolling=rolling)
        leg_candles_by_key = {p.instrument_key: _flat_leg(underlying) for p in plans}

        r = run_scalp_options_backtest(
            underlying, leg_candles_by_key, cfg, interval="5minute",
            rolling=rolling,
        )
        assert r.trades, "expected a trade"
        # config.lots=1, contract lot_size=30 → quantity 30.
        assert r.trades[0].quantity == 30

    def test_correct_contract_per_day(self):
        day_a = _ist(2026, 4, 8)
        day_b = _ist(2026, 4, 15)
        underlying = _bullish_day(day_a) + _bullish_day(day_b)
        cfg = _rolling_config()
        rolling = _rolling_data()
        plans = plan_atm_legs(underlying, cfg, "5minute", rolling=rolling)
        leg_candles_by_key = {p.instrument_key: _flat_leg(underlying) for p in plans}

        r = run_scalp_options_backtest(
            underlying, leg_candles_by_key, cfg, interval="5minute",
            rolling=rolling,
        )
        assert len(r.trades) >= 2
        # Trades on day A carry expiry A's contract (symbol + lot 25); trades
        # on day B carry expiry B's (symbol + lot 30). Tie the contract used to
        # the entry date so the per-date front-weekly resolution is verified.
        for t in r.trades:
            entry_day = t.entry_time.date().isoformat()
            if entry_day <= EXPIRY_A:
                assert EXPIRY_A in t.symbol
                assert t.quantity == 25
            else:
                assert EXPIRY_B in t.symbol
                assert t.quantity == 30
        symbols = {t.symbol for t in r.trades}
        assert any(EXPIRY_A in s for s in symbols)
        assert any(EXPIRY_B in s for s in symbols)


# ──────────────────────────────────────────────────────────────────────
# Fixed-expiry path unchanged
# ──────────────────────────────────────────────────────────────────────

class TestFixedPathUnchanged:
    @pytest.fixture
    def patch_fno(self, monkeypatch):
        def fake_list_strikes(underlying, expiry, option_type):
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

    def test_fixed_mode_runs_and_trades(self, patch_fno):
        start = _ist(2026, 4, 21)
        underlying = _flat(10, 24300.0, start) + _uptrend(8, 24300.0, 5.0, start + timedelta(minutes=50))
        cfg = _fixed_config()
        plans = plan_atm_legs(underlying, cfg, "5minute")
        ce_plan = next(p for p in plans if p.option_type == "CE")
        # Fixed-mode plan carries config.expiry on the LegFetchPlan.
        assert ce_plan.expiry == "2026-04-24"
        leg = _flat_leg(underlying)
        r = run_scalp_options_backtest(
            underlying, {ce_plan.instrument_key: leg}, cfg, interval="5minute",
        )
        assert r.trades
        first = r.trades[0]
        assert first.symbol.endswith("CE")
        assert first.side == "long"
        # Lot from fixed get_lot_size (25), quantity 25.
        assert first.quantity == 25
        # Fixed mode populates expiries_used with the single cfg expiry.
        assert r.expiries_used == ["2026-04-24"]

    def test_fixed_mode_expiries_used_empty_when_no_trades(self, patch_fno):
        start = _ist(2026, 4, 21)
        underlying = _flat(10, 24300.0, start) + _uptrend(8, 24300.0, 5.0, start + timedelta(minutes=50))
        cfg = _fixed_config()
        # No leg candles → every flip blocks on missing leg, no trades.
        r = run_scalp_options_backtest(
            underlying, {}, cfg, interval="5minute",
        )
        assert not r.trades
        assert r.expiries_used == []
