"""Unit tests for backtesting.htf_trend (daily regime detection, no-lookahead)
and the engine's ``entry_gate`` hook in run_scalp_equity_backtest.

Synthetic candles only; no network.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from backtesting.htf_trend import (
    HTF_VARIANTS,
    compute_daily_trend,
    make_entry_gate,
)
from backtesting.scalp_equity import run_scalp_equity_backtest
from monitor.scalp_models import ScalpSessionConfig, SessionMode

IST = timezone(timedelta(hours=5, minutes=30))


# ──────────────────────────────────────────────────────────────────────
# Daily candle helpers
# ──────────────────────────────────────────────────────────────────────

def _daily(d: date, close: float) -> dict:
    ts = datetime(d.year, d.month, d.day, 15, 30, tzinfo=IST)
    return {"timestamp": ts.isoformat(), "open": close, "high": close,
            "low": close, "close": close, "volume": 100_000}


def _daily_series(closes: list[float], start: date = date(2026, 1, 5)) -> list[dict]:
    """One daily candle per consecutive calendar day (weekends don't matter
    for the math — the map is keyed by whatever dates exist)."""
    return [_daily(start + timedelta(days=i), c) for i, c in enumerate(closes)]


# ──────────────────────────────────────────────────────────────────────
# compute_daily_trend — variants
# ──────────────────────────────────────────────────────────────────────

class TestDailyEma20:
    def test_rising_series_turns_up_after_warmup_shifted(self):
        # 30 strictly rising closes. Direction at close of day i (i>=19) is
        # "up"; the MAP value for a date is the PRIOR day's direction.
        candles = _daily_series([100.0 + i for i in range(30)])
        trend = compute_daily_trend(candles, "daily_ema20")
        dates = sorted(d for d in trend)
        # dates[19]'s value = direction at close of dates[18] → insufficient → flat
        assert trend[dates[19]] == "flat"
        # dates[20]'s value = direction at close of dates[19] (20th close) → up
        assert trend[dates[20]] == "up"
        assert trend[dates[-1]] == "up"

    def test_falling_series_turns_down(self):
        candles = _daily_series([200.0 - i for i in range(30)])
        trend = compute_daily_trend(candles, "daily_ema20")
        dates = sorted(trend)
        assert trend[dates[-1]] == "down"

    def test_insufficient_history_all_flat(self):
        candles = _daily_series([100.0 + i for i in range(10)])  # < 20 closes
        trend = compute_daily_trend(candles, "daily_ema20")
        assert set(trend.values()) == {"flat"}


class TestDailyEma2050:
    def test_rising_series_up_after_50(self):
        candles = _daily_series([100.0 + i for i in range(60)])
        trend = compute_daily_trend(candles, "daily_ema20_50")
        dates = sorted(trend)
        # dates[49]'s value = direction at close of dates[48] → ema50 not yet seeded → flat
        assert trend[dates[49]] == "flat"
        # dates[50]'s value = direction at dates[49] (50th close): ema20 > ema50 → up
        assert trend[dates[50]] == "up"
        assert trend[dates[-1]] == "up"

    def test_falling_series_down(self):
        candles = _daily_series([300.0 - i for i in range(60)])
        trend = compute_daily_trend(candles, "daily_ema20_50")
        dates = sorted(trend)
        assert trend[dates[-1]] == "down"

    def test_insufficient_history_all_flat(self):
        candles = _daily_series([100.0 + i for i in range(40)])  # < 50 closes
        trend = compute_daily_trend(candles, "daily_ema20_50")
        assert set(trend.values()) == {"flat"}


class TestDailyMom3:
    def test_momentum_sign_and_shift(self):
        # closes: 100,100,100,103 → direction at close of index 3 is "up"
        # (103-100>0). The MAP gives that to the NEXT date (index 4 / ghost).
        candles = _daily_series([100.0, 100.0, 100.0, 103.0])
        trend = compute_daily_trend(candles, "daily_mom3")
        dates = sorted(trend)
        # dates[3]'s value = direction at close of index 2 → insufficient → flat
        assert trend[dates[3]] == "flat"
        # ghost key (last date + 1) carries direction at the last close → up
        assert trend[dates[-1]] == "up"

    def test_down_and_flat(self):
        down = compute_daily_trend(
            _daily_series([110.0, 109.0, 108.0, 100.0, 99.0]), "daily_mom3")
        assert down[sorted(down)[-1]] == "down"
        # Zero 3-day diff → flat.
        flat = compute_daily_trend(
            _daily_series([100.0, 105.0, 95.0, 100.0, 100.0]), "daily_mom3")
        # direction at close of last candle: 100 - 105 < 0 → down... use the
        # 4th candle instead: 100 - 100 == 0 → flat, served on dates[4].
        assert flat[sorted(flat)[4]] == "flat"


class TestVariantValidation:
    def test_unknown_variant_raises(self):
        with pytest.raises(ValueError, match="unknown HTF trend variant"):
            compute_daily_trend(_daily_series([100.0] * 5), "daily_sma200")

    def test_unknown_variant_raises_even_on_empty(self):
        with pytest.raises(ValueError):
            compute_daily_trend([], "bogus")

    def test_empty_candles_empty_map(self):
        assert compute_daily_trend([], "daily_ema20") == {}

    def test_variant_list_is_the_three(self):
        assert HTF_VARIANTS == ["daily_ema20", "daily_ema20_50", "daily_mom3"]


# ──────────────────────────────────────────────────────────────────────
# NO LOOKAHEAD — the critical invariant
# ──────────────────────────────────────────────────────────────────────

class TestNoLookahead:
    def test_huge_up_candle_on_day_d_does_not_make_day_d_up(self):
        # 25 gently declining closes (trend firmly "down" at each close), then
        # day D explodes upward far above EMA20. A trade ON day D must still
        # see "down" — D's close hasn't printed when intraday entries fire.
        closes = [200.0 - i for i in range(25)] + [400.0]
        candles = _daily_series(closes)
        trend = compute_daily_trend(candles, "daily_ema20")
        dates = sorted(d for d in trend)
        spike_day = dates[25]  # the +400 day (last real candle date)
        assert trend[spike_day] == "down"      # judged by D-1's close only
        # The day AFTER the spike (ghost key) sees the spike close → up.
        assert trend[dates[26]] == "up"

    def test_mom3_spike_day_not_up(self):
        closes = [100.0, 99.0, 98.0, 97.0, 96.0, 300.0]
        trend = compute_daily_trend(_daily_series(closes), "daily_mom3")
        dates = sorted(trend)
        spike_day = dates[5]
        assert trend[spike_day] == "down"      # 96 - 99 < 0, spike not seen
        assert trend[dates[6]] == "up"         # ghost: 300 - 97 > 0


# ──────────────────────────────────────────────────────────────────────
# make_entry_gate
# ──────────────────────────────────────────────────────────────────────

class TestMakeEntryGate:
    def _ts(self, d: date) -> datetime:
        return datetime(d.year, d.month, d.day, 10, 30, tzinfo=IST)

    def test_align_semantics(self):
        d_up, d_down, d_flat = date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)
        gate = make_entry_gate({d_up: "up", d_down: "down", d_flat: "flat"})
        assert gate(self._ts(d_up), "long") is True
        assert gate(self._ts(d_up), "short") is False
        assert gate(self._ts(d_down), "long") is False
        assert gate(self._ts(d_down), "short") is True
        # flat blocks BOTH (conservative: no detected regime, no trade).
        assert gate(self._ts(d_flat), "long") is False
        assert gate(self._ts(d_flat), "short") is False

    def test_missing_date_falls_back_to_most_recent_prior(self):
        gate = make_entry_gate({date(2026, 6, 1): "up"})
        # 2026-06-05 absent → most recent PRIOR key (06-01) → up → long ok.
        assert gate(self._ts(date(2026, 6, 5)), "long") is True
        assert gate(self._ts(date(2026, 6, 5)), "short") is False

    def test_date_before_series_blocks(self):
        gate = make_entry_gate({date(2026, 6, 10): "up"})
        assert gate(self._ts(date(2026, 6, 1)), "long") is False

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="unknown entry-gate mode"):
            make_entry_gate({}, mode="contra")


# ──────────────────────────────────────────────────────────────────────
# Engine entry_gate hook (run_scalp_equity_backtest)
# ──────────────────────────────────────────────────────────────────────

def _intraday_candle(ts: datetime, o: float, h: float, l: float, c: float) -> dict:
    return {"timestamp": ts.isoformat(), "open": o, "high": h, "low": l,
            "close": c, "volume": 1000}


def _oscillating_day(day: datetime, n: int = 60) -> list[dict]:
    """One session of 5-min bars whose closes oscillate up/down so an EMA
    crossover (fast 3 / slow 5) flips repeatedly → long AND short entries."""
    bars = []
    price = 100.0
    prev = price
    for i in range(n):
        price += 0.6 if (i % 14) < 7 else -0.6
        ts = day.replace(hour=9, minute=15) + timedelta(minutes=5 * i)
        c = round(price, 2)
        bars.append(_intraday_candle(ts, prev, max(prev, c) + 0.2,
                                     min(prev, c) - 0.2, c))
        prev = c
    return bars


def _gate_test_config() -> ScalpSessionConfig:
    return ScalpSessionConfig(
        name="gate-test",
        session_mode=SessionMode.EQUITY_INTRADAY.value,
        underlying="TEST",
        indicator_timeframe="5m",
        primary_indicator="ema_crossover",
        primary_params={"fast": 3, "slow": 5},
        squareoff_time="15:15",
        max_trades=20,
        cooldown_seconds=0,
        entry_side="both",
        quantity=10,
    )


class TestEngineEntryGate:
    def _runs(self):
        candles = _oscillating_day(datetime(2026, 6, 1, tzinfo=IST))
        cfg = _gate_test_config()
        ungated = run_scalp_equity_backtest(
            candles, cfg, symbol="TEST", interval="5minute")
        gated = run_scalp_equity_backtest(
            candles, cfg, symbol="TEST", interval="5minute",
            entry_gate=lambda ts, side: side != "short")
        return ungated, gated

    def test_gate_blocks_shorts_only(self):
        ungated, gated = self._runs()
        # Sanity: the ungated run produced both sides (else the test is vacuous).
        assert any(t.side == "short" for t in ungated.trades)
        assert any(t.side == "long" for t in ungated.trades)
        # Gated run: only longs, with blocks counted.
        assert all(t.side == "long" for t in gated.trades)
        assert gated.entry_gate_blocks > 0
        assert ungated.entry_gate_blocks == 0

    def test_taken_trades_match_ungated_longs(self):
        # With permissive guards (max_trades=20, cooldown=0) blocking shorts
        # must not perturb the long entries: same flips, same fills. This also
        # proves position state was NOT mutated for blocked entries — a stuck
        # phantom position would shift or swallow subsequent longs.
        ungated, gated = self._runs()
        ungated_longs = [(t.entry_time, t.exit_time, t.pnl)
                         for t in ungated.trades if t.side == "long"]
        gated_longs = [(t.entry_time, t.exit_time, t.pnl) for t in gated.trades]
        assert gated_longs == ungated_longs

    def test_default_none_is_zero_change(self):
        candles = _oscillating_day(datetime(2026, 6, 1, tzinfo=IST))
        cfg = _gate_test_config()
        a = run_scalp_equity_backtest(candles, cfg, symbol="TEST", interval="5minute")
        b = run_scalp_equity_backtest(candles, cfg, symbol="TEST", interval="5minute",
                                      entry_gate=None)
        assert [(t.entry_time, t.exit_time, t.pnl) for t in a.trades] == \
               [(t.entry_time, t.exit_time, t.pnl) for t in b.trades]
        assert a.entry_gate_blocks == b.entry_gate_blocks == 0

    def test_block_everything_yields_no_trades(self):
        candles = _oscillating_day(datetime(2026, 6, 1, tzinfo=IST))
        cfg = _gate_test_config()
        r = run_scalp_equity_backtest(
            candles, cfg, symbol="TEST", interval="5minute",
            entry_gate=lambda ts, side: False)
        assert r.trades == []
        assert r.entry_gate_blocks > 0
