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


# Substrings that mean "the SDK didn't get a definitive response from Upstox,
# the order's status is unknown." Used by the place_order paths to flag
# ``ambiguous=True`` so the daemon's revert path skips the fire_count rewind.
# httpx and the order-node surface these as either an exception class name
# (ReadTimeout, ConnectTimeout) or a node-formatted message ("Order timed out:
# Upstox SDK call exceeded 40s timeout").
_TIMEOUT_TOKENS = (
    "timed out",
    "timeout",
    "ReadTimeout",
    "ConnectTimeout",
    "ConnectError",
)


def _looks_like_timeout(message: str | None, status: str | None) -> bool:
    """Best-effort classifier — distinguishes 'unknown-outcome' from 'rejected'."""
    blob = f"{message or ''} {status or ''}"
    return any(tok in blob for tok in _TIMEOUT_TOKENS)


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

    def _broker_for(self, user_id: int) -> str:
        """The broker a user trades on — stamped on order-node requests so the
        node dispatches correctly. Defaults to 'upstox' until the per-user
        broker discriminator lands (Phase C); derive from the user then."""
        return "upstox"

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

        # Best-effort Telegram notification. Failures here must not affect the
        # fire path — the notifier already swallows network errors but a stray
        # bug at this seam shouldn't be allowed to break order execution logic.
        try:
            await self._notify_fire(rule, result, action_result)
        except Exception:
            logger.exception("ActionExecutor telegram notify raised; ignoring")

        return action_result

    async def _notify_fire(
        self,
        rule: MonitorRule,
        result: RuleResult,
        action_result: dict,
    ) -> None:
        """Send a per-fire Telegram message to the rule's owner.

        Success → monitor_fire (informational). Failure → monitor_failure
        (more important; users typically want this even when they've muted
        the chatty success category).
        """
        from services.telegram_notifier import notify

        success = bool(action_result.get("success"))
        category = "monitor_fire" if success else "monitor_failure"

        action_type = result.action_type or "unknown"
        config = result.action_config or {}
        rule_label = rule.name or f"#{rule.id}"

        # Build a tight one-line summary that survives a phone notification preview.
        if action_type == "place_order":
            symbol = config.get("symbol") or config.get("instrument_token") or "?"
            side = config.get("transaction_type") or config.get("side") or "?"
            qty = config.get("quantity") or "?"
            head = f"{'✅' if success else '❌'} {rule_label} → {side} {qty} {symbol}"
        elif action_type == "cancel_order":
            order_id = config.get("order_id") or config.get("order_ref") or "?"
            head = f"{'✅' if success else '❌'} {rule_label} → cancel order {order_id}"
        elif action_type == "cancel_rule":
            head = f"{'✅' if success else '❌'} {rule_label} → disabled linked rule(s)"
        else:
            head = f"{'✅' if success else '❌'} {rule_label} → {action_type}"

        detail = action_result.get("error") if not success else ""
        text = head if not detail else f"{head}\n{detail[:300]}"

        await notify(user_id=rule.user_id, category=category, text=text)

    async def _execute_place_order(self, rule: MonitorRule, config: dict) -> dict:
        """Place an order, routing through the user's order node if configured.

        For F&O contracts, action_config should include 'instrument_token' with
        the pre-resolved instrument key (e.g., 'NSE_FO|43885'). This bypasses
        the equity symbol→key lookup which doesn't handle option tradingsymbols.
        """
        action = PlaceOrderAction(**config)

        if self._paper_mode:
            logger.info("[PAPER] Placing order for rule %d: %s", rule.id, action)

        # Pre-fire idempotency scan: if a prior fire of this rule already has
        # a live order at the broker (any status that could still fill), don't
        # send a new one. Closes the window where the SDK times out, the daemon
        # treats it as failure and reverts fire_count, then re-fires while the
        # original request is still queued at Upstox. 2026-05-11 TATACONSUM:
        # rule 2741 fired 13× this way, ending with 3 actual buy fills for a
        # max_fires=1 rule. One extra Upstox API call per fire (~200-500ms).
        if not self._paper_mode:
            prior = await self._find_prior_fire_order(rule)
            if prior is not None:
                logger.warning(
                    "Rule %d: pre-fire scan found prior order %s (status=%s tag=%s) — "
                    "skipping new placement",
                    rule.id, prior.get("order_id"), prior.get("status"), prior.get("tag"),
                )
                return {
                    "success": True,
                    "order_id": prior.get("order_id"),
                    "status": prior.get("status") or "PLACED",
                    "message": f"Skipped — prior fire already at broker (id={prior.get('order_id')})",
                    "deduped_from_prior_fire": True,
                }

        # Check if this user has an order node configured
        node_url = None
        if self._get_order_node_url:
            node_url = await self._get_order_node_url(rule.user_id)

        if node_url:
            return await self._place_order_via_node(rule, action, node_url)

        # Direct path (no order node)
        return await self._place_order_direct(rule, action)

    async def _find_prior_fire_order(self, rule: MonitorRule) -> dict | None:
        """Scan today's broker order book for an order tagged with the exact
        ``rule:<id>:fire:<fire_count>`` we're about to use.

        Matches the *current* fire_count specifically — not any prior fire.
        Rationale: with ``max_fires > 1`` each fire gets a distinct number
        (1, 2, 3...), so finding ``fire:1`` should not block placing
        ``fire:2``. The bug we guard against is fire_count being reverted
        after a timeout, then re-firing with the same number while the
        original request is still queued at Upstox (2026-05-11 TATACONSUM).

        Returns ``{"order_id", "status", "tag"}`` if a live order with the
        exact tag exists, else None. Live = anything except rejected/cancelled.
        Errors are swallowed so a transient API failure doesn't block fires.
        """
        try:
            import asyncio
            import upstox_client
            # Same truncation the node applies (Upstox V3 tag limit is 40 chars).
            expected_tag = f"rule:{rule.id}:fire:{rule.fire_count}"[:40]
            client = await self._get_client(rule.user_id)
            api = upstox_client.OrderApi(upstox_client.ApiClient(client._configuration))
            resp = await asyncio.wait_for(
                asyncio.to_thread(api.get_order_book, api_version="2"),
                timeout=10,
            )
            for o in (resp.data or []):
                tag = getattr(o, "tag", None) or ""
                if tag != expected_tag:
                    continue
                status = (getattr(o, "status", None) or "").lower()
                # Live statuses Upstox uses: open, pending, trigger pending,
                # validation pending, after market order req received, modified,
                # complete. Dead statuses: rejected, cancelled.
                if status in ("rejected", "cancelled", "cancel"):
                    continue
                return {
                    "order_id": getattr(o, "order_id", None),
                    "status": getattr(o, "status", None),
                    "tag": tag,
                }
            return None
        except Exception as e:
            logger.warning("Pre-fire idempotency scan failed for rule %d: %r", rule.id, e)
            return None

    async def _place_order_via_node(self, rule: MonitorRule, action: PlaceOrderAction, node_url: str) -> dict:
        """Place an order through the user's order node proxy."""
        from services.order_node_proxy import OrderNodeProxy

        # Get the access token for auth header
        client = await self._get_client(rule.user_id)
        token = client.access_token

        proxy = OrderNodeProxy(node_url, token, broker=self._broker_for(rule.user_id))
        try:
            # Resolve instrument_token if not already set (equity path)
            instrument_token = action.instrument_token
            if not instrument_token:
                instrument_token = client._get_instrument_key(action.symbol)

            # Idempotency id keyed on (rule, fire_count): the rule_evaluator
            # increments fire_count atomically before each fire, so two parallel
            # tick processings of the same rule share the same id and collapse
            # at the order node. Distinct fires get distinct ids.
            client_request_id = f"rule:{rule.id}:fire:{rule.fire_count}"

            result = await proxy.place_order(
                symbol=action.symbol,
                instrument_token=instrument_token,
                transaction_type=action.transaction_type,
                quantity=action.quantity,
                order_type=action.order_type,
                price=action.price if action.price is not None else 0,
                product=action.product,
                client_request_id=client_request_id,
            )
            # Timeouts are ambiguous: the order may have reached Upstox even
            # though the SDK didn't return in time. Flag so the daemon's
            # revert path keeps fire_count incremented rather than rearming
            # the rule for another fire on the next tick.
            ambiguous = (
                not result.success
                and _looks_like_timeout(result.message, result.status)
            )
            return {
                "success": result.success,
                "order_id": result.order_id,
                "message": result.message,
                "status": result.status,
                "ambiguous": ambiguous,
            }
        except Exception as e:
            logger.error("place_order via node failed for rule %d: %s", rule.id, e)
            return {
                "success": False,
                "error": str(e),
                # httpx ReadTimeout / ConnectError on the transport itself is
                # also ambiguous — the request may have reached Upstox.
                "ambiguous": _looks_like_timeout(str(e), ""),
            }

    async def _place_order_direct(self, rule: MonitorRule, action: PlaceOrderAction) -> dict:
        """Place an order directly via httpx (fallback when no order node URL).

        Migrated off upstox-python-sdk on 2026-05-11 to avoid urllib3 hang
        on the HFT host. Both F&O (instrument_token supplied) and equity
        (symbol-only) paths go through AsyncUpstoxOrderApi now.
        """
        from services.upstox_order_api import AsyncUpstoxOrderApi
        client = await self._get_client(rule.user_id)
        try:
            instrument_token = action.instrument_token
            if not instrument_token:
                # Equity path: resolve symbol to instrument key. Same lookup
                # we use in _place_order_via_node so the path is identical.
                instrument_token = client._get_instrument_key(action.symbol)

            is_amo = not client._is_market_open()
            api = AsyncUpstoxOrderApi(client.access_token)
            r = await api.place_order(
                quantity=action.quantity,
                product=action.product,
                validity="DAY",
                price=action.price if action.order_type == "LIMIT" else 0,
                trigger_price=0,
                instrument_token=instrument_token,
                order_type=action.order_type,
                transaction_type=action.transaction_type,
                disclosed_quantity=0,
                is_amo=is_amo,
                market_protection=-1,
            )
            if r.get("success"):
                return {
                    "success": True,
                    "order_id": r.get("order_id"),
                    "message": f"Order placed: {action.transaction_type} {action.quantity} of {action.symbol}",
                    "status": r.get("status", "PLACED"),
                }
            return {
                "success": False,
                "error": r.get("message"),
                "status": r.get("status", "REJECTED"),
                "ambiguous": _looks_like_timeout(r.get("message"), r.get("status")),
            }
        except Exception as e:
            logger.error("place_order failed for rule %d: %r", rule.id, e, exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "ambiguous": _looks_like_timeout(str(e), ""),
            }

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
            proxy = OrderNodeProxy(node_url, client.access_token, broker=self._broker_for(rule.user_id))
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
