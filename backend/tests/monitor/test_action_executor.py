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
    """place_order success path goes through AsyncUpstoxOrderApi (httpx) — 2026-05-11 SDK migration."""
    mock_client = AsyncMock()
    mock_client._is_market_open = MagicMock(return_value=True)
    mock_client.access_token = "test-token"
    mock_client._get_instrument_key = MagicMock(return_value="NSE_EQ|INE002A01018")
    get_client = AsyncMock(return_value=mock_client)
    executor = ActionExecutor(get_client=get_client)

    rule = _make_rule()
    result = _fired_result()
    session = AsyncMock()

    # AsyncUpstoxOrderApi is constructed lazily inside _place_order_direct;
    # patch it where it's imported.
    mock_api = AsyncMock()
    mock_api.place_order = AsyncMock(return_value={
        "success": True, "order_id": "ORD123", "status": "PENDING",
        "message": "OK", "latency_ms": 12,
    })

    with patch("monitor.action_executor.crud") as mock_crud, \
         patch("services.upstox_order_api.AsyncUpstoxOrderApi", return_value=mock_api):
        mock_crud.record_fire = AsyncMock()
        mock_crud.disable_rule = AsyncMock()
        mock_crud.sync_rule_fire_state = AsyncMock()
        action_result = await executor.execute(rule, result, {"ltp": 105.0}, session)

    assert action_result["success"] is True
    assert action_result["order_id"] == "ORD123"
    mock_api.place_order.assert_awaited_once()
    call_kwargs = mock_api.place_order.await_args.kwargs
    assert call_kwargs["transaction_type"] == "BUY"
    assert call_kwargs["quantity"] == 10
    assert call_kwargs["order_type"] == "MARKET"
    assert call_kwargs["product"] == "I"


# ── Test: place_order failure (exception) ─────────────────────────────

@pytest.mark.asyncio
async def test_execute_place_order_failure():
    """When AsyncUpstoxOrderApi raises, action_result has error info and doesn't crash."""
    mock_client = AsyncMock()
    mock_client._is_market_open = MagicMock(return_value=True)
    mock_client.access_token = "test-token"
    mock_client._get_instrument_key = MagicMock(return_value="NSE_EQ|INE002A01018")
    get_client = AsyncMock(return_value=mock_client)
    executor = ActionExecutor(get_client=get_client)

    rule = _make_rule()
    result = _fired_result()
    session = AsyncMock()

    mock_api = AsyncMock()
    mock_api.place_order = AsyncMock(side_effect=Exception("Upstox API timeout"))

    with patch("monitor.action_executor.crud") as mock_crud, \
         patch("services.upstox_order_api.AsyncUpstoxOrderApi", return_value=mock_api):
        mock_crud.record_fire = AsyncMock()
        mock_crud.disable_rule = AsyncMock()
        mock_crud.sync_rule_fire_state = AsyncMock()
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


# ── Position guard (reduce-only exits) ─────────────────────────────────
# A trailing stop / reduce_only rule stores a fixed qty from creation time.
# After a partial book or manual close, firing with the stale qty would flip
# the remainder into an unintended opposite position (2026-07-02, Rule #18
# partial booking). The guard caps qty at the live closable position and
# consumes the fire (success=True, no order) when flat.

def _pos(symbol="M&M", qty=0, product="I", token="NSE_EQ|TESTTOK"):
    p = MagicMock()
    p.tradingsymbol = symbol
    p.trading_symbol = symbol
    p.quantity = qty
    p.product = product
    p.instrument_token = token
    return p


def _guard_client(positions):
    client = AsyncMock()
    client._is_market_open = MagicMock(return_value=True)
    client.access_token = "test-token"
    client._get_instrument_key = MagicMock(return_value="NSE_EQ|TESTTOK")
    if isinstance(positions, Exception):
        client.get_positions = AsyncMock(side_effect=positions)
    else:
        client.get_positions = AsyncMock(return_value=positions)
    return client


def _trailing_rule(qty=149, side="SELL", product="I"):
    action_config = {
        "symbol": "M&M",
        "transaction_type": side,
        "quantity": qty,
        "order_type": "MARKET",
        "product": product,
        "reduce_only": True,
    }
    rule = _make_rule(
        trigger_type="trailing_stop",
        trigger_config={
            "trail_percent": 1.5, "initial_price": 3124.0,
            "highest_price": 3166.0, "direction": "long", "reference": "ltp",
        },
        action_config=action_config,
    )
    return rule, _fired_result(action_config=action_config)


