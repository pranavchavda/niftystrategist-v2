"""Tests for utbot-scalp-options-ladder.

Ladder deploys N parallel utbot-scalp-options instances at adjacent
strikes. Each strike has an isolated rule chain (entry/3 exits/squareoff)
with unique role suffixes so they don't interfere.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from strategies.templates import get_template


def _fake_inst(strike: float) -> dict:
    """Return a fake instrument dict for any strike."""
    return {
        "instrument_key": f"NSE_FO|FAKE_{int(strike)}",
        "tradingsymbol": f"NIFTY{int(strike)}CE",
        "lot_size": 25,
        "name": "NIFTY",
    }


def _ladder_plan(**overrides):
    params = {
        "underlying": "NIFTY",
        "expiry": "2026-04-30",
        "option_type": "CE",
        "lots": 1,
        "center_strike": 24200,
    }
    params.update(overrides)
    # Stub resolve_option_instrument to accept arbitrary strikes. The
    # ladder generates strikes via arithmetic, so we need to respond
    # uniformly rather than only to a fixed set.
    with patch(
        "strategies.utbot.resolve_option_instrument",
        side_effect=lambda underlying, expiry, strike, option_type: _fake_inst(strike),
    ):
        return get_template("utbot-scalp-options-ladder").plan("NIFTY", params)


# ── Structure ────────────────────────────────────────────────────────

class TestStructure:
    def test_default_ladder_size_is_3(self):
        plan = _ladder_plan()
        # 3 strikes * 5 rules per strike = 15 rules
        assert len(plan.rules) == 15

    def test_ladder_size_5_produces_25_rules(self):
        plan = _ladder_plan(ladder_size=5)
        assert len(plan.rules) == 25

    def test_ladder_size_1_produces_5_rules(self):
        plan = _ladder_plan(ladder_size=1)
        assert len(plan.rules) == 5

    def test_three_strikes_centered_on_center_strike(self):
        plan = _ladder_plan(center_strike=24200, ladder_size=3)
        # strike_interval for NIFTY defaults to 50 → 24150, 24200, 24250
        instrument_tokens = sorted({
            r.action_config["instrument_token"]
            for r in plan.rules
            if r.action_config.get("instrument_token")
        })
        assert instrument_tokens == [
            "NSE_FO|FAKE_24150",
            "NSE_FO|FAKE_24200",
            "NSE_FO|FAKE_24250",
        ]

    def test_banknifty_uses_100_point_interval(self):
        """BANKNIFTY default strike_interval should be 100, not 50."""
        plan = _ladder_plan(
            underlying="BANKNIFTY", center_strike=54000, ladder_size=3
        )
        tokens = sorted({
            r.action_config["instrument_token"]
            for r in plan.rules
            if r.action_config.get("instrument_token")
        })
        assert tokens == [
            "NSE_FO|FAKE_53900",
            "NSE_FO|FAKE_54000",
            "NSE_FO|FAKE_54100",
        ]

    def test_explicit_strike_interval_overrides_default(self):
        plan = _ladder_plan(
            underlying="NIFTY", center_strike=24200, ladder_size=3,
            strike_interval=25,
        )
        tokens = sorted({
            r.action_config["instrument_token"]
            for r in plan.rules
            if r.action_config.get("instrument_token")
        })
        assert tokens == [
            "NSE_FO|FAKE_24175",
            "NSE_FO|FAKE_24200",
            "NSE_FO|FAKE_24225",
        ]


# ── Role suffixing ───────────────────────────────────────────────────

class TestRoleSuffixes:
    def test_each_strike_has_unique_role_suffix(self):
        plan = _ladder_plan(ladder_size=3)
        roles = [r.role for r in plan.rules]
        # 3 strikes × 5 roles each = 15 unique role names
        assert len(roles) == len(set(roles))
        # Every role should carry a strike suffix
        for role in roles:
            assert "_s24" in role, f"role {role!r} missing strike suffix"

    def test_suffix_matches_strike_integer(self):
        plan = _ladder_plan(center_strike=24200, ladder_size=3)
        entry_roles = sorted([r.role for r in plan.rules if r.role.startswith("entry")])
        assert entry_roles == ["entry_s24150", "entry_s24200", "entry_s24250"]


# ── Chain isolation ──────────────────────────────────────────────────

class TestChainIsolation:
    def test_entry_activates_only_its_own_strikes_exits(self):
        """entry_s24200 must activate exit_*_s24200, not exit_*_s24150
        or exit_*_s24250. Otherwise firing one strike's entry would
        arm another strike's exits against a non-existent position."""
        plan = _ladder_plan(ladder_size=3, center_strike=24200)
        entry = next(r for r in plan.rules if r.role == "entry_s24200")
        for activated in entry.activates_roles:
            assert activated.endswith("_s24200"), (
                f"entry_s24200 wrongly activates {activated}"
            )
        # And should activate all 4 expected siblings
        assert set(entry.activates_roles) == {
            "exit_utbot_s24200",
            "exit_lr_upper_s24200",
            "exit_lr_lower_s24200",
            "squareoff_s24200",
        }

    def test_exit_kills_only_its_own_strikes_siblings(self):
        plan = _ladder_plan(ladder_size=3, center_strike=24200)
        exit_rule = next(r for r in plan.rules if r.role == "exit_lr_upper_s24150")
        for killed in exit_rule.kills_roles:
            assert killed.endswith("_s24150"), (
                f"exit_lr_upper_s24150 wrongly kills {killed}"
            )
        # And should kill all sibling exits + own squareoff
        assert set(exit_rule.kills_roles) == {
            "exit_utbot_s24150",
            "exit_lr_upper_s24150",
            "exit_lr_lower_s24150",
            "squareoff_s24150",
        }

    def test_squareoff_kills_only_its_own_strikes_chain(self):
        plan = _ladder_plan(ladder_size=3, center_strike=24200)
        sq = next(r for r in plan.rules if r.role == "squareoff_s24250")
        for killed in sq.kills_roles:
            assert killed.endswith("_s24250")

    def test_exits_kill_squareoff_of_same_strike(self):
        """The post-2026-04-15 fix: exits must kill their own squareoff
        so 15:15 can't fire against a flat position. Ladder must
        preserve this invariant per-strike."""
        plan = _ladder_plan(ladder_size=3, center_strike=24200)
        for suffix in ("_s24150", "_s24200", "_s24250"):
            for exit_role in (f"exit_utbot{suffix}", f"exit_lr_upper{suffix}",
                              f"exit_lr_lower{suffix}"):
                rule = next(r for r in plan.rules if r.role == exit_role)
                assert f"squareoff{suffix}" in rule.kills_roles


