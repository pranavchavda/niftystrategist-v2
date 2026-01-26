"""Watchlist management tools for tracking stocks of interest."""

import logging
from datetime import datetime, timezone

from pydantic_ai import RunContext

logger = logging.getLogger(__name__)


def register_watchlist_tools(agent, deps_type):
    """Register watchlist management tools with the agent."""

    @agent.tool
    async def add_to_watchlist(
        ctx: RunContext[deps_type],
        symbol: str,
        notes: str | None = None,
        target_buy_price: float | None = None,
        target_sell_price: float | None = None,
    ) -> str:
        """
        Add a stock to the user's watchlist.

        Args:
            symbol: Stock symbol (e.g., "RELIANCE", "TCS")
            notes: Optional notes about why this stock is being watched
            target_buy_price: Optional price at which to consider buying
            target_sell_price: Optional price at which to consider selling

        Returns:
            Confirmation of addition with current price
        """
        from services.upstox_client import UpstoxClient
        from database.session import AsyncSessionLocal
        from database.models import WatchlistItem
        from sqlalchemy import select

        try:
            # Get user_id from deps
            user_id = getattr(ctx.deps, 'user_id', None)
            if not user_id:
                return "❌ User not authenticated. Please log in first."

            symbol = symbol.upper()

            # Validate symbol exists
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                client = UpstoxClient(paper_trading=True)

            try:
                quote = await client.get_quote(symbol)
                current_price = quote['ltp']
            except ValueError:
                return f"❌ Unknown symbol: {symbol}. Use list_supported_stocks to see available symbols."

            # Check if already in watchlist
            async with AsyncSessionLocal() as session:
                existing = await session.execute(
                    select(WatchlistItem).where(
                        WatchlistItem.user_id == user_id,
                        WatchlistItem.symbol == symbol
                    )
                )
                if existing.scalar_one_or_none():
                    return f"⚠️ {symbol} is already in your watchlist. Use update_watchlist to modify it."

                # Add to watchlist
                watchlist_item = WatchlistItem(
                    user_id=user_id,
                    symbol=symbol,
                    notes=notes,
                    target_buy_price=target_buy_price,
                    target_sell_price=target_sell_price,
                    added_price=current_price,
                )
                session.add(watchlist_item)
                await session.commit()

            result = [
                f"✅ **Added {symbol} to watchlist**",
                "",
                f"**Current Price:** ₹{current_price:,.2f}",
            ]

            if target_buy_price:
                diff = ((current_price - target_buy_price) / target_buy_price) * 100
                result.append(f"**Target Buy:** ₹{target_buy_price:,.2f} ({diff:+.1f}% from current)")

            if target_sell_price:
                diff = ((target_sell_price - current_price) / current_price) * 100
                result.append(f"**Target Sell:** ₹{target_sell_price:,.2f} ({diff:+.1f}% from current)")

            if notes:
                result.append(f"**Notes:** {notes}")

            return "\n".join(result)

        except Exception as e:
            logger.error(f"Unexpected error in add_to_watchlist: {e}")
            return f"❌ Failed to add to watchlist: {str(e)}"

    @agent.tool
    async def get_watchlist(
        ctx: RunContext[deps_type],
    ) -> str:
        """
        Get the user's watchlist with current prices and alerts.

        Returns:
            Watchlist with current prices, changes, and any triggered alerts
        """
        from services.upstox_client import UpstoxClient
        from database.session import AsyncSessionLocal
        from database.models import WatchlistItem
        from sqlalchemy import select

        try:
            user_id = getattr(ctx.deps, 'user_id', None)
            if not user_id:
                return "❌ User not authenticated. Please log in first."

            # Get watchlist items
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(WatchlistItem).where(
                        WatchlistItem.user_id == user_id
                    ).order_by(WatchlistItem.created_at.desc())
                )
                items = result.scalars().all()

            if not items:
                return "📭 Your watchlist is empty. Use add_to_watchlist to add stocks."

            # Get current prices
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                client = UpstoxClient(paper_trading=True)

            output = ["📋 **Your Watchlist**\n"]
            alerts = []

            for item in items:
                try:
                    quote = await client.get_quote(item.symbol)
                    current_price = quote['ltp']

                    # Calculate change from added price
                    if item.added_price:
                        change = current_price - item.added_price
                        change_pct = (change / item.added_price) * 100
                        emoji = "🟢" if change >= 0 else "🔴"
                        change_str = f"{emoji} {change_pct:+.2f}%"
                    else:
                        change_str = "-"

                    output.append(f"**{item.symbol}** - ₹{current_price:,.2f} ({change_str})")

                    # Check for price alerts
                    if item.target_buy_price and current_price <= item.target_buy_price:
                        alerts.append(f"🔔 {item.symbol} hit buy target! ₹{current_price:,.2f} ≤ ₹{item.target_buy_price:,.2f}")

                    if item.target_sell_price and current_price >= item.target_sell_price:
                        alerts.append(f"🔔 {item.symbol} hit sell target! ₹{current_price:,.2f} ≥ ₹{item.target_sell_price:,.2f}")

                    # Add targets if set
                    targets = []
                    if item.target_buy_price:
                        targets.append(f"Buy: ₹{item.target_buy_price:,.2f}")
                    if item.target_sell_price:
                        targets.append(f"Sell: ₹{item.target_sell_price:,.2f}")
                    if targets:
                        output.append(f"  └─ Targets: {' | '.join(targets)}")

                    if item.notes:
                        output.append(f"  └─ Notes: {item.notes}")

                except Exception as e:
                    output.append(f"**{item.symbol}** - ⚠️ Price unavailable")

            # Add alerts section if any
            if alerts:
                output.append("")
                output.append("---")
                output.append("**🚨 ALERTS:**")
                for alert in alerts:
                    output.append(alert)

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Unexpected error in get_watchlist: {e}")
            return f"❌ Failed to get watchlist: {str(e)}"

    @agent.tool
    async def remove_from_watchlist(
        ctx: RunContext[deps_type],
        symbol: str,
    ) -> str:
        """
        Remove a stock from the user's watchlist.

        Args:
            symbol: Stock symbol to remove

        Returns:
            Confirmation of removal
        """
        from database.session import AsyncSessionLocal
        from database.models import WatchlistItem
        from sqlalchemy import select, delete

        try:
            user_id = getattr(ctx.deps, 'user_id', None)
            if not user_id:
                return "❌ User not authenticated. Please log in first."

            symbol = symbol.upper()

            async with AsyncSessionLocal() as session:
                # Check if exists
                result = await session.execute(
                    select(WatchlistItem).where(
                        WatchlistItem.user_id == user_id,
                        WatchlistItem.symbol == symbol
                    )
                )
                item = result.scalar_one_or_none()

                if not item:
                    return f"⚠️ {symbol} is not in your watchlist."

                # Delete
                await session.execute(
                    delete(WatchlistItem).where(
                        WatchlistItem.user_id == user_id,
                        WatchlistItem.symbol == symbol
                    )
                )
                await session.commit()

            return f"✅ Removed {symbol} from your watchlist."

        except Exception as e:
            logger.error(f"Unexpected error in remove_from_watchlist: {e}")
            return f"❌ Failed to remove from watchlist: {str(e)}"

    @agent.tool
    async def update_watchlist(
        ctx: RunContext[deps_type],
        symbol: str,
        notes: str | None = None,
        target_buy_price: float | None = None,
        target_sell_price: float | None = None,
        clear_targets: bool = False,
    ) -> str:
        """
        Update a stock's watchlist entry (targets, notes).

        Args:
            symbol: Stock symbol to update
            notes: New notes (replaces existing if provided)
            target_buy_price: New buy target price
            target_sell_price: New sell target price
            clear_targets: If True, clears all target prices

        Returns:
            Updated watchlist entry details
        """
        from database.session import AsyncSessionLocal
        from database.models import WatchlistItem
        from sqlalchemy import select

        try:
            user_id = getattr(ctx.deps, 'user_id', None)
            if not user_id:
                return "❌ User not authenticated. Please log in first."

            symbol = symbol.upper()

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(WatchlistItem).where(
                        WatchlistItem.user_id == user_id,
                        WatchlistItem.symbol == symbol
                    )
                )
                item = result.scalar_one_or_none()

                if not item:
                    return f"⚠️ {symbol} is not in your watchlist. Use add_to_watchlist first."

                # Update fields
                if clear_targets:
                    item.target_buy_price = None
                    item.target_sell_price = None
                else:
                    if target_buy_price is not None:
                        item.target_buy_price = target_buy_price
                    if target_sell_price is not None:
                        item.target_sell_price = target_sell_price

                if notes is not None:
                    item.notes = notes

                item.updated_at = datetime.now(timezone.utc)
                await session.commit()

                # Build response
                output = [f"✅ **Updated {symbol} watchlist entry**", ""]

                if item.target_buy_price:
                    output.append(f"**Target Buy:** ₹{item.target_buy_price:,.2f}")
                if item.target_sell_price:
                    output.append(f"**Target Sell:** ₹{item.target_sell_price:,.2f}")
                if item.notes:
                    output.append(f"**Notes:** {item.notes}")

                return "\n".join(output) if len(output) > 2 else f"✅ Updated {symbol} (no targets or notes set)"

        except Exception as e:
            logger.error(f"Unexpected error in update_watchlist: {e}")
            return f"❌ Failed to update watchlist: {str(e)}"

    @agent.tool
    async def check_watchlist_alerts(
        ctx: RunContext[deps_type],
    ) -> str:
        """
        Check for any triggered price alerts in the watchlist.

        Returns:
            List of triggered alerts or "no alerts" message
        """
        from services.upstox_client import UpstoxClient
        from database.session import AsyncSessionLocal
        from database.models import WatchlistItem
        from sqlalchemy import select

        try:
            user_id = getattr(ctx.deps, 'user_id', None)
            if not user_id:
                return "❌ User not authenticated. Please log in first."

            # Get watchlist items with targets
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(WatchlistItem).where(
                        WatchlistItem.user_id == user_id
                    )
                )
                items = result.scalars().all()

            items_with_targets = [
                i for i in items
                if i.target_buy_price or i.target_sell_price
            ]

            if not items_with_targets:
                return "📭 No price alerts set. Use update_watchlist to set target prices."

            # Check current prices
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                client = UpstoxClient(paper_trading=True)

            alerts = []

            for item in items_with_targets:
                try:
                    quote = await client.get_quote(item.symbol)
                    current_price = quote['ltp']

                    if item.target_buy_price and current_price <= item.target_buy_price:
                        diff = ((item.target_buy_price - current_price) / item.target_buy_price) * 100
                        alerts.append({
                            'symbol': item.symbol,
                            'type': 'BUY',
                            'current': current_price,
                            'target': item.target_buy_price,
                            'diff': diff,
                            'notes': item.notes
                        })

                    if item.target_sell_price and current_price >= item.target_sell_price:
                        diff = ((current_price - item.target_sell_price) / item.target_sell_price) * 100
                        alerts.append({
                            'symbol': item.symbol,
                            'type': 'SELL',
                            'current': current_price,
                            'target': item.target_sell_price,
                            'diff': diff,
                            'notes': item.notes
                        })

                except Exception:
                    continue

            if not alerts:
                return "✅ No price alerts triggered. All stocks are within your target ranges."

            output = ["🚨 **Price Alerts Triggered!**\n"]

            for alert in alerts:
                emoji = "🟢" if alert['type'] == 'BUY' else "🔴"
                output.append(
                    f"{emoji} **{alert['symbol']}** - {alert['type']} alert!\n"
                    f"   Current: ₹{alert['current']:,.2f} | Target: ₹{alert['target']:,.2f}"
                )
                if alert['notes']:
                    output.append(f"   Notes: {alert['notes']}")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Unexpected error in check_watchlist_alerts: {e}")
            return f"❌ Failed to check alerts: {str(e)}"
