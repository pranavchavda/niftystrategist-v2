"""Regression tests for the exit-gating invariant.

Every strategy template that has both entry rules and exit rules (SL, target,
trailing, squareoff, exit signals) must follow this invariant:

    Exit rules start disabled (enabled=False). The entry rule lists every
    exit role in activates_roles so the daemon's also_enable_rules chain
    flips them on only after the entry actually fires.

Without this, exits fire independently of entries and create rogue positions
(see the RELIANCE breakout incident on 2026-04-13).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from strategies.templates import get_template, RuleSpec


FAKE_FNO_INST = {"instrument_key": "NSE_FO|FAKE", "lot_size": 25}


def _exit_roles(rules: list[RuleSpec]) -> list[RuleSpec]:
    """Return all non-entry rules. Entry = role starts with 'entry'."""
    return [r for r in rules if not r.role.startswith("entry")]


def _entry_rules(rules: list[RuleSpec]) -> list[RuleSpec]:
    return [r for r in rules if r.role.startswith("entry")]


def _assert_exits_start_disabled(rules: list[RuleSpec], template_name: str):
    for r in _exit_roles(rules):
        assert r.enabled is False, (
            f"{template_name}: exit rule {r.role!r} must start disabled "
            f"(got enabled={r.enabled})"
        )


def _assert_every_exit_is_activated(rules: list[RuleSpec], template_name: str):
    """Every non-entry role must appear in at least one entry's activates_roles."""
    exit_role_names = {r.role for r in _exit_roles(rules)}
    activated = set()
    for entry in _entry_rules(rules):
        activated.update(entry.activates_roles)
    missing = exit_role_names - activated
    assert not missing, (
        f"{template_name}: exit roles {missing} are never activated by any entry. "
        f"Activated: {activated}. All exits: {exit_role_names}"
    )


# ── Equity templates ─────────────────────────────────────────────────

class TestBreakoutGating:
    """The template whose failure prompted this rule set (RELIANCE 2026-04-13)."""

    def test_short_side_exits_start_disabled(self):
        plan = get_template("breakout").plan(
            "RELIANCE", {"capital": 100000, "entry": 1310, "sl": 1327}
        )
        _assert_exits_start_disabled(plan.rules, "breakout-short")
        _assert_every_exit_is_activated(plan.rules, "breakout-short")

    def test_long_side_exits_start_disabled(self):
        plan = get_template("breakout").plan(
            "RELIANCE", {"capital": 100000, "entry": 1350, "sl": 1310}
        )
        _assert_exits_start_disabled(plan.rules, "breakout-long")
        _assert_every_exit_is_activated(plan.rules, "breakout-long")

    def test_entry_activates_every_exit_role(self):
        plan = get_template("breakout").plan(
            "TEST", {"capital": 100000, "entry": 100, "sl": 95}
        )
        entry = [r for r in plan.rules if r.role == "entry"][0]
        assert set(entry.activates_roles) == {"sl", "target", "trailing", "squareoff"}


class TestMeanReversionGating:
    def test_exits_disabled_and_activated(self):
        plan = get_template("mean-reversion").plan(
            "TEST", {"capital": 100000, "sl": 95}
        )
        _assert_exits_start_disabled(plan.rules, "mean-reversion")
        _assert_every_exit_is_activated(plan.rules, "mean-reversion")


class TestScalpGating:
    def test_exits_disabled_and_activated(self):
        plan = get_template("scalp").plan(
            "TEST", {"capital": 100000, "entry": 100, "sl": 95}
        )
        _assert_exits_start_disabled(plan.rules, "scalp")
        _assert_every_exit_is_activated(plan.rules, "scalp")

    def test_exits_self_disable_for_reentry_safety(self):
        """Scalp allows re-entries (max_fires > 1). Each exit must kill
        itself via kills_roles so the daemon disables it after firing and
        only the next entry re-activates it."""
        plan = get_template("scalp").plan(
            "TEST", {"capital": 100000, "entry": 100, "sl": 95}
        )
        for r in _exit_roles(plan.rules):
            if r.role != "squareoff":  # time-trigger single-fire, OK
                assert r.role in r.kills_roles, (
                    f"scalp exit {r.role!r} does not self-disable; would fire "
                    f"repeatedly between re-entries"
                )


