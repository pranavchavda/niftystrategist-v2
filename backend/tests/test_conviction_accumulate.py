"""Tests for the conviction-accumulate strategy template + its sizing helper.

Covers:
1. Tranche structure (rule count, roles, equal quantity)
2. Gating: only the breakout starts enabled; dips + all exits start disabled
3. Activate chains: breakout arms its exits AND the dip entries; each dip arms its own exits
4. Kill chains: an exit only disables its own tranche's sibling exits (quantity isolation)
5. Quantity safety: every SELL quantity equals the tranche BUY quantity
6. Sizing: worst-case risk (all tranches fill) is bounded by capital × risk_percent
7. Validation: stop must be below entry; dips must sit between stop and entry
8. Degenerate cases: no dips (single tranche), no trail (no trail rules)
"""
import pytest

from strategies.sizing import compute_accumulation_quantity
from strategies.templates import get_template


def _plan(**params):
    base = {"capital": 200000, "entry": 460.0, "sl": 428.0}
    base.update(params)
    return get_template("conviction-accumulate").plan("COALINDIA", base)


# ── Structure ────────────────────────────────────────────────────────

class TestStructure:
    def setup_method(self):
        self.plan = _plan(dip_levels=[450.58, 445.0], trail_percent=5.0)

    def test_rule_count(self):
        # 3 tranches × 4 rules (entry, sl, sqoff, trail)
        assert len(self.plan.rules) == 12

    def test_all_roles_present(self):
        roles = {s.role for s in self.plan.rules}
        expected = set()
        for i in range(3):
            expected |= {f"entry_{i}", f"sl_{i}", f"sqoff_{i}", f"trail_{i}"}
        assert roles == expected

    def test_equal_quantity_across_tranches(self):
        qtys = {s.action_config["quantity"] for s in self.plan.rules}
        assert len(qtys) == 1  # every rule uses the same per-tranche qty

    def test_entries_sorted_high_to_low(self):
        entries = [
            s.trigger_config["price"]
            for s in self.plan.rules if s.role and s.role.startswith("entry_")
        ]
        assert entries == [460.0, 450.58, 445.0]


# ── Gating ───────────────────────────────────────────────────────────

class TestGating:
    def setup_method(self):
        self.plan = _plan(dip_levels=[450.58, 445.0], trail_percent=5.0)
        self.by_role = {s.role: s for s in self.plan.rules}

    def test_only_breakout_enabled(self):
        enabled = [s.role for s in self.plan.rules if s.enabled]
        assert enabled == ["entry_0"]

    def test_dip_entries_disabled(self):
        assert self.by_role["entry_1"].enabled is False
        assert self.by_role["entry_2"].enabled is False

    def test_all_exits_disabled(self):
        for role, spec in self.by_role.items():
            if role.startswith(("sl_", "sqoff_", "trail_")):
                assert spec.enabled is False, f"{role} should be gated"


# ── Activate / kill chains ───────────────────────────────────────────

class TestChains:
    def setup_method(self):
        self.plan = _plan(dip_levels=[450.58, 445.0], trail_percent=5.0)
        self.by_role = {s.role: s for s in self.plan.rules}

    def test_breakout_arms_its_exits_and_dip_entries(self):
        assert set(self.by_role["entry_0"].activates_roles) == {
            "sl_0", "sqoff_0", "trail_0", "entry_1", "entry_2",
        }

    def test_dip_entry_arms_only_its_own_exits(self):
        assert set(self.by_role["entry_1"].activates_roles) == {"sl_1", "sqoff_1", "trail_1"}
        assert set(self.by_role["entry_2"].activates_roles) == {"sl_2", "sqoff_2", "trail_2"}

    def test_exit_kills_same_tranche_siblings(self):
        # an exit disables its own tranche's other exits, never another tranche's
        assert {"sqoff_1", "trail_1"} <= set(self.by_role["sl_1"].kills_roles)
        assert {"sl_1", "trail_1"} <= set(self.by_role["sqoff_1"].kills_roles)
        # trail only touches its siblings (does NOT stop further accumulation)
        assert set(self.by_role["trail_1"].kills_roles) == {"sl_1", "sqoff_1"}
        # no tranche-1 exit ever kills another tranche's EXIT rule
        for role in ("sl_1", "sqoff_1", "trail_1"):
            other_tranche_exits = {
                k for k in self.by_role[role].kills_roles
                if k.startswith(("sl_", "sqoff_", "trail_")) and not k.endswith("_1")
            }
            assert other_tranche_exits == set(), f"{role} kills {other_tranche_exits}"

    def test_stop_and_squareoff_kill_remaining_dip_adds(self):
        # a stop-out / square-off invalidates the thesis → no re-entry on later
        # bounces; remaining dip-add entries get torn down.
        assert {"entry_1", "entry_2"} <= set(self.by_role["sl_0"].kills_roles)
        assert {"entry_1", "entry_2"} <= set(self.by_role["sqoff_0"].kills_roles)
        # trail does NOT kill dip entries — it's per-tranche profit protection
        assert not any(k.startswith("entry_") for k in self.by_role["trail_0"].kills_roles)

    def test_all_referenced_roles_are_defined(self):
        defined = {s.role for s in self.plan.rules}
        for s in self.plan.rules:
            for r in (*s.activates_roles, *s.kills_roles):
                assert r in defined, f"{s.role} references undefined role {r}"


