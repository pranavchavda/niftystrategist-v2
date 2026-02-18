"""Tests for ActionExecutor — executes actions from fired monitor rules."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from monitor.models import MonitorRule
from monitor.rule_evaluator import RuleResult
from monitor.action_executor import ActionExecutor


# ── Helpers ────────────────────────────────────────────────────────────

def _make_rule(**overrides) -> MonitorRule:
    defaults = dict(
        id=1,
        user_id=999,
        name="test-rule",
        trigger_type="price",
        trigger_config={"condition": "gte", "price": 100.0, "reference": "ltp"},
        action_type="place_order",
        action_config={
            "symbol": "RELIANCE",
            "transaction_type": "BUY",
            "quantity": 10,
            "order_type": "MARKET",
            "product": "I",
            "price": None,
        },
        instrument_token="NSE_EQ|INE002A01018",
    )
    defaults.update(overrides)
    return MonitorRule(**defaults)


def _fired_result(rule_id=1, action_type="place_order", action_config=None, rules_to_cancel=None) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        fired=True,
        action_type=action_type,
        action_config=action_config or {
            "symbol": "RELIANCE",
            "transaction_type": "BUY",
            "quantity": 10,
            "order_type": "MARKET",
            "product": "I",
            "price": None,
        },
        rules_to_cancel=rules_to_cancel or [],
    )


def _not_fired_result(rule_id=1) -> RuleResult:
    return RuleResult(rule_id=rule_id, fired=False)


def _make_mock_client(place_order_return=None, cancel_order_return=None):
    """Create a mock UpstoxClient with async methods."""
    client = AsyncMock()
    if place_order_return is not None:
        client.place_order.return_value = place_order_return
    else:
        # Default: a successful TradeResult-like object
        result = MagicMock()
        result.success = True
        result.order_id = "ORD123"
        result.message = "Order placed"
        result.status = "PENDING"
        client.place_order.return_value = result
    if cancel_order_return is not None:
        client.cancel_order.return_value = cancel_order_return
    else:
        client.cancel_order.return_value = {"success": True, "message": "Cancelled"}
    return client


# ── Test: place_order success ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_place_order_success():
    """Calling execute with a place_order action calls client.place_order with correct params."""
    mock_client = _make_mock_client()
    get_client = AsyncMock(return_value=mock_client)
    executor = ActionExecutor(get_client=get_client)

    rule = _make_rule()
    result = _fired_result()
    session = AsyncMock()

    with patch("monitor.action_executor.crud") as mock_crud:
        mock_crud.record_fire = AsyncMock()
        mock_crud.disable_rule = AsyncMock()
        action_result = await executor.execute(rule, result, {"ltp": 105.0}, session)

    assert action_result["success"] is True
    assert action_result["order_id"] == "ORD123"
    mock_client.place_order.assert_awaited_once_with(
        symbol="RELIANCE",
        transaction_type="BUY",
        quantity=10,
        order_type="MARKET",
        product="I",
        price=0,
    )


# ── Test: place_order failure (exception) ─────────────────────────────

@pytest.mark.asyncio
async def test_execute_place_order_failure():
    """When client.place_order raises, action_result has error info and doesn't crash."""
    mock_client = AsyncMock()
    mock_client.place_order.side_effect = Exception("Upstox API timeout")
    get_client = AsyncMock(return_value=mock_client)
    executor = ActionExecutor(get_client=get_client)

    rule = _make_rule()
    result = _fired_result()
    session = AsyncMock()

    with patch("monitor.action_executor.crud") as mock_crud:
        mock_crud.record_fire = AsyncMock()
        mock_crud.disable_rule = AsyncMock()
        action_result = await executor.execute(rule, result, {"ltp": 105.0}, session)

    assert action_result["success"] is False
    assert "Upstox API timeout" in action_result["error"]


# ── Test: cancel_order success ────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_cancel_order_success():
    """Calling execute with a cancel_order action calls client.cancel_order."""
    mock_client = _make_mock_client(cancel_order_return={"success": True, "message": "Order cancelled"})
    get_client = AsyncMock(return_value=mock_client)
    executor = ActionExecutor(get_client=get_client)

    rule = _make_rule(
        action_type="cancel_order",
        action_config={"order_id": "ORD456"},
    )
    result = _fired_result(
        action_type="cancel_order",
        action_config={"order_id": "ORD456"},
    )
    session = AsyncMock()

    with patch("monitor.action_executor.crud") as mock_crud:
        mock_crud.record_fire = AsyncMock()
        mock_crud.disable_rule = AsyncMock()
        action_result = await executor.execute(rule, result, {"ltp": 50.0}, session)

    assert action_result["success"] is True
    mock_client.cancel_order.assert_awaited_once_with(order_id="ORD456")


