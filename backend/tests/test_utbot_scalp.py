"""Tests for the utbot-scalp cycling template and supporting primitives.

Covers:
- Template structure: mutual activate chain, self-kill, cooldown wired through
- Cooldown suppression in rule_evaluator (in-memory fired_at check)
- Parameter validation (cycles >= 1, cooldown >= 0)
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from monitor.models import MonitorRule
from monitor.rule_evaluator import EvalContext, evaluate_rule
from strategies.templates import get_template


# ── Template structure ───────────────────────────────────────────────

class TestUTBotScalpTemplate:
    def _plan(self, **params):
        base = {"quantity": 10}
        base.update(params)
        return get_template("utbot-scalp").plan("TEST", base)

    def test_three_rules_entry_exit_squareoff(self):
        plan = self._plan()
        roles = [r.role for r in plan.rules]
        assert roles == ["entry", "exit_utbot", "squareoff"]

    def test_entry_starts_enabled_exit_and_squareoff_gated(self):
        plan = self._plan()
        by_role = {r.role: r for r in plan.rules}
        assert by_role["entry"].enabled is True
        assert by_role["exit_utbot"].enabled is False
        assert by_role["squareoff"].enabled is False

    def test_mutual_activate_chain(self):
        """Entry activates exit, exit activates entry. This is what makes
        the template cyclical — without it, after one round-trip both
        rules would be disabled forever."""
        plan = self._plan()
        by_role = {r.role: r for r in plan.rules}
        assert "exit_utbot" in by_role["entry"].activates_roles
        assert "entry" in by_role["exit_utbot"].activates_roles

    def test_entry_also_activates_squareoff(self):
        """Squareoff arms when the first position opens, not at deploy."""
        plan = self._plan()
        by_role = {r.role: r for r in plan.rules}
        assert "squareoff" in by_role["entry"].activates_roles

    def test_self_kill_on_entry_and_exit(self):
        """Each side disables itself on fire so it can only re-fire after
        the other side re-enables it. Prevents stacking buys/sells if the
        same signal fires twice in quick succession."""
        plan = self._plan()
        by_role = {r.role: r for r in plan.rules}
        assert "entry" in by_role["entry"].kills_roles
        assert "exit_utbot" in by_role["exit_utbot"].kills_roles

    def test_exit_kills_squareoff_so_15_15_cant_fire_flat(self):
        """Origin: 2026-04-15 live test of utbot-scalp-options. Exit fired
        at 11:58 closing the position; at 15:15 the squareoff time-trigger
        fired anyway, opening a naked short. Exit must kill squareoff;
        re-entry re-activates it via entry.activates_roles."""
        plan = self._plan()
        by_role = {r.role: r for r in plan.rules}
        assert "squareoff" in by_role["exit_utbot"].kills_roles

    def test_squareoff_kills_both_sides(self):
        """After 15:15 squareoff, neither entry nor exit should be able to
        re-fire — day is done."""
        plan = self._plan()
        by_role = {r.role: r for r in plan.rules}
        assert set(by_role["squareoff"].kills_roles) >= {"entry", "exit_utbot"}

    def test_max_fires_respects_cycles_param(self):
        plan = self._plan(cycles=15)
        by_role = {r.role: r for r in plan.rules}
        assert by_role["entry"].max_fires == 15
        assert by_role["exit_utbot"].max_fires == 15

    def test_default_cycles(self):
        plan = self._plan()
        by_role = {r.role: r for r in plan.rules}
        assert by_role["entry"].max_fires == 20  # documented default

    def test_cooldown_baked_into_trigger_config(self):
        plan = self._plan(cooldown_seconds=120)
        by_role = {r.role: r for r in plan.rules}
        assert by_role["entry"].trigger_config.get("cooldown_seconds") == 120
        assert by_role["exit_utbot"].trigger_config.get("cooldown_seconds") == 120

    def test_zero_cooldown_omits_field(self):
        """cooldown=0 means "no cooldown" — the field should not appear at
        all so evaluate_rule skips the check entirely."""
        plan = self._plan(cooldown_seconds=0)
        by_role = {r.role: r for r in plan.rules}
        assert "cooldown_seconds" not in by_role["entry"].trigger_config
        assert "cooldown_seconds" not in by_role["exit_utbot"].trigger_config

    def test_buy_and_sell_sides_correct(self):
        plan = self._plan()
        by_role = {r.role: r for r in plan.rules}
        assert by_role["entry"].action_config["transaction_type"] == "BUY"
        assert by_role["exit_utbot"].action_config["transaction_type"] == "SELL"

    def test_cycles_must_be_positive(self):
        with pytest.raises(ValueError, match="cycles must be >= 1"):
            self._plan(cycles=0)

    def test_cooldown_must_be_non_negative(self):
        with pytest.raises(ValueError, match="cooldown_seconds must be >= 0"):
            self._plan(cooldown_seconds=-1)


# ── Cooldown evaluator behavior ──────────────────────────────────────

def _cooldown_rule(cooldown: int = 60, fired_at: datetime | None = None) -> MonitorRule:
    """Build a minimal price rule with a cooldown for evaluator testing."""
    return MonitorRule(
        id=1,
        user_id=999,
        name="test cooldown",
        trigger_type="price",
        trigger_config={
            "condition": "gte",
            "price": 100.0,
            "reference": "ltp",
            "cooldown_seconds": cooldown,
        },
        action_type="place_order",
        action_config={
            "symbol": "X", "transaction_type": "BUY",
            "quantity": 1, "order_type": "MARKET", "product": "I",
        },
        instrument_token="NSE_EQ|TEST",
        fired_at=fired_at,
    )


class TestCooldownSuppression:
    def test_fires_normally_with_no_previous_fire(self):
        """Cooldown doesn't block the very first fire."""
        rule = _cooldown_rule(cooldown=60, fired_at=None)
        ctx = EvalContext(market_data={"ltp": 150.0}, now=datetime.utcnow())
        assert evaluate_rule(rule, ctx).fired is True

    def test_suppresses_rapid_refire(self):
        """If the rule fired 10s ago and cooldown is 60s, suppress."""
        now = datetime.utcnow()
        rule = _cooldown_rule(cooldown=60, fired_at=now - timedelta(seconds=10))
        ctx = EvalContext(market_data={"ltp": 150.0}, now=now)
        assert evaluate_rule(rule, ctx).fired is False

    def test_allows_refire_after_cooldown_expires(self):
        """If the rule fired 120s ago and cooldown is 60s, allow."""
        now = datetime.utcnow()
        rule = _cooldown_rule(cooldown=60, fired_at=now - timedelta(seconds=120))
        ctx = EvalContext(market_data={"ltp": 150.0}, now=now)
        assert evaluate_rule(rule, ctx).fired is True

    def test_no_cooldown_field_means_no_suppression(self):
        """Rules without cooldown_seconds should never be suppressed."""
        rule = _cooldown_rule(cooldown=60, fired_at=datetime.utcnow())
        # Strip the cooldown key entirely
        rule.trigger_config.pop("cooldown_seconds")
        ctx = EvalContext(market_data={"ltp": 150.0}, now=datetime.utcnow())
        assert evaluate_rule(rule, ctx).fired is True

    def test_zero_cooldown_means_no_suppression(self):
        """cooldown_seconds=0 should treat as no cooldown."""
        rule = _cooldown_rule(cooldown=0, fired_at=datetime.utcnow())
        ctx = EvalContext(market_data={"ltp": 150.0}, now=datetime.utcnow())
        assert evaluate_rule(rule, ctx).fired is True

    def test_suppression_does_not_populate_action_details(self):
        """A suppressed fire must not populate action_type/config or
        kill/activate chains — downstream code uses fired=False to short-
        circuit everything."""
        now = datetime.utcnow()
        rule = _cooldown_rule(cooldown=60, fired_at=now - timedelta(seconds=10))
        rule.action_config["also_enable_rules"] = [42]
        ctx = EvalContext(market_data={"ltp": 150.0}, now=now)
        result = evaluate_rule(rule, ctx)
        assert result.fired is False
        assert result.action_type is None
        assert result.rules_to_enable == []

    def test_cooldown_does_not_fire_when_trigger_would_not_fire(self):
        """If the underlying trigger wouldn't fire anyway, cooldown check
        is moot. Make sure we don't accidentally turn a non-fire into
        something weird."""
        rule = _cooldown_rule(cooldown=60, fired_at=None)
        ctx = EvalContext(market_data={"ltp": 50.0}, now=datetime.utcnow())  # below threshold
        assert evaluate_rule(rule, ctx).fired is False
