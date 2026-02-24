"""Tests for MonitorDaemon — main daemon loop that ties everything together."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from monitor.models import MonitorRule
from monitor.rule_evaluator import RuleResult, EvalContext


# ── Helpers ──────────────────────────────────────────────────────────


def _make_rule(
    rule_id: int = 1,
    user_id: int = 999,
    trigger_type: str = "price",
    instrument_token: str = "NSE_EQ|INE002A01018",
    trigger_config: dict | None = None,
    action_type: str = "place_order",
    action_config: dict | None = None,
) -> MonitorRule:
    """Create a minimal MonitorRule for testing."""
    if trigger_config is None:
        if trigger_type == "price":
            trigger_config = {"condition": "gte", "price": 100.0, "reference": "ltp"}
        elif trigger_type == "time":
            trigger_config = {"at": "09:30", "on_days": ["mon", "tue", "wed", "thu", "fri"]}
        elif trigger_type == "order_status":
            trigger_config = {"order_id": "ORD-123", "status": "complete"}
        elif trigger_type == "indicator":
            trigger_config = {
                "indicator": "rsi",
                "timeframe": "5m",
                "condition": "lte",
                "value": 30.0,
                "params": {},
            }
        elif trigger_type == "compound":
            trigger_config = {
                "operator": "and",
                "conditions": [
                    {"type": "price", "condition": "gte", "price": 100.0, "reference": "ltp"},
                ],
            }
        else:
            trigger_config = {}
    if action_config is None:
        action_config = {
            "symbol": "RELIANCE",
            "transaction_type": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
            "product": "I",
            "price": None,
        }
    return MonitorRule(
        id=rule_id,
        user_id=user_id,
        name=f"test-rule-{rule_id}",
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        action_type=action_type,
        action_config=action_config,
        instrument_token=instrument_token,
    )


def _make_db_rule(rule_id: int = 1, user_id: int = 999, **overrides) -> MagicMock:
    """Create a mock DB rule object (MonitorRuleDB) that crud.db_rule_to_schema can handle."""
    db_rule = MagicMock()
    db_rule.id = rule_id
    db_rule.user_id = user_id
    db_rule.name = overrides.get("name", f"test-rule-{rule_id}")
    db_rule.enabled = overrides.get("enabled", True)
    db_rule.trigger_type = overrides.get("trigger_type", "price")
    db_rule.trigger_config = overrides.get(
        "trigger_config", {"condition": "gte", "price": 100.0, "reference": "ltp"}
    )
    db_rule.action_type = overrides.get("action_type", "place_order")
    db_rule.action_config = overrides.get("action_config", {
        "symbol": "RELIANCE",
        "transaction_type": "BUY",
        "quantity": 1,
        "order_type": "MARKET",
        "product": "I",
        "price": None,
    })
    db_rule.instrument_token = overrides.get("instrument_token", "NSE_EQ|INE002A01018")
    db_rule.symbol = overrides.get("symbol", None)
    db_rule.linked_trade_id = overrides.get("linked_trade_id", None)
    db_rule.linked_order_id = overrides.get("linked_order_id", None)
    db_rule.fire_count = overrides.get("fire_count", 0)
    db_rule.max_fires = overrides.get("max_fires", None)
    db_rule.expires_at = overrides.get("expires_at", None)
    db_rule.fired_at = overrides.get("fired_at", None)
    return db_rule


def _make_user_session(user_id: int = 999, rules: list | None = None) -> MagicMock:
    """Create a mock UserSession object."""
    session = MagicMock()
    session.user_id = user_id
    session.rules = rules or []
    session.prev_prices = {"NSE_EQ|INE002A01018": 99.0}
    session.indicator_values = {}
    session.prev_indicator_values = {}
    return session


# ── Test: _poll_rules starts new users ───────────────────────────────


@pytest.mark.asyncio
async def test_poll_rules_starts_new_users():
    """When rules appear for a new user, start_user is called."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()
    daemon.set_access_token(999, "test-token")

    db_rule = _make_db_rule(rule_id=1, user_id=999)

    with patch("monitor.daemon.get_db_context") as mock_ctx, \
         patch("monitor.daemon.crud") as mock_crud:

        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_crud.get_active_rules_for_daemon = AsyncMock(return_value=[db_rule])
        mock_crud.db_rule_to_schema.side_effect = lambda r: _make_rule(
            rule_id=r.id, user_id=r.user_id
        )

        daemon._user_manager = AsyncMock()
        daemon._user_manager.get_session.return_value = None

        await daemon._poll_rules()

    daemon._user_manager.start_user.assert_awaited_once()
    call_args = daemon._user_manager.start_user.call_args
    assert call_args[0][0] == 999  # user_id
    assert call_args[0][1] == "test-token"  # access_token
    assert len(call_args[0][2]) == 1  # rules list


