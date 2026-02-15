"""Cockpit dashboard API endpoints — live data for the trading cockpit UI."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from auth import User, get_current_user
from database.models import (
    Trade, WatchlistItem as WatchlistItemDB, User as DBUser,
    Conversation, Message, utc_now,
)
from services.upstox_client import UpstoxClient
from services.instruments_cache import get_company_name as cache_get_company_name
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


def invalidate_client_cache(user_id: int) -> None:
    """Remove cached live client for a user (e.g. after trading mode switch)."""
    _live_clients.pop(user_id, None)


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
            company = company_map.get(pos.symbol) or cache_get_company_name(pos.symbol) or pos.symbol
            item = {
                "symbol": pos.symbol,
                "company": company,
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

            company = item.company_name or UpstoxClient.SYMBOL_TO_COMPANY.get(item.symbol) or cache_get_company_name(item.symbol) or item.symbol

            # Fetch live quote
            quote_data = {"ltp": 0, "volume": 0, "close": 0, "net_change": 0, "pct_change": 0}
            try:
                quote = await client.get_quote(item.symbol)
                quote_data = {
                    "ltp": quote.get("ltp", 0),
                    "volume": quote.get("volume", 0),
                    "close": quote.get("close", 0),
                    "net_change": quote.get("net_change", 0),
                    "pct_change": quote.get("pct_change", 0),
                }
            except Exception as qe:
                logger.warning(f"Quote fetch failed for {item.symbol}: {qe}")

            ltp = quote_data["ltp"] or 0
            # Prefer API-provided net_change/pct_change (correct even on weekends)
            change = quote_data["net_change"] or 0
            change_pct = quote_data["pct_change"] or 0

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
        intraday = interval in ("1minute", "5minute", "15minute", "30minute")
        return [
            {
                "time": int(datetime.fromisoformat(c.timestamp).timestamp()) if intraday else (c.timestamp[:10] if len(c.timestamp) >= 10 else c.timestamp),
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


# ---------------------------------------------------------------------------
# POST /daily-thread  — Get or create today's cockpit thread
# ---------------------------------------------------------------------------
COCKPIT_COMPACT_THRESHOLD = 60   # message count that triggers compaction
COCKPIT_KEEP_RECENT = 20         # recent messages to keep after compaction
IST_OFFSET = timedelta(hours=5, minutes=30)


def _ist_today_start_utc() -> datetime:
    """Return naive-UTC datetime corresponding to midnight IST today."""
    now_utc = utc_now()
    now_ist = now_utc + IST_OFFSET          # approximate IST (naive)
    midnight_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight_ist - IST_OFFSET         # back to naive UTC


def _ist_today_label() -> str:
    """Return a human label like 'Tue, Feb 10' in IST."""
    now_ist = utc_now() + IST_OFFSET
    return now_ist.strftime("%a, %b %d")


def _format_msg(m: Message) -> dict:
    """Serialise a Message row for the frontend."""
    return {
        "id": m.message_id,
        "role": m.role,
        "content": m.content,
        "timestamp": m.timestamp.isoformat() + "Z" if m.timestamp else None,
        "tool_calls": m.tool_calls or [],
        "reasoning": m.reasoning,
    }


@router.post("/daily-thread")
async def get_or_create_daily_thread(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(_get_db),
):
    """Get or create today's cockpit daily thread.

    If a ``[Cockpit]`` conversation already exists for today (IST), it is
    returned with its messages.  If the message count exceeds
    ``COCKPIT_COMPACT_THRESHOLD``, the old thread is archived and a fresh
    thread is created with a summary of the archived messages plus the most
    recent messages copied over.
    """
    today_start = _ist_today_start_utc()
    today_label = _ist_today_label()

    # ── Find existing cockpit thread for today ──────────────────────────
    result = await db.execute(
        select(Conversation)
        .where(
            and_(
                Conversation.user_id == user.email,
                Conversation.title.like("[Cockpit]%"),
                Conversation.created_at >= today_start,
                Conversation.is_archived == False,  # noqa: E712
            )
        )
        .order_by(Conversation.created_at.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Load messages
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == existing.id)
            .order_by(Message.timestamp)
        )
        messages = msg_result.scalars().all()

        # ── Compaction check ────────────────────────────────────────────
        if len(messages) > COCKPIT_COMPACT_THRESHOLD:
            return await _compact_daily_thread(
                db, user, existing, messages, today_label
            )

        return {
            "threadId": existing.id,
            "messages": [_format_msg(m) for m in messages],
            "isNew": False,
            "compacted": False,
        }

    # ── Create new cockpit thread ───────────────────────────────────────
    thread_id = f"cockpit_{(utc_now() + IST_OFFSET).strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
    conv = Conversation(
        id=thread_id,
        user_id=user.email,
        title=f"[Cockpit] {today_label}",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(conv)
    await db.commit()

    logger.info(f"Created cockpit daily thread {thread_id} for {user.email}")

    return {
        "threadId": thread_id,
        "messages": [],
        "isNew": True,
        "compacted": False,
    }


async def _compact_daily_thread(
    db: AsyncSession,
    user: User,
    old_conv: Conversation,
    messages: list[Message],
    today_label: str,
) -> dict:
    """Archive the old thread, create a fresh one with a summary + recent messages."""
    logger.info(
        f"Compacting cockpit thread {old_conv.id} ({len(messages)} messages) for {user.email}"
    )

    # ── 1. Build summary of old messages ────────────────────────────────
    old_messages = messages[: -COCKPIT_KEEP_RECENT]
    recent_messages = messages[-COCKPIT_KEEP_RECENT:]

    summary_parts = [
        f"**Cockpit session compacted** — {len(old_messages)} earlier messages archived.",
        "",
        "Key topics discussed:",
    ]

    # Extract user messages for topic summary
    user_msgs = [m for m in old_messages if m.role == "user"]
    for m in user_msgs[-10:]:  # last 10 user messages from the archived portion
        snippet = m.content[:80].replace("\n", " ")
        summary_parts.append(f"- {snippet}")

    summary_text = "\n".join(summary_parts)

    # ── 2. Archive old thread ───────────────────────────────────────────
    old_conv.title = f"[Cockpit-Archive] {today_label}"
    old_conv.is_archived = True
    old_conv.updated_at = utc_now()

    # ── 3. Create new thread ────────────────────────────────────────────
    new_thread_id = f"cockpit_{(utc_now() + IST_OFFSET).strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
    new_conv = Conversation(
        id=new_thread_id,
        user_id=user.email,
        title=f"[Cockpit] {today_label}",
        forked_from_id=old_conv.id,
        fork_summary=summary_text,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(new_conv)

    # ── 4. Add summary as first system message ──────────────────────────
    summary_msg = Message(
        conversation_id=new_thread_id,
        message_id=f"msg_{uuid.uuid4().hex[:12]}",
        role="system",
        content=summary_text,
        timestamp=utc_now(),
    )
    db.add(summary_msg)

    # ── 5. Copy recent messages to new thread ───────────────────────────
    new_messages_out = [_format_msg(summary_msg)]
    for m in recent_messages:
        new_msg = Message(
            conversation_id=new_thread_id,
            message_id=f"msg_{uuid.uuid4().hex[:12]}",
            role=m.role,
            content=m.content,
            timestamp=m.timestamp,
            tool_calls=m.tool_calls,
            reasoning=m.reasoning,
        )
        db.add(new_msg)
        new_messages_out.append(_format_msg(new_msg))

    await db.commit()

    logger.info(
        f"Compacted: archived {old_conv.id}, new thread {new_thread_id} "
        f"({len(new_messages_out)} messages including summary)"
    )

    return {
        "threadId": new_thread_id,
        "messages": new_messages_out,
        "isNew": False,
        "compacted": True,
    }


# ---------------------------------------------------------------------------
# POST /invalidate-client  — Clear cached Upstox client after mode switch
# ---------------------------------------------------------------------------
@router.post("/invalidate-client")
async def invalidate_client(user: User = Depends(get_current_user)):
    """Clear cached Upstox client for the current user.

    Call this after switching trading mode so the next cockpit request
    picks up the correct client (paper vs live).
    """
    invalidate_client_cache(user.id)
    logger.info(f"Invalidated cockpit client cache for user {user.id}")
    return {"status": "ok"}
