"""Regression fixtures for backtesting/engine.py.

Engine math is now load-bearing for several user-facing flows (template
backtests, F&O leg replay, future strategy work). It had zero unit tests
before 2026-05-06. These pin trade output against deterministic candle
fixtures so the indicator-cache refactor (and future changes) can't
silently move the needle.

Each test runs a real strategy template end-to-end on synthetic candles
crafted to trigger a specific path. We pin trade count + entry/exit
prices + reasons; PnL falls out of those.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backtesting.engine import BacktestEngine, run_backtest_for_day
from strategies.orb import ORBTemplate
from strategies.breakout import BreakoutTemplate


def _candle(ts: datetime, o: float, h: float, l: float, c: float, v: int = 1000) -> dict:
    return {
        "timestamp": ts.isoformat(),
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": v,
    }


def _series(start: datetime, ohlc_list: list[tuple[float, float, float, float]],
            step_min: int = 5) -> list[dict]:
    return [
        _candle(start + timedelta(minutes=i * step_min), o, h, l, c)
        for i, (o, h, l, c) in enumerate(ohlc_list)
    ]


# ──────────────────────────────────────────────────────────────────────
# ORB — long entry, target hit
# ──────────────────────────────────────────────────────────────────────


def test_orb_long_entry_target_hit():
    """First candle defines the range. Bar 2 spikes above range_high → long entry.
    Trail stays inactive (still under arm threshold). A later bar hits target."""
    base = datetime(2026, 5, 1, 9, 15)
    # Range bar (skipped by run_backtest_for_day's `sim_candles = day_candles[1:]`):
    # high=100, low=98 → range_high=100, range_low=98
    bars = _series(base, [
        (99, 100, 98, 99),    # range bar
        (99, 99.5, 98.5, 99.2),    # below range_high — no fire
        (99, 101, 99, 100.8),      # crosses 100 → long entry @ 100
        (101, 102, 101, 101.5),    # holding
        (101.5, 105, 101, 104.8),  # target should hit (target = entry + 2 * (entry - sl))
        (104.5, 105, 100, 100.5),  # post-target
    ])

    template = ORBTemplate()
    plan = template.plan(
        "TEST",
        {
            "capital": 100_000,
            "risk_percent": 2.0,
            "rr_ratio": 2.0,
            "range_high": 100.0,
            "range_low": 98.0,
            "side": "long",
            "trail_percent": 1.5,
            "squareoff_time": "15:15",
        },
    )
    # ORB feeds bars[1:] to the engine in api/backtest.py — mirror that here.
    result = run_backtest_for_day(bars[1:], plan.rules, "TEST", "orb", 100_000)
    assert len(result.trades) >= 1, "expected at least one trade"
    t = result.trades[0]
    assert t.side == "long"
    assert t.entry_price == 100.0  # trigger fires at price-trigger value
    assert t.exit_reason in ("target", "trailing", "squareoff")


# ──────────────────────────────────────────────────────────────────────
# ORB — long entry, SL hit (no target)
# ──────────────────────────────────────────────────────────────────────


def test_orb_long_sl_hit():
    base = datetime(2026, 5, 1, 9, 15)
    bars = _series(base, [
        (99, 100, 98, 99),
        (99, 100.5, 99, 100.3),    # crosses 100 → long entry
        (100.3, 100.5, 99, 99.5),
        (99.5, 99.6, 97.8, 97.9),  # breaches SL @ 98
    ])
    template = ORBTemplate()
    plan = template.plan(
        "TEST",
        {
            "capital": 100_000,
            "risk_percent": 2.0,
            "rr_ratio": 2.0,
            "range_high": 100.0,
            "range_low": 98.0,
            "side": "long",
            "trail_percent": 1.5,
            "squareoff_time": "15:15",
        },
    )
    result = run_backtest_for_day(bars[1:], plan.rules, "TEST", "orb", 100_000)
    assert len(result.trades) >= 1
    t = result.trades[0]
    assert t.side == "long"
    assert t.exit_reason in ("sl", "trailing", "squareoff")


# ──────────────────────────────────────────────────────────────────────
# Multi-rule indicator cache: same indicator+params shared across rules
# ──────────────────────────────────────────────────────────────────────


def test_engine_handles_indicator_rule_via_cache():
    """An indicator-triggered rule fires through the precomputed series
    path. Smoke check the engine doesn't crash and produces deterministic
    trades — the parity is enforced by test_indicator_series_parity.py.
    """
    from strategies.templates import RuleSpec

    base = datetime(2026, 5, 1, 9, 15)
    # Long downtrend then upspike — RSI (centered) flips negative then back.
    closes = [100 - i * 0.5 for i in range(20)] + [90 + i * 1.2 for i in range(15)]
    bars = [_candle(base + timedelta(minutes=i * 5), c - 0.3, c + 0.5, c - 0.5, c)
            for i, c in enumerate(closes)]

    rules = [
        RuleSpec(
            name="rsi-entry",
            trigger_type="indicator",
            trigger_config={
                "indicator": "rsi",
                "condition": "lte",
                "value": 35,
                "params": {"period": 14},
            },
            action_type="place_order",
            action_config={"transaction_type": "BUY", "quantity": 1},
            role="entry",
        ),
        RuleSpec(
            name="rsi-exit",
            trigger_type="indicator",
            trigger_config={
                "indicator": "rsi",
                "condition": "gte",
                "value": 60,
                "params": {"period": 14},  # same params — should share cached series
            },
            action_type="place_order",
            action_config={"transaction_type": "SELL", "quantity": 1},
            role="exit",
        ),
    ]
    eng = BacktestEngine(bars, rules, "TEST", "rsi-test", 100_000)
    eng.run()
    # Cache should hold exactly one (indicator, params) entry — both rules share it.
    assert len(eng._indicator_cache) == 1
    assert ("rsi", (("period", 14),)) in eng._indicator_cache


# ──────────────────────────────────────────────────────────────────────
# Mean-reversion SL re-anchoring (2026-06-09 fake-"sl"-profit fix)
#
# A % stop was anchored to the day OPEN at rule-build time. A mean-reversion
# entry fires on an RSI spike away from the open, so the static stop landed on
# the wrong (profit) side of the fill and triggered as a guaranteed fake "sl"
# win. The engine now re-anchors entry_anchor_pct price exits to the real fill.
# ──────────────────────────────────────────────────────────────────────


def _engine_with(rules: list) -> BacktestEngine:
    base = datetime(2026, 5, 1, 9, 15)
    bars = _series(base, [(100, 100, 100, 100), (100, 100, 100, 100)])
    return BacktestEngine(bars, rules, "TEST", "mr-test", 100_000)


def test_reanchor_short_stop_moves_above_fill():
    from strategies.templates import RuleSpec
    sl = RuleSpec(
        name="sl", trigger_type="price",
        trigger_config={"condition": "gte", "price": 105.0, "reference": "ltp",
                        "entry_anchor_pct": 1.0},
        action_type="place_order",
        action_config={"transaction_type": "BUY", "quantity": 1},
        role="sl", enabled=False,
    )
    # An absolute --sl (no entry_anchor_pct) must be left exactly as given.
    abs_sl = RuleSpec(
        name="abs-sl", trigger_type="price",
        trigger_config={"condition": "gte", "price": 105.0, "reference": "ltp"},
        action_type="place_order",
        action_config={"transaction_type": "BUY", "quantity": 1},
        role="sl", enabled=False,
    )
    eng = _engine_with([sl, abs_sl])
    eng._reanchor_exits_to_entry(110.0)   # spike fill well above the 105 placeholder
    assert sl.trigger_config["price"] == 111.1     # 110 * 1.01 → above the fill
    assert abs_sl.trigger_config["price"] == 105.0  # untouched


def test_reanchor_long_stop_moves_below_fill():
    from strategies.templates import RuleSpec
    sl = RuleSpec(
        name="sl", trigger_type="price",
        trigger_config={"condition": "lte", "price": 95.0, "reference": "ltp",
                        "entry_anchor_pct": -1.0},
        action_type="place_order",
        action_config={"transaction_type": "SELL", "quantity": 1},
        role="sl", enabled=False,
    )
    eng = _engine_with([sl])
    eng._reanchor_exits_to_entry(90.0)
    assert sl.trigger_config["price"] == round(90.0 * 0.99, 2)  # 89.1 → below the fill


def test_mean_reversion_template_tags_entry_anchor_only_with_sl_pct():
    from strategies.mean_reversion import MeanReversionTemplate
    tpl = MeanReversionTemplate()

    short = tpl.plan("WIPRO", {"capital": 100_000, "sl": 198.0, "side": "short", "sl_pct": 1.0})
    sl_short = [r for r in short.rules if r.role == "sl"][0]
    assert sl_short.trigger_config.get("entry_anchor_pct") == 1.0   # short stop above entry

    lng = tpl.plan("WIPRO", {"capital": 100_000, "sl": 195.0, "side": "long", "sl_pct": 1.0})
    sl_long = [r for r in lng.rules if r.role == "sl"][0]
    assert sl_long.trigger_config.get("entry_anchor_pct") == -1.0   # long stop below entry

    # Absolute --sl (live `nf-strategy deploy` path) carries NO anchor tag, so
    # live rule behaviour is unchanged by this backtest fix.
    absolute = tpl.plan("WIPRO", {"capital": 100_000, "sl": 198.0, "side": "short"})
    sl_abs = [r for r in absolute.rules if r.role == "sl"][0]
    assert "entry_anchor_pct" not in sl_abs.trigger_config


# ──────────────────────────────────────────────────────────────────────
# Last-candle entry / break-even handling (2026-06-09 PF=inf artifact fix)
# ──────────────────────────────────────────────────────────────────────


def test_no_phantom_trade_from_last_candle_entry():
    """An entry that fires on the final candle has no bars left to manage and
    would close same-bar via end_of_data as a 0-duration, 0-P&L phantom that
    counts as a 'loser' with 0 gross loss → profit_factor=inf. The engine must
    skip the last-bar entry so no phantom trade is recorded."""
    from strategies.templates import RuleSpec
    base = datetime(2026, 5, 1, 9, 15)
    # Flat bars; a price-gte entry that only triggers on the very last bar.
    bars = _series(base, [(100, 100, 100, 100), (100, 100, 100, 100), (100, 120, 100, 120)])
    rules = [
        RuleSpec(
            name="entry-last-bar", trigger_type="price",
            trigger_config={"condition": "gte", "price": 115.0, "reference": "ltp"},
            action_type="place_order",
            action_config={"transaction_type": "BUY", "quantity": 1},
            role="entry",
        ),
    ]
    eng = BacktestEngine(bars, rules, "TEST", "phantom-test", 100_000)
    result = eng.run()
    # Entry fires only on the last bar (high 120 >= 115) → skipped → no trade.
    assert len(result.trades) == 0


def test_breakeven_trade_not_counted_as_loser():
    """A pnl==0 trade is break-even, not a loss — counting it as a loser gave it
    0 gross loss and inflated profit_factor to inf."""
    from backtesting.metrics import compute_metrics
    from backtesting.simulator import Trade

    def _t(pnl, reason="end_of_data"):
        return Trade(
            symbol="X", side="short", entry_price=100.0, entry_time="t0",
            exit_price=100.0 - pnl, exit_time="t1", quantity=1, pnl=pnl,
            pnl_pct=pnl, exit_reason=reason, holding_minutes=15,
        )

    m = compute_metrics([_t(50.0), _t(30.0), _t(0.0)], 100_000)
    # The break-even trade is neither winner nor loser → 0 losers → PF stays
    # inf ONLY because there are genuinely no losses (correct), not because a
    # 0-pnl trade was miscounted.
    assert m["winners"] == 2
    assert m["losers"] == 0
    # Add a real loss → PF must be finite and exclude the break-even from losses.
    m2 = compute_metrics([_t(80.0), _t(0.0), _t(-40.0)], 100_000)
    assert m2["winners"] == 1
    assert m2["losers"] == 1
    assert m2["profit_factor"] == 2.0  # 80 / 40, break-even ignored