# ── Test: _poll_rules stops users with no rules ─────────────────────


@pytest.mark.asyncio
async def test_poll_rules_stops_users_with_no_rules():
    """When a user's rules are all disabled/deleted, stop_user is called."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    # Pre-populate: user 999 previously had rules
    daemon._rules_by_user = {999: [_make_rule()]}

    with patch("monitor.daemon.get_db_context") as mock_ctx, \
         patch("monitor.daemon.crud") as mock_crud:

        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        # No rules returned from DB
        mock_crud.get_active_rules_for_daemon = AsyncMock(return_value=[])
        mock_crud.db_rule_to_schema.side_effect = lambda r: _make_rule(
            rule_id=r.id, user_id=r.user_id
        )

        daemon._user_manager = AsyncMock()

        await daemon._poll_rules()

    daemon._user_manager.stop_user.assert_awaited_once_with(999)


# ── Test: _poll_rules syncs existing users ───────────────────────────


@pytest.mark.asyncio
async def test_poll_rules_syncs_existing_users():
    """When rules change for an existing user, sync_rules is called."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()
    daemon.set_access_token(999, "test-token")

    # Pre-populate: user 999 already had a rule
    old_rule = _make_rule(rule_id=1, user_id=999)
    daemon._rules_by_user = {999: [old_rule]}

    # New rules from DB: same user but different rule
    db_rule = _make_db_rule(rule_id=2, user_id=999)

    with patch("monitor.daemon.get_db_context") as mock_ctx, \
         patch("monitor.daemon.crud") as mock_crud:

        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_crud.get_active_rules_for_daemon = AsyncMock(return_value=[db_rule])
        mock_crud.db_rule_to_schema.side_effect = lambda r: _make_rule(
            rule_id=r.id, user_id=r.user_id
        )

        mock_um = AsyncMock()
        # get_session is sync — return a mock with matching access_token
        mock_session_obj = MagicMock()
        mock_session_obj.access_token = "test-token"
        mock_um.get_session = MagicMock(return_value=mock_session_obj)
        daemon._user_manager = mock_um

        await daemon._poll_rules()

    daemon._user_manager.sync_rules.assert_awaited_once()
    call_args = daemon._user_manager.sync_rules.call_args
    assert call_args[0][0] == 999  # user_id
    assert len(call_args[0][1]) == 1  # updated rules list

    # start_user and stop_user should NOT be called (same token)
    daemon._user_manager.start_user.assert_not_awaited()
    daemon._user_manager.stop_user.assert_not_awaited()


# ── Test: _on_tick evaluates price rules ─────────────────────────────


