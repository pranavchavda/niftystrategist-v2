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
        paper_mode: If True, log that actions run in paper mode. Default False.
    """

    def __init__(
        self,
        get_client: Callable[[int], Awaitable[Any]],
        paper_mode: bool = False,
    ) -> None:
        self._get_client = get_client
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

            # Cancel linked rules (OCO pattern)
            if result.rules_to_cancel:
                for cancel_id in result.rules_to_cancel:
                    try:
                        await crud.disable_rule(session, cancel_id)
                        logger.info("Disabled linked rule %d (OCO from rule %d)", cancel_id, rule.id)
                    except Exception as e:
                        logger.error("Failed to disable linked rule %d: %s", cancel_id, e)

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

        return action_result

    async def _execute_place_order(self, rule: MonitorRule, config: dict) -> dict:
        """Place an order using UpstoxClient."""
        action = PlaceOrderAction(**config)

        if self._paper_mode:
            logger.info("[PAPER] Placing order for rule %d: %s", rule.id, action)

        client = await self._get_client(rule.user_id)
        try:
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
        """Cancel an order using UpstoxClient."""
        action = CancelOrderAction(**config)

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
