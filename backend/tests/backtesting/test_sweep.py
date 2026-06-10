"""Unit tests for backtesting.sweep — grid expansion, fingerprint stability,
and an end-to-end run_combo on SYNTHETIC candles (no network).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backtesting.sweep import (
    _combo_fingerprint,
    assemble_symbol,
    compute_split_date,
    expand_grid,
    run_combo,
)

IST = timezone(timedelta(hours=5, minutes=30))


# ──────────────────────────────────────────────────────────────────────
# Grid expansion
# ──────────────────────────────────────────────────────────────────────

class TestExpandGrid:
    def test_solo_only_when_confirms_none(self):
        combos = expand_grid(
            primaries=["utbot", "macd"],
            confirms=None,
            intervals=["5minute"],
            exit_variants=[{"trail_percent": 1.0, "sl_points": None, "target_points": None}],
            sides=["long"],
        )
        # 2 primaries × 1 (solo) × 1 interval × 1 exit × 1 side = 2
        assert len(combos) == 2
        assert all(c["confirm"] is None for c in combos)

    def test_pairs_added_and_self_confirm_skipped(self):
        combos = expand_grid(
            primaries=["utbot", "macd"],
            confirms=["utbot", "macd"],
            intervals=["5minute"],
            exit_variants=[{"trail_percent": 1.0, "sl_points": None, "target_points": None}],
            sides=["long"],
        )
        # confirm options = [None, utbot, macd]; per primary skip confirm==primary.
        # utbot: None, macd  (skip utbot)  → 2
        # macd:  None, utbot (skip macd)   → 2
        assert len(combos) == 4
        # No combo confirms itself.
        assert not any(c["confirm"] == c["primary"] for c in combos)
        # Solo combos are included.
        assert any(c["primary"] == "utbot" and c["confirm"] is None for c in combos)

    def test_full_cartesian_count(self):
        combos = expand_grid(
            primaries=["a_primary", "b_primary"],  # placeholders; counting only
            confirms=None,
            intervals=["5minute", "15minute"],
            exit_variants=[
                {"trail_percent": 0.8, "sl_points": None, "target_points": None},
                {"trail_percent": 1.0, "sl_points": None, "target_points": None},
            ],
            sides=["long", "short"],
        )
        # 2 primaries × 1 confirm-opt × 2 intervals × 2 exits × 2 sides = 16
        assert len(combos) == 16


# ──────────────────────────────────────────────────────────────────────
# Fingerprint stability
# ──────────────────────────────────────────────────────────────────────

class TestFingerprint:
    def _combo(self, **over):
        c = {"primary": "utbot", "confirm": None, "interval": "5minute",
             "entry_side": "long", "trail_percent": 1.0, "sl_points": None,
             "target_points": None}
        c.update(over)
        return c

    def _sizing(self):
        return {"quantity": 10, "days": 15}

    def test_stable_across_calls(self):
        a = _combo_fingerprint(self._combo(), self._sizing(), "2026-06-09")
        b = _combo_fingerprint(self._combo(), self._sizing(), "2026-06-09")
        assert a == b

    def test_changes_with_combo(self):
        a = _combo_fingerprint(self._combo(), self._sizing(), "2026-06-09")
        b = _combo_fingerprint(self._combo(confirm="macd"), self._sizing(), "2026-06-09")
        assert a != b

    def test_changes_with_date(self):
        a = _combo_fingerprint(self._combo(), self._sizing(), "2026-06-09")
        b = _combo_fingerprint(self._combo(), self._sizing(), "2026-06-10")
        assert a != b

    def test_changes_with_sizing(self):
        a = _combo_fingerprint(self._combo(), {"quantity": 10, "days": 15}, "2026-06-09")
        b = _combo_fingerprint(self._combo(), {"quantity": 20, "days": 15}, "2026-06-09")
        assert a != b


# ──────────────────────────────────────────────────────────────────────
# Synthetic candle builder (deterministic, multi-day, clears warm-up)
# ──────────────────────────────────────────────────────────────────────

def _session_bars(day: datetime, prices: list[float], step_mins: int = 5) -> list[dict]:
    """One trading session's worth of 5-min bars from a close-price path."""
    bars = []
    prev = prices[0]
    for i, c in enumerate(prices):
        ts = day.replace(hour=9, minute=15) + timedelta(minutes=step_mins * i)
        o = prev
        h = max(o, c) + 0.2
        l = min(o, c) - 0.2
        bars.append({"timestamp": ts.isoformat(), "open": o, "high": h,
                     "low": l, "close": c, "volume": 1000})
        prev = c
    return bars


