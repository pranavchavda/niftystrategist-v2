"""Tests for plausibility_warnings — the self-flagging layer that keeps
artifact-driven backtest results from being quoted as edge.

Origin: 2026-06-09 mean-reversion day-open SL bug (100% WR / PF=inf reported
with no red flags; EOD reflection pivoted strategy allocation on it).
"""
from datetime import datetime, timedelta

import pytest

from backtesting.metrics import compute_metrics, plausibility_warnings
from backtesting.simulator import Trade


def _trade(pnl: float, exit_reason: str = "target",
           holding_minutes: int = 30, side: str = "long") -> Trade:
    t0 = datetime(2026, 6, 9, 10, 0)
    return Trade(
        symbol="TEST", side=side,
        entry_price=100.0, entry_time=t0,
        exit_price=100.0 + pnl, exit_time=t0 + timedelta(minutes=holding_minutes),
        quantity=1, pnl=pnl, pnl_pct=pnl,
        exit_reason=exit_reason, holding_minutes=holding_minutes,
    )


def _warns(trades: list[Trade]) -> list[str]:
    return plausibility_warnings(trades, compute_metrics(trades, 100_000))


class TestPlausibilityWarnings:
    def test_no_trades_no_warnings(self):
        assert _warns([]) == []

    def test_healthy_result_is_clean(self):
        # 12 trades, mixed outcomes, varied holds, signal exits — no flags.
        trades = []
        for i in range(12):
            pnl = 50.0 if i % 2 == 0 else -40.0
            trades.append(_trade(pnl, exit_reason="target" if pnl > 0 else "sl",
                                 holding_minutes=20 + i * 5))
        assert _warns(trades) == []

    def test_pf_inf_flagged(self):
        trades = [_trade(50.0, holding_minutes=20 + i * 5) for i in range(12)]
        warns = _warns(trades)
        assert any("PF=inf" in w for w in warns)

    def test_small_sample_flagged(self):
        trades = [_trade(50.0 if i % 2 else -40.0,
                         exit_reason="target" if i % 2 else "sl",
                         holding_minutes=20 + i * 5) for i in range(5)]
        warns = _warns(trades)
        assert any("sample too small" in w for w in warns)

    def test_high_win_rate_flagged(self):
        # 11 winners, 1 loser → 91.7% WR, finite PF, n>=10.
        trades = [_trade(50.0, holding_minutes=20 + i * 3) for i in range(11)]
        trades.append(_trade(-40.0, exit_reason="sl", holding_minutes=15))
        warns = _warns(trades)
        assert any("win_rate=" in w for w in warns)

    def test_time_exit_dominated_flagged(self):
        # 7 of 12 exits are squareoff/end_of_data (>50%).
        trades = [_trade(30.0 if i % 2 else -25.0, exit_reason="squareoff",
                         holding_minutes=200 + i) for i in range(6)]
        trades.append(_trade(30.0, exit_reason="end_of_data", holding_minutes=190))
        trades += [_trade(40.0 if i % 2 else -35.0,
                          exit_reason="target" if i % 2 else "sl",
                          holding_minutes=20 + i * 5) for i in range(5)]
        warns = _warns(trades)
        assert any("time-based" in w for w in warns)

    def test_minority_time_exits_not_flagged(self):
        # 3 of 12 squareoffs — fine.
        trades = [_trade(40.0 if i % 2 else -35.0,
                         exit_reason="target" if i % 2 else "sl",
                         holding_minutes=20 + i * 5) for i in range(9)]
        trades += [_trade(10.0, exit_reason="squareoff",
                          holding_minutes=200 + i) for i in range(3)]
        assert not any("time-based" in w for w in _warns(trades))

    def test_zero_duration_flagged(self):
        trades = [_trade(40.0 if i % 2 else -35.0,
                         exit_reason="target" if i % 2 else "sl",
                         holding_minutes=20 + i * 5) for i in range(11)]
        trades.append(_trade(0.0, exit_reason="end_of_data", holding_minutes=0))
        warns = _warns(trades)
        assert any("zero-duration" in w for w in warns)

    def test_identical_winner_holds_flagged(self):
        # The MR day-open SL signature: every winner exits after exactly one
        # bar (15 min), losers vary.
        trades = [_trade(50.0, exit_reason="sl", holding_minutes=15)
                  for _ in range(9)]
        trades += [_trade(-40.0, exit_reason="end_of_data",
                          holding_minutes=100 + i * 17) for i in range(3)]
        warns = _warns(trades)
        assert any("exactly 15 min" in w for w in warns)

    def test_varied_winner_holds_not_flagged(self):
        trades = [_trade(50.0, holding_minutes=15 + i) for i in range(9)]
        trades += [_trade(-40.0, exit_reason="sl",
                          holding_minutes=30 + i) for i in range(3)]
        assert not any("mechanical exit pattern" in w for w in _warns(trades))

    def test_mr_bug_replica_fires_multiple_flags(self):
        # Reconstruction of the pre-fix mean-reversion artifact: all "sl"
        # exits, all profitable, all one bar, PF=inf, 100% WR.
        trades = [_trade(300.0, exit_reason="sl", holding_minutes=15)
                  for _ in range(8)]
        warns = _warns(trades)
        joined = " ".join(warns)
        assert "PF=inf" in joined
        assert "win_rate=" in joined
        assert "exactly 15 min" in joined
        # Must be loud: at least 3 distinct flags on this pattern.
        assert len(warns) >= 3
