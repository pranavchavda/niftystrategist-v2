"""Regression tests for nf-deploy-sessions quality gates.

These gates were added after the 2026-06-04 end-of-day review (daily thread
daily_1_2026-06-04_8a692488), where three losing scalp sessions could have been
filtered before deploy:

* GESHIP   — PF 8.86 off only 3 backtest trades  → min-trades gate
* ZENTEC   — best indicator only 'low' confidence → confidence gate (pre-existing)
* TEJASNET — +6.3% gap-up, deployed LONG, faded   → gap-exhaustion filter

And one stock that MUST survive (the day's only winner):

* TATACOMM — PF 1.95 → must NOT be killed by the default config (min-pf OFF).
"""
import argparse
import importlib.util
import os
import sys

import pytest

_CLI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cli-tools")
if _CLI_DIR not in sys.path:
    sys.path.insert(0, _CLI_DIR)


@pytest.fixture(scope="module")
def deploy():
    """Load the extensionless cli-tools/nf-deploy-sessions as a module."""
    path = os.path.join(_CLI_DIR, "nf-deploy-sessions")
    spec = importlib.util.spec_from_loader(
        "nf_deploy_sessions",
        importlib.machinery.SourceFileLoader("nf_deploy_sessions", path),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cand(sym, indicator, direction, conf, pf, wr, trades, classification="signal_sensitive"):
    return {
        "symbol": sym,
        "classification": classification,
        "recommended": {"indicator": indicator, "direction": direction, "confidence": conf},
        "best_signal": {"profit_factor": pf, "win_rate": wr, "total_trades": trades},
    }


def _args(**kw):
    defaults = dict(
        min_confidence="medium", min_trades=6, min_pf=0.0, max_gap_pct=5.0,
        max_sessions=12, max_family_fraction=0.4,
    )
    defaults.update(kw)
    return argparse.Namespace(**defaults)


@pytest.fixture
def eod_candidates():
    """The real 2026-06-04 cases."""
    return [
        _cand("TATACOMM", "hilega_milega", "long", "medium", 1.95, 0.52, 18),
        _cand("GESHIP", "supertrend", "short", "medium", 8.86, 0.50, 3),
        _cand("ZENTEC", "hilega_milega", "long", "low", 1.92, 0.45, 14),
        _cand("INDUSINDBK", "ema_crossover", "long", "none", 0.66, 0.30, 20, "untradeable"),
        _cand("TEJASNET", "macd", "long", "medium", 2.74, 0.50, 22),
    ]


# ---------------------------------------------------------------------------
# Stage 1 — intrinsic gates
# ---------------------------------------------------------------------------

def test_min_trades_kills_phantom(deploy, eod_candidates):
    eligible, skipped = deploy._eligible(eod_candidates, _args())
    syms = [c["symbol"] for c in eligible]
    reasons = {c["symbol"]: c["_skip_reason"] for c in skipped}
    assert "GESHIP" not in syms
    assert "3 backtest trades" in reasons["GESHIP"]


def test_confidence_gate_kills_low(deploy, eod_candidates):
    _, skipped = deploy._eligible(eod_candidates, _args())
    reasons = {c["symbol"]: c["_skip_reason"] for c in skipped}
    assert "confidence" in reasons["ZENTEC"]


def test_untradeable_excluded(deploy, eod_candidates):
    eligible, skipped = deploy._eligible(eod_candidates, _args())
    reasons = {c["symbol"]: c["_skip_reason"] for c in skipped}
    assert "INDUSINDBK" not in [c["symbol"] for c in eligible]
    assert "untradeable" in reasons["INDUSINDBK"]


def test_tatacomm_survives_default(deploy, eod_candidates):
    """The day's only winner (PF 1.95) must NOT be filtered by defaults."""
    eligible, _ = deploy._eligible(eod_candidates, _args())
    assert "TATACOMM" in [c["symbol"] for c in eligible]


def test_min_pf_2_would_kill_tatacomm(deploy, eod_candidates):
    """Documents WHY min-pf is OFF by default: a 2.0 floor drops the winner."""
    eligible, _ = deploy._eligible(eod_candidates, _args(min_pf=2.0))
    assert "TATACOMM" not in [c["symbol"] for c in eligible]


def test_min_trades_zero_disables(deploy, eod_candidates):
    eligible, _ = deploy._eligible(eod_candidates, _args(min_trades=0))
    assert "GESHIP" in [c["symbol"] for c in eligible]


# ---------------------------------------------------------------------------
# Gap-exhaustion logic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("direction,gap,expected", [
    ("long", 6.3, True),    # TEJASNET: chasing a gap-up long
    ("long", -6.3, False),  # gap-down + long is not exhaustion
    ("short", -6.3, True),  # chasing a gap-down short
    ("short", 6.3, False),
    ("both", 6.3, True),    # extended either way for a fresh both-sided entry
    ("both", -6.3, True),
    ("long", 4.9, False),   # below threshold
    ("auto", 6.3, True),
])
def test_gap_exhausted(deploy, direction, gap, expected):
    assert deploy._gap_exhausted(direction, gap, 5.0) is expected


def test_gap_disabled_when_zero(deploy):
    assert deploy._gap_exhausted("long", 99.0, 0.0) is False


def test_gap_pct_matches_open_minus_prevclose(deploy):
    # (571 - 537) / 537 * 100 ≈ 6.33
    assert deploy._gap_pct({"open": 571.0, "close": 537.0}) == pytest.approx(6.33, abs=0.01)
    assert deploy._gap_pct({"open": None, "close": 537.0}) is None


# ---------------------------------------------------------------------------
# Stage 2 — gap filter end-to-end with synthetic quotes
# ---------------------------------------------------------------------------

def test_gap_filter_drops_gapped_long(deploy, eod_candidates):
    eligible, _ = deploy._eligible(eod_candidates, _args())
    quotes = {
        "TATACOMM": {"ltp": 1973.0, "open": 1965.0, "close": 1960.0},  # +0.26% — ok
        "TEJASNET": {"ltp": 571.0, "open": 571.0, "close": 537.0},     # +6.33% gap up, LONG
    }
    survivors, skipped = deploy._apply_gap_filter(eligible, quotes, _args())
    syms = [c["symbol"] for c in survivors]
    assert "TATACOMM" in syms
    assert "TEJASNET" not in syms
    reasons = {c["symbol"]: c["_skip_reason"] for c in skipped}
    assert "exhaustion" in reasons["TEJASNET"]


def test_gap_filter_drops_missing_quote(deploy, eod_candidates):
    eligible, _ = deploy._eligible(eod_candidates, _args())
    survivors, skipped = deploy._apply_gap_filter(eligible, {}, _args())
    assert survivors == []
    assert all("no live LTP" in c["_skip_reason"] for c in skipped)


# ---------------------------------------------------------------------------
# Stage 3 — caps
# ---------------------------------------------------------------------------

def test_caps_limit_session_count(deploy, eod_candidates):
    eligible, _ = deploy._eligible(eod_candidates, _args())
    selected, skipped = deploy._apply_caps(eligible, _args(max_sessions=1))
    assert len(selected) == 1
    assert all("max-sessions cap" in c["_skip_reason"] for c in skipped)
