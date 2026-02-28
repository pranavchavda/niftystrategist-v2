"""Tests for evaluate_trailing_stop_trigger — pure function, no I/O."""
from monitor.models import MonitorRule
from monitor.rule_evaluator import evaluate_trailing_stop_trigger


def _make_trailing_rule(
    trail_percent: float = 15.0,
    initial_price: float = 1000.0,
    highest_price: float = 1000.0,
    reference: str = "ltp",
) -> MonitorRule:
    return MonitorRule(
        id=1,
        user_id=999,
        name="test trailing",
        trigger_type="trailing_stop",
        trigger_config={
            "trail_percent": trail_percent,
            "initial_price": initial_price,
            "highest_price": highest_price,
            "reference": reference,
        },
        action_type="place_order",
        action_config={
            "symbol": "X",
            "transaction_type": "SELL",
            "quantity": 1,
            "order_type": "MARKET",
            "product": "I",
            "price": None,
        },
        instrument_token="NSE_EQ|TEST",
    )


# -- Fires when price drops below stop level ---------------------------------

class TestTrailingStopFires:
    def test_fires_at_stop_level(self):
        """15% trail from 1000 = stop at 850. Price at 850 should fire."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 850.0})
        assert fired is True
        assert update is None

    def test_fires_below_stop_level(self):
        """Price well below stop should fire."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 800.0})
        assert fired is True

    def test_fires_with_updated_highest(self):
        """After highest_price moved to 1200, stop is 1020. Price at 1020 fires."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1200.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1020.0})
        assert fired is True


# -- Does not fire when price is above stop -----------------------------------

class TestTrailingStopDoesNotFire:
    def test_no_fire_above_stop(self):
        """Price above stop level should not fire."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 900.0})
        assert fired is False
        assert update is None

    def test_no_fire_at_highest(self):
        """Price at highest should not fire (stop is 15% below)."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1000.0})
        assert fired is False
        assert update is None


# -- Updates highest_price when price rises -----------------------------------

class TestTrailingStopUpdatesHighest:
    def test_updates_highest_when_price_rises(self):
        """When price exceeds highest_price, return updated config."""
        rule = _make_trailing_rule(trail_percent=15.0, initial_price=1000.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1100.0})
        assert fired is False
        assert update is not None
        assert update["highest_price"] == 1100.0
        # Other fields preserved
        assert update["trail_percent"] == 15.0
        assert update["initial_price"] == 1000.0
        assert update["reference"] == "ltp"

    def test_no_update_when_price_equals_highest(self):
        """Same price as highest -- no update needed."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1000.0})
        assert update is None

    def test_no_update_when_price_drops(self):
        """Price drops but above stop -- no update, no fire."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 900.0})
        assert update is None


# -- Edge cases ---------------------------------------------------------------

class TestTrailingStopEdgeCases:
    def test_missing_reference_field_returns_no_fire(self):
        """If market_data doesn't have the reference field, don't fire."""
        rule = _make_trailing_rule(reference="bid")
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 500.0})
        assert fired is False
        assert update is None

    def test_custom_reference_field(self):
        """Use 'high' as reference instead of 'ltp'."""
        rule = _make_trailing_rule(trail_percent=10.0, highest_price=100.0, reference="high")
        fired, update = evaluate_trailing_stop_trigger(rule, {"high": 110.0, "ltp": 105.0})
        assert fired is False
        assert update is not None
        assert update["highest_price"] == 110.0

    def test_zero_trail_percent_fires_on_any_drop(self):
        """0% trail means stop == highest. Any drop fires."""
        rule = _make_trailing_rule(trail_percent=0.0, highest_price=100.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 99.99})
        assert fired is True

    def test_small_trail_precision(self):
        """Verify floating point doesn't cause false fires."""
        rule = _make_trailing_rule(trail_percent=1.0, highest_price=100.0)
        # Stop at 99.0. Price at 99.01 should NOT fire.
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 99.01})
        assert fired is False

    def test_backward_compat_no_direction_defaults_long(self):
        """Rules created before direction field was added default to long behavior."""
        rule = _make_trailing_rule(trail_percent=10.0, highest_price=100.0)
        # No 'direction' key in trigger_config — should default to "long"
        assert "direction" not in rule.trigger_config
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 90.0})
        assert fired is True