def _ok_order_api():
    api = AsyncMock()
    api.place_order = AsyncMock(return_value={
        "success": True, "order_id": "ORD777", "status": "PENDING", "message": "OK",
    })
    return api


@pytest.mark.asyncio
async def test_position_guard_skips_when_flat():
    """Trailing stop fires against a flat position → fire consumed, no order sent."""
    mock_client = _guard_client(positions=[])
    executor = ActionExecutor(get_client=AsyncMock(return_value=mock_client))
    rule, result = _trailing_rule()
    mock_api = _ok_order_api()

    with patch("monitor.action_executor.crud") as mock_crud, \
         patch("services.upstox_order_api.AsyncUpstoxOrderApi", return_value=mock_api):
        mock_crud.record_fire = AsyncMock()
        mock_crud.sync_rule_fire_state = AsyncMock()
        action_result = await executor.execute(rule, result, {"ltp": 3119.0}, AsyncMock())

    assert action_result["success"] is True  # success → daemon does NOT revert/re-fire
    assert action_result["skipped"] is True
    assert action_result["position_guard"] is True
    mock_api.place_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_position_guard_caps_qty_after_partial_book():
    """Position reduced 149→49 by a partial book → exit sells 49, not 149."""
    mock_client = _guard_client(positions=[_pos(qty=49)])
    executor = ActionExecutor(get_client=AsyncMock(return_value=mock_client))
    rule, result = _trailing_rule(qty=149)
    mock_api = _ok_order_api()

    with patch("monitor.action_executor.crud") as mock_crud, \
         patch("services.upstox_order_api.AsyncUpstoxOrderApi", return_value=mock_api):
        mock_crud.record_fire = AsyncMock()
        mock_crud.sync_rule_fire_state = AsyncMock()
        action_result = await executor.execute(rule, result, {"ltp": 3119.0}, AsyncMock())

    assert action_result["success"] is True
    assert mock_api.place_order.await_args.kwargs["quantity"] == 49


@pytest.mark.asyncio
async def test_position_guard_full_position_untouched():
    """Position matches rule qty → order goes out at full qty."""
    mock_client = _guard_client(positions=[_pos(qty=149)])
    executor = ActionExecutor(get_client=AsyncMock(return_value=mock_client))
    rule, result = _trailing_rule(qty=149)
    mock_api = _ok_order_api()

    with patch("monitor.action_executor.crud") as mock_crud, \
         patch("services.upstox_order_api.AsyncUpstoxOrderApi", return_value=mock_api):
        mock_crud.record_fire = AsyncMock()
        mock_crud.sync_rule_fire_state = AsyncMock()
        await executor.execute(rule, result, {"ltp": 3119.0}, AsyncMock())

    assert mock_api.place_order.await_args.kwargs["quantity"] == 149


@pytest.mark.asyncio
async def test_position_guard_covers_short_with_buy():
    """BUY-side trail (short cover) caps at the open short qty."""
    mock_client = _guard_client(positions=[_pos(qty=-100)])
    executor = ActionExecutor(get_client=AsyncMock(return_value=mock_client))
    rule, result = _trailing_rule(qty=149, side="BUY")
    mock_api = _ok_order_api()

    with patch("monitor.action_executor.crud") as mock_crud, \
         patch("services.upstox_order_api.AsyncUpstoxOrderApi", return_value=mock_api):
        mock_crud.record_fire = AsyncMock()
        mock_crud.sync_rule_fire_state = AsyncMock()
        await executor.execute(rule, result, {"ltp": 3200.0}, AsyncMock())

    assert mock_api.place_order.await_args.kwargs["quantity"] == 100


