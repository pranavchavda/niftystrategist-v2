"""Tests for the linear_regression indicator in indicator_engine.

Covers:
- Each output variant (line, slope, upper, lower, pctb, r2)
- Edge cases: insufficient candles, flat series, pure trend
- Real-world use: pctb >= 1.0 fires when price touches upper band
"""
from __future__ import annotations

import random

import pytest

from monitor.indicator_engine import compute_indicator


def _make_candles(closes: list[float]) -> list[dict]:
    """Build minimal candle dicts from a close-price series."""
    return [
        {
            "timestamp": i,
            "open": c,
            "high": c,
            "low": c,
            "close": c,
            "volume": 0,
        }
        for i, c in enumerate(closes)
    ]


class TestInsufficientCandles:
    def test_returns_none_when_fewer_candles_than_period(self):
        candles = _make_candles([100.0] * 10)
        assert compute_indicator(
            "linear_regression", candles, {"period": 20, "output": "line"}
        ) is None

    def test_returns_none_below_engine_minimum(self):
        """compute_indicator has a global minimum of 3 candles."""
        candles = _make_candles([100.0, 101.0])
        assert compute_indicator(
            "linear_regression", candles, {"period": 20, "output": "line"}
        ) is None


class TestFlatSeries:
    """All closes identical → slope=0, bands collapse, pctb=0.5 midline."""

    def setup_method(self):
        self.candles = _make_candles([100.0] * 25)
        self.params = {"period": 20}

    def test_slope_is_zero(self):
        result = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "slope"}
        )
        assert abs(result) < 1e-6

    def test_line_matches_price(self):
        result = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "line"}
        )
        assert result == pytest.approx(100.0)

    def test_pctb_is_midline(self):
        """Epsilon guard kicks in because residuals are float-noise-tiny."""
        result = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "pctb"}
        )
        assert result == pytest.approx(0.5)

    def test_r2_is_one_for_perfectly_flat(self):
        """Convention: zero variance → perfect fit."""
        result = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "r2"}
        )
        assert result == pytest.approx(1.0)


class TestPureTrend:
    """Perfectly linear uptrend: y = 100 + i. Slope should be exactly 1."""

    def setup_method(self):
        self.candles = _make_candles([100.0 + i for i in range(25)])
        self.params = {"period": 20}

    def test_slope_matches_actual(self):
        result = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "slope"}
        )
        assert result == pytest.approx(1.0)

    def test_r2_is_perfect(self):
        result = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "r2"}
        )
        assert result == pytest.approx(1.0)

    def test_line_endpoint_matches_last_close(self):
        """For a perfect fit, the line endpoint equals the last close."""
        result = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "line"}
        )
        last_close = self.candles[-1]["close"]
        assert result == pytest.approx(last_close)

    def test_pctb_is_midline_when_price_on_line(self):
        """Perfect fit → bands collapse → pctb = 0.5 via epsilon guard."""
        result = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "pctb"}
        )
        assert result == pytest.approx(0.5)


class TestNoisyTrend:
    """Trend with small noise so bands have real width."""

    def setup_method(self):
        random.seed(42)
        self.closes = [100.0 + i + random.uniform(-2, 2) for i in range(25)]
        self.candles = _make_candles(self.closes)
        self.params = {"period": 20, "stdev": 2.0}

    def test_slope_is_positive(self):
        result = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "slope"}
        )
        assert result > 0.5  # approximately 1.0 but noise perturbs it

    def test_r2_is_high_but_not_perfect(self):
        result = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "r2"}
        )
        assert 0.8 < result < 1.0

    def test_upper_above_line(self):
        line = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "line"}
        )
        upper = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "upper"}
        )
        assert upper > line

    def test_lower_below_line(self):
        line = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "line"}
        )
        lower = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "lower"}
        )
        assert lower < line

    def test_pctb_in_valid_range_for_in_band_price(self):
        """When price is within ±2 stdev of the line, pctb ∈ [0, 1]."""
        result = compute_indicator(
            "linear_regression", self.candles, {**self.params, "output": "pctb"}
        )
        assert 0.0 <= result <= 1.0


class TestPriceAboveUpperBand:
    """The main use case: pctb >= 1.0 should fire "exit at upper band"."""

    def test_spike_above_upper_gives_pctb_gt_1(self):
        random.seed(7)
        closes = [100.0 + i + random.uniform(-1, 1) for i in range(24)]
        closes.append(145.0)  # unambiguous spike well above the trend line
        candles = _make_candles(closes)
        pctb = compute_indicator(
            "linear_regression", candles, {"period": 20, "output": "pctb", "stdev": 2.0}
        )
        assert pctb > 1.0, f"expected pctb > 1.0 on upper-band breakout, got {pctb}"

    def test_dip_below_lower_gives_pctb_lt_0(self):
        random.seed(7)
        closes = [100.0 + i + random.uniform(-1, 1) for i in range(24)]
        closes.append(80.0)  # unambiguous drop well below the trend line
        candles = _make_candles(closes)
        pctb = compute_indicator(
            "linear_regression", candles, {"period": 20, "output": "pctb", "stdev": 2.0}
        )
        assert pctb < 0.0, f"expected pctb < 0.0 on lower-band break, got {pctb}"


class TestParameterVariations:
    def test_wider_stdev_means_wider_band(self):
        random.seed(1)
        closes = [100.0 + i + random.uniform(-2, 2) for i in range(25)]
        candles = _make_candles(closes)
        narrow_upper = compute_indicator(
            "linear_regression", candles, {"period": 20, "output": "upper", "stdev": 1.0}
        )
        wide_upper = compute_indicator(
            "linear_regression", candles, {"period": 20, "output": "upper", "stdev": 3.0}
        )
        assert wide_upper > narrow_upper

    def test_different_periods_produce_different_fits(self):
        closes = [100.0 + i for i in range(12)] + [110.0 - i for i in range(13)]
        candles = _make_candles(closes)
        short_slope = compute_indicator(
            "linear_regression", candles, {"period": 10, "output": "slope"}
        )
        long_slope = compute_indicator(
            "linear_regression", candles, {"period": 25, "output": "slope"}
        )
        # Recent 10 bars are downtrend, full 25 bars net flat-ish
        assert short_slope < 0
        assert abs(long_slope) < abs(short_slope)

    def test_default_output_is_pctb(self):
        candles = _make_candles([100.0 + i * 0.5 for i in range(25)])
        default = compute_indicator("linear_regression", candles, {"period": 20})
        pctb = compute_indicator(
            "linear_regression", candles, {"period": 20, "output": "pctb"}
        )
        assert default == pytest.approx(pctb)