# ── Quantity safety ──────────────────────────────────────────────────

class TestQuantitySafety:
    def test_every_sell_matches_tranche_buy(self):
        plan = _plan(dip_levels=[450.58, 445.0], trail_percent=5.0)
        # group by tranche suffix; each tranche's BUY qty == every SELL qty in it
        by_tranche: dict[str, list] = {}
        for s in plan.rules:
            suffix = s.role.split("_")[-1]
            by_tranche.setdefault(suffix, []).append(s)
        for suffix, specs in by_tranche.items():
            qtys = {s.action_config["quantity"] for s in specs}
            assert len(qtys) == 1, f"tranche {suffix} has mismatched quantities {qtys}"

    def test_breakout_is_buy_exits_are_sell(self):
        plan = _plan(dip_levels=[445.0])
        for s in plan.rules:
            if s.role.startswith("entry_"):
                assert s.action_config["transaction_type"] == "BUY"
            else:
                assert s.action_config["transaction_type"] == "SELL"


# ── Sizing ───────────────────────────────────────────────────────────

class TestSizing:
    def test_worst_case_risk_bounded(self):
        capital, risk_pct = 200000, 2.0
        entries = [460.0, 450.58, 445.0]
        sl = 428.0
        qty = compute_accumulation_quantity(capital, risk_pct, entries, sl)
        worst_case_risk = qty * sum(e - sl for e in entries)
        assert worst_case_risk <= capital * risk_pct / 100

    def test_one_more_share_would_breach_risk(self):
        capital, risk_pct = 200000, 2.0
        entries = [460.0, 450.58, 445.0]
        sl = 428.0
        qty = compute_accumulation_quantity(capital, risk_pct, entries, sl)
        breach = (qty + 1) * sum(e - sl for e in entries)
        assert breach > capital * risk_pct / 100

    def test_minimum_one_share(self):
        # tiny capital still yields at least one share
        qty = compute_accumulation_quantity(1000, 2.0, [460.0], 428.0)
        assert qty >= 1


# ── Validation ───────────────────────────────────────────────────────

class TestValidation:
    def test_stop_above_entry_rejected(self):
        with pytest.raises(ValueError, match="below the entry"):
            _plan(sl=470.0)

    def test_dip_above_entry_rejected(self):
        with pytest.raises(ValueError, match="between the stop"):
            _plan(dip_levels=[470.0])

    def test_dip_below_stop_rejected(self):
        with pytest.raises(ValueError, match="between the stop"):
            _plan(dip_levels=[420.0])


# ── Degenerate cases ─────────────────────────────────────────────────

class TestDegenerate:
    def test_no_dips_single_tranche(self):
        plan = _plan()  # no dip_levels
        entry_roles = [s.role for s in plan.rules if s.role.startswith("entry_")]
        assert entry_roles == ["entry_0"]

    def test_no_trail_omits_trail_rules(self):
        plan = _plan(dip_levels=[445.0], trail_percent=0.0)
        assert not any(s.role.startswith("trail_") for s in plan.rules)
        # breakout should not try to arm a non-existent trail role
        breakout = next(s for s in plan.rules if s.role == "entry_0")
        assert not any(r.startswith("trail_") for r in breakout.activates_roles)
