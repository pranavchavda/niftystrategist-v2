"""Technical analysis tools for stock market analysis."""

import logging
from typing import Literal

from pydantic_ai import RunContext

logger = logging.getLogger(__name__)


def register_analysis_tools(agent, deps_type):
    """Register technical analysis tools with the agent."""

    @agent.tool
    async def analyze_stock(
        ctx: RunContext[deps_type],
        symbol: str,
        interval: Literal["15minute", "30minute", "day"] = "15minute",
    ) -> str:
        """
        Perform comprehensive technical analysis on a stock.

        This tool calculates key indicators (RSI, MACD, moving averages, etc.)
        and provides a trading signal with beginner-friendly explanations.

        Args:
            symbol: Stock symbol (e.g., "RELIANCE", "TCS", "INFY")
            interval: Analysis timeframe - "15minute", "30minute", or "day"

        Returns:
            Complete technical analysis with indicators, signals, and recommendations
        """
        from services.upstox_client import UpstoxClient
        from services.technical_analysis import TechnicalAnalysisService

        try:
            # Get Upstox client
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                client = UpstoxClient(paper_trading=True)

            # Fetch historical data (need at least 50 candles)
            candles = await client.get_historical_data(symbol.upper(), interval, days=60)

            if len(candles) < 50:
                return f"❌ Insufficient data for {symbol}. Need at least 50 candles, got {len(candles)}."

            # Perform technical analysis
            ta_service = TechnicalAnalysisService()
            analysis = ta_service.analyze(symbol.upper(), candles)

            # Format the output
            indicators = analysis.indicators
            signal_emoji = {
                "strong_buy": "🟢🟢",
                "buy": "🟢",
                "hold": "🟡",
                "sell": "🔴",
                "strong_sell": "🔴🔴",
            }

            result = [
                f"📊 **Technical Analysis: {analysis.symbol}**",
                f"**Current Price:** ₹{analysis.current_price:,.2f}",
                "",
                f"**Overall Signal:** {signal_emoji.get(analysis.overall_signal, '')} {analysis.overall_signal.upper().replace('_', ' ')}",
                f"**Confidence:** {analysis.confidence:.0%}",
                "",
                "---",
                "**Indicators:**",
                f"- RSI (14): {indicators.rsi_14:.1f} → {analysis.rsi_signal.upper()}",
                f"- MACD: {indicators.macd_value:.2f} (Signal: {indicators.macd_signal:.2f}) → {analysis.macd_trend.upper()}",
                f"- Trend: {analysis.price_trend.upper()}",
                f"- Volume: {analysis.volume_signal.upper()} ({indicators.current_volume:,.0f} vs avg {indicators.volume_avg_20:,.0f})",
                "",
                "**Moving Averages:**",
                f"- SMA 20: ₹{indicators.sma_20:,.2f}",
                f"- SMA 50: ₹{indicators.sma_50:,.2f}",
                f"- EMA 12: ₹{indicators.ema_12:,.2f}",
                f"- EMA 26: ₹{indicators.ema_26:,.2f}",
                "",
                "**Volatility:**",
                f"- ATR (14): ₹{indicators.atr_14:.2f}",
            ]

            # Add support/resistance if available
            if analysis.support_level or analysis.resistance_level:
                result.append("")
                result.append("**Key Levels:**")
                if analysis.support_level:
                    result.append(f"- Support: ₹{analysis.support_level:,.2f}")
                if analysis.resistance_level:
                    result.append(f"- Resistance: ₹{analysis.resistance_level:,.2f}")

            # Add reasoning
            result.append("")
            result.append("---")
            result.append("**Analysis:**")
            result.append(analysis.reasoning)

            return "\n".join(result)

        except ValueError as e:
            return f"❌ Analysis failed for {symbol}: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in analyze_stock: {e}")
            return f"❌ Failed to analyze {symbol}: {str(e)}"

    @agent.tool
    async def compare_stocks(
        ctx: RunContext[deps_type],
        symbols: str,
    ) -> str:
        """
        Compare technical signals across multiple stocks.

        Args:
            symbols: Comma-separated stock symbols (e.g., "RELIANCE,TCS,INFY")

        Returns:
            Comparison table with signals for each stock
        """
        from services.upstox_client import UpstoxClient
        from services.technical_analysis import TechnicalAnalysisService

        symbol_list = [s.strip().upper() for s in symbols.split(",")]

        if len(symbol_list) < 2:
            return "❌ Please provide at least 2 symbols to compare (e.g., 'RELIANCE,TCS,INFY')"

        if len(symbol_list) > 5:
            return "❌ Maximum 5 symbols can be compared at once"

        try:
            client = getattr(ctx.deps, 'upstox_client', None)
            if not client:
                client = UpstoxClient(paper_trading=True)

            ta_service = TechnicalAnalysisService()

            results = []
            for symbol in symbol_list:
                try:
                    candles = await client.get_historical_data(symbol, "15minute", days=60)
                    if len(candles) >= 50:
                        analysis = ta_service.analyze(symbol, candles)
                        results.append({
                            "symbol": symbol,
                            "price": analysis.current_price,
                            "signal": analysis.overall_signal,
                            "confidence": analysis.confidence,
                            "rsi": analysis.indicators.rsi_14,
                            "trend": analysis.price_trend,
                        })
                    else:
                        results.append({
                            "symbol": symbol,
                            "error": "Insufficient data"
                        })
                except Exception as e:
                    results.append({
                        "symbol": symbol,
                        "error": str(e)
                    })

            # Format comparison table
            signal_emoji = {
                "strong_buy": "🟢🟢",
                "buy": "🟢",
                "hold": "🟡",
                "sell": "🔴",
                "strong_sell": "🔴🔴",
            }

            output = ["📊 **Stock Comparison**\n"]
            output.append("| Symbol | Price | Signal | Confidence | RSI | Trend |")
            output.append("|--------|-------|--------|------------|-----|-------|")

            for r in results:
                if "error" in r:
                    output.append(f"| {r['symbol']} | ❌ {r['error']} | - | - | - | - |")
                else:
                    emoji = signal_emoji.get(r['signal'], '')
                    output.append(
                        f"| {r['symbol']} | ₹{r['price']:,.2f} | {emoji} {r['signal'].upper()} | "
                        f"{r['confidence']:.0%} | {r['rsi']:.1f} | {r['trend']} |"
                    )

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Unexpected error in compare_stocks: {e}")
            return f"❌ Comparison failed: {str(e)}"