def _build_candles(n_days: int = 8, bars_per_day: int = 60):
    """Build a deterministic multi-day candle series with oscillating trends so
    an EMA-crossover primary actually flips and produces trades. Returns
    (candles, warmup_bars) where warmup covers the first ~3 days.
    """
    candles: list[dict] = []
    base_day = datetime(2026, 5, 4, tzinfo=IST)  # a Monday
    price = 100.0
    for d in range(n_days):
        day = base_day + timedelta(days=d)
        # Skip weekends to keep distinct trading dates realistic.
        if day.weekday() >= 5:
            continue
        prices = []
        # Oscillate up then down within the session to force EMA crossovers.
        for i in range(bars_per_day):
            phase = i % 20
            if phase < 10:
                price += 0.4
            else:
                price -= 0.4
            prices.append(round(price, 2))
        candles.extend(_session_bars(day, prices))
    # Warm-up = first 3 trading days of bars (compute-only).
    distinct_days = sorted({c["timestamp"][:10] for c in candles})
    warmup_cutoff = distinct_days[3] if len(distinct_days) > 3 else distinct_days[0]
    warmup_bars = sum(1 for c in candles if c["timestamp"][:10] < warmup_cutoff)
    return candles, warmup_bars


# ──────────────────────────────────────────────────────────────────────
# compute_split_date
# ──────────────────────────────────────────────────────────────────────

class TestSplitDate:
    def test_last_third_held_out(self):
        candles, warmup = _build_candles()
        split = compute_split_date(candles, warmup)
        assert split is not None
        in_window_days = sorted({c["timestamp"][:10] for c in candles[warmup:]})
        # split date is one of the in-window days, and not the first.
        assert split.isoformat() in in_window_days
        assert split.isoformat() != in_window_days[0]

    def test_single_day_returns_none(self):
        day = datetime(2026, 5, 4, tzinfo=IST)
        candles = _session_bars(day, [100.0, 101.0, 100.5])
        assert compute_split_date(candles, 0) is None


# ──────────────────────────────────────────────────────────────────────
# run_combo end-to-end on synthetic candles
# ──────────────────────────────────────────────────────────────────────

class TestRunCombo:
    def test_structure_and_single_run(self):
        candles, warmup = _build_candles()
        combo = {
            "primary": "ema_crossover", "confirm": None, "interval": "5minute",
            "entry_side": "long", "trail_percent": 1.0,
            "sl_points": None, "target_points": None,
        }
        row = run_combo(
            candles, warmup, "TEST", combo,
            quantity=10, slippage_bps=5.0, min_trades=1,
        )
        # Required structure.
        assert row["symbol"] == "TEST"
        assert row["primary"] == "ema_crossover"
        assert "gated" in row and isinstance(row["gated"], bool)
        assert "gate_reasons" in row and isinstance(row["gate_reasons"], list)
        assert "score" in row and "tstat" in row["score"]
        assert "walk_forward" in row
        wf = row["walk_forward"]
        assert "confirmed" in wf
        assert "train" in wf and "validation" in wf
        # Train/validate present (window has > 1 day).
        assert wf["train"] is not None
        assert wf["validation"] is not None
        assert "confidence" in row
        assert "validation_per_day" in row
        # Some trades should have fired on this oscillating series.
        assert row["total_trades"] >= 1

    def test_confirm_combo_runs(self):
        # A confirm pair must also run without error.
        candles, warmup = _build_candles()
        combo = {
            "primary": "ema_crossover", "confirm": "macd", "interval": "5minute",
            "entry_side": "long", "trail_percent": 1.0,
            "sl_points": None, "target_points": None,
        }
        row = run_combo(candles, warmup, "TEST", combo, quantity=10, min_trades=1)
        assert row["confirm"] == "macd"
        assert "walk_forward" in row

    def test_min_trades_gate_applies(self):
        candles, warmup = _build_candles()
        combo = {
            "primary": "ema_crossover", "confirm": None, "interval": "5minute",
            "entry_side": "long", "trail_percent": 1.0,
            "sl_points": None, "target_points": None,
        }
        # An absurdly high min_trades floor should gate it out.
        row = run_combo(candles, warmup, "TEST", combo, quantity=10, min_trades=99999)
        assert row["gated"] is True
        assert any("trades" in r for r in row["gate_reasons"])


# ──────────────────────────────────────────────────────────────────────
# assemble_symbol — gate_summary + --show-gated row inclusion
# ──────────────────────────────────────────────────────────────────────

