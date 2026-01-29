"""
Trade persistence service for paper trading.
Handles saving/loading trades from the database.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Trade, TradeStatus
from models.trading import Portfolio, PortfolioPosition

logger = logging.getLogger(__name__)

# Starting capital for paper trading
PAPER_TRADING_CAPITAL = 1_000_000.0  # 10 lakh


class TradePersistence:
    """Handles persisting paper trades to the database."""

    def __init__(self, async_session_maker):
        """
        Initialize with a session maker.

        Args:
            async_session_maker: Callable that returns an async session context manager
        """
        self._async_session_maker = async_session_maker

    async def save_trade(
        self,
        user_id: int,
        symbol: str,
        direction: str,
        quantity: int,
        executed_price: float,
        order_type: str,
        order_id: str,
        reasoning: Optional[str] = None,
    ) -> Trade:
        """
        Save a completed trade to the database.

        Args:
            user_id: User who placed the trade
            symbol: Stock symbol
            direction: BUY or SELL
            quantity: Number of shares
            executed_price: Price at which order was filled
            order_type: MARKET or LIMIT
            order_id: Paper order ID
            reasoning: Optional AI reasoning for the trade

        Returns:
            The created Trade record
        """
        async with self._async_session_maker() as db:
            trade = Trade(
                user_id=user_id,
                symbol=symbol.upper(),
                exchange="NSE",
                direction=direction,
                quantity=quantity,
                order_type=order_type,
                executed_price=executed_price,
                proposed_price=executed_price,
                status=TradeStatus.COMPLETED.value,
                upstox_order_id=order_id,
                reasoning=reasoning,
                proposed_at=datetime.utcnow(),  # Use naive datetime for DB compatibility
                executed_at=datetime.utcnow(),
            )
            db.add(trade)
            await db.commit()
            await db.refresh(trade)

            logger.info(f"[TradePersistence] Saved trade: {direction} {quantity} {symbol} @ ₹{executed_price:.2f} for user {user_id}")
            return trade

    async def get_portfolio_for_user(self, user_id: int) -> Portfolio:
        """
        Calculate portfolio from trade history.

        Args:
            user_id: User to get portfolio for

        Returns:
            Portfolio with positions and P&L calculated from trades
        """
        async with self._async_session_maker() as db:
            # Get all completed trades for user
            stmt = (
                select(Trade)
                .where(Trade.user_id == user_id)
                .where(Trade.status == TradeStatus.COMPLETED.value)
                .order_by(Trade.executed_at)
            )
            result = await db.execute(stmt)
            trades = result.scalars().all()

            # Calculate positions from trades
            positions_dict: dict[str, dict] = {}
            total_invested = 0.0
            realized_pnl = 0.0

            for trade in trades:
                symbol = trade.symbol
                if symbol not in positions_dict:
                    positions_dict[symbol] = {
                        "quantity": 0,
                        "total_cost": 0.0,
                        "average_price": 0.0,
                    }

                pos = positions_dict[symbol]

                if trade.direction == "BUY":
                    # Add to position
                    new_qty = pos["quantity"] + trade.quantity
                    if new_qty > 0:
                        pos["total_cost"] += trade.executed_price * trade.quantity
                        pos["average_price"] = pos["total_cost"] / new_qty
                    pos["quantity"] = new_qty
                    total_invested += trade.executed_price * trade.quantity

                else:  # SELL
                    # Remove from position
                    if pos["quantity"] > 0:
                        # Calculate realized P&L
                        cost_basis = pos["average_price"] * trade.quantity
                        sale_value = trade.executed_price * trade.quantity
                        realized_pnl += sale_value - cost_basis

                        pos["total_cost"] -= pos["average_price"] * trade.quantity
                        pos["quantity"] -= trade.quantity
                        total_invested -= pos["average_price"] * trade.quantity

                        if pos["quantity"] <= 0:
                            pos["quantity"] = 0
                            pos["total_cost"] = 0.0
                            pos["average_price"] = 0.0

            # Build portfolio positions (only those with quantity > 0)
            portfolio_positions = []
            current_invested = 0.0

            for symbol, pos in positions_dict.items():
                if pos["quantity"] > 0:
                    # TODO: Get current price from market data
                    # For now, use average price as current price
                    current_price = pos["average_price"]

                    position = PortfolioPosition(
                        symbol=symbol,
                        quantity=pos["quantity"],
                        average_price=pos["average_price"],
                        current_price=current_price,
                        pnl=0.0,  # Will be calculated with real prices
                        pnl_percentage=0.0,
                        day_change=0.0,
                        day_change_percentage=0.0,
                    )
                    portfolio_positions.append(position)
                    current_invested += pos["average_price"] * pos["quantity"]

            # Calculate available cash
            available_cash = PAPER_TRADING_CAPITAL - current_invested + realized_pnl

            portfolio = Portfolio(
                total_value=available_cash + current_invested,
                available_cash=available_cash,
                invested_value=current_invested,
                day_pnl=0.0,
                day_pnl_percentage=0.0,
                total_pnl=realized_pnl,
                total_pnl_percentage=(realized_pnl / PAPER_TRADING_CAPITAL * 100) if PAPER_TRADING_CAPITAL > 0 else 0.0,
                positions=portfolio_positions,
            )

            logger.info(
                f"[TradePersistence] Loaded portfolio for user {user_id}: "
                f"₹{portfolio.total_value:,.2f} total, {len(portfolio_positions)} positions"
            )
            return portfolio

    async def get_trade_history(
        self, user_id: int, limit: int = 50
    ) -> list[dict]:
        """
        Get recent trade history for a user.

        Args:
            user_id: User to get history for
            limit: Maximum number of trades to return

        Returns:
            List of trade dictionaries
        """
        async with self._async_session_maker() as db:
            stmt = (
                select(Trade)
                .where(Trade.user_id == user_id)
                .order_by(Trade.executed_at.desc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            trades = result.scalars().all()

            return [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "direction": t.direction,
                    "quantity": t.quantity,
                    "executed_price": t.executed_price,
                    "order_type": t.order_type,
                    "status": t.status,
                    "executed_at": t.executed_at.isoformat() if t.executed_at else None,
                    "pnl": t.pnl,
                    "reasoning": t.reasoning,
                }
                for t in trades
            ]


# Global instance (will be initialized in main.py)
trade_persistence: Optional[TradePersistence] = None


def init_trade_persistence(async_session_maker) -> TradePersistence:
    """Initialize the global trade persistence instance."""
    global trade_persistence
    trade_persistence = TradePersistence(async_session_maker)
    logger.info("[TradePersistence] Initialized trade persistence service")
    return trade_persistence


def get_trade_persistence() -> Optional[TradePersistence]:
    """Get the global trade persistence instance."""
    return trade_persistence
