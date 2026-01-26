"""Market data tools for fetching stock quotes and historical data."""

import logging
from typing import Literal, Optional

from pydantic_ai import RunContext

logger = logging.getLogger(__name__)


def register_market_data_tools(agent, deps_type):
    """Register market data tools with the agent."""

    @agent.tool
    async def get_stock_quote(
        ctx: RunContext[deps_type],
        symbol: str,
    ) -> str:
        """
        Get the current market quote for a stock.

        Args:
            symbol: Stock symbol (e.g., "RELIANCE", "TCS", "INFY")

        Returns:
            Current price, open, high, low, close, and volume
        """
        from services.upstox_client import UpstoxClient

        try:
            # Get Upstox client from deps or create new one
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                client = UpstoxClient(paper_trading=True)

            quote = await client.get_quote(symbol.upper())

            return (
                f"📊 **{quote['symbol']}** Quote:\n"
                f"- Last Price: ₹{quote['ltp']:,.2f}\n"
                f"- Open: ₹{quote['open']:,.2f}\n"
                f"- High: ₹{quote['high']:,.2f}\n"
                f"- Low: ₹{quote['low']:,.2f}\n"
                f"- Close: ₹{quote['close']:,.2f}\n"
                f"- Volume: {quote['volume']:,}"
            )

        except ValueError as e:
            return f"❌ Error fetching quote for {symbol}: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in get_stock_quote: {e}")
            return f"❌ Failed to get quote for {symbol}: {str(e)}"

    @agent.tool
    async def get_historical_data(
        ctx: RunContext[deps_type],
        symbol: str,
        interval: Literal["1minute", "5minute", "15minute", "30minute", "day"] = "15minute",
        days: int = 30,
    ) -> str:
        """
        Get historical OHLCV (candlestick) data for a stock.

        Args:
            symbol: Stock symbol (e.g., "RELIANCE", "TCS")
            interval: Candle interval - "1minute", "5minute", "15minute", "30minute", or "day"
            days: Number of days of history to fetch (default: 30)

        Returns:
            Summary of historical data with recent candles
        """
        from services.upstox_client import UpstoxClient

        try:
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                client = UpstoxClient(paper_trading=True)

            candles = await client.get_historical_data(symbol.upper(), interval, days)

            if not candles:
                return f"No historical data available for {symbol}"

            # Get recent candles (first 5 since newest is first)
            recent = candles[:5]

            # Calculate summary stats
            closes = [c.close for c in candles]
            highs = [c.high for c in candles]
            lows = [c.low for c in candles]

            result = [
                f"📈 **{symbol}** Historical Data ({interval}, {days} days):",
                f"- Total candles: {len(candles)}",
                f"- Price range: ₹{min(lows):,.2f} - ₹{max(highs):,.2f}",
                f"- Latest close: ₹{closes[0]:,.2f}",
                f"- Period change: {((closes[0] - closes[-1]) / closes[-1] * 100):.2f}%",
                "",
                "**Recent candles:**"
            ]

            for candle in recent:
                result.append(
                    f"- {candle.timestamp[:16]}: O={candle.open:.2f} H={candle.high:.2f} "
                    f"L={candle.low:.2f} C={candle.close:.2f} V={candle.volume:,}"
                )

            return "\n".join(result)

        except ValueError as e:
            return f"❌ Error fetching historical data for {symbol}: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in get_historical_data: {e}")
            return f"❌ Failed to get historical data for {symbol}: {str(e)}"

    @agent.tool
    async def list_supported_stocks(
        ctx: RunContext[deps_type],
    ) -> str:
        """
        List all supported stock symbols that can be traded.

        Returns:
            List of all supported NSE stock symbols
        """
        from services.upstox_client import UpstoxClient

        client = UpstoxClient(paper_trading=True)
        symbols = client.get_known_symbols()

        # Group by first letter for readability
        grouped = {}
        for s in symbols:
            first = s[0]
            if first not in grouped:
                grouped[first] = []
            grouped[first].append(s)

        result = [f"📋 **Supported Stocks ({len(symbols)} total):**\n"]
        for letter in sorted(grouped.keys()):
            result.append(f"**{letter}**: {', '.join(grouped[letter])}")

        return "\n".join(result)