def _fake_row(*, gated: bool, confirmed: bool, gate_reasons: list[str] | None = None,
              val_per_day: float = 0.0, net_pnl: float = 0.0, trail: float = 1.0) -> dict:
    """Minimal combo row carrying every key assemble_symbol touches."""
    return {
        "primary": "utbot", "confirm": None, "interval": "5minute",
        "entry_side": "long", "trail_percent": trail,
        "sl_points": None, "target_points": None,
        "total_trades": 12, "total_pnl": net_pnl,
        "gated": gated, "gate_reasons": gate_reasons or [],
        "confirmed": confirmed, "confidence": "low",
        "validation_per_day": val_per_day, "net_pnl": net_pnl,
        "walk_forward": {"confirmed": confirmed, "train": None, "validation": None},
    }


class TestAssembleSymbol:
    def _rows(self):
        return [
            # 3 gated: two net-pnl failures, one min_trades + plausibility.
            _fake_row(gated=True, confirmed=False,
                      gate_reasons=["net P&L ₹-100.00 ≤ 0 — not profitable"]),
            _fake_row(gated=True, confirmed=False,
                      gate_reasons=["net P&L ₹-55.00 ≤ 0 — not profitable"]),
            _fake_row(gated=True, confirmed=False,
                      gate_reasons=[
                          "only 4 trades (< 10 min) — sample too small; also kills PF=inf flukes",
                          "plausibility: n=4 trades: sample too small to establish an edge — "
                          "treat as anecdote, not statistics.",
                      ]),
            # 1 survived gates but failed validation.
            _fake_row(gated=False, confirmed=False, net_pnl=500.0),
            # 1 confirmed.
            _fake_row(gated=False, confirmed=True, val_per_day=350.0, net_pnl=900.0),
        ]

    def test_counts_and_gate_summary(self):
        blk = assemble_symbol("TEST", None, self._rows())
        assert blk["counts"] == {
            "tested": 5, "gated_out": 3, "failed_validation": 1, "confirmed": 1,
        }
        assert blk["gate_summary"] == {
            "net_pnl<=0": 2, "min_trades": 1, "plausibility": 1,
        }
        # Most-frequent category first.
        assert list(blk["gate_summary"])[0] == "net_pnl<=0"

    def test_default_excludes_dropped_rows(self):
        blk = assemble_symbol("TEST", None, self._rows())
        assert "gated_combos" not in blk
        assert "failed_validation_combos" not in blk
        assert len(blk["confirmed_combos"]) == 1
        assert blk["best"]["validation_per_day"] == 350.0

    def test_show_gated_includes_full_rows(self):
        blk = assemble_symbol("TEST", None, self._rows(), show_gated=True)
        gated = blk["gated_combos"]
        failed = blk["failed_validation_combos"]
        assert len(gated) == 3
        assert len(failed) == 1
        # Full rows, not summaries: combo spec + reasons + walk_forward intact.
        for r in gated:
            assert r["primary"] == "utbot"
            assert r["gate_reasons"]
            assert "walk_forward" in r
        assert failed[0]["confirmed"] is False and failed[0]["gated"] is False

    def test_all_gated_symbol_still_summarized(self):
        rows = [
            _fake_row(gated=True, confirmed=False,
                      gate_reasons=["net P&L ₹-10.00 ≤ 0 — not profitable"])
            for _ in range(4)
        ]
        blk = assemble_symbol("TEST", None, rows)
        assert blk["counts"]["confirmed"] == 0
        assert blk["gate_summary"] == {"net_pnl<=0": 4}
        assert blk["best"] is None


# ──────────────────────────────────────────────────────────────────────
# Window offset (replication runs)
# ──────────────────────────────────────────────────────────────────────

class _FakeCandle:
    def __init__(self, ts, px=100.0):
        self.timestamp = ts
        self.open = self.high = self.low = self.close = px
        self.volume = 1000


class _FakeClient:
    """Returns one candle per calendar day going back `days` from now."""

    def __init__(self):
        self.requested_days = None

    async def get_historical_data(self, symbol, interval="day", days=10):
        self.requested_days = days
        now = datetime.now(IST).replace(hour=10, minute=0, second=0, microsecond=0)
        return [_FakeCandle(now - timedelta(days=i)) for i in range(days, 0, -1)]


