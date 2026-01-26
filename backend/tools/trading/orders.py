"""Order execution tools with Human-in-the-Loop approval."""

import logging
from typing import Literal

from pydantic_ai import RunContext

from utils.hitl_decorator import requires_approval

logger = logging.getLogger(__name__)


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
        lines.append("⚠️ This will execute a real trade. Please confirm.")

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
        from services.upstox_client import UpstoxClient

        try:
            # Validate limit order has a price
            if order_type == "LIMIT" and not limit_price:
                return "❌ Limit orders require a limit_price. Please specify the price."

            # Get or create client
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                client = UpstoxClient(paper_trading=True)

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
            result_lines = [
                f"{emoji} **Order Placed Successfully**",
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

            # Add note about paper trading
            if client.paper_trading:
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
        from services.upstox_client import UpstoxClient

        try:
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                client = UpstoxClient(paper_trading=True)

            orders = await client.get_orders()

            if not orders:
                return "📭 No open orders."

            # Filter for open orders only
            open_orders = [o for o in orders if o.get('status') in ('open', 'pending', 'trigger_pending')]

            if not open_orders:
                return "📭 No open orders. All orders have been executed or cancelled."

            result = ["📋 **Open Orders:**\n"]
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
        from services.upstox_client import UpstoxClient

        try:
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                client = UpstoxClient(paper_trading=True)

            orders = await client.get_orders()

            if not orders:
                return "📭 No order history found."

            # Sort by timestamp if available, take most recent
            recent_orders = orders[:limit]

            result = ["📋 **Order History:**\n"]
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
        from services.upstox_client import UpstoxClient

        try:
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                client = UpstoxClient(paper_trading=True)

            result = await client.cancel_order(order_id)

            if result.get('success'):
                return f"✅ Order {order_id} has been cancelled."
            else:
                return f"❌ Failed to cancel order: {result.get('message', 'Unknown error')}"

        except ValueError as e:
            return f"❌ Cancel failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in cancel_order: {e}")
            return f"❌ Failed to cancel order: {str(e)}"
