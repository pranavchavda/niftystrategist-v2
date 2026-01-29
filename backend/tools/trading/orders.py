"""Order execution tools with Human-in-the-Loop approval."""

import logging
from typing import Literal, Optional

from pydantic_ai import RunContext
from sqlalchemy import select

from utils.hitl_decorator import requires_approval

logger = logging.getLogger(__name__)


async def get_trading_client_for_user(user_email: str):
    """
    Get the appropriate UpstoxClient for a user based on their trading mode.

    Returns:
        Tuple of (client, is_live_trading)
    """
    from database.session import get_db_session
    from database.models import User as DBUser
    from services.upstox_client import UpstoxClient
    from api.upstox_oauth import get_user_upstox_token
    from utils.encryption import decrypt_token
    from datetime import datetime, timezone

    async with get_db_session() as session:
        result = await session.execute(
            select(DBUser).where(DBUser.email == user_email)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            # Fallback to shared paper trading client
            from main import shared_upstox_client
            return shared_upstox_client, False

        # Check if user wants live trading
        if db_user.trading_mode == "live":
            # Verify Upstox connection is valid (use naive datetime for DB compatibility)
            if (db_user.upstox_access_token and
                db_user.upstox_token_expiry and
                db_user.upstox_token_expiry > datetime.utcnow()):

                # Decrypt token and create live client
                access_token = decrypt_token(db_user.upstox_access_token)
                if access_token:
                    logger.info(f"Creating live trading client for user {db_user.id}")
                    client = UpstoxClient(
                        access_token=access_token,
                        paper_trading=False,
                        user_id=db_user.id,
                    )
                    return client, True
                else:
                    logger.warning(f"Failed to decrypt token for user {db_user.id}")
            else:
                logger.warning(f"User {db_user.id} has live mode but invalid/expired Upstox token")

        # Fallback to paper trading with user's ID
        from main import shared_upstox_client

        # Update user_id on shared client for proper trade tracking
        shared_upstox_client.user_id = db_user.id
        return shared_upstox_client, False


def register_order_tools(agent, deps_type):
    """Register order execution tools with the agent."""

    def _format_order_explanation(args: dict) -> str:
        """Format a human-readable explanation for order approval."""
        symbol = args.get("symbol", "UNKNOWN")
        action = args.get("action", "BUY")
        quantity = args.get("quantity", 0)
        order_type = args.get("order_type", "MARKET")
        limit_price = args.get("limit_price")
        stop_loss = args.get("stop_loss")
        target = args.get("target")

        lines = [
            f"📊 **{action} Order for {symbol}**",
            f"",
            f"**Quantity:** {quantity} shares",
            f"**Order Type:** {order_type}",
        ]

        if limit_price:
            lines.append(f"**Limit Price:** ₹{limit_price:,.2f}")

        if stop_loss:
            lines.append(f"**Stop Loss:** ₹{stop_loss:,.2f}")

        if target:
            lines.append(f"**Target:** ₹{target:,.2f}")

        lines.append("")
        lines.append("⚠️ Please confirm to execute this trade.")

        return "\n".join(lines)

    @agent.tool
    @requires_approval(
        explanation_fn=_format_order_explanation,
        tool_name_override="place_order"
    )
    async def place_order(
        ctx: RunContext[deps_type],
        symbol: str,
        action: Literal["BUY", "SELL"],
        quantity: int,
        order_type: Literal["MARKET", "LIMIT"] = "MARKET",
        limit_price: float | None = None,
        stop_loss: float | None = None,
        target: float | None = None,
    ) -> str:
        """
        Place a buy or sell order for a stock. REQUIRES USER APPROVAL.

        This tool will pause and request explicit user approval before
        executing the order. The user can approve or reject the order.

        Args:
            symbol: Stock symbol (e.g., "RELIANCE", "TCS")
            action: "BUY" or "SELL"
            quantity: Number of shares to trade
            order_type: "MARKET" (immediate) or "LIMIT" (at specific price)
            limit_price: Price for limit orders (required if order_type is LIMIT)
            stop_loss: Optional stop loss price
            target: Optional target price

        Returns:
            Order confirmation with order ID and details
        """
        try:
            # Validate limit order has a price
            if order_type == "LIMIT" and not limit_price:
                return "❌ Limit orders require a limit_price. Please specify the price."

            # Get user email from context
            user_email = ctx.deps.state.user_id

            # Get the appropriate client based on user's trading mode
            client, is_live = await get_trading_client_for_user(user_email)

            # Execute the order
            order_result = await client.place_order(
                symbol=symbol.upper(),
                transaction_type=action,
                quantity=quantity,
                order_type=order_type,
                price=limit_price if limit_price else 0,
            )

            # Check if order was successful
            if not order_result.success:
                return f"❌ Order failed: {order_result.message}"

            # Format success response
            emoji = "🟢" if action == "BUY" else "🔴"
            mode_indicator = "🔴 LIVE" if is_live else "📝 Paper"

            result_lines = [
                f"{emoji} **Order Placed Successfully** [{mode_indicator}]",
                "",
                f"**Order ID:** {order_result.order_id}",
                f"**Symbol:** {symbol.upper()}",
                f"**Action:** {action}",
                f"**Quantity:** {quantity} shares",
                f"**Type:** {order_type}",
            ]

            if order_result.executed_price:
                result_lines.append(f"**Executed Price:** ₹{order_result.executed_price:,.2f}")

            if order_result.status:
                result_lines.append(f"**Status:** {order_result.status}")

            if stop_loss:
                result_lines.append("")
                result_lines.append(f"📍 **Stop Loss:** ₹{stop_loss:,.2f}")
                result_lines.append("*(Note: Bracket orders not yet implemented - set stop loss manually)*")

            if target:
                result_lines.append(f"🎯 **Target:** ₹{target:,.2f}")

            # Add note about trading mode
            if is_live:
                result_lines.append("")
                result_lines.append("⚠️ *Live trading - real money at risk*")
            else:
                result_lines.append("")
                result_lines.append("📝 *Paper trading mode - no real money at risk*")

            return "\n".join(result_lines)

        except ValueError as e:
            return f"❌ Order failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in place_order: {e}")
            return f"❌ Failed to place order: {str(e)}"

    @agent.tool
    async def get_open_orders(
        ctx: RunContext[deps_type],
    ) -> str:
        """
        Get all open/pending orders.

        Returns:
            List of open orders with their status
        """
        try:
            user_email = ctx.deps.state.user_id
            client, is_live = await get_trading_client_for_user(user_email)

            orders = await client.get_orders()

            if not orders:
                return "📭 No open orders."

            # Filter for open orders only
            open_orders = [o for o in orders if o.get('status') in ('open', 'pending', 'trigger_pending')]

            if not open_orders:
                return "📭 No open orders. All orders have been executed or cancelled."

            mode_indicator = "🔴 LIVE" if is_live else "📝 Paper"
            result = [f"📋 **Open Orders** [{mode_indicator}]\n"]
            result.append("| Order ID | Symbol | Action | Qty | Type | Price | Status |")
            result.append("|----------|--------|--------|-----|------|-------|--------|")

            for order in open_orders:
                price_str = f"₹{order['price']:,.2f}" if order.get('price') else "MARKET"
                result.append(
                    f"| {order['order_id'][:8]}... | {order['symbol']} | "
                    f"{order['transaction_type']} | {order['quantity']} | "
                    f"{order['order_type']} | {price_str} | {order['status']} |"
                )

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Unexpected error in get_open_orders: {e}")
            return f"❌ Failed to get orders: {str(e)}"

    @agent.tool
    async def get_order_history(
        ctx: RunContext[deps_type],
        limit: int = 10,
    ) -> str:
        """
        Get recent order history (executed, cancelled, rejected).

        Args:
            limit: Maximum number of orders to return (default: 10)

        Returns:
            List of recent orders with their status
        """
        try:
            user_email = ctx.deps.state.user_id
            client, is_live = await get_trading_client_for_user(user_email)

            orders = await client.get_orders()

            if not orders:
                return "📭 No order history found."

            # Sort by timestamp if available, take most recent
            recent_orders = orders[:limit]

            mode_indicator = "🔴 LIVE" if is_live else "📝 Paper"
            result = [f"📋 **Order History** [{mode_indicator}]\n"]
            result.append("| Time | Symbol | Action | Qty | Price | Status |")
            result.append("|------|--------|--------|-----|-------|--------|")

            for order in recent_orders:
                timestamp = order.get('timestamp', '')[:16] if order.get('timestamp') else '-'
                price_str = f"₹{order.get('average_price', order.get('price', 0)):,.2f}"
                status_emoji = {
                    'complete': '✅',
                    'executed': '✅',
                    'rejected': '❌',
                    'cancelled': '🚫',
                    'open': '⏳',
                    'pending': '⏳',
                }.get(order.get('status', '').lower(), '❓')

                result.append(
                    f"| {timestamp} | {order['symbol']} | "
                    f"{order['transaction_type']} | {order['quantity']} | "
                    f"{price_str} | {status_emoji} {order.get('status', 'unknown')} |"
                )

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Unexpected error in get_order_history: {e}")
            return f"❌ Failed to get order history: {str(e)}"

    @agent.tool
    @requires_approval(
        explanation_fn=lambda args: f"❌ Cancel order: {args.get('order_id', 'UNKNOWN')}",
        tool_name_override="cancel_order"
    )
    async def cancel_order(
        ctx: RunContext[deps_type],
        order_id: str,
    ) -> str:
        """
        Cancel an open order. REQUIRES USER APPROVAL.

        Args:
            order_id: The order ID to cancel

        Returns:
            Confirmation of cancellation
        """
        try:
            user_email = ctx.deps.state.user_id
            client, is_live = await get_trading_client_for_user(user_email)

            result = await client.cancel_order(order_id)

            mode_indicator = "🔴 LIVE" if is_live else "📝 Paper"
            if result.get('success'):
                return f"✅ Order {order_id} has been cancelled. [{mode_indicator}]"
            else:
                return f"❌ Failed to cancel order: {result.get('message', 'Unknown error')}"

        except ValueError as e:
            return f"❌ Cancel failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in cancel_order: {e}")
            return f"❌ Failed to cancel order: {str(e)}"