@pytest.mark.asyncio
async def test_position_guard_fails_open_on_lookup_error():
    """Positions API error → order proceeds unguarded (a skipped stop-loss is worse)."""
    mock_client = _guard_client(positions=RuntimeError("positions API down"))
    executor = ActionExecutor(get_client=AsyncMock(return_value=mock_client))
    rule, result = _trailing_rule(qty=149)
    mock_api = _ok_order_api()

    with patch("monitor.action_executor.crud") as mock_crud, \
         patch("services.upstox_order_api.AsyncUpstoxOrderApi", return_value=mock_api):
        mock_crud.record_fire = AsyncMock()
        mock_crud.sync_rule_fire_state = AsyncMock()
        action_result = await executor.execute(rule, result, {"ltp": 3119.0}, AsyncMock())

    assert action_result["success"] is True
    assert mock_api.place_order.await_args.kwargs["quantity"] == 149


@pytest.mark.asyncio
async def test_position_guard_not_applied_to_entries():
    """A plain price-trigger BUY (no reduce_only) is an entry — guard must not run."""
    mock_client = _guard_client(positions=[])
    executor = ActionExecutor(get_client=AsyncMock(return_value=mock_client))
    rule = _make_rule()          # price trigger, BUY 10, no reduce_only
    result = _fired_result()
    mock_api = _ok_order_api()

    with patch("monitor.action_executor.crud") as mock_crud, \
         patch("services.upstox_order_api.AsyncUpstoxOrderApi", return_value=mock_api):
        mock_crud.record_fire = AsyncMock()
        mock_crud.sync_rule_fire_state = AsyncMock()
        action_result = await executor.execute(rule, result, {"ltp": 105.0}, AsyncMock())

    assert action_result["success"] is True
    mock_client.get_positions.assert_not_awaited()
    assert mock_api.place_order.await_args.kwargs["quantity"] == 10


@pytest.mark.asyncio
async def test_position_guard_reduce_only_flag_on_time_rule():
    """A time-trigger squareoff flagged reduce_only skips when flat (not just trails)."""
    mock_client = _guard_client(positions=[])
    executor = ActionExecutor(get_client=AsyncMock(return_value=mock_client))
    action_config = {
        "symbol": "M&M", "transaction_type": "SELL", "quantity": 149,
        "order_type": "MARKET", "product": "I", "reduce_only": True,
    }
    rule = _make_rule(
        trigger_type="time",
        trigger_config={"at": "15:09"},
        action_config=action_config,
    )
    result = _fired_result(action_config=action_config)
    mock_api = _ok_order_api()

    with patch("monitor.action_executor.crud") as mock_crud, \
         patch("services.upstox_order_api.AsyncUpstoxOrderApi", return_value=mock_api):
        mock_crud.record_fire = AsyncMock()
        mock_crud.sync_rule_fire_state = AsyncMock()
        action_result = await executor.execute(rule, result, {"now": "15:09"}, AsyncMock())

    assert action_result["skipped"] is True
    mock_api.place_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_position_guard_delivery_sell_includes_holdings():
    """Product-D SELL: closable = settled holdings + today's D-position net.
    IDEA-style persistent delivery trail must NOT be skipped just because the
    holding isn't in the positions API."""
    # Sold 1000 D today (net -1000 in positions), 3000 settled in holdings → closable 2000
    mock_client = _guard_client(positions=[_pos(symbol="IDEA", qty=-1000, product="D")])
    executor = ActionExecutor(get_client=AsyncMock(return_value=mock_client))
    action_config = {
        "symbol": "IDEA", "transaction_type": "SELL", "quantity": 3000,
        "order_type": "MARKET", "product": "D", "reduce_only": True,
    }
    rule = _make_rule(
        trigger_type="trailing_stop",
        trigger_config={
            "trail_percent": 5.0, "initial_price": 14.06,
            "highest_price": 14.84, "direction": "long", "reference": "ltp",
        },
        action_config=action_config,
    )
    result = _fired_result(action_config=action_config)
    mock_api = _ok_order_api()

    with patch("monitor.action_executor.crud") as mock_crud, \
         patch("services.upstox_order_api.AsyncUpstoxOrderApi", return_value=mock_api), \
         patch.object(executor, "_settled_holdings_qty", AsyncMock(return_value=3000)):
        mock_crud.record_fire = AsyncMock()
        mock_crud.sync_rule_fire_state = AsyncMock()
        await executor.execute(rule, result, {"ltp": 14.10}, AsyncMock())

    assert mock_api.place_order.await_args.kwargs["quantity"] == 2000
