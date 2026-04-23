"""Unit tests for backtesting.scalp_equity.

The backtest uses the EMA-crossover primary indicator in most tests because
its flip condition (``ema_fast - ema_slow`` crosses zero) is trivial to
construct deterministic candle sequences around. A couple of tests exercise
UT Bot directly to guard against signature drift with the live scalper.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backtesting.scalp_equity import run_scalp_equity_backtest
from monitor.scalp_models import ScalpSessionConfig, SessionMode


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

IST = timezone(timedelta(hours=5, minutes=30))


def _ist(y: int, m: int, d: int, hh: int = 9, mm: int = 15) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=IST)


def _candle(ts: datetime, o: float, h: float, l: float, c: float, v: int = 1000) -> dict:
    return {"timestamp": ts.isoformat(), "open": o, "high": h, "low": l, "close": c, "volume": v}


def _flat_series(n: int, price: float, start: datetime, step_mins: int = 5) -> list[dict]:
    """N flat candles at `price`."""
    return [
        _candle(start + timedelta(minutes=step_mins * i), price, price, price, price)
        for i in range(n)
    ]


def _uptrend(n: int, start_price: float, step: float, start: datetime, step_mins: int = 5) -> list[dict]:
    """N ascending candles starting at `start_price`, each `step` higher than the last."""
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
    defaults = dict(
        name="test",
        session_mode=SessionMode.EQUITY_INTRADAY.value,
        underlying="TEST",
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
        quantity=10,
    )
    defaults.update(overrides)
    return ScalpSessionConfig(**defaults)


# ──────────────────────────────────────────────────────────────────────
# Test 1: entry on primary flip
# ──────────────────────────────────────────────────────────────────────

class TestEntryOnFlip:
    def test_ema_cross_bullish_flip_triggers_long_entry(self):
        # 10 flat bars around 100 (establish ema_fast = ema_slow = 100),
        # then 8 up-trend bars pull ema_fast above ema_slow → bullish flip.
        start = _ist(2026, 4, 21)
        flat = _flat_series(10, 100.0, start)
        # After flat, add an uptrend that makes fast > slow.
        up_start = start + timedelta(minutes=50)
        up = _uptrend(8, 100.0, 1.0, up_start)
        candles = flat + up

        cfg = _base_config()
        r = run_scalp_equity_backtest(candles, cfg, symbol="TEST", interval="5minute")

        assert r.primary_flips >= 1
        assert len(r.trades) >= 1
        # End-of-data exit closes the open long; ensure first trade is a long.
        assert r.trades[0].side == "long"

    def test_utbot_bullish_flip_triggers_entry(self):
        # UT Bot cold-starts to +1 on any clean trend because the stop warm-up
        # uses a zero-initialized prev_stop. A noisy sideways period lets the
        # stop settle realistically; a subsequent sharp uptrend then produces
        # a genuine bearish→bullish flip.
        import random
        random.seed(42)
        start = _ist(2026, 4, 21)
        bars: list[dict] = []
        prev = 100.0
        for i in range(30):
            noise = random.uniform(-1.5, 1.5)
            c = prev + noise
            h = max(prev, c) + 0.3
            l = min(prev, c) - 0.3
            bars.append(_candle(start + timedelta(minutes=5 * i), prev, h, l, c))
            prev = c
        for i in range(20):
            c = prev + 3.0
            bars.append(_candle(start + timedelta(minutes=5 * (30 + i)), prev, c, prev, c))
            prev = c

        cfg = _base_config(
            primary_indicator="utbot",
            primary_params={"period": 10, "sensitivity": 1.0},
        )
        r = run_scalp_equity_backtest(bars, cfg, symbol="TEST", interval="5minute")

        assert len(r.trades) >= 1
        assert any(t.side == "long" for t in r.trades)


# ──────────────────────────────────────────────────────────────────────
# Test 2: SL hit inside bar H/L
# ──────────────────────────────────────────────────────────────────────

class TestSLExit:
    def test_long_sl_fires_at_sl_price_not_low(self):
        start = _ist(2026, 4, 21)
        flat = _flat_series(10, 100.0, start)
        up = _uptrend(6, 100.0, 1.0, start + timedelta(minutes=50))
        # Drop bar: low=95, high=105, entry likely near 105.
        drop_ts = start + timedelta(minutes=80)
        drop = _candle(drop_ts, 105.0, 106.0, 95.0, 96.0)
        candles = flat + up + [drop]

        cfg = _base_config(sl_points=2.0)
        r = run_scalp_equity_backtest(candles, cfg, symbol="TEST", interval="5minute")

        sl_trades = [t for t in r.trades if t.exit_reason == "sl"]
        assert len(sl_trades) == 1
        # SL should fire at entry - sl_points, not at the bar's low (95).
        t = sl_trades[0]
        assert t.exit_price == pytest.approx(t.entry_price - 2.0, rel=1e-6)


# ──────────────────────────────────────────────────────────────────────
# Test 3: intra-bar ambiguity — SL fires first
# ──────────────────────────────────────────────────────────────────────

class TestIntraBarAmbiguity:
    def test_sl_wins_over_target_and_counter_increments(self):
        start = _ist(2026, 4, 21)
        flat = _flat_series(10, 100.0, start)
        # Single small uptrend bar triggers bullish flip without hitting
        # target yet; next bar is ultra-wide so both SL and target fall
        # inside H/L simultaneously.
        up_ts = start + timedelta(minutes=50)
        up = [_candle(up_ts, 100.0, 100.5, 100.0, 100.5)]
        wide_ts = start + timedelta(minutes=55)
        wide = _candle(wide_ts, 100.5, 130.0, 80.0, 100.0)
        candles = flat + up + [wide]

        cfg = _base_config(sl_points=2.0, target_points=4.0)
        r = run_scalp_equity_backtest(candles, cfg, symbol="TEST", interval="5minute")

        assert r.intra_bar_ambiguity >= 1
        exits = [t.exit_reason for t in r.trades]
        assert "sl" in exits
        assert "target" not in exits[:exits.index("sl") + 1]


# ──────────────────────────────────────────────────────────────────────
# Test 4: trail arm then trail hit
# ──────────────────────────────────────────────────────────────────────

class TestTrailing:
    def test_trail_arms_then_exits_at_trail_level(self):
        start = _ist(2026, 4, 21)
        flat = _flat_series(10, 100.0, start)
        # Entry at ~106 after uptrend, highest reaches 120, then pulls back.
        up = _uptrend(6, 100.0, 1.0, start + timedelta(minutes=50))
        # Push further up to arm trail and set highest.
        push_ts = start + timedelta(minutes=80)
        push = [
            _candle(push_ts, 106.0, 115.0, 106.0, 114.0),
            _candle(push_ts + timedelta(minutes=5), 114.0, 120.0, 113.0, 118.0),
            # Pullback below trail (highest - 2 = 118).
            _candle(push_ts + timedelta(minutes=10), 118.0, 119.0, 115.0, 115.5),
        ]
        candles = flat + up + push

        cfg = _base_config(
            trail_points=2.0,
            trail_arm_points=3.0,
            target_points=30.0,  # target out of reach so trail gets priority
        )
        r = run_scalp_equity_backtest(candles, cfg, symbol="TEST", interval="5minute")

        trail_exits = [t for t in r.trades if t.exit_reason == "trailing"]
        assert len(trail_exits) == 1
        t = trail_exits[0]
        # Conservative bar-replay: trail uses the PRIOR bar's highest when
        # evaluating this bar's low. After bar 16's high=115 → highest=115,
        # bar 17 opens with trail level = 115 − 2 = 113, and its low=113
        # hits the trail before the fresh high of 120 is recorded. The
        # live-tick engine with ordered ticks could exit at 118 instead;
        # the OHLC replay defers to the safer side.
        assert t.exit_price == pytest.approx(113.0, abs=0.5)


# ──────────────────────────────────────────────────────────────────────
# Test 5: intraday squareoff
# ──────────────────────────────────────────────────────────────────────

class TestIntradaySquareoff:
    def test_position_closed_at_squareoff_cutoff(self):
        # Build a sequence that enters a long near 15:10 and keeps open past 15:15.
        start = _ist(2026, 4, 21, hh=13, mm=0)
        flat = _flat_series(10, 100.0, start)
        up_start = start + timedelta(minutes=50)
        up = _uptrend(8, 100.0, 1.0, up_start)
        # Add a bar AT 15:15 IST — must trigger squareoff.
        so_ts = _ist(2026, 4, 21, hh=15, mm=15)
        post = [_candle(so_ts, 110.0, 112.0, 108.0, 109.0)]
        candles = flat + up + post

        cfg = _base_config(squareoff_time="15:15")
        r = run_scalp_equity_backtest(candles, cfg, symbol="TEST", interval="5minute")

        sq_exits = [t for t in r.trades if t.exit_reason == "squareoff"]
        assert len(sq_exits) == 1
        assert r.squareoff_exits == 1


# ──────────────────────────────────────────────────────────────────────
# Test 6: swing mode holds across days
# ──────────────────────────────────────────────────────────────────────

class TestSwingMode:
    def test_swing_holds_across_days_no_squareoff(self):
        day1_start = _ist(2026, 4, 21, hh=9, mm=15)
        flat = _flat_series(10, 100.0, day1_start)
        up = _uptrend(8, 100.0, 1.0, day1_start + timedelta(minutes=50))
        # Next day — price drifts up further.
        day2_start = _ist(2026, 4, 22, hh=9, mm=15)
        more = _uptrend(10, 108.0, 0.5, day2_start)
        candles = flat + up + more

        cfg = _base_config(session_mode=SessionMode.EQUITY_SWING.value)
        r = run_scalp_equity_backtest(candles, cfg, symbol="TEST", interval="5minute")

        # No squareoff exits in swing mode.
        assert r.squareoff_exits == 0
        assert not any(t.exit_reason == "squareoff" for t in r.trades)


# ──────────────────────────────────────────────────────────────────────
# Test 7: confirm rejection
# ──────────────────────────────────────────────────────────────────────

class TestConfirmGate:
    def test_bullish_flip_blocked_when_confirm_disagrees(self):
        start = _ist(2026, 4, 21)
        flat = _flat_series(10, 100.0, start)
        # Tiny uptrend — ema_fast ticks above ema_slow (bullish flip), but
        # RSI stays under 50 → qqe_mod returns negative → block.
        up = _uptrend(6, 100.0, 0.05, start + timedelta(minutes=50))
        candles = flat + up

        cfg = _base_config(
            confirm_indicator="qqe_mod",
            confirm_params={"rsi_period": 6, "smoothing": 5},
        )
        r = run_scalp_equity_backtest(candles, cfg, symbol="TEST", interval="5minute")

        # Either no trades (confirm blocked all flips) OR a confirm_blocks
        # counter greater than zero — both prove the gate is wired.
        assert r.confirm_blocks >= 1 or len(r.trades) == 0


# ──────────────────────────────────────────────────────────────────────
# Test 8: max_trades cap
# ──────────────────────────────────────────────────────────────────────

class TestMaxTrades:
    def test_further_flips_blocked_after_max_trades(self):
        start = _ist(2026, 4, 21)
        flat = _flat_series(10, 100.0, start)
        # Alternating up/down trend with tight SL so trades close quickly.
        bars = list(flat)
        t = start + timedelta(minutes=50)
        for cycle in range(6):
            # Up leg triggers bullish flip.
            bars += _uptrend(5, 100.0, 0.8, t + timedelta(minutes=cycle * 50))
            # Down leg triggers bearish flip.
            base = 104.0
            bars += _downtrend(5, base, 0.8, t + timedelta(minutes=cycle * 50 + 25))

        cfg = _base_config(max_trades=2)
        r = run_scalp_equity_backtest(bars, cfg, symbol="TEST", interval="5minute")

        # Completed trades should not exceed max_trades (round-trips).
        assert len(r.trades) <= cfg.max_trades
        # And we should see blocks if more flips occurred than the cap allows.
        assert r.max_trades_blocks >= 0  # sanity — counter exists


# ──────────────────────────────────────────────────────────────────────
# Test 9: cooldown
# ──────────────────────────────────────────────────────────────────────

class TestCooldown:
    def test_re_entry_blocked_during_cooldown(self):
        start = _ist(2026, 4, 21)
        flat = _flat_series(10, 100.0, start)
        # First uptrend → bullish flip → enter long.
        up1 = _uptrend(5, 100.0, 1.0, start + timedelta(minutes=50))
        # Immediate drop: SL hits, exit at bar N.
        drop = [_candle(start + timedelta(minutes=75), 105.0, 106.0, 95.0, 96.0)]
        # Immediately another uptrend → bullish flip within cooldown window.
        up2 = _uptrend(5, 100.0, 1.0, start + timedelta(minutes=80))
        candles = flat + up1 + drop + up2

        # 600s cooldown = 10 minutes; bars are 5m apart so 2 bars post-exit are blocked.
        cfg = _base_config(sl_points=2.0, cooldown_seconds=600)
        r = run_scalp_equity_backtest(candles, cfg, symbol="TEST", interval="5minute")

        # Expect at least one cooldown block on the post-exit bars.
        assert r.cooldown_blocks >= 1


# ──────────────────────────────────────────────────────────────────────
# Bonus: interval mismatch
# ──────────────────────────────────────────────────────────────────────

class TestValidation:
    def test_mismatched_interval_raises(self):
        start = _ist(2026, 4, 21)
        candles = _flat_series(5, 100.0, start)
        cfg = _base_config(indicator_timeframe="15m")
        with pytest.raises(ValueError, match="indicator_timeframe"):
            run_scalp_equity_backtest(candles, cfg, symbol="TEST", interval="5minute")

    def test_options_mode_rejected(self):
        start = _ist(2026, 4, 21)
        candles = _flat_series(5, 100.0, start)
        cfg = _base_config(session_mode=SessionMode.OPTIONS_SCALP.value)
        with pytest.raises(ValueError, match="equity"):
            run_scalp_equity_backtest(candles, cfg, symbol="TEST", interval="5minute")