class TestEndOffsetDays:
    def test_offset_trims_recent_candles(self):
        import asyncio
        from backtesting.sweep import fetch_candles_with_warmup

        client = _FakeClient()
        candles, _ = asyncio.run(fetch_candles_with_warmup(
            client, "X", "day", days=10, end_offset_days=5))
        # Window must end 5 days ago: nothing newer than now-5d survives.
        cutoff = datetime.now(IST) - timedelta(days=5)
        assert candles, "offset window should still contain candles"
        assert all(c["timestamp"] < cutoff for c in candles)
        # Fetch must cover days + offset (+ warmup) so the shifted window is full.
        assert client.requested_days >= 15

    def test_offset_zero_keeps_recent_candles(self):
        import asyncio
        from backtesting.sweep import fetch_candles_with_warmup

        client = _FakeClient()
        candles, _ = asyncio.run(fetch_candles_with_warmup(
            client, "X", "day", days=10, end_offset_days=0))
        newest = max(c["timestamp"] for c in candles)
        assert newest > datetime.now(IST) - timedelta(days=2)

    def test_offset_changes_fingerprint(self):
        combo = {"primary": "macd", "confirm": None, "interval": "15minute",
                 "entry_side": "long", "trail_percent": 1.0,
                 "sl_points": None, "target_points": None}
        base = {"quantity": 10, "squareoff": "15:09", "max_trades": 3,
                "cooldown": 60, "slippage_bps": 5.0, "days": 40,
                "min_trades": 10, "max_single_trade_share": 0.5,
                "daily_loss_cap": None}
        fp0 = _combo_fingerprint(combo, {**base, "end_offset_days": 0}, "2026-06-10")
        fp40 = _combo_fingerprint(combo, {**base, "end_offset_days": 40}, "2026-06-10")
        assert fp0 != fp40


# ──────────────────────────────────────────────────────────────────────
# HTF gate axis — grid expansion, fingerprint, run_combo passthrough
# ──────────────────────────────────────────────────────────────────────

class TestHtfGateAxis:
    _EV = [{"trail_percent": 1.0, "sl_points": None, "target_points": None}]

    def test_default_grid_is_ungated(self):
        combos = expand_grid(["utbot"], None, ["5minute"], self._EV, ["long"])
        assert len(combos) == 1
        assert combos[0]["htf_gate"] is None

    def test_axis_multiplies_grid(self):
        combos = expand_grid(
            ["utbot", "macd"], None, ["5minute"], self._EV, ["long", "short"],
            htf_gates=[None, "daily_ema20", "daily_mom3"],
        )
        # 2 primaries × 1 confirm-opt × 1 interval × 1 exit × 2 sides × 3 gates = 12
        assert len(combos) == 12
        gates = {c["htf_gate"] for c in combos}
        assert gates == {None, "daily_ema20", "daily_mom3"}
        # The ungated baseline is a real grid member, not implied.
        assert sum(1 for c in combos if c["htf_gate"] is None) == 4

    def test_fingerprint_sensitive_to_htf_gate(self):
        base = {"primary": "utbot", "confirm": None, "interval": "5minute",
                "entry_side": "long", "trail_percent": 1.0,
                "sl_points": None, "target_points": None}
        sizing = {"quantity": 10, "days": 15}
        fp_none = _combo_fingerprint({**base, "htf_gate": None}, sizing, "2026-06-10")
        fp_ema = _combo_fingerprint({**base, "htf_gate": "daily_ema20"}, sizing, "2026-06-10")
        fp_mom = _combo_fingerprint({**base, "htf_gate": "daily_mom3"}, sizing, "2026-06-10")
        assert len({fp_none, fp_ema, fp_mom}) == 3


class TestRunComboHtfGate:
    def _combo(self, **over):
        c = {"primary": "ema_crossover", "confirm": None, "interval": "5minute",
             "entry_side": "long", "trail_percent": 1.0,
             "sl_points": None, "target_points": None,
             "htf_gate": "daily_ema20"}
        c.update(over)
        return c

    def test_row_carries_gate_fields_and_blocks(self):
        candles, warmup = _build_candles()
        # A gate that blocks everything: zero trades, every veto counted.
        row = run_combo(
            candles, warmup, "TEST", self._combo(),
            quantity=10, min_trades=1,
            entry_gate=lambda ts, side: False,
        )
        assert row["htf_gate"] == "daily_ema20"
        assert row["total_trades"] == 0
        assert row["entry_gate_blocks"] > 0

    def test_permissive_gate_matches_ungated(self):
        candles, warmup = _build_candles()
        ungated = run_combo(candles, warmup, "TEST",
                            self._combo(htf_gate=None),
                            quantity=10, min_trades=1)
        gated = run_combo(candles, warmup, "TEST", self._combo(),
                          quantity=10, min_trades=1,
                          entry_gate=lambda ts, side: True)
        assert gated["total_trades"] == ungated["total_trades"]
        assert gated["total_pnl"] == ungated["total_pnl"]
        assert gated["entry_gate_blocks"] == 0
        assert ungated["htf_gate"] is None
        assert ungated["entry_gate_blocks"] == 0
