"""Cockpit dashboard API endpoints — live data for the trading cockpit UI."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from auth import User, get_current_user
from database.models import Trade, WatchlistItem as WatchlistItemDB, User as DBUser, utc_now
from services.upstox_client import UpstoxClient
from utils.market_status import get_market_status
from utils.encryption import decrypt_token

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level references set by main.py
_db_manager = None
_upstox_client: UpstoxClient | None = None


def _get_upstox_client() -> UpstoxClient:
    if _upstox_client is None:
        raise HTTPException(status_code=503, detail="Upstox client not initialized")
    return _upstox_client


# Cache live clients so the dynamic symbol map persists across endpoints
_live_clients: dict[int, UpstoxClient] = {}


async def _get_client_for_user(user: User) -> UpstoxClient:
    """Resolve the right Upstox client based on the user's trading mode.

    Returns a cached live client (with the user's decrypted token) when
    trading_mode='live' and token is valid, otherwise falls back to the
    shared paper client.  Caching ensures the dynamic symbol map
    (populated by get_portfolio) is available for chart/quote endpoints.
    """
    if _db_manager is None:
        return _get_upstox_client()

    # Return cached live client if token hasn't changed
    if user.id in _live_clients:
        return _live_clients[user.id]

    async with _db_manager.async_session() as session:
        result = await session.execute(
            select(DBUser).where(DBUser.id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if db_user and db_user.trading_mode == "live":
            if (db_user.upstox_access_token
                    and db_user.upstox_token_expiry
                    and db_user.upstox_token_expiry > datetime.utcnow()):
                access_token = decrypt_token(db_user.upstox_access_token)
                if access_token:
                    logger.info(f"Cockpit: live client for user {user.id}")
                    client = UpstoxClient(
                        access_token=access_token,
                        paper_trading=False,
                        user_id=db_user.id,
                    )
                    _live_clients[user.id] = client
                    return client
                else:
                    logger.warning(f"Cockpit: token decrypt failed for user {user.id}")
            else:
                logger.warning(f"Cockpit: user {user.id} has live mode but expired token")
                _live_clients.pop(user.id, None)
        else:
            _live_clients.pop(user.id, None)

    return _get_upstox_client()


async def _get_db() -> AsyncSession:
    if _db_manager is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    async with _db_manager.async_session() as session:
        yield session


# ---------------------------------------------------------------------------
# GET /market-status  (no auth required — pure time calculation)
# ---------------------------------------------------------------------------
@router.get("/market-status")
async def cockpit_market_status():
    """Return current NSE market status."""
    return get_market_status()


# ---------------------------------------------------------------------------
# GET /portfolio
# ---------------------------------------------------------------------------
@router.get("/portfolio")
async def cockpit_portfolio(user: User = Depends(get_current_user)):
    """Return portfolio summary matching the PortfolioSummary TypeScript interface."""
    client = await _get_client_for_user(user)
    try:
        portfolio = await client.get_portfolio()
        invested = portfolio.invested_value or 0
        total = portfolio.total_value or 0
        margin_used = (invested / total * 100) if total > 0 else 0

        return {
            "totalValue": portfolio.total_value,
            "investedValue": portfolio.invested_value,
            "availableCash": portfolio.available_cash,
            "dayPnl": portfolio.day_pnl,
            "dayPnlPct": portfolio.day_pnl_percentage,
            "totalPnl": portfolio.total_pnl,
            "totalPnlPct": portfolio.total_pnl_percentage,
            "marginUsed": round(margin_used, 2),
            "paperTrading": client.paper_trading,
        }
    except Exception as e:
        logger.error(f"Error fetching portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /positions
# ---------------------------------------------------------------------------
@router.get("/positions")
async def cockpit_positions(user: User = Depends(get_current_user)):
    """Return positions and holdings with company names."""
    client = await _get_client_for_user(user)
    try:
        portfolio = await client.get_portfolio()
        company_map = UpstoxClient.SYMBOL_TO_COMPANY

        positions = []
        holdings = []

        for pos in portfolio.positions:
            item = {
                "symbol": pos.symbol,
                "company": company_map.get(pos.symbol, pos.symbol),
                "qty": pos.quantity,
                "avgPrice": pos.average_price,
                "ltp": pos.current_price,
                "pnl": pos.pnl,
                "pnlPct": pos.pnl_percentage,
                "dayChange": pos.day_change,
                "dayChangePct": pos.day_change_percentage,
                "holdDays": 0,
            }
            # In live mode, get_portfolio() calls get_holdings() → these are holdings.
            # In paper mode, everything is a position (simulated intraday).
            if client.paper_trading:
                positions.append(item)
            else:
                holdings.append(item)

        return {"positions": positions, "holdings": holdings}
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /indices
# ---------------------------------------------------------------------------
@router.get("/indices")
async def cockpit_indices(user: User = Depends(get_current_user)):
    """Return NIFTY 50, BANK NIFTY, INDIA VIX quotes."""
    client = await _get_client_for_user(user)
    try:
        indices = await client.get_index_quotes()
        return indices
    except Exception as e:
        logger.error(f"Error fetching indices: {e}")
        # Graceful fallback: return empty array
        return []


# ---------------------------------------------------------------------------
# GET /watchlist
# ---------------------------------------------------------------------------
@router.get("/watchlist")
async def cockpit_watchlist(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(_get_db),
):
    """Return user's watchlists with live quotes and sparkline data."""
    client = await _get_client_for_user(user)

    try:
        # Fetch watchlist items from DB
        result = await db.execute(
            select(WatchlistItemDB)
            .where(WatchlistItemDB.user_id == user.id)
            .order_by(WatchlistItemDB.watchlist_name, WatchlistItemDB.sort_order)
        )
        db_items = result.scalars().all()

        if not db_items:
            return {}

        # Group by watchlist name
        grouped: dict[str, list] = {}
        for item in db_items:
            wl_name = item.watchlist_name or "Default"
            if wl_name not in grouped:
                grouped[wl_name] = []

            company = item.company_name or UpstoxClient.SYMBOL_TO_COMPANY.get(item.symbol, item.symbol)

            # Fetch live quote
            quote_data = {"ltp": 0, "volume": 0, "close": 0}
            try:
                quote = await client.get_quote(item.symbol)
                quote_data = {
                    "ltp": quote.get("ltp", 0),
                    "volume": quote.get("volume", 0),
                    "close": quote.get("close", 0),
                }
            except Exception as qe:
                logger.warning(f"Quote fetch failed for {item.symbol}: {qe}")

            ltp = quote_data["ltp"] or 0
            close = quote_data["close"] or ltp
            change = ltp - close if close else 0
            change_pct = (change / close * 100) if close else 0

            # Fetch sparkline (7 days of closing prices)
            sparkline = []
            try:
                candles = await client.get_historical_data(item.symbol, interval="day", days=10)
                sparkline = [c.close for c in candles[-7:]]
            except Exception:
                pass

            grouped[wl_name].append({
                "symbol": item.symbol,
                "company": company,
                "ltp": ltp,
                "change": round(change, 2),
                "changePct": round(change_pct, 2),
                "volume": quote_data["volume"] or 0,
                "sparkline": sparkline,
                "alertAbove": item.alert_above,
                "alertBelow": item.alert_below,
            })

        return grouped

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /chart/{symbol}
# ---------------------------------------------------------------------------
@router.get("/chart/{symbol}")
async def cockpit_chart(
    symbol: str,
    days: int = Query(default=90, ge=1, le=365),
    interval: str = Query(default="day"),
    user: User = Depends(get_current_user),
):
    """Return OHLCV data for a symbol, formatted for lightweight-charts."""
    client = await _get_client_for_user(user)
    try:
        candles = await client.get_historical_data(symbol.upper(), interval=interval, days=days)
        # Upstox returns newest-first; lightweight-charts requires ascending order
        candles.sort(key=lambda c: c.timestamp)
        return [
            {
                "time": c.timestamp[:10] if len(c.timestamp) >= 10 else c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
            }
            for c in candles
        ]
    except Exception as e:
        logger.error(f"Error fetching chart for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /scorecard
# ---------------------------------------------------------------------------
@router.get("/scorecard")
async def cockpit_scorecard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(_get_db),
):
    """Return today's trading scorecard."""
    try:
        # Today's date range (UTC, since DB uses naive UTC timestamps)
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await db.execute(
            select(Trade)
            .where(
                and_(
                    Trade.user_id == user.id,
                    Trade.status == "completed",
                    Trade.executed_at >= today_start,
                )
            )
            .order_by(Trade.executed_at)
        )
        trades = result.scalars().all()

        if not trades:
            return {
                "trades": 0,
                "won": 0,
                "lost": 0,
                "winRate": 0,
                "avgWinner": 0,
                "avgLoser": 0,
                "biggestWin": 0,
                "biggestLoss": 0,
                "profitFactor": 0,
                "streak": 0,
                "streakType": "neutral",
            }

        winners = [t for t in trades if (t.pnl or 0) > 0]
        losers = [t for t in trades if (t.pnl or 0) < 0]
        won = len(winners)
        lost = len(losers)
        total = len(trades)

        avg_winner = sum(t.pnl for t in winners) / won if won else 0
        avg_loser = abs(sum(t.pnl for t in losers) / lost) if lost else 0
        biggest_win = max((t.pnl for t in winners), default=0)
        biggest_loss = abs(min((t.pnl for t in losers), default=0))
        total_wins = sum(t.pnl for t in winners)
        total_losses = abs(sum(t.pnl for t in losers))
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 0

        # Calculate streak
        streak = 0
        streak_type = "neutral"
        for t in reversed(trades):
            pnl = t.pnl or 0
            if streak == 0:
                streak_type = "win" if pnl > 0 else ("loss" if pnl < 0 else "neutral")
                streak = 1
            elif (streak_type == "win" and pnl > 0) or (streak_type == "loss" and pnl < 0):
                streak += 1
            else:
                break

        return {
            "trades": total,
            "won": won,
            "lost": lost,
            "winRate": round(won / total * 100, 1) if total else 0,
            "avgWinner": round(avg_winner, 2),
            "avgLoser": round(avg_loser, 2),
            "biggestWin": round(biggest_win, 2),
            "biggestLoss": round(biggest_loss, 2),
            "profitFactor": round(profit_factor, 2),
            "streak": streak,
            "streakType": streak_type,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing scorecard: {e}")
        raise HTTPException(status_code=500, detail=str(e))
