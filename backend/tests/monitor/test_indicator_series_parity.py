"""Parity test for compute_indicator_series.

Guarantee: for every supported indicator and every prefix length n,
    compute_indicator_series(ind, candles, params)[n - 1]
        == compute_indicator(ind, candles[:n], params)

This is the contract that lets backtests precompute once and index by
bar — if it fails, the backtest will silently disagree with the live
engine on signal timing.

We don't test every possible params combo, just enough to cover the
output branches of each indicator and a representative warmup window.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest

from monitor.indicator_engine import compute_indicator
from monitor.indicator_series import compute_indicator_series, has_native_series


# ──────────────────────────────────────────────────────────────────────
# Candle generators
# ──────────────────────────────────────────────────────────────────────


def _make(prices: list[float], step_min: int = 5) -> list[dict]:
    base = datetime(2026, 5, 1, 9, 15)
    out = []
    for i, p in enumerate(prices):
        out.append({
            "timestamp": (base + timedelta(minutes=i * step_min)).isoformat(),
            "open": p - 0.5,
            "high": p + 1.0,
            "low": p - 1.0,
            "close": p,
            "volume": 1000 + i,
        })
    return out


def _uptrend(n: int, start: float = 100.0, step: float = 0.5) -> list[dict]:
    return _make([start + i * step for i in range(n)])


def _downtrend(n: int, start: float = 200.0, step: float = 0.5) -> list[dict]:
    return _make([start - i * step for i in range(n)])


def _zigzag(n: int, base: float = 100.0, amp: float = 5.0) -> list[dict]:
    return _make([base + amp * (-1) ** i for i in range(n)])


def _flat(n: int, price: float = 100.0) -> list[dict]:
    return _make([price] * n)


# ──────────────────────────────────────────────────────────────────────
# Parity helper
# ──────────────────────────────────────────────────────────────────────


def _approx_equal(a: float | None, b: float | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, float) and math.isnan(a) and isinstance(b, float) and math.isnan(b):
        return True
    return abs(a - b) < 1e-6 or (
        abs(a) > 1e-6 and abs((a - b) / a) < 1e-6
    )


def _check_parity(indicator: str, candles: list[dict], params: dict) -> None:
    """Compute series, then compute compute_indicator on every prefix and
    assert they agree. Slow (O(n²) by design — that's the test's cost)."""
    series = compute_indicator_series(indicator, candles, params)
    assert len(series) == len(candles), (
        f"{indicator}: series length {len(series)} != candles length {len(candles)}"
    )
    for i in range(len(candles)):
        prefix = candles[: i + 1]
        expected = compute_indicator(indicator, prefix, params)
        actual = series[i]
        assert _approx_equal(actual, expected), (
            f"{indicator} mismatch at i={i}: series={actual}, "
            f"compute_indicator(prefix)={expected}, params={params}"
        )


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("output", ["value", "centered"])
def test_rsi_parity(output):
    candles = _zigzag(40)
    _check_parity("rsi", candles, {"period": 14, "output": output})


def test_macd_parity():
    candles = _uptrend(40, step=0.3)
    _check_parity("macd", candles, {})


def test_macd_parity_warmup():
    # MACD diff is NaN early; series must hit the line-fallback path.
    candles = _uptrend(30, step=0.3)
    _check_parity("macd", candles, {})


def test_ema_crossover_parity():
    candles = _uptrend(40)
    _check_parity("ema_crossover", candles, {"fast": 9, "slow": 21})


def test_ema_crossover_parity_short_window():
    candles = _uptrend(15)
    # Below slow period — series should be all None
    _check_parity("ema_crossover", candles, {"fast": 9, "slow": 21})


def test_ema_crossover_parity_legacy_keys():
    # Legacy ema_fast/ema_slow spelling must work and stay engine↔series
    # consistent — and equal the canonical fast/slow result.
    candles = _uptrend(40)
    _check_parity("ema_crossover", candles, {"ema_fast": 9, "ema_slow": 21})
    legacy = compute_indicator_series(
        "ema_crossover", candles, {"ema_fast": 9, "ema_slow": 21}
    )
    canonical = compute_indicator_series(
        "ema_crossover", candles, {"fast": 9, "slow": 21}
    )
    assert legacy == canonical


def test_volume_spike_parity():
    candles = _uptrend(30)
    # Bump volume on the last few bars to get a real spike
    for i in range(25, 30):
        candles[i]["volume"] = 5000
    _check_parity("volume_spike", candles, {"lookback": 10})


def test_vwap_parity():
    candles = _zigzag(30)
    _check_parity("vwap", candles, {})


@pytest.mark.parametrize("band", ["upper", "lower", "width", "pctb"])
def test_bollinger_parity(band):
    candles = _zigzag(40, amp=3.0)
    _check_parity("bollinger", candles, {"period": 20, "band": band})


def test_supertrend_parity():
    # Use a longer trending sequence so supertrend has time to flip.
    prices = [100 + i * 0.5 for i in range(20)] + [110 - i * 0.6 for i in range(20)]
    candles = _make(prices)
    _check_parity("supertrend", candles, {"period": 10, "multiplier": 2.0})


@pytest.mark.parametrize("output", ["trend", "stop", "signal"])
def test_utbot_parity(output):
    prices = [100 + i * 0.4 for i in range(15)] + [106 - i * 0.5 for i in range(15)]
    candles = _make(prices)
    _check_parity("utbot", candles, {"period": 10, "sensitivity": 1.0, "output": output})


def test_halftrend_parity():
    # halftrend needs >= atr_period bars; use atr_period=5 to keep test fast.
    prices = [100 + i * 0.3 for i in range(15)] + [104.5 - i * 0.4 for i in range(15)]
    candles = _make(prices)
    _check_parity("halftrend", candles, {"amplitude": 2, "atr_period": 5})


def test_qqe_mod_parity():
    candles = _zigzag(30)
    _check_parity("qqe_mod", candles, {"rsi_period": 6, "smoothing": 5})


@pytest.mark.parametrize("output", ["signal", "raw", "rsi", "ema", "wma"])
def test_hilega_milega_parity(output):
    candles = _zigzag(50)
    _check_parity(
        "hilega_milega",
        candles,
        {"rsi_period": 9, "wma_period": 21, "ema_period": 3, "output": output},
    )


def test_ssl_hybrid_parity():
    prices = [100 + i * 0.3 for i in range(15)] + [104.5 - i * 0.4 for i in range(15)]
    candles = _make(prices)
    _check_parity("ssl_hybrid", candles, {"period": 10})


def test_ssl_hybrid_with_baseline_parity():
    prices = [100 + i * 0.3 for i in range(20)] + [106 - i * 0.5 for i in range(20)]
    candles = _make(prices)
    _check_parity("ssl_hybrid", candles, {"period": 10, "baseline_period": 14})


# ──────────────────────────────────────────────────────────────────────
# Registry coverage
# ──────────────────────────────────────────────────────────────────────


def test_registry_has_expected_indicators():
    """Catch silent dropouts if someone removes an indicator from the registry."""
    expected = {
        "rsi", "macd", "ema_crossover", "volume_spike", "vwap", "bollinger",
        "supertrend", "utbot", "halftrend", "qqe_mod", "hilega_milega",
        "ssl_hybrid",
    }
    for ind in expected:
        assert has_native_series(ind), f"{ind} dropped from native series registry"


def test_unsupported_falls_back_to_prefix():
    """linear_regression has no native impl — must still return a series via
    prefix recompute, not error."""
    candles = _uptrend(30)
    series = compute_indicator_series(
        "linear_regression", candles, {"period": 20, "output": "slope"}
    )
    assert len(series) == 30
    # Below period, expect None; at and beyond, expect a numeric slope.
    assert all(v is None for v in series[:19])
    assert all(isinstance(v, float) for v in series[19:])


def test_empty_candles():
    assert compute_indicator_series("rsi", [], {}) == []


def test_unknown_indicator_returns_nones():
    candles = _uptrend(20)
    series = compute_indicator_series("totally_made_up_indicator", candles, {})
    assert series == [None] * 20
