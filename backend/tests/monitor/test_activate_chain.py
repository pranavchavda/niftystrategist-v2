"""Tests for the activates_roles / also_enable_rules mechanism.

Covers:
1. RuleResult.rules_to_enable populated from also_enable_rules in action_config
2. ORB template creates exit rules as disabled when side=both
3. ORB entry rules have correct activates_roles / kills_roles
4. Unidirectional ORB (side=long) creates exit rules enabled
"""
from monitor.models import MonitorRule
from monitor.rule_evaluator import EvalContext, evaluate_rule
from strategies.templates import get_template


def _make_rule(**overrides) -> MonitorRule:
    defaults = dict(
        id=1,
        user_id=999,
        name="test",
        trigger_type="price",
        trigger_config={"condition": "gte", "price": 100.0, "reference": "ltp"},
        action_type="place_order",
        action_config={
            "symbol": "X", "transaction_type": "BUY",
            "quantity": 10, "order_type": "MARKET", "product": "I",
        },
        instrument_token="NSE_EQ|TEST",
    )
    defaults.update(overrides)
    return MonitorRule(**defaults)


# ── RuleResult.rules_to_enable ───────────────────────────────────────

class TestRulestoEnable:
    def test_also_enable_rules_populated_on_fire(self):
        rule = _make_rule(action_config={
            "symbol": "X", "transaction_type": "BUY", "quantity": 10,
            "order_type": "MARKET", "product": "I",
            "also_enable_rules": [10, 11, 12],
        })
        ctx = EvalContext(market_data={"ltp": 150.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is True
        assert result.rules_to_enable == [10, 11, 12]

    def test_no_enable_rules_when_absent(self):
        rule = _make_rule()
        ctx = EvalContext(market_data={"ltp": 150.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is True
        assert result.rules_to_enable == []

    def test_no_enable_rules_when_not_fired(self):
        rule = _make_rule(action_config={
            "symbol": "X", "transaction_type": "BUY", "quantity": 10,
            "order_type": "MARKET", "product": "I",
            "also_enable_rules": [10, 11],
        })
        ctx = EvalContext(market_data={"ltp": 50.0})  # below trigger
        result = evaluate_rule(rule, ctx)
        assert result.fired is False
        assert result.rules_to_enable == []

    def test_both_cancel_and_enable_rules(self):
        rule = _make_rule(action_config={
            "symbol": "X", "transaction_type": "BUY", "quantity": 10,
            "order_type": "MARKET", "product": "I",
            "also_cancel_rules": [20, 21],
            "also_enable_rules": [30, 31],
        })
        ctx = EvalContext(market_data={"ltp": 150.0})
        result = evaluate_rule(rule, ctx)
        assert result.rules_to_cancel == [20, 21]
        assert result.rules_to_enable == [30, 31]


# ── ORB template: bidirectional (side=both) ──────────────────────────

class TestORBBidirectional:
    def setup_method(self):
        self.template = get_template("orb")
        self.plan = self.template.plan("TEST", {
            "capital": 100000,
            "range_high": 100.0,
            "range_low": 95.0,
            "side": "both",
        })

    def test_exit_rules_disabled_when_bidirectional(self):
        """SL, target, trailing for both sides should start disabled."""
        for spec in self.plan.rules:
            if spec.role in ("sl_long", "target_long", "trailing_long",
                             "sl_short", "target_short", "trailing_short"):
                assert spec.enabled is False, f"{spec.role} should be disabled"

    def test_entry_rules_enabled(self):
        """Entry rules should always start enabled."""
        for spec in self.plan.rules:
            if spec.role in ("entry_long", "entry_short"):
                assert spec.enabled is True, f"{spec.role} should be enabled"

    def test_squareoff_always_enabled(self):
        """Auto square-off is a safety net, always enabled."""
        squareoff = [s for s in self.plan.rules if s.role == "squareoff"]
        assert len(squareoff) == 1
        assert squareoff[0].enabled is True

    def test_entry_long_activates_long_exits(self):
        entry = [s for s in self.plan.rules if s.role == "entry_long"][0]
        assert set(entry.activates_roles) == {"sl_long", "target_long", "trailing_long"}

    def test_entry_long_kills_short_side(self):
        entry = [s for s in self.plan.rules if s.role == "entry_long"][0]
        assert "entry_short" in entry.kills_roles
        assert "sl_short" in entry.kills_roles
        assert "trailing_short" in entry.kills_roles

    def test_entry_short_activates_short_exits(self):
        entry = [s for s in self.plan.rules if s.role == "entry_short"][0]
        assert set(entry.activates_roles) == {"sl_short", "target_short", "trailing_short"}

    def test_entry_short_kills_long_side(self):
        entry = [s for s in self.plan.rules if s.role == "entry_short"][0]
        assert "entry_long" in entry.kills_roles
        assert "sl_long" in entry.kills_roles

    def test_all_roles_present(self):
        roles = {s.role for s in self.plan.rules}
        expected = {
            "entry_long", "sl_long", "target_long", "trailing_long",
            "entry_short", "sl_short", "target_short", "trailing_short",
            "squareoff",
        }
        assert roles == expected


# ── ORB template: unidirectional (side=long) ─────────────────────────

class TestORBUnidirectional:
    def setup_method(self):
        self.template = get_template("orb")
        self.plan = self.template.plan("TEST", {
            "capital": 100000,
            "range_high": 100.0,
            "range_low": 95.0,
            "side": "long",
        })

    def test_exit_rules_enabled_when_unidirectional(self):
        """When side=long, all long exit rules start enabled (no ambiguity)."""
        for spec in self.plan.rules:
            if spec.role in ("sl_long", "target_long", "trailing_long"):
                assert spec.enabled is True, f"{spec.role} should be enabled for side=long"

    def test_no_short_rules(self):
        roles = {s.role for s in self.plan.rules}
        assert not any("short" in r for r in roles)

    def test_entry_has_no_kills(self):
        """Unidirectional entry doesn't need to kill opposite side."""
        entry = [s for s in self.plan.rules if s.role == "entry_long"][0]
        assert entry.kills_roles == []

    def test_entry_activates_harmless_when_unidirectional(self):
        """Unidirectional entry still has activates (no-op since exits already enabled)."""
        entry = [s for s in self.plan.rules if s.role == "entry_long"][0]
        # activates_roles is set but since exits start enabled, it's a no-op
        assert set(entry.activates_roles) == {"sl_long", "target_long", "trailing_long"}


# ── ORB template: reversal mode ──────────────────────────────────────

class TestORBReversal:
    def test_target_long_activates_entry_short(self):
        template = get_template("orb")
        plan = template.plan("TEST", {
            "capital": 100000,
            "range_high": 100.0,
            "range_low": 95.0,
            "side": "both",
            "enable_reversal": True,
        })
        target_long = [s for s in plan.rules if s.role == "target_long"][0]
        assert "entry_short" in target_long.activates_roles

    def test_target_short_activates_entry_long(self):
        template = get_template("orb")
        plan = template.plan("TEST", {
            "capital": 100000,
            "range_high": 100.0,
            "range_low": 95.0,
            "side": "both",
            "enable_reversal": True,
        })
        target_short = [s for s in plan.rules if s.role == "target_short"][0]
        assert "entry_long" in target_short.activates_roles

    def test_no_reversal_by_default(self):
        template = get_template("orb")
        plan = template.plan("TEST", {
            "capital": 100000,
            "range_high": 100.0,
            "range_low": 95.0,
            "side": "both",
        })
        target_long = [s for s in plan.rules if s.role == "target_long"][0]
        assert target_long.activates_roles == []