# ── Enabled state per strike ─────────────────────────────────────────

class TestEnabledState:
    def test_each_strike_entry_starts_enabled(self):
        plan = _ladder_plan(ladder_size=3)
        entries = [r for r in plan.rules if r.role.startswith("entry_s")]
        assert len(entries) == 3
        for e in entries:
            assert e.enabled is True

    def test_each_strike_exits_and_squareoff_start_disabled(self):
        plan = _ladder_plan(ladder_size=3)
        for r in plan.rules:
            if r.role.startswith(("exit_", "squareoff_")):
                assert r.enabled is False, (
                    f"{r.role} should start disabled (exit-gating invariant)"
                )


# ── Shared params flow through ───────────────────────────────────────

class TestSharedParams:
    def test_cycles_per_strike(self):
        plan = _ladder_plan(ladder_size=3, cycles=50)
        entries = [r for r in plan.rules if r.role.startswith("entry_")]
        for e in entries:
            assert e.max_fires == 50

    def test_cooldown_applies_to_all_strikes_indicator_rules(self):
        plan = _ladder_plan(ladder_size=3, cooldown_seconds=120)
        for r in plan.rules:
            if r.trigger_type == "indicator":
                assert r.trigger_config.get("cooldown_seconds") == 120

    def test_lr_period_and_stdev_flow_through(self):
        plan = _ladder_plan(ladder_size=3, lr_period=15, lr_stdev=2.5)
        for r in plan.rules:
            if r.role.startswith("exit_lr_"):
                assert r.trigger_config["params"]["period"] == 15
                assert r.trigger_config["params"]["stdev"] == 2.5

    def test_lots_times_lot_size_per_strike(self):
        plan = _ladder_plan(ladder_size=3, lots=2)
        for r in plan.rules:
            if r.action_type == "place_order":
                # All strikes use lot_size=25, so 2 lots → qty=50
                assert r.action_config["quantity"] == 50

    def test_pe_option_type_works(self):
        plan = _ladder_plan(ladder_size=3, option_type="PE")
        entries = [r for r in plan.rules if r.role.startswith("entry_")]
        for e in entries:
            assert e.action_config["transaction_type"] == "BUY"


# ── Validation ───────────────────────────────────────────────────────

class TestValidation:
    def test_ladder_size_must_be_odd(self):
        with pytest.raises(ValueError, match="odd"):
            _ladder_plan(ladder_size=4)

    def test_ladder_size_2_rejected(self):
        with pytest.raises(ValueError, match="odd"):
            _ladder_plan(ladder_size=2)

    def test_ladder_size_must_be_positive(self):
        with pytest.raises(ValueError, match="ladder_size must be >= 1"):
            _ladder_plan(ladder_size=0)

    def test_ladder_size_capped_at_9(self):
        with pytest.raises(ValueError, match="ladder_size must be <= 9"):
            _ladder_plan(ladder_size=11)

    def test_invalid_option_type(self):
        with pytest.raises(ValueError, match="option_type must be CE or PE"):
            _ladder_plan(option_type="XX")

    def test_option_type_as_int_raises_clear_error(self):
        """Origin: 2026-04-15 backtest form submitted option_type=1 (int)
        from a numeric input field. Template was crashing with an opaque
        AttributeError on .upper() instead of returning a clear param
        validation error. Must convert to string and raise ValueError."""
        with pytest.raises(ValueError, match="option_type must be CE or PE"):
            _ladder_plan(option_type=1)

    def test_cycles_must_be_positive(self):
        with pytest.raises(ValueError, match="cycles must be >= 1"):
            _ladder_plan(cycles=0)

    def test_cooldown_must_be_non_negative(self):
        with pytest.raises(ValueError, match="cooldown_seconds must be >= 0"):
            _ladder_plan(cooldown_seconds=-1)

    def test_lr_period_must_be_at_least_three(self):
        with pytest.raises(ValueError, match="lr_period must be >= 3"):
            _ladder_plan(lr_period=2)

    def test_lr_stdev_must_be_positive(self):
        with pytest.raises(ValueError, match="lr_stdev must be > 0"):
            _ladder_plan(lr_stdev=0)

    def test_explicit_zero_strike_interval_rejected(self):
        with pytest.raises(ValueError, match="strike_interval must be > 0"):
            _ladder_plan(strike_interval=0)
