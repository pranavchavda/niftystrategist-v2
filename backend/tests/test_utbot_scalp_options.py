"""Tests for utbot-scalp-options (F&O cycling scalper with LR channel exits).

Also covers the opt-in LR exit path added to the equity utbot-scalp template.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from strategies.templates import get_template


FAKE_OPTION_INST = {
    "instrument_key": "NSE_FO|43885",
    "tradingsymbol": "NIFTY30APR23000CE",
    "lot_size": 25,
    "name": "NIFTY",
}


def _scalp_options_plan(**overrides):
    params = {
        "underlying": "NIFTY",
        "expiry": "2026-04-30",
        "strike": 23000,
        "option_type": "CE",
        "lots": 1,
    }
    params.update(overrides)
    with patch("strategies.utbot.resolve_option_instrument", return_value=FAKE_OPTION_INST):
        return get_template("utbot-scalp-options").plan("NIFTY", params)


# ── Structure ────────────────────────────────────────────────────────

class TestStructure:
    def test_five_rules_entry_three_exits_squareoff(self):
        plan = _scalp_options_plan()
        roles = [r.role for r in plan.rules]
        assert roles == [
            "entry",
            "exit_utbot",
            "exit_lr_upper",
            "exit_lr_lower",
            "squareoff",
        ]

    def test_entry_enabled_all_exits_gated(self):
        plan = _scalp_options_plan()
        by_role = {r.role: r for r in plan.rules}
        assert by_role["entry"].enabled is True
        assert by_role["exit_utbot"].enabled is False
        assert by_role["exit_lr_upper"].enabled is False
        assert by_role["exit_lr_lower"].enabled is False
        assert by_role["squareoff"].enabled is False

    def test_entry_activates_all_exits_and_squareoff(self):
        plan = _scalp_options_plan()
        by_role = {r.role: r for r in plan.rules}
        expected = {"exit_utbot", "exit_lr_upper", "exit_lr_lower", "squareoff"}
        assert set(by_role["entry"].activates_roles) == expected

    def test_every_exit_reactivates_entry(self):
        """Mutual activate chain: any exit firing re-arms entry."""
        plan = _scalp_options_plan()
        for role in ("exit_utbot", "exit_lr_upper", "exit_lr_lower"):
            exit_rule = next(r for r in plan.rules if r.role == role)
            assert "entry" in exit_rule.activates_roles, (
                f"{role} must re-activate entry to continue cycling"
            )

    def test_every_exit_kills_all_exits_and_squareoff(self):
        """First exit to fire wins — the other two get disabled so the
        daemon doesn't double-close a single position. Squareoff is also
        killed so 15:15 can't fire against a flat position. Re-entry
        re-activates squareoff via entry.activates_roles.

        Origin: 2026-04-15 live test. NIFTY 24500CE exit fired at 11:58,
        closed the position. At 15:15 the squareoff time-trigger fired
        anyway, opening a naked short that had to be manually covered
        at 15:20."""
        plan = _scalp_options_plan()
        expected_kills = {"exit_utbot", "exit_lr_upper", "exit_lr_lower", "squareoff"}
        for role in ("exit_utbot", "exit_lr_upper", "exit_lr_lower"):
            exit_rule = next(r for r in plan.rules if r.role == role)
            assert set(exit_rule.kills_roles) == expected_kills

    def test_re_entry_re_activates_squareoff(self):
        """After an exit kills the squareoff, a re-entry must re-activate
        it so the 15:15 safety net is back in place for the new cycle."""
        plan = _scalp_options_plan()
        entry = next(r for r in plan.rules if r.role == "entry")
        assert "squareoff" in entry.activates_roles


# ── Trigger configs ──────────────────────────────────────────────────

class TestTriggerConfigs:
    def test_entry_uses_utbot_crosses_above(self):
        plan = _scalp_options_plan()
        entry = next(r for r in plan.rules if r.role == "entry")
        cfg = entry.trigger_config
        assert cfg["indicator"] == "utbot"
        assert cfg["condition"] == "crosses_above"
        assert cfg["params"]["output"] == "trend"

    def test_utbot_exit_uses_crosses_below(self):
        plan = _scalp_options_plan()
        exit_rule = next(r for r in plan.rules if r.role == "exit_utbot")
        cfg = exit_rule.trigger_config
        assert cfg["indicator"] == "utbot"
        assert cfg["condition"] == "crosses_below"

    def test_lr_upper_exit_uses_pctb_crosses_above_1(self):
        plan = _scalp_options_plan()
        exit_rule = next(r for r in plan.rules if r.role == "exit_lr_upper")
        cfg = exit_rule.trigger_config
        assert cfg["indicator"] == "linear_regression"
        assert cfg["condition"] == "crosses_above"
        assert cfg["value"] == 1.0
        assert cfg["params"]["output"] == "pctb"

    def test_lr_lower_exit_uses_pctb_crosses_below_0(self):
        plan = _scalp_options_plan()
        exit_rule = next(r for r in plan.rules if r.role == "exit_lr_lower")
        cfg = exit_rule.trigger_config
        assert cfg["indicator"] == "linear_regression"
        assert cfg["condition"] == "crosses_below"
        assert cfg["value"] == 0.0
        assert cfg["params"]["output"] == "pctb"

    def test_lr_period_and_stdev_flow_through(self):
        plan = _scalp_options_plan(lr_period=15, lr_stdev=2.5)
        for role in ("exit_lr_upper", "exit_lr_lower"):
            rule = next(r for r in plan.rules if r.role == role)
            params = rule.trigger_config["params"]
            assert params["period"] == 15
            assert params["stdev"] == 2.5

    def test_cooldown_applied_to_all_indicator_rules(self):
        plan = _scalp_options_plan(cooldown_seconds=120)
        for role in ("entry", "exit_utbot", "exit_lr_upper", "exit_lr_lower"):
            rule = next(r for r in plan.rules if r.role == role)
            assert rule.trigger_config.get("cooldown_seconds") == 120

    def test_zero_cooldown_omits_field(self):
        plan = _scalp_options_plan(cooldown_seconds=0)
        for role in ("entry", "exit_utbot", "exit_lr_upper", "exit_lr_lower"):
            rule = next(r for r in plan.rules if r.role == role)
            assert "cooldown_seconds" not in rule.trigger_config


# ── F&O wiring ───────────────────────────────────────────────────────

class TestFnoResolution:
    def test_instrument_token_on_every_order(self):
        """Every place_order must carry the pre-resolved instrument_token
        so the F&O order path in action_executor is used."""
        plan = _scalp_options_plan()
        for rule in plan.rules:
            if rule.action_type == "place_order":
                assert rule.action_config.get("instrument_token") == "NSE_FO|43885"

    def test_quantity_is_lots_times_lot_size(self):
        plan = _scalp_options_plan(lots=3)
        for rule in plan.rules:
            if rule.action_type == "place_order":
                assert rule.action_config["quantity"] == 3 * 25  # 3 lots * 25 lot_size

    def test_pe_option_type_parses(self):
        """PE variant should work the same — user bets on declining
        underlying, we still buy the PE on bullish flips of its premium."""
        plan = _scalp_options_plan(option_type="PE")
        entry = next(r for r in plan.rules if r.role == "entry")
        assert entry.action_config["transaction_type"] == "BUY"
        # The logic is symmetric; template doesn't care about CE vs PE

    def test_invalid_option_type_raises(self):
        with pytest.raises(ValueError, match="option_type must be CE or PE"):
            _scalp_options_plan(option_type="XX")


# ── Parameter validation ─────────────────────────────────────────────

class TestParamValidation:
    def test_cycles_must_be_positive(self):
        with pytest.raises(ValueError, match="cycles must be >= 1"):
            _scalp_options_plan(cycles=0)

    def test_cooldown_must_be_non_negative(self):
        with pytest.raises(ValueError, match="cooldown_seconds must be >= 0"):
            _scalp_options_plan(cooldown_seconds=-1)

    def test_lr_period_must_be_at_least_three(self):
        with pytest.raises(ValueError, match="lr_period must be >= 3"):
            _scalp_options_plan(lr_period=2)

    def test_lr_stdev_must_be_positive(self):
        with pytest.raises(ValueError, match="lr_stdev must be > 0"):
            _scalp_options_plan(lr_stdev=0)


# ── Equity utbot-scalp with opt-in LR exits ──────────────────────────

class TestEquityScalpWithLR:
    def test_lr_off_by_default_three_rules(self):
        plan = get_template("utbot-scalp").plan("RELIANCE", {"quantity": 5})
        roles = [r.role for r in plan.rules]
        assert roles == ["entry", "exit_utbot", "squareoff"]

    def test_lr_enabled_adds_two_exit_rules(self):
        plan = get_template("utbot-scalp").plan(
            "RELIANCE", {"quantity": 5, "lr_exit_enabled": True}
        )
        roles = [r.role for r in plan.rules]
        assert roles == [
            "entry", "exit_utbot", "exit_lr_upper", "exit_lr_lower", "squareoff"
        ]

    def test_entry_activates_lr_exits_when_enabled(self):
        plan = get_template("utbot-scalp").plan(
            "RELIANCE", {"quantity": 5, "lr_exit_enabled": True}
        )
        entry = next(r for r in plan.rules if r.role == "entry")
        assert "exit_lr_upper" in entry.activates_roles
        assert "exit_lr_lower" in entry.activates_roles

    def test_lr_period_validation_only_when_enabled(self):
        """Passing a bad lr_period with lr_exit_enabled=False should NOT
        raise — it's only validated when the feature is turned on."""
        # Should succeed:
        get_template("utbot-scalp").plan(
            "RELIANCE", {"quantity": 5, "lr_period": 2}
        )

    def test_lr_period_validation_fires_when_enabled(self):
        with pytest.raises(ValueError, match="lr_period must be >= 3"):
            get_template("utbot-scalp").plan(
                "RELIANCE", {"quantity": 5, "lr_exit_enabled": True, "lr_period": 2}
            )