class TestVwapBounceGating:
    def test_exits_disabled_and_activated(self):
        plan = get_template("vwap-bounce").plan(
            "TEST", {"capital": 100000, "vwap": 100, "sl": 95}
        )
        _assert_exits_start_disabled(plan.rules, "vwap-bounce")
        _assert_every_exit_is_activated(plan.rules, "vwap-bounce")


class TestEMACrossGating:
    @pytest.mark.parametrize("name", ["ema-cross-long", "ema-cross-short", "ema-cross-pair"])
    def test_exits_disabled_and_activated(self, name):
        plan = get_template(name).plan("TEST", {"quantity": 10})
        _assert_exits_start_disabled(plan.rules, name)
        _assert_every_exit_is_activated(plan.rules, name)


class TestUTBotGating:
    @pytest.mark.parametrize("name", ["utbot-long", "utbot-short", "utbot-pair"])
    def test_exits_disabled_and_activated(self, name):
        plan = get_template(name).plan("TEST", {"quantity": 10})
        _assert_exits_start_disabled(plan.rules, name)
        _assert_every_exit_is_activated(plan.rules, name)


class TestRenkoGating:
    @pytest.mark.parametrize("direction", ["long", "short", "both"])
    def test_exits_disabled_and_activated(self, direction):
        plan = get_template("renko").plan(
            "TEST", {"capital": 100000, "direction": direction}
        )
        _assert_exits_start_disabled(plan.rules, f"renko-{direction}")
        _assert_every_exit_is_activated(plan.rules, f"renko-{direction}")

    def test_short_has_squareoff(self):
        """Regression: direction='short' previously emitted no squareoff."""
        plan = get_template("renko").plan(
            "TEST", {"capital": 100000, "direction": "short"}
        )
        squareoff_roles = [r.role for r in plan.rules if r.role.startswith("squareoff")]
        assert "squareoff_short" in squareoff_roles, (
            f"renko direction=short must emit a squareoff safety net; got {squareoff_roles}"
        )

    def test_both_has_squareoffs_for_each_side(self):
        plan = get_template("renko").plan(
            "TEST", {"capital": 100000, "direction": "both"}
        )
        squareoff_roles = {r.role for r in plan.rules if r.role.startswith("squareoff")}
        assert {"squareoff_long", "squareoff_short"} <= squareoff_roles


# ── F&O templates ────────────────────────────────────────────────────

def _patch_fno(*templates):
    """Return a list of patches stubbing resolve_option_instrument in each template module."""
    return [
        patch(f"strategies.{t}.resolve_option_instrument", return_value=FAKE_FNO_INST)
        for t in templates
    ]


class TestStraddleGating:
    def test_sell_exits_disabled_and_activated(self):
        with patch("strategies.straddle.resolve_option_instrument", return_value=FAKE_FNO_INST):
            plan = get_template("straddle").plan(
                "NIFTY",
                {"underlying": "NIFTY", "expiry": "2026-04-30", "strike": 23000, "lots": 1, "direction": "sell"},
            )
        _assert_exits_start_disabled(plan.rules, "straddle-sell")
        _assert_every_exit_is_activated(plan.rules, "straddle-sell")

    def test_buy_exits_disabled_and_activated(self):
        with patch("strategies.straddle.resolve_option_instrument", return_value=FAKE_FNO_INST):
            plan = get_template("straddle").plan(
                "NIFTY",
                {"underlying": "NIFTY", "expiry": "2026-04-30", "strike": 23000, "lots": 1, "direction": "buy"},
            )
        _assert_exits_start_disabled(plan.rules, "straddle-buy")
        _assert_every_exit_is_activated(plan.rules, "straddle-buy")

    def test_unique_roles_per_leg(self):
        """Multi-leg F&O templates must use unique roles per leg so the
        deploy-time role_to_id map doesn't collapse duplicates."""
        with patch("strategies.straddle.resolve_option_instrument", return_value=FAKE_FNO_INST):
            plan = get_template("straddle").plan(
                "NIFTY",
                {"underlying": "NIFTY", "expiry": "2026-04-30", "strike": 23000, "lots": 1},
            )
        roles = [r.role for r in plan.rules]
        assert len(roles) == len(set(roles)), f"straddle has duplicate roles: {roles}"

    def test_sl_rules_carry_premium_multiplier(self):
        with patch("strategies.straddle.resolve_option_instrument", return_value=FAKE_FNO_INST):
            plan = get_template("straddle").plan(
                "NIFTY",
                {
                    "underlying": "NIFTY", "expiry": "2026-04-30", "strike": 23000,
                    "lots": 1, "direction": "sell", "sl_percent": 30,
                },
            )
        sl_rules = [r for r in plan.rules if r.role.startswith("sl_")]
        assert sl_rules, "straddle-sell must emit SL rules"
        for r in sl_rules:
            assert r.premium_sl_multiplier == pytest.approx(1.30), (
                f"straddle SL rule {r.role!r} missing premium_sl_multiplier"
            )


