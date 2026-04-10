"""ActionExecutor — executes actions from fired monitor rules.

Takes a RuleResult and dispatches to the appropriate handler:
place_order, cancel_order, or cancel_rule. Logs every fire via CRUD.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession

from monitor import crud
from monitor.models import (
    CancelOrderAction,
    CancelRuleAction,
    MonitorRule,
    PlaceOrderAction,
)
from monitor.rule_evaluator import RuleResult

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Executes actions from fired rules.

    Args:
        get_client: Async callable that returns an UpstoxClient for a given user_id.
                    Signature: (user_id: int) -> UpstoxClient
        get_order_node_url: Async callable returning the user's order node URL (or None).
                    Signature: (user_id: int) -> str | None
        paper_mode: If True, log that actions run in paper mode. Default False.
    """

    def __init__(
        self,
        get_client: Callable[[int], Awaitable[Any]],
        get_order_node_url: Callable[[int], Awaitable[Any]] | None = None,
        paper_mode: bool = False,
    ) -> None:
        self._get_client = get_client
        self._get_order_node_url = get_order_node_url
        self._paper_mode = paper_mode

    async def execute(
        self,
        rule: MonitorRule,
        result: RuleResult,
        trigger_snapshot: dict,
        session: AsyncSession,
    ) -> dict | None:
        """Execute the action for a fired rule.

        Dispatches to _execute_place_order, _execute_cancel_order, or
        _execute_cancel_rule based on result.action_type.

        Records the fire in MonitorLog via crud.record_fire().
        Returns the action result dict, or None if the rule didn't fire.
        """
        if not result.fired:
            return None

        action_result: dict = {}
        try:
            if result.action_type == "place_order":
                action_result = await self._execute_place_order(rule, result.action_config)
            elif result.action_type == "cancel_order":
                action_result = await self._execute_cancel_order(rule, result.action_config)
            elif result.action_type == "cancel_rule":
                action_result = await self._execute_cancel_rule(result.action_config, session)
            else:
                action_result = {"success": False, "error": f"Unknown action_type: {result.action_type}"}

            # Cancel linked rules (OCO / kill chain)
            if result.rules_to_cancel:
                for cancel_id in result.rules_to_cancel:
                    try:
                        await crud.disable_rule(session, cancel_id)
                        logger.info("Disabled linked rule %d (kill chain from rule %d)", cancel_id, rule.id)
                    except Exception as e:
                        logger.error("Failed to disable linked rule %d: %s", cancel_id, e)

            # Enable linked rules (activate chain — e.g. entry enables exit rules)
            if result.rules_to_enable:
                for enable_id in result.rules_to_enable:
                    try:
                        await crud.enable_rule(session, enable_id)
                        logger.info("Enabled rule %d (activate chain from rule %d)", enable_id, rule.id)
                    except Exception as e:
                        logger.error("Failed to enable rule %d: %s", enable_id, e)

        except Exception as e:
            logger.error("ActionExecutor error for rule %d: %s", rule.id, e, exc_info=True)
            action_result = {"success": False, "error": str(e)}

        # Always record the fire, even if the action errored
        try:
            await crud.record_fire(
                session=session,
                rule_id=result.rule_id,
                user_id=rule.user_id,
                trigger_snapshot=trigger_snapshot,
                action_taken=result.action_type or "unknown",
                action_result=action_result,
            )
        except Exception as e:
            logger.error("Failed to record fire for rule %d: %s", rule.id, e, exc_info=True)

        # Sync the daemon's authoritative fire_count/enabled to DB.
        # The daemon already updated these in-memory before launching this
        # background task; this persists them for crash recovery.
        try:
            await crud.sync_rule_fire_state(
                session=session,
                rule_id=rule.id,
                fire_count=rule.fire_count,
                enabled=rule.enabled,
            )
        except Exception as e:
            logger.error("Failed to sync rule fire state for rule %d: %s", rule.id, e, exc_info=True)

        return action_result

    async def _execute_place_order(self, rule: MonitorRule, config: dict) -> dict:
        """Place an order, routing through the user's order node if configured.

        For F&O contracts, action_config should include 'instrument_token' with
        the pre-resolved instrument key (e.g., 'NSE_FO|43885'). This bypasses
        the equity symbol→key lookup which doesn't handle option tradingsymbols.
        """
        action = PlaceOrderAction(**config)

        if self._paper_mode:
            logger.info("[PAPER] Placing order for rule %d: %s", rule.id, action)

        # Check if this user has an order node configured
        node_url = None
        if self._get_order_node_url:
            node_url = await self._get_order_node_url(rule.user_id)

        if node_url:
            return await self._place_order_via_node(rule, action, node_url)

        # Direct path (no order node)
        return await self._place_order_direct(rule, action)

    async def _place_order_via_node(self, rule: MonitorRule, action: PlaceOrderAction, node_url: str) -> dict:
        """Place an order through the user's order node proxy."""
        from services.order_node_proxy import OrderNodeProxy

        # Get the access token for auth header
        client = await self._get_client(rule.user_id)
        token = client.access_token

        proxy = OrderNodeProxy(node_url, token)
        try:
            # Resolve instrument_token if not already set (equity path)
            instrument_token = action.instrument_token
            if not instrument_token:
                instrument_token = client._get_instrument_key(action.symbol)

            result = await proxy.place_order(
                symbol=action.symbol,
                instrument_token=instrument_token,
                transaction_type=action.transaction_type,
                quantity=action.quantity,
                order_type=action.order_type,
                price=action.price if action.price is not None else 0,
                product=action.product,
            )
            return {
                "success": result.success,
                "order_id": result.order_id,
                "message": result.message,
                "status": result.status,
            }
        except Exception as e:
            logger.error("place_order via node failed for rule %d: %s", rule.id, e)
            return {"success": False, "error": str(e)}

    async def _place_order_direct(self, rule: MonitorRule, action: PlaceOrderAction) -> dict:
        """Place an order directly via UpstoxClient (no order node)."""
        client = await self._get_client(rule.user_id)
        try:
            if action.instrument_token:
                # F&O path: use instrument_token directly via Upstox SDK
                import upstox_client
                api_client = upstox_client.ApiClient(client._configuration)
                order_api = upstox_client.OrderApiV3(api_client)

                is_amo = not client._is_market_open()
                body = upstox_client.PlaceOrderV3Request(
                    quantity=action.quantity,
                    product=action.product,
                    validity="DAY",
                    price=action.price if action.order_type == "LIMIT" else 0,
                    trigger_price=0,
                    instrument_token=action.instrument_token,
                    order_type=action.order_type,
                    transaction_type=action.transaction_type,
                    disclosed_quantity=0,
                    is_amo=is_amo,
                )
                response = order_api.place_order(body)
                order_ids = response.data.order_ids if response.data else []
                order_id = order_ids[0] if order_ids else None
                return {
                    "success": True,
                    "order_id": order_id,
                    "message": f"F&O order placed: {action.transaction_type} {action.quantity} of {action.symbol}",
                    "status": "PLACED",
                }
            else:
                # Equity path: use client.place_order which resolves symbol internally
                trade_result = await client.place_order(
                    symbol=action.symbol,
                    transaction_type=action.transaction_type,
                    quantity=action.quantity,
                    order_type=action.order_type,
                    product=action.product,
                    price=action.price if action.price is not None else 0,
                )
                return {
                    "success": trade_result.success,
                    "order_id": trade_result.order_id,
                    "message": trade_result.message,
                    "status": trade_result.status,
                }
        except Exception as e:
            logger.error("place_order failed for rule %d: %s", rule.id, e)
            return {"success": False, "error": str(e)}

    async def _execute_cancel_order(self, rule: MonitorRule, config: dict) -> dict:
        """Cancel an order, routing through the user's order node if configured."""
        action = CancelOrderAction(**config)

        # Check if this user has an order node configured
        node_url = None
        if self._get_order_node_url:
            node_url = await self._get_order_node_url(rule.user_id)

        if node_url:
            from services.order_node_proxy import OrderNodeProxy
            client = await self._get_client(rule.user_id)
            proxy = OrderNodeProxy(node_url, client.access_token)
            try:
                result = await proxy.cancel_order(order_id=action.order_id)
                return {
                    "success": result.success,
                    "order_id": result.order_id,
                    "message": result.message,
                }
            except Exception as e:
                logger.error("cancel_order via node failed for rule %d: %s", rule.id, e)
                return {"success": False, "error": str(e)}

        # Direct path
        client = await self._get_client(rule.user_id)
        try:
            result = await client.cancel_order(order_id=action.order_id)
            return result
        except Exception as e:
            logger.error("cancel_order failed for rule %d: %s", rule.id, e)
            return {"success": False, "error": str(e)}

    async def _execute_cancel_rule(self, config: dict, session: AsyncSession) -> dict:
        """Disable another rule (OCO pattern)."""
        action = CancelRuleAction(**config)

        try:
            disabled = await crud.disable_rule(session, action.rule_id)
            if disabled:
                return {"success": True, "disabled_rule_id": action.rule_id}
            else:
                return {"success": False, "error": f"Rule {action.rule_id} not found"}
        except Exception as e:
            logger.error("cancel_rule failed: %s", e)
            return {"success": False, "error": str(e)}
