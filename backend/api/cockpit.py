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
    Trade, WatchlistItem as WatchlistItemDB,
    Conversation, Message, utc_now,
)
from services.upstox_client import UpstoxClient
from services.instruments_cache import get_company_name as cache_get_company_name
from utils.market_status import get_market_status
from api.upstox_oauth import get_user_upstox_token

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
    """Resolve the Upstox client for a user.

    Uses get_user_upstox_token() which handles decryption + expiry check +
    TOTP auto-refresh.  Caches the live client so the dynamic symbol map
    (populated by get_portfolio) persists across endpoints within a session.

    Raises HTTPException(401) if no valid token is available — this lets the
    frontend show a clear "connect Upstox" message instead of an infinite
    skeleton loader.
    """
    if _db_manager is None:
        return _get_upstox_client()

    # Return cached live client if we have one
    if user.id in _live_clients:
        return _live_clients[user.id]

    # Use the canonical token resolver (decrypt + expiry + TOTP refresh)
    access_token = await get_user_upstox_token(user.id)

    if access_token:
        logger.info(f"Cockpit: live client for user {user.id}")
        client = UpstoxClient(
            access_token=access_token,
            paper_trading=False,
            user_id=user.id,
        )
        _live_clients[user.id] = client
        return client

    # No valid token — try the shared default client as fallback
    logger.warning(f"Cockpit: no valid token for user {user.id}, using default client")
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
# GET /market-status
# ---------------------------------------------------------------------------
@router.get("/market-status")
async def cockpit_market_status(user: User = Depends(get_current_user)):
    """Return current NSE market status (Upstox API with IST-based fallback)."""
    upstox_status = None
    try:
        client = await _get_client_for_user(user)
        api_result = await client.get_market_status_api()
        if api_result:
            upstox_status = api_result.get("status")
            logger.debug(f"Upstox market status API: {upstox_status}")
    except Exception as e:
        logger.warning(f"Upstox market status API unavailable, using time-based: {e}")

    return get_market_status(upstox_api_status=upstox_status)


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
        # Evict cached client so next request gets a fresh one
        _live_clients.pop(user.id, None)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Trade cost estimation (Upstox standard rates)
# ---------------------------------------------------------------------------
def _estimate_charges(sell_value: float, buy_value: float, is_intraday: bool) -> dict:
    """Estimate trading charges using standard Upstox rate structure.

    Returns estimated total charges and breakdown for a round-trip trade.
    """
    turnover = buy_value + sell_value

    # Brokerage: flat Rs 30/order for intraday (Upstox Plus plan), Rs 0 for delivery
    brokerage = 60.0 if is_intraday else 0.0  # 2 legs (buy + sell)

    # STT: 0.025% on sell side (intraday), 0.1% on sell side (delivery)
    stt = sell_value * (0.00025 if is_intraday else 0.001)

    # Transaction charges (NSE): ~0.00345% of turnover
    txn_charges = turnover * 0.0000345

    # GST: 18% on (brokerage + transaction charges)
    gst = (brokerage + txn_charges) * 0.18

    # SEBI turnover fee: 0.0001% of turnover
    sebi = turnover * 0.000001

    # Stamp duty: 0.003% of buy value (intraday), 0.015% (delivery)
    stamp = buy_value * (0.00003 if is_intraday else 0.00015)

    total = brokerage + stt + txn_charges + gst + sebi + stamp
    cost_pct = (total / turnover * 100) if turnover > 0 else 0

    return {
        "total": round(total, 2),
        "costPct": round(cost_pct, 4),
        "brokerage": round(brokerage, 2),
        "stt": round(stt, 2),
        "gst": round(gst, 2),
        "stampDuty": round(stamp, 2),
        "other": round(txn_charges + sebi, 2),
    }