class TestStrangleGating:
    def test_sell_exits_disabled_and_activated(self):
        with patch("strategies.strangle.resolve_option_instrument", return_value=FAKE_FNO_INST):
            plan = get_template("strangle").plan(
                "NIFTY",
                {
                    "underlying": "NIFTY", "expiry": "2026-04-30",
                    "call_strike": 23500, "put_strike": 22500, "lots": 1,
                },
            )
        _assert_exits_start_disabled(plan.rules, "strangle-sell")
        _assert_every_exit_is_activated(plan.rules, "strangle-sell")

    def test_unique_roles_per_leg(self):
        with patch("strategies.strangle.resolve_option_instrument", return_value=FAKE_FNO_INST):
            plan = get_template("strangle").plan(
                "NIFTY",
                {
                    "underlying": "NIFTY", "expiry": "2026-04-30",
                    "call_strike": 23500, "put_strike": 22500, "lots": 1,
                },
            )
        roles = [r.role for r in plan.rules]
        assert len(roles) == len(set(roles)), f"strangle has duplicate roles: {roles}"

    def test_sl_rules_carry_premium_multiplier(self):
        with patch("strategies.strangle.resolve_option_instrument", return_value=FAKE_FNO_INST):
            plan = get_template("strangle").plan(
                "NIFTY",
                {
                    "underlying": "NIFTY", "expiry": "2026-04-30",
                    "call_strike": 23500, "put_strike": 22500, "lots": 1,
                    "sl_percent": 40,
                },
            )
        sl_rules = [r for r in plan.rules if r.role.startswith("sl_")]
        for r in sl_rules:
            assert r.premium_sl_multiplier == pytest.approx(1.40)


class TestSpreadGating:
    @pytest.mark.parametrize("template_name,module,extra_params", [
        (
            "bull-call-spread",
            "bull_call_spread",
            {"buy_strike": 23000, "sell_strike": 23500},
        ),
        (
            "bear-put-spread",
            "bear_put_spread",
            {"buy_strike": 23500, "sell_strike": 23000},
        ),
    ])
    def test_exits_disabled_and_activated(self, template_name, module, extra_params):
        with patch(f"strategies.{module}.resolve_option_instrument", return_value=FAKE_FNO_INST):
            params = {"underlying": "NIFTY", "expiry": "2026-04-30", "lots": 1, **extra_params}
            plan = get_template(template_name).plan("NIFTY", params)
        _assert_exits_start_disabled(plan.rules, template_name)
        _assert_every_exit_is_activated(plan.rules, template_name)
        roles = [r.role for r in plan.rules]
        assert len(roles) == len(set(roles)), (
            f"{template_name} has duplicate roles: {roles}"
        )


class TestIronCondorGating:
    def test_exits_disabled_and_activated(self):
        with patch("strategies.iron_condor.resolve_option_instrument", return_value=FAKE_FNO_INST):
            plan = get_template("iron-condor").plan(
                "NIFTY",
                {
                    "underlying": "NIFTY", "expiry": "2026-04-30",
                    "call_sell_strike": 23500, "call_buy_strike": 24000,
                    "put_sell_strike": 22500, "put_buy_strike": 22000,
                    "lots": 1,
                },
            )
        _assert_exits_start_disabled(plan.rules, "iron-condor")
        _assert_every_exit_is_activated(plan.rules, "iron-condor")
        roles = [r.role for r in plan.rules]
        assert len(roles) == len(set(roles)), f"iron-condor has duplicate roles: {roles}"