@pytest.mark.asyncio
async def test_on_tick_evaluates_price_rules():
    """A market tick triggers price rule evaluation and fires action."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    rule = _make_rule(
        rule_id=1,
        user_id=999,
        trigger_type="price",
        instrument_token="NSE_EQ|A",
        trigger_config={"condition": "gte", "price": 100.0, "reference": "ltp"},
    )

    session_obj = _make_user_session(999, rules=[rule])
    daemon._user_manager = MagicMock()
    daemon._user_manager.get_session.return_value = session_obj
    daemon._rules_by_user = {999: [rule]}

    # Mock evaluate_rule to fire
    fired_result = RuleResult(rule_id=1, fired=True, action_type="place_order", action_config=rule.action_config)

    with patch("monitor.daemon.evaluate_rule", return_value=fired_result) as mock_eval, \
         patch.object(daemon, "_evaluate_and_execute", new_callable=AsyncMock) as mock_exec:

        market_data = {"ltp": 105.0}
        await daemon._on_tick(999, "NSE_EQ|A", market_data)

    mock_exec.assert_awaited_once()
    exec_args = mock_exec.call_args[0]
    assert exec_args[0] is rule  # rule
    assert exec_args[1].market_data == market_data  # ctx


# ── Test: _on_tick skips non-matching instrument ─────────────────────


@pytest.mark.asyncio
async def test_on_tick_skips_non_matching_instrument():
    """Ticks for other instruments don't trigger rules."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    rule = _make_rule(
        rule_id=1,
        user_id=999,
        trigger_type="price",
        instrument_token="NSE_EQ|A",
    )

    session_obj = _make_user_session(999, rules=[rule])
    daemon._user_manager = MagicMock()
    daemon._user_manager.get_session.return_value = session_obj

    with patch.object(daemon, "_evaluate_and_execute", new_callable=AsyncMock) as mock_exec:
        # Tick for a different instrument
        await daemon._on_tick(999, "NSE_EQ|B", {"ltp": 50.0})

    mock_exec.assert_not_awaited()


# ── Test: _on_portfolio_event evaluates order_status rules ───────────


@pytest.mark.asyncio
async def test_on_portfolio_event_evaluates_order_status_rules():
    """Portfolio event triggers order_status evaluation."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    rule = _make_rule(
        rule_id=1,
        user_id=999,
        trigger_type="order_status",
        instrument_token=None,
        trigger_config={"order_id": "ORD-123", "status": "complete"},
    )

    daemon._rules_by_user = {999: [rule]}

    with patch.object(daemon, "_evaluate_and_execute", new_callable=AsyncMock) as mock_exec:
        event = {"order_id": "ORD-123", "status": "complete"}
        await daemon._on_portfolio_event(999, event)

    mock_exec.assert_awaited_once()
    exec_args = mock_exec.call_args[0]
    assert exec_args[0] is rule
    assert exec_args[1].order_event == event


# ── Test: _check_time_rules evaluates time-based rules ───────────────


@pytest.mark.asyncio
async def test_check_time_rules_evaluates_time_rules():
    """Time check evaluates time-based rules."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    rule = _make_rule(
        rule_id=1,
        user_id=999,
        trigger_type="time",
        instrument_token=None,
        trigger_config={"at": "09:30", "on_days": ["mon", "tue", "wed", "thu", "fri"]},
    )

    daemon._rules_by_user = {999: [rule]}

    with patch.object(daemon, "_evaluate_and_execute", new_callable=AsyncMock) as mock_exec:
        await daemon._check_time_rules()

    mock_exec.assert_awaited_once()
    exec_args = mock_exec.call_args[0]
    assert exec_args[0] is rule
    assert isinstance(exec_args[1].now, datetime)


# ── Test: _evaluate_and_execute fires action ─────────────────────────


@pytest.mark.asyncio
async def test_evaluate_and_execute_fires_action():
    """When a rule fires, ActionExecutor.execute is called."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    rule = _make_rule(rule_id=1, user_id=999)
    ctx = EvalContext(market_data={"ltp": 105.0}, now=datetime.utcnow())

    fired_result = RuleResult(
        rule_id=1, fired=True, action_type="place_order", action_config=rule.action_config
    )

    with patch("monitor.daemon.evaluate_rule", return_value=fired_result), \
         patch("monitor.daemon.get_db_context") as mock_ctx, \
         patch.object(daemon._action_executor, "execute", new_callable=AsyncMock) as mock_exec:

        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await daemon._evaluate_and_execute(rule, ctx)

    mock_exec.assert_awaited_once()
    call_args = mock_exec.call_args
    assert call_args[0][0] is rule
    assert call_args[0][1] is fired_result


# ── Test: _evaluate_and_execute no action when not fired ─────────────


@pytest.mark.asyncio
async def test_evaluate_and_execute_no_action_when_not_fired():
    """When evaluation returns fired=False, no action."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    rule = _make_rule(rule_id=1, user_id=999)
    ctx = EvalContext(market_data={"ltp": 50.0}, now=datetime.utcnow())

    not_fired = RuleResult(rule_id=1, fired=False)

    with patch("monitor.daemon.evaluate_rule", return_value=not_fired), \
         patch.object(daemon._action_executor, "execute", new_callable=AsyncMock) as mock_exec:

        await daemon._evaluate_and_execute(rule, ctx)

    mock_exec.assert_not_awaited()