# -- SHORT direction trailing stop ────────────────────────────────────────────


def _make_short_trailing_rule(
    trail_percent: float = 1.5,
    initial_price: float = 1300.0,
    lowest_price: float = 1300.0,
    reference: str = "ltp",
) -> MonitorRule:
    return MonitorRule(
        id=2,
        user_id=999,
        name="test short trailing",
        trigger_type="trailing_stop",
        trigger_config={
            "trail_percent": trail_percent,
            "initial_price": initial_price,
            "lowest_price": lowest_price,
            "direction": "short",
            "reference": reference,
        },
        action_type="place_order",
        action_config={
            "symbol": "INFY",
            "transaction_type": "BUY",
            "quantity": 60,
            "order_type": "MARKET",
            "product": "I",
            "price": None,
        },
        instrument_token="NSE_EQ|INE009A01021",
    )


class TestShortTrailingStopFires:
    def test_fires_when_price_rises_above_stop(self):
        """1.5% trail from lowest=1300 → stop at 1319.5. Price 1320 fires."""
        rule = _make_short_trailing_rule(trail_percent=1.5, lowest_price=1300.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1320.0})
        assert fired is True
        assert update is None

    def test_fires_at_stop_level(self):
        """Exactly at stop level should fire."""
        rule = _make_short_trailing_rule(trail_percent=1.5, lowest_price=1300.0)
        # stop = 1300 * 1.015 = 1319.5
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1319.5})
        assert fired is True

    def test_fires_well_above_stop(self):
        """Price far above stop fires."""
        rule = _make_short_trailing_rule(trail_percent=1.5, lowest_price=1300.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1400.0})
        assert fired is True


class TestShortTrailingStopDoesNotFire:
    def test_no_fire_below_stop(self):
        """Price below stop level should not fire."""
        rule = _make_short_trailing_rule(trail_percent=1.5, lowest_price=1300.0)
        # stop = 1319.5, price 1310 is below
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1310.0})
        assert fired is False
        assert update is None

    def test_no_fire_at_lowest(self):
        """Price at lowest should not fire (stop is above)."""
        rule = _make_short_trailing_rule(trail_percent=1.5, lowest_price=1300.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1300.0})
        assert fired is False


class TestShortTrailingStopUpdatesLowest:
    def test_updates_lowest_when_price_drops(self):
        """When price drops below lowest_price, return updated config."""
        rule = _make_short_trailing_rule(trail_percent=1.5, lowest_price=1300.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1280.0})
        assert fired is False
        assert update is not None
        assert update["lowest_price"] == 1280.0
        assert update["trail_percent"] == 1.5
        assert update["direction"] == "short"

    def test_no_update_when_price_equals_lowest(self):
        """Same price as lowest — no update."""
        rule = _make_short_trailing_rule(trail_percent=1.5, lowest_price=1300.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1300.0})
        assert update is None

    def test_no_update_when_price_rises_but_below_stop(self):
        """Price rises but still below stop — no update, no fire."""
        rule = _make_short_trailing_rule(trail_percent=1.5, lowest_price=1300.0)
        # stop = 1319.5, price 1310 is below stop but above lowest
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1310.0})
        assert fired is False
        assert update is None

    def test_tightening_stop_on_new_low(self):
        """As price drops from 1300→1280→1260, stop tightens: 1319.5→1299.2→1278.9."""
        rule = _make_short_trailing_rule(trail_percent=1.5, lowest_price=1300.0)

        # Drop to 1280
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1280.0})
        assert not fired
        assert update["lowest_price"] == 1280.0
        new_stop = 1280.0 * 1.015
        assert abs(new_stop - 1299.2) < 0.1

        # Apply update and drop further
        rule.trigger_config = update
        fired, update2 = evaluate_trailing_stop_trigger(rule, {"ltp": 1260.0})
        assert not fired
        assert update2["lowest_price"] == 1260.0
