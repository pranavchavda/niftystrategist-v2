"""Tests for the shared session_vwap helper (services/indicators.py).

Consolidated from the previously duplicated implementations in
nf-morning-scan and technical_analysis.
"""
import pandas as pd
import pytest

from services.indicators import session_vwap


def _df(rows):
    # rows: list of (timestamp, high, low, close, volume)
    return pd.DataFrame(
        rows, columns=["timestamp", "high", "low", "close", "volume"]
    )


def test_basic_cumulative_vwap():
    # two equal-volume bars; VWAP = mean of the two typical prices
    df = _df([
        ("2026-05-27T09:15:00+05:30", 102, 98, 100, 100),   # tp 100
        ("2026-05-27T09:30:00+05:30", 112, 108, 110, 100),  # tp 110
    ])
    assert session_vwap(df) == pytest.approx(105.0)


def test_volume_weighted():
    # heavier volume on the lower bar pulls VWAP down
    df = _df([
        ("2026-05-27T09:15:00+05:30", 100, 100, 100, 300),  # tp 100, vol 300
        ("2026-05-27T09:30:00+05:30", 110, 110, 110, 100),  # tp 110, vol 100
    ])
    # (100*300 + 110*100) / 400 = 102.5
    assert session_vwap(df) == pytest.approx(102.5)


def test_anchor_slices_to_latest_session():
    df = _df([
        ("2026-05-26T09:15:00+05:30", 200, 200, 200, 100),  # yesterday — excluded
        ("2026-05-27T09:15:00+05:30", 100, 100, 100, 100),
        ("2026-05-27T09:30:00+05:30", 110, 110, 110, 100),
    ])
    assert session_vwap(df, anchor_latest_session=True) == pytest.approx(105.0)


def test_no_anchor_uses_all_rows():
    df = _df([
        ("2026-05-26T09:15:00+05:30", 200, 200, 200, 100),
        ("2026-05-27T09:15:00+05:30", 100, 100, 100, 100),
    ])
    assert session_vwap(df, anchor_latest_session=False) == pytest.approx(150.0)


def test_min_rows_suppresses_single_bar():
    # one bar in the latest session + min_rows=2 → None (daily-interval guard)
    df = _df([
        ("2026-05-26T00:00:00+05:30", 100, 100, 100, 100),
        ("2026-05-27T00:00:00+05:30", 110, 110, 110, 100),
    ])
    assert session_vwap(df, anchor_latest_session=True, min_rows=2) is None


def test_zero_volume_returns_none():
    df = _df([
        ("2026-05-27T09:15:00+05:30", 100, 100, 100, 0),
        ("2026-05-27T09:30:00+05:30", 110, 110, 110, 0),
    ])
    assert session_vwap(df) is None


def test_empty_returns_none():
    assert session_vwap(pd.DataFrame()) is None