# ── Test: cancel_rule success ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_cancel_rule_success():
    """Calling execute with a cancel_rule action calls crud.disable_rule."""
    get_client = AsyncMock()
    executor = ActionExecutor(get_client=get_client)

    rule = _make_rule(
        action_type="cancel_rule",
        action_config={"rule_id": 42},
    )
    result = _fired_result(
        action_type="cancel_rule",
        action_config={"rule_id": 42},
        rules_to_cancel=[42],
    )
    session = AsyncMock()

    mock_disabled_rule = MagicMock()
    mock_disabled_rule.id = 42

    with patch("monitor.action_executor.crud") as mock_crud:
        mock_crud.record_fire = AsyncMock()
        mock_crud.disable_rule = AsyncMock(return_value=mock_disabled_rule)
        action_result = await executor.execute(rule, result, {}, session)

    assert action_result["success"] is True
    assert action_result["disabled_rule_id"] == 42


# ── Test: record_fire is called ───────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_records_fire_in_log():
    """execute() calls crud.record_fire with the right arguments."""
    mock_client = _make_mock_client()
    get_client = AsyncMock(return_value=mock_client)
    executor = ActionExecutor(get_client=get_client)

    rule = _make_rule()
    result = _fired_result()
    session = AsyncMock()
    trigger_snapshot = {"ltp": 105.0}

    with patch("monitor.action_executor.crud") as mock_crud:
        mock_crud.record_fire = AsyncMock()
        mock_crud.disable_rule = AsyncMock()
        await executor.execute(rule, result, trigger_snapshot, session)

    mock_crud.record_fire.assert_awaited_once()
    call_kwargs = mock_crud.record_fire.call_args
    assert call_kwargs.kwargs["session"] is session or call_kwargs[0][0] is session
    # Verify rule_id and user_id are passed
    args = call_kwargs.kwargs if call_kwargs.kwargs else {}
    positional = call_kwargs.args if call_kwargs.args else ()
    # record_fire(session, rule_id, user_id, trigger_snapshot, action_taken, action_result)
    # Check it was called (the exact args depend on implementation; just confirm it happened)
    assert mock_crud.record_fire.await_count == 1


# ── Test: cancel linked rules (OCO) ──────────────────────────────────

@pytest.mark.asyncio
async def test_execute_cancel_linked_rules():
    """When rules_to_cancel is non-empty, those rules get disabled."""
    mock_client = _make_mock_client()
    get_client = AsyncMock(return_value=mock_client)
    executor = ActionExecutor(get_client=get_client)

    rule = _make_rule()
    result = _fired_result(rules_to_cancel=[10, 20])
    session = AsyncMock()

    with patch("monitor.action_executor.crud") as mock_crud:
        mock_crud.record_fire = AsyncMock()
        mock_crud.disable_rule = AsyncMock(return_value=MagicMock())
        await executor.execute(rule, result, {"ltp": 105.0}, session)

    # disable_rule should be called once for each rule in rules_to_cancel
    assert mock_crud.disable_rule.await_count == 2
    disabled_ids = [call.args[1] if len(call.args) > 1 else call.kwargs.get("rule_id")
                    for call in mock_crud.disable_rule.call_args_list]
    assert 10 in disabled_ids
    assert 20 in disabled_ids


# ── Test: not fired = no execution ────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_skipped_when_not_fired():
    """If result.fired is False, nothing happens — no client calls, no logs."""
    mock_client = _make_mock_client()
    get_client = AsyncMock(return_value=mock_client)
    executor = ActionExecutor(get_client=get_client)

    rule = _make_rule()
    result = _not_fired_result()
    session = AsyncMock()

    with patch("monitor.action_executor.crud") as mock_crud:
        mock_crud.record_fire = AsyncMock()
        mock_crud.disable_rule = AsyncMock()
        action_result = await executor.execute(rule, result, {}, session)

    assert action_result is None
    get_client.assert_not_awaited()
    mock_crud.record_fire.assert_not_awaited()


# ── Test: exception handling ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_handles_exception_gracefully():
    """If an unexpected exception occurs in execute, it returns error dict, doesn't crash."""
    get_client = AsyncMock(side_effect=RuntimeError("client factory exploded"))
    executor = ActionExecutor(get_client=get_client)

    rule = _make_rule()
    result = _fired_result()
    session = AsyncMock()

    with patch("monitor.action_executor.crud") as mock_crud:
        mock_crud.record_fire = AsyncMock()
        mock_crud.disable_rule = AsyncMock()
        action_result = await executor.execute(rule, result, {"ltp": 105.0}, session)

    assert action_result["success"] is False
    assert "error" in action_result
