"""Portfolio management tools for viewing holdings and positions."""

import logging

from pydantic_ai import RunContext

logger = logging.getLogger(__name__)


def register_portfolio_tools(agent, deps_type):
    """Register portfolio management tools with the agent."""

    @agent.tool
    async def get_portfolio(
        ctx: RunContext[deps_type],
    ) -> str:
        """
        Get the current portfolio summary including all positions and P&L.

        Returns:
            Portfolio summary with total value, available cash, positions, and P&L
        """
        try:
            # Use shared client from deps or import the global one
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                # Import the shared global client
                from main import shared_upstox_client
                client = shared_upstox_client

            portfolio = await client.get_portfolio()

            # Format portfolio summary
            pnl_emoji = "🟢" if portfolio.total_pnl >= 0 else "🔴"
            day_pnl_emoji = "🟢" if portfolio.day_pnl >= 0 else "🔴"

            result = [
                "💼 **Portfolio Summary**",
                "",
                f"**Total Value:** ₹{portfolio.total_value:,.2f}",
                f"**Available Cash:** ₹{portfolio.available_cash:,.2f}",
                f"**Invested Value:** ₹{portfolio.invested_value:,.2f}",
                "",
                f"**Today's P&L:** {day_pnl_emoji} ₹{portfolio.day_pnl:,.2f} ({portfolio.day_pnl_percentage:+.2f}%)",
                f"**Total P&L:** {pnl_emoji} ₹{portfolio.total_pnl:,.2f} ({portfolio.total_pnl_percentage:+.2f}%)",
            ]

            if portfolio.positions:
                result.append("")
                result.append("---")
                result.append("**Positions:**")
                result.append("")
                result.append("| Symbol | Qty | Avg Price | Current | P&L | % |")
                result.append("|--------|-----|-----------|---------|-----|---|")

                for pos in portfolio.positions:
                    pos_emoji = "🟢" if pos.pnl >= 0 else "🔴"
                    result.append(
                        f"| {pos.symbol} | {pos.quantity} | ₹{pos.average_price:,.2f} | "
                        f"₹{pos.current_price:,.2f} | {pos_emoji} ₹{pos.pnl:,.2f} | {pos.pnl_percentage:+.2f}% |"
                    )
            else:
                result.append("")
                result.append("*No open positions*")

            # Add note about paper trading if applicable
            if client.paper_trading:
                result.append("")
                result.append("📝 *Paper trading mode - no real money at risk*")

            return "\n".join(result)

        except ValueError as e:
            return f"❌ Error fetching portfolio: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in get_portfolio: {e}")
            return f"❌ Failed to get portfolio: {str(e)}"

    @agent.tool
    async def get_position(
        ctx: RunContext[deps_type],
        symbol: str,
    ) -> str:
        """
        Get details for a specific position in the portfolio.

        Args:
            symbol: Stock symbol to check (e.g., "RELIANCE")

        Returns:
            Position details including quantity, average price, current price, and P&L
        """
        try:
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                from main import shared_upstox_client
                client = shared_upstox_client

            portfolio = await client.get_portfolio()

            # Find the position
            position = next(
                (p for p in portfolio.positions if p.symbol.upper() == symbol.upper()),
                None
            )

            if not position:
                return f"📭 No position found for {symbol.upper()}"

            pnl_emoji = "🟢" if position.pnl >= 0 else "🔴"
            day_emoji = "🟢" if position.day_change >= 0 else "🔴"

            return (
                f"📊 **Position: {position.symbol}**\n"
                f"\n"
                f"**Quantity:** {position.quantity} shares\n"
                f"**Average Price:** ₹{position.average_price:,.2f}\n"
                f"**Current Price:** ₹{position.current_price:,.2f}\n"
                f"\n"
                f"**Total Value:** ₹{position.quantity * position.current_price:,.2f}\n"
                f"**Total P&L:** {pnl_emoji} ₹{position.pnl:,.2f} ({position.pnl_percentage:+.2f}%)\n"
                f"**Day Change:** {day_emoji} ₹{position.day_change:,.2f} ({position.day_change_percentage:+.2f}%)"
            )

        except Exception as e:
            logger.error(f"Unexpected error in get_position: {e}")
            return f"❌ Failed to get position for {symbol}: {str(e)}"

    @agent.tool
    async def calculate_position_size(
        ctx: RunContext[deps_type],
        symbol: str,
        risk_amount: float,
        stop_loss_percent: float = 2.0,
    ) -> str:
        """
        Calculate recommended position size based on risk management rules.

        Args:
            symbol: Stock symbol to calculate position for
            risk_amount: Maximum amount willing to risk in rupees (e.g., 5000)
            stop_loss_percent: Stop loss percentage from entry (default: 2%)

        Returns:
            Recommended quantity and position details
        """
        try:
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                from main import shared_upstox_client
                client = shared_upstox_client

            # Get current price
            quote = await client.get_quote(symbol.upper())
            current_price = quote['ltp']

            # Calculate position size
            # Risk per share = current_price * stop_loss_percent / 100
            risk_per_share = current_price * (stop_loss_percent / 100)

            # Quantity = risk_amount / risk_per_share
            recommended_qty = int(risk_amount / risk_per_share)

            if recommended_qty < 1:
                return (
                    f"⚠️ With ₹{risk_amount:,.2f} risk and {stop_loss_percent}% stop loss, "
                    f"you cannot buy even 1 share of {symbol} at ₹{current_price:,.2f}.\n"
                    f"Consider increasing your risk budget or using a tighter stop loss."
                )

            total_investment = recommended_qty * current_price
            stop_loss_price = current_price * (1 - stop_loss_percent / 100)

            return (
                f"📐 **Position Size Calculator: {symbol}**\n"
                f"\n"
                f"**Current Price:** ₹{current_price:,.2f}\n"
                f"**Risk Amount:** ₹{risk_amount:,.2f}\n"
                f"**Stop Loss:** {stop_loss_percent}% (₹{stop_loss_price:,.2f})\n"
                f"\n"
                f"**Recommended Quantity:** {recommended_qty} shares\n"
                f"**Total Investment:** ₹{total_investment:,.2f}\n"
                f"**Max Loss if SL Hit:** ₹{risk_amount:,.2f}\n"
                f"\n"
                f"💡 This position size limits your maximum loss to ₹{risk_amount:,.2f} "
                f"if the stop loss is triggered."
            )

        except ValueError as e:
            return f"❌ Error calculating position size: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in calculate_position_size: {e}")
            return f"❌ Failed to calculate position size: {str(e)}"