# ── Test: stop() stops all ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_stop_stops_all():
    """stop() calls user_manager.stop_all()."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()
    daemon._user_manager = AsyncMock()
    daemon._running = True

    await daemon.stop()

    assert daemon._running is False
    daemon._user_manager.stop_all.assert_awaited_once()


# ── Test: _get_client returns UpstoxClient ───────────────────────────


@pytest.mark.asyncio
async def test_get_client_returns_upstox_client():
    """_get_client creates UpstoxClient with correct token."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()
    daemon.set_access_token(999, "my-access-token")

    with patch("monitor.daemon.UpstoxClient") as MockClient:
        MockClient.return_value = MagicMock()
        client = await daemon._get_client(999)

    MockClient.assert_called_once_with(access_token="my-access-token", user_id=999, paper_trading=False)
    assert client is MockClient.return_value


# ── Test: _get_client raises without token ───────────────────────────


@pytest.mark.asyncio
async def test_get_client_raises_without_token():
    """_get_client raises ValueError if no token."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()
    # No access token set for user 999

    with pytest.raises(ValueError, match="No access token for user 999"):
        await daemon._get_client(999)


# ── Test: _poll_rules loads tokens from DB ────────────────────────────


@pytest.mark.asyncio
async def test_poll_rules_loads_tokens_from_db():
    """When no manual token is set, _poll_rules loads from DB via _load_access_token."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()
    # No manual set_access_token call — token comes from DB

    db_rule = _make_db_rule(rule_id=1, user_id=999)

    with patch("monitor.daemon.get_db_context") as mock_ctx, \
         patch("monitor.daemon.crud") as mock_crud, \
         patch.object(daemon, "_load_access_token", new_callable=AsyncMock, return_value="db-token") as mock_load:

        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_crud.get_active_rules_for_daemon = AsyncMock(return_value=[db_rule])
        mock_crud.db_rule_to_schema.side_effect = lambda r: _make_rule(
            rule_id=r.id, user_id=r.user_id
        )

        daemon._user_manager = AsyncMock()
        daemon._user_manager.get_session.return_value = None

        await daemon._poll_rules()

        # Token was loaded from DB
        mock_load.assert_awaited_once_with(999)

    # User session started with DB token
    daemon._user_manager.start_user.assert_awaited_once()
    call_args = daemon._user_manager.start_user.call_args
    assert call_args[0][1] == "db-token"


# ── Test: _poll_rules stops user when token expires ──────────────────


@pytest.mark.asyncio
async def test_poll_rules_stops_user_when_token_expires():
    """A running user whose token expires gets stopped."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    # Pre-populate: user 999 had a running session
    old_rule = _make_rule(rule_id=1, user_id=999)
    daemon._rules_by_user = {999: [old_rule]}
    daemon._access_tokens = {999: "old-token"}

    # Same rule still active, but token expired
    db_rule = _make_db_rule(rule_id=1, user_id=999)

    with patch("monitor.daemon.get_db_context") as mock_ctx, \
         patch("monitor.daemon.crud") as mock_crud, \
         patch.object(daemon, "_load_access_token", new_callable=AsyncMock, return_value=None):

        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_crud.get_active_rules_for_daemon = AsyncMock(return_value=[db_rule])
        mock_crud.db_rule_to_schema.side_effect = lambda r: _make_rule(
            rule_id=r.id, user_id=r.user_id
        )

        daemon._user_manager = AsyncMock()

        await daemon._poll_rules()

    # User should be stopped (token expired)
    daemon._user_manager.stop_user.assert_awaited_once_with(999)
    # Not synced or started
    daemon._user_manager.sync_rules.assert_not_awaited()
    daemon._user_manager.start_user.assert_not_awaited()


# ── Test: _on_tick evaluates trailing_stop rules ─────────────────────


@pytest.mark.asyncio
async def test_on_tick_evaluates_trailing_stop_rules():
    """A market tick triggers trailing_stop rule evaluation."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    rule = _make_rule(
        rule_id=1,
        user_id=999,
        trigger_type="trailing_stop",
        instrument_token="NSE_EQ|A",
        trigger_config={
            "trail_percent": 15.0,
            "initial_price": 1000.0,
            "highest_price": 1000.0,
        },
    )

    session_obj = _make_user_session(999, rules=[rule])
    daemon._user_manager = MagicMock()
    daemon._user_manager.get_session.return_value = session_obj
    daemon._rules_by_user = {999: [rule]}

    with patch.object(daemon, "_evaluate_and_execute", new_callable=AsyncMock) as mock_exec:
        await daemon._on_tick(999, "NSE_EQ|A", {"ltp": 850.0})

    mock_exec.assert_awaited_once()


