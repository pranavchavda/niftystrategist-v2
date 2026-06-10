"""Unit tests for backtesting.ranking — the three-layer "best" definition.

Synthetic Trade objects throughout; no engine, no network. The per-trade NET
P&L is whatever we put in ``Trade.pnl`` (which on a real ScalpBacktestResult is
already net of charges+slippage).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from backtesting.ranking import (
    apply_gates,
    categorize_gate_reason,
    combo_score,
    confidence_label,
    day_consistency,
    gate_summary,
    plateau_flags,
    split_trades,
    tstat,
    validate_combo,
)
from backtesting.metrics import compute_metrics
from backtesting.simulator import Trade

IST = timezone(timedelta(hours=5, minutes=30))


def _trade(pnl: float, day: int = 9, hh: int = 10, mm: int = 0,
           exit_reason: str = "target", holding_minutes: int = 30,
           side: str = "long") -> Trade:
    """A synthetic completed trade with a given net pnl, opened on 2026-06-<day>."""
    t0 = datetime(2026, 6, day, hh, mm, tzinfo=IST)
    return Trade(
        symbol="TEST", side=side,
        entry_price=100.0, entry_time=t0,
        exit_price=100.0 + pnl, exit_time=t0 + timedelta(minutes=holding_minutes),
        quantity=1, pnl=pnl, pnl_pct=pnl,
        exit_reason=exit_reason, holding_minutes=holding_minutes,
    )


# ──────────────────────────────────────────────────────────────────────
# Layer 2a — tstat math
# ──────────────────────────────────────────────────────────────────────

class TestTstat:
    def test_too_few_returns_zero(self):
        assert tstat([]) == 0.0
        assert tstat([5.0]) == 0.0

    def test_zero_std_returns_zero(self):
        assert tstat([3.0, 3.0, 3.0, 3.0]) == 0.0

    def test_known_value(self):
        # pnls = [1,2,3,4,5]: mean=3, stdev(ddof=1)=sqrt(2.5), n=5
        # tstat = 3/sqrt(2.5)*sqrt(5)
        pnls = [1.0, 2.0, 3.0, 4.0, 5.0]
        import statistics
        expected = (3.0 / statistics.stdev(pnls)) * math.sqrt(5)
        assert tstat(pnls) == pytest.approx(expected)

    def test_negative_mean_negative_tstat(self):
        assert tstat([-1.0, -2.0, -3.0, -4.0]) < 0

    def test_outlier_dominated_series_lower_tstat_than_steady(self):
        # Same total/mean, but one is steady, one is a single spike.
        steady = [10.0, 10.0, 10.0, 10.0, 10.0]
        spiky = [0.0, 0.0, 0.0, 0.0, 50.0]
        # steady has zero std → tstat 0 (degenerate); compare a near-steady set.
        near_steady = [9.0, 10.0, 11.0, 10.0, 10.0]
        assert tstat(near_steady) > tstat(spiky)


# ──────────────────────────────────────────────────────────────────────
# Layer 2b — day consistency
# ──────────────────────────────────────────────────────────────────────

class TestDayConsistency:
    def test_empty(self):
        dc = day_consistency([])
        assert dc == {"profitable_day_fraction": 0.0, "median_day_pnl": 0.0, "n_days": 0}

    def test_groups_by_entry_date(self):
        trades = [
            _trade(10.0, day=9), _trade(20.0, day=9),   # day1 net +30
            _trade(-5.0, day=10),                        # day2 net -5
            _trade(40.0, day=11),                        # day3 net +40
        ]
        dc = day_consistency(trades)
        assert dc["n_days"] == 3
        assert dc["profitable_day_fraction"] == pytest.approx(2 / 3, abs=1e-4)
        # day pnls = [30, -5, 40] → median 30
        assert dc["median_day_pnl"] == 30.0


# ──────────────────────────────────────────────────────────────────────
# Layer 2c — combo_score keeps components separate
# ──────────────────────────────────────────────────────────────────────

class TestComboScore:
    def test_components_present_and_separate(self):
        trades = [_trade(10.0, day=9), _trade(-4.0, day=10), _trade(8.0, day=11)]
        sc = combo_score(trades)
        assert set(sc) >= {
            "tstat", "n_trades", "net_pnl", "expectancy_per_trade",
            "profitable_day_fraction", "median_day_pnl", "n_days",
        }
        assert sc["n_trades"] == 3
        assert sc["net_pnl"] == pytest.approx(14.0)
        assert sc["expectancy_per_trade"] == pytest.approx(14.0 / 3, abs=0.01)


# ──────────────────────────────────────────────────────────────────────
# Layer 1 — gates, each independent
# ──────────────────────────────────────────────────────────────────────

class TestGates:
    def _healthy(self, n=14):
        # Alternating winners/losers across many days, net positive, no flukes.
        trades = []
        for i in range(n):
            pnl = 30.0 if i % 2 == 0 else -20.0
            trades.append(_trade(pnl, day=9 + (i % 10),
                                 exit_reason="target" if pnl > 0 else "sl",
                                 holding_minutes=20 + i * 3))
        return trades

    def test_healthy_passes(self):
        trades = self._healthy()
        reasons = apply_gates(trades, compute_metrics(trades, 100_000))
        assert reasons == []

    def test_min_trades_gate(self):
        trades = [_trade(50.0, day=9 + i, holding_minutes=20 + i)
                  for i in range(5)]
        reasons = apply_gates(trades, compute_metrics(trades, 100_000), min_trades=10)
        assert any("only 5 trades" in r for r in reasons)

    def test_plausibility_gate_pf_inf(self):
        # 12 all-winners → PF=inf plausibility flag, also high WR.
        trades = [_trade(50.0, day=9 + (i % 10), holding_minutes=20 + i * 3)
                  for i in range(12)]
        reasons = apply_gates(trades, compute_metrics(trades, 100_000))
        assert any("plausibility:" in r and "PF=inf" in r for r in reasons)

    def test_single_trade_dominance_gate(self):
        # One ₹1000 winner, plus small winners/losers; best > 50% of gross profit.
        trades = [_trade(1000.0, day=9, holding_minutes=20)]
        for i in range(11):
            pnl = 30.0 if i % 2 else -25.0
            trades.append(_trade(pnl, day=10 + (i % 8),
                                 exit_reason="target" if pnl > 0 else "sl",
                                 holding_minutes=20 + i * 4))
        reasons = apply_gates(trades, compute_metrics(trades, 100_000))
        assert any("single-trade dominance" in r for r in reasons)

    def test_daily_loss_cap_gate(self):
        # One day stacks deep losses beyond the cap; force-squareoff would truncate.
        trades = []
        # day 9: three -2000 losers = -6000 (beyond a -5000 cap)
        for i in range(3):
            trades.append(_trade(-2000.0, day=9, mm=i * 5, exit_reason="sl",
                                 holding_minutes=15))
        # other days net positive so net_pnl gate doesn't also fire as the only reason
        for i in range(10):
            trades.append(_trade(900.0, day=11 + (i % 5), holding_minutes=20 + i))
        reasons = apply_gates(trades, compute_metrics(trades, 100_000),
                              daily_loss_cap=5000)
        assert any("daily loss cap breached" in r for r in reasons)

    def test_daily_loss_cap_not_triggered_when_under(self):
        trades = [_trade(-1000.0, day=9, mm=i * 5, exit_reason="sl",
                         holding_minutes=15) for i in range(3)]  # -3000, under 5000
        for i in range(10):
            trades.append(_trade(900.0, day=11 + (i % 5), holding_minutes=20 + i))
        reasons = apply_gates(trades, compute_metrics(trades, 100_000),
                              daily_loss_cap=5000)
        assert not any("daily loss cap" in r for r in reasons)

    def test_non_positive_net_gate(self):
        # 12 trades, net negative.
        trades = [_trade(-30.0 if i % 2 == 0 else 20.0, day=9 + (i % 10),
                         exit_reason="sl" if i % 2 == 0 else "target",
                         holding_minutes=20 + i * 3) for i in range(12)]
        reasons = apply_gates(trades, compute_metrics(trades, 100_000))
        assert any("≤ 0" in r for r in reasons)


# ──────────────────────────────────────────────────────────────────────
# Gate-reason categorization + gate_summary
# ──────────────────────────────────────────────────────────────────────

class TestGateCategorization:
    def test_round_trip_every_gate_maps_to_its_category(self):
        """Generate REAL reasons via apply_gates and assert each maps to its
        category — guards against the reason text and the prefix table drifting
        apart."""
        # min_trades
        few = [_trade(50.0, day=9 + i, holding_minutes=20 + i) for i in range(3)]
        reasons = apply_gates(few, compute_metrics(few, 100_000), min_trades=10)
        assert any(categorize_gate_reason(r) == "min_trades" for r in reasons)

        # plausibility (PF=inf all-winners)
        winners = [_trade(50.0, day=9 + (i % 10), holding_minutes=20 + i * 3)
                   for i in range(12)]
        reasons = apply_gates(winners, compute_metrics(winners, 100_000))
        assert any(categorize_gate_reason(r) == "plausibility" for r in reasons)

        # single-trade dominance
        dom = [_trade(1000.0, day=9, holding_minutes=20)]
        for i in range(11):
            pnl = 30.0 if i % 2 else -25.0
            dom.append(_trade(pnl, day=10 + (i % 8),
                              exit_reason="target" if pnl > 0 else "sl",
                              holding_minutes=20 + i * 4))
        reasons = apply_gates(dom, compute_metrics(dom, 100_000))
        assert any(categorize_gate_reason(r) == "single_trade_dominance"
                   for r in reasons)

        # daily loss cap
        cap = [_trade(-2000.0, day=9, mm=i * 5, exit_reason="sl",
                      holding_minutes=15) for i in range(3)]
        cap += [_trade(900.0, day=11 + (i % 5), holding_minutes=20 + i)
                for i in range(10)]
        reasons = apply_gates(cap, compute_metrics(cap, 100_000),
                              daily_loss_cap=5000)
        assert any(categorize_gate_reason(r) == "daily_loss_cap" for r in reasons)

        # net_pnl<=0
        losing = [_trade(-30.0 if i % 2 == 0 else 20.0, day=9 + (i % 10),
                         exit_reason="sl" if i % 2 == 0 else "target",
                         holding_minutes=20 + i * 3) for i in range(12)]
        reasons = apply_gates(losing, compute_metrics(losing, 100_000))
        assert any(categorize_gate_reason(r) == "net_pnl<=0" for r in reasons)

    def test_unknown_reason_falls_back_to_other(self):
        assert categorize_gate_reason("some future gate nobody wrote yet") == "other"

    def test_gate_summary_counts_and_orders(self):
        reason_lists = [
            ["net P&L ₹-120.00 ≤ 0 — not profitable"],
            ["net P&L ₹-50.00 ≤ 0 — not profitable",
             "only 4 trades (< 10 min) — sample too small; also kills PF=inf flukes"],
            ["net P&L ₹-9.00 ≤ 0 — not profitable"],
            ["single-trade dominance: best trade is 80% of gross profit (> 50%) — "
             "edge rides on one print"],
        ]
        summary = gate_summary(reason_lists)
        assert summary["net_pnl<=0"] == 3
        assert summary["min_trades"] == 1
        assert summary["single_trade_dominance"] == 1
        # Most-frequent category first.
        assert list(summary)[0] == "net_pnl<=0"

    def test_gate_summary_empty(self):
        assert gate_summary([]) == {}


# ──────────────────────────────────────────────────────────────────────
# Layer 3 — split + validate
# ──────────────────────────────────────────────────────────────────────

class TestSplit:
    def test_partition_by_date_boundary(self):
        from datetime import date
        trades = [
            _trade(1.0, day=9), _trade(2.0, day=10),
            _trade(3.0, day=11), _trade(4.0, day=12),
        ]
        train, validate = split_trades(trades, date(2026, 6, 11))
        # day 9,10 < 11 → train; day 11,12 → validate (on-or-after).
        assert [t.pnl for t in train] == [1.0, 2.0]
        assert [t.pnl for t in validate] == [3.0, 4.0]

    def test_split_date_equals_a_trade_date_goes_to_validate(self):
        from datetime import date
        trades = [_trade(1.0, day=10), _trade(2.0, day=10)]
        train, validate = split_trades(trades, date(2026, 6, 10))
        assert train == []
        assert len(validate) == 2


class TestValidate:
    def test_confirmed_when_validation_positive_same_sign(self):
        train = [_trade(10.0, day=9), _trade(8.0, day=10), _trade(-3.0, day=10)]
        validate = [_trade(7.0, day=12), _trade(5.0, day=13), _trade(-2.0, day=13)]
        wf = validate_combo(train, validate)
        assert wf["confirmed"] is True
        assert wf["validation"]["net_pnl"] > 0
        assert wf["train"]["n_trades"] == 3
        assert wf["validation"]["n_trades"] == 3

    def test_rejected_when_validation_negative(self):
        train = [_trade(10.0, day=9), _trade(8.0, day=10)]
        validate = [_trade(-7.0, day=12), _trade(-5.0, day=13)]
        wf = validate_combo(train, validate)
        assert wf["confirmed"] is False

    def test_rejected_on_sign_flip(self):
        # Validation is net-positive but train mean was NEGATIVE → sign flip → reject.
        train = [_trade(-10.0, day=9), _trade(-8.0, day=10)]
        validate = [_trade(7.0, day=12), _trade(5.0, day=13)]
        wf = validate_combo(train, validate)
        assert wf["validation"]["net_pnl"] > 0
        assert wf["confirmed"] is False  # sign flip

    def test_expectancy_per_day_uses_distinct_days(self):
        # 2 validation days, net +12 → 6/day.
        validate = [_trade(10.0, day=12), _trade(-4.0, day=12), _trade(6.0, day=13)]
        wf = validate_combo([_trade(5.0, day=9)], validate)
        assert wf["validation"]["n_days"] == 2
        assert wf["validation"]["expectancy_per_day"] == pytest.approx(6.0)


# ──────────────────────────────────────────────────────────────────────
# Confidence labels
# ──────────────────────────────────────────────────────────────────────

class TestConfidence:
    def test_high(self):
        assert confidence_label(2.5, 10) == "high"
        assert confidence_label(2.0, 8) == "high"

    def test_high_needs_both_tstat_and_n(self):
        assert confidence_label(2.5, 7) == "medium"   # n too small
        assert confidence_label(1.5, 20) == "medium"  # tstat too low

    def test_medium(self):
        assert confidence_label(1.0, 5) == "medium"
        assert confidence_label(1.9, 4) == "medium"

    def test_low(self):
        assert confidence_label(0.5, 20) == "low"
        assert confidence_label(0.0, 2) == "low"


# ──────────────────────────────────────────────────────────────────────
# Plateau flags — spike vs plateau
# ──────────────────────────────────────────────────────────────────────

class TestPlateauFlags:
    def _row(self, trail, net, **rest):
        r = {"trail_percent": trail, "sl_points": None, "target_points": None,
             "net_pnl": net}
        r.update(rest)
        return r

    def test_spike_flagged(self):
        # trail 1.0 wins, neighbours 0.8 and 1.2 are net-negative → spike.
        rows = [
            self._row(0.8, -500),
            self._row(1.0, 5000),
            self._row(1.2, -300),
        ]
        plateau_flags(rows, ["trail_percent", "sl_points", "target_points"])
        assert "plateau_warning" in rows[1]
        assert "spike" in rows[1]["plateau_warning"]
        assert "plateau_warning" not in rows[0]
        assert "plateau_warning" not in rows[2]

    def test_plateau_not_flagged(self):
        # All three trail values net-positive → robust plateau, no flag.
        rows = [
            self._row(0.8, 3000),
            self._row(1.0, 5000),
            self._row(1.2, 2500),
        ]
        plateau_flags(rows, ["trail_percent", "sl_points", "target_points"])
        assert all("plateau_warning" not in r for r in rows)

    def test_only_one_neighbour_negative_not_flagged(self):
        # 0.8 negative but 1.2 positive → not a lone spike.
        rows = [
            self._row(0.8, -500),
            self._row(1.0, 5000),
            self._row(1.2, 2500),
        ]
        plateau_flags(rows, ["trail_percent", "sl_points", "target_points"])
        assert "plateau_warning" not in rows[1]

    def test_fewer_than_three_no_flag(self):
        rows = [self._row(0.8, -500), self._row(1.0, 5000)]
        plateau_flags(rows, ["trail_percent", "sl_points", "target_points"])
        assert all("plateau_warning" not in r for r in rows)

    def test_does_not_mix_groups_across_other_axes(self):
        # Two SL groups; a spike in one must not be confused by the other's rows.
        rows = [
            self._row(0.8, -500, sl_points=10),
            self._row(1.0, 5000, sl_points=10),
            self._row(1.2, -300, sl_points=10),
            self._row(0.8, 4000, sl_points=20),
            self._row(1.0, 4500, sl_points=20),
            self._row(1.2, 4200, sl_points=20),
        ]
        plateau_flags(rows, ["trail_percent", "sl_points", "target_points"])
        # sl=10 centre is a spike; sl=20 centre is a plateau.
        spike_row = next(r for r in rows if r["sl_points"] == 10 and r["trail_percent"] == 1.0)
        plateau_row = next(r for r in rows if r["sl_points"] == 20 and r["trail_percent"] == 1.0)
        assert "plateau_warning" in spike_row
        assert "plateau_warning" not in plateau_row