# ---------------------------------------------------------------------------
# GET /positions
# ---------------------------------------------------------------------------
@router.get("/positions")
async def cockpit_positions(user: User = Depends(get_current_user)):
    """Return positions and holdings with company names and estimated charges."""
    client = await _get_client_for_user(user)
    try:
        portfolio = await client.get_portfolio()
        company_map = UpstoxClient.SYMBOL_TO_COMPANY

        positions = []
        holdings = []

        for pos in portfolio.positions:
            company = company_map.get(pos.symbol) or cache_get_company_name(pos.symbol) or pos.symbol
            buy_val = pos.average_price * pos.quantity
            sell_val = pos.current_price * pos.quantity
            charges = _estimate_charges(sell_val, buy_val, is_intraday=False)
            holdings.append({
                "symbol": pos.symbol,
                "company": company,
                "qty": pos.quantity,
                "avgPrice": pos.average_price,
                "ltp": pos.current_price,
                "pnl": pos.pnl,
                "pnlPct": pos.pnl_percentage,
                "dayChange": pos.day_change,
                "dayChangePct": pos.day_change_percentage,
                "holdDays": None,
                "product": pos.product or "D",
                "charges": charges,
            })

        for pos in portfolio.intraday_positions:
            company = company_map.get(pos.symbol) or cache_get_company_name(pos.symbol) or pos.symbol
            buy_val = pos.average_price * abs(pos.quantity)
            sell_val = pos.current_price * abs(pos.quantity)
            charges = _estimate_charges(sell_val, buy_val, is_intraday=True)
            positions.append({
                "symbol": pos.symbol,
                "company": company,
                "qty": pos.quantity,
                "avgPrice": pos.average_price,
                "ltp": pos.current_price,
                "pnl": pos.pnl,
                "pnlPct": pos.pnl_percentage,
                "dayChange": pos.day_change,
                "dayChangePct": pos.day_change_percentage,
                "holdDays": None,
                "product": "I",
                "charges": charges,
            })

        # In paper mode, all positions are simulated (treat as intraday/positions)
        if client.paper_trading and not positions and holdings:
            positions = holdings
            holdings = []

        return {"positions": positions, "holdings": holdings}
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        _live_clients.pop(user.id, None)
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
            change = quote_data["net_change"]
            change_pct = quote_data["pct_change"]

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
async def cockpit_scorecard(user: User = Depends(get_current_user)):
    """Return today's trading scorecard from live Upstox trades."""
    try:
        client = await _get_client_for_user(user)
        trades = await client.get_trades_for_day()

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
                "totalBuyValue": 0,
                "totalSellValue": 0,
                "netPnl": 0,
            }

        total_buy = sum(
            t.get("average_price", 0) * t.get("quantity", 0)
            for t in trades if t.get("transaction_type") == "BUY"
        )
        total_sell = sum(
            t.get("average_price", 0) * t.get("quantity", 0)
            for t in trades if t.get("transaction_type") == "SELL"
        )

        # Group by symbol to compute per-symbol P&L from paired BUY/SELL trades
        from collections import defaultdict
        symbol_trades = defaultdict(lambda: {"buy_value": 0, "buy_qty": 0, "sell_value": 0, "sell_qty": 0})
        for t in trades:
            sym = t.get("symbol", "?")
            side = t.get("transaction_type", "")
            qty = t.get("quantity", 0)
            val = t.get("average_price", 0) * qty
            if side == "BUY":
                symbol_trades[sym]["buy_value"] += val
                symbol_trades[sym]["buy_qty"] += qty
            elif side == "SELL":
                symbol_trades[sym]["sell_value"] += val
                symbol_trades[sym]["sell_qty"] += qty

        # Compute P&L only for symbols with both buy and sell (round-trip trades)
        pnls = []
        for sym, data in symbol_trades.items():
            paired_qty = min(data["buy_qty"], data["sell_qty"])
            if paired_qty > 0:
                avg_buy = data["buy_value"] / data["buy_qty"] if data["buy_qty"] else 0
                avg_sell = data["sell_value"] / data["sell_qty"] if data["sell_qty"] else 0
                pnl = (avg_sell - avg_buy) * paired_qty
                pnls.append(pnl)

        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]
        won = len(winners)
        lost = len(losers)
        total_round_trips = won + lost + len([p for p in pnls if p == 0])

        avg_winner = sum(winners) / won if won else 0
        avg_loser = abs(sum(losers) / lost) if lost else 0
        biggest_win = max(winners, default=0)
        biggest_loss = abs(min(losers, default=0))
        total_wins = sum(winners)
        total_losses_val = abs(sum(losers))
        profit_factor = (total_wins / total_losses_val) if total_losses_val > 0 else 0

        # Streak from pnls list
        streak = 0
        streak_type = "neutral"
        for p in reversed(pnls):
            if streak == 0:
                streak_type = "win" if p > 0 else ("loss" if p < 0 else "neutral")
                streak = 1
            elif (streak_type == "win" and p > 0) or (streak_type == "loss" and p < 0):
                streak += 1
            else:
                break

        return {
            "trades": len(trades),
            "roundTrips": total_round_trips,
            "won": won,
            "lost": lost,
            "winRate": round(won / total_round_trips * 100, 1) if total_round_trips else 0,
            "avgWinner": round(avg_winner, 2),
            "avgLoser": round(avg_loser, 2),
            "biggestWin": round(biggest_win, 2),
            "biggestLoss": round(biggest_loss, 2),
            "profitFactor": round(profit_factor, 2),
            "streak": streak,
            "streakType": streak_type,
            "totalBuyValue": round(total_buy, 2),
            "totalSellValue": round(total_sell, 2),
            "netPnl": round(sum(pnls), 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing scorecard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /funds
# ---------------------------------------------------------------------------
@router.get("/funds")
async def cockpit_funds(user: User = Depends(get_current_user)):
    """Return funds and margin breakdown from Upstox."""
    client = await _get_client_for_user(user)
    try:
        funds = await client.get_funds_and_margin()
        return funds
    except Exception as e:
        logger.error(f"Error fetching funds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /trades
# ---------------------------------------------------------------------------
@router.get("/trades")
async def cockpit_trades(user: User = Depends(get_current_user)):
    """Return today's executed trades from Upstox."""
    client = await _get_client_for_user(user)
    try:
        trades = await client.get_trades_for_day()
        return {"trades": trades, "count": len(trades)}
    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
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