# ── Test: _evaluate_and_execute persists trigger_config_update ────────


@pytest.mark.asyncio
async def test_evaluate_and_execute_persists_trigger_config_update():
    """When evaluate_rule returns trigger_config_update, daemon persists it."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    rule = _make_rule(
        rule_id=5,
        user_id=999,
        trigger_type="trailing_stop",
        trigger_config={
            "trail_percent": 15.0,
            "initial_price": 1000.0,
            "highest_price": 1000.0,
        },
    )

    updated_config = {
        "trail_percent": 15.0,
        "initial_price": 1000.0,
        "highest_price": 1100.0,
        "reference": "ltp",
    }

    not_fired_result = RuleResult(
        rule_id=5,
        fired=False,
        trigger_config_update=updated_config,
    )

    ctx = EvalContext(market_data={"ltp": 1100.0}, now=datetime.utcnow())

    with patch("monitor.daemon.evaluate_rule", return_value=not_fired_result), \
         patch("monitor.daemon.get_db_context") as mock_ctx, \
         patch("monitor.daemon.crud") as mock_crud:

        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_crud.update_rule = AsyncMock()

        await daemon._evaluate_and_execute(rule, ctx)

    # Should persist the trigger_config_update to DB
    mock_crud.update_rule.assert_awaited_once_with(
        mock_session, 5, trigger_config=updated_config
    )
    # Should update in-memory rule
    assert rule.trigger_config == updated_config


@pytest.mark.asyncio
async def test_evaluate_and_execute_no_persist_when_no_update():
    """When trigger_config_update is None, no DB write happens."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    rule = _make_rule(rule_id=5, user_id=999)
    not_fired_result = RuleResult(rule_id=5, fired=False)

    ctx = EvalContext(market_data={"ltp": 50.0}, now=datetime.utcnow())

    with patch("monitor.daemon.evaluate_rule", return_value=not_fired_result), \
         patch("monitor.daemon.crud") as mock_crud:

        mock_crud.update_rule = AsyncMock()
        await daemon._evaluate_and_execute(rule, ctx)

    mock_crud.update_rule.assert_not_awaited()


# ── Test: _load_access_token tries TOTP on expired ────────────────────


@pytest.mark.asyncio
async def test_load_access_token_delegates_to_get_user_upstox_token():
    """_load_access_token delegates to get_user_upstox_token (which handles TOTP internally)."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    with patch("api.upstox_oauth.get_user_upstox_token", new_callable=AsyncMock, return_value="refreshed-token") as mock_get:
        token = await daemon._load_access_token(999)

    assert token == "refreshed-token"
    mock_get.assert_awaited_once_with(999)


# ── Test: _load_access_token returns None when no token ──────────────


@pytest.mark.asyncio
async def test_load_access_token_returns_none_when_no_token():
    """Returns None when get_user_upstox_token returns None (expired, no TOTP)."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    with patch("api.upstox_oauth.get_user_upstox_token", new_callable=AsyncMock, return_value=None):
        token = await daemon._load_access_token(999)

    assert token is None


# ── Test: _load_access_token manual overrides DB ────────────────────


@pytest.mark.asyncio
async def test_load_access_token_manual_overrides_db():
    """Manual set_access_token takes precedence over DB lookup."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()
    daemon.set_access_token(999, "manual-token")

    with patch("api.upstox_oauth.get_user_upstox_token", new_callable=AsyncMock) as mock_get:
        token = await daemon._load_access_token(999)

    assert token == "manual-token"
    mock_get.assert_not_awaited()
