"""
Trading Tools Module for Nifty Strategist v2

Provides Pydantic AI tools for:
- Market data (quotes, historical data)
- Technical analysis
- Portfolio management
- Order execution (with HITL)
- Watchlist management
"""

from .market_data import register_market_data_tools
from .analysis import register_analysis_tools
from .portfolio import register_portfolio_tools
from .orders import register_order_tools
from .watchlist import register_watchlist_tools


def register_all_trading_tools(agent, deps_type):
    """
    Register all trading tools with a Pydantic AI agent.

    Args:
        agent: The Pydantic AI agent to register tools with
        deps_type: The dependencies type (e.g., OrchestratorDeps)

    Usage:
        from tools.trading import register_all_trading_tools
        register_all_trading_tools(self.agent, OrchestratorDeps)
    """
    # Market data tools removed — now handled by CLI tools (nf-quote, nf-market-status)
    # register_market_data_tools(agent, deps_type)
    register_analysis_tools(agent, deps_type)
    register_portfolio_tools(agent, deps_type)
    register_order_tools(agent, deps_type)
    register_watchlist_tools(agent, deps_type)


__all__ = [
    "register_all_trading_tools",
    "register_market_data_tools",
    "register_analysis_tools",
    "register_portfolio_tools",
    "register_order_tools",
    "register_watchlist_tools",
]
