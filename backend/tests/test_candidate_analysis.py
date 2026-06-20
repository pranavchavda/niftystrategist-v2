"""Tests for the candidate deep-analysis precompute (decision-surface enrichment).

Covers: compact_analysis reduction, analyze_symbol guards (insufficient candles,
fetch failure), enrich_rows_with_analysis batching/best-effort, and the snapshot
one-line render.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.candidate_analysis import (
    analyze_symbol,
    compact_analysis,
    enrich_rows_with_analysis,
)
from services.trading_snapshot import _analysis_line


def _indicators(**over):
    base = dict(
        rsi_14=58.0, macd_histogram=2.5, supertrend=1.0, utbot_trend="long",
        renko_trend="up", renko_brick_count=3, vwap=100.0, bb_pctb=0.74,
        atr_14=12.3,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _analysis(**over):
    base = dict(
        symbol="COFORGE", current_price=110.0, overall_signal="strong_buy",
        confidence=0.72, macd_trend="bullish", price_trend="uptrend",
        support_level=100.0, resistance_level=120.0, indicators=_indicators(),
    )
    base.update(over)
    return SimpleNamespace(**base)


# ── compact_analysis ─────────────────────────────────────────────────────────

def test_compact_analysis_full():
    c = compact_analysis(_analysis())
    assert c["signal"] == "strong_buy"
    assert c["conf"] == 0.72
    assert c["rsi"] == 58.0
    assert c["macd_hist"] == 2.5
    assert c["macd_trend"] == "bullish"
    assert c["supertrend"] == "bull"
    assert c["utbot"] == "long"
    assert c["renko"] == "↑3"
    assert c["vwap_pos"] == "above"   # price 110 >= vwap 100
    assert c["bb_pctb"] == 0.74
    assert c["atr"] == 12.3
    assert c["sup"] == 100.0 and c["res"] == 120.0


def test_compact_analysis_bearish_supertrend_and_below_vwap():
    c = compact_analysis(_analysis(
        current_price=90.0, indicators=_indicators(supertrend=-1.0, renko_trend="down", renko_brick_count=2),
    ))
    assert c["supertrend"] == "bear"
    assert c["vwap_pos"] == "below"
    assert c["renko"] == "↓2"


def test_compact_analysis_handles_none_fields():
    c = compact_analysis(_analysis(
        confidence=None,
        indicators=_indicators(supertrend=None, renko_trend=None, vwap=None,
                               bb_pctb=None, atr_14=None, rsi_14=None, macd_histogram=None),
    ))
    assert c["supertrend"] is None
    assert c["renko"] is None
    assert c["vwap_pos"] is None
    assert c["rsi"] is None
    assert c["conf"] is None


# ── analyze_symbol guards ────────────────────────────────────────────────────

class _Client:
    def __init__(self, candles=None, raise_on_fetch=False):
        self._candles = candles or []
        self._raise = raise_on_fetch

    async def get_historical_data(self, symbol, interval, days):
        if self._raise:
            raise RuntimeError("fetch boom")
        return self._candles


@pytest.mark.asyncio
async def test_analyze_symbol_none_on_empty_symbol():
    assert await analyze_symbol(_Client(), "") is None


@pytest.mark.asyncio
async def test_analyze_symbol_none_on_fetch_error():
    assert await analyze_symbol(_Client(raise_on_fetch=True), "TCS") is None


@pytest.mark.asyncio
async def test_analyze_symbol_none_on_insufficient_candles():
    # fewer than the 50-candle minimum → None (don't compute on thin data)
    assert await analyze_symbol(_Client(candles=[object()] * 10), "TCS") is None


# ── enrich_rows_with_analysis ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enrich_attaches_analysis_best_effort(monkeypatch):
    import services.candidate_analysis as mod

    async def fake_analyze(client, symbol, **kw):
        return None if symbol == "BADSYM" else {"signal": "buy", "conf": 0.6}

    monkeypatch.setattr(mod, "analyze_symbol", fake_analyze)
    rows = [{"symbol": "AAA"}, {"symbol": "BADSYM"}, {"symbol": "CCC"}]
    out = await enrich_rows_with_analysis(rows, client=object(), deep_n=10)
    assert out[0]["analysis"]["signal"] == "buy"
    assert "analysis" not in out[1]   # failed symbol left un-enriched
    assert out[2]["analysis"]["signal"] == "buy"


@pytest.mark.asyncio
async def test_enrich_only_top_deep_n(monkeypatch):
    import services.candidate_analysis as mod

    async def fake_analyze(client, symbol, **kw):
        return {"signal": "hold"}

    monkeypatch.setattr(mod, "analyze_symbol", fake_analyze)
    rows = [{"symbol": f"S{i}"} for i in range(10)]
    await enrich_rows_with_analysis(rows, client=object(), deep_n=3)
    assert all("analysis" in r for r in rows[:3])
    assert all("analysis" not in r for r in rows[3:])


@pytest.mark.asyncio
async def test_enrich_empty_rows_noop():
    assert await enrich_rows_with_analysis([], client=object()) == []


# ── snapshot render ──────────────────────────────────────────────────────────

def test_analysis_line_render():
    line = _analysis_line(compact_analysis(_analysis()))
    assert "STRONG_BUY 72%" in line
    assert "ST bull" in line
    assert "MACD +2.5" in line
    assert "UTBot LONG" in line
    assert "Renko ↑3" in line
    assert ">VWAP" in line
    assert "BB%B 0.74" in line
    assert "S/R 100/120" in line  # plain levels, not abbreviated


def test_analysis_line_empty_on_none():
    assert _analysis_line(None) == ""
    assert _analysis_line({}) == ""
