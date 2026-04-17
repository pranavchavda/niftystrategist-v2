"""DB CRUD operations for scalp sessions and logs."""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import ScalpSessionDB, ScalpSessionLogDB, utc_now
from monitor.scalp_models import ScalpSession, ScalpSessionConfig, ScalpSessionRuntime, ScalpState

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────


def db_to_session(row: ScalpSessionDB) -> ScalpSession:
    """Convert a DB row to an in-memory ScalpSession."""
    config = ScalpSessionConfig(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        enabled=row.enabled,
        underlying=row.underlying,
        underlying_instrument_token=row.underlying_instrument_token,
        expiry=row.expiry,
        lots=row.lots,
        product=row.product,
        indicator_timeframe=row.indicator_timeframe,
        utbot_period=row.utbot_period,
        utbot_sensitivity=row.utbot_sensitivity,
        sl_points=row.sl_points,
        target_points=row.target_points,
        trail_percent=row.trail_percent,
        squareoff_time=row.squareoff_time,
        max_trades=row.max_trades,
        cooldown_seconds=row.cooldown_seconds,
    )
    runtime = ScalpSessionRuntime(
        state=ScalpState(row.state) if row.state else ScalpState.IDLE,
        current_option_type=row.current_option_type,
        current_strike=row.current_strike,
        current_instrument_token=row.current_instrument_token,
        current_tradingsymbol=row.current_tradingsymbol,
        entry_price=row.entry_price,
        entry_time=row.entry_time,
        highest_premium=row.highest_premium,
        trade_count=row.trade_count or 0,
        last_exit_time=row.last_exit_time,
    )
    return ScalpSession(config=config, runtime=runtime)


# ── Session CRUD ─────────────────────────────────────────────────────


async def create_session(
    db: AsyncSession,
    user_id: int,
    name: str,
    underlying: str,
    underlying_instrument_token: str,
    expiry: str,
    **kwargs,
) -> ScalpSessionDB:
    """Create a new scalp session."""
    row = ScalpSessionDB(
        user_id=user_id,
        name=name,
        underlying=underlying,
        underlying_instrument_token=underlying_instrument_token,
        expiry=expiry,
        **kwargs,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_session(db: AsyncSession, session_id: int) -> ScalpSessionDB | None:
    result = await db.execute(
        select(ScalpSessionDB).where(ScalpSessionDB.id == session_id)
    )
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession,
    user_id: int,
    enabled_only: bool = False,
) -> list[ScalpSessionDB]:
    q = select(ScalpSessionDB).where(ScalpSessionDB.user_id == user_id)
    if enabled_only:
        q = q.where(ScalpSessionDB.enabled == True)
    q = q.order_by(ScalpSessionDB.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_enabled_sessions(db: AsyncSession) -> list[ScalpSessionDB]:
    """Load all enabled sessions across all users (for daemon poll)."""
    result = await db.execute(
        select(ScalpSessionDB).where(ScalpSessionDB.enabled == True)
    )
    return list(result.scalars().all())


async def update_session(
    db: AsyncSession,
    session_id: int,
    **kwargs,
) -> ScalpSessionDB | None:
    row = await get_session(db, session_id)
    if not row:
        return None
    for key, val in kwargs.items():
        if hasattr(row, key):
            setattr(row, key, val)
    await db.commit()
    await db.refresh(row)
    return row


async def delete_session(db: AsyncSession, session_id: int) -> bool:
    row = await get_session(db, session_id)
    if not row:
        return False
    await db.delete(row)
    await db.commit()
    return True


async def persist_session_state(
    db: AsyncSession,
    session_id: int,
    runtime: ScalpSessionRuntime,
) -> None:
    """Persist runtime state to DB for crash recovery."""
    row = await get_session(db, session_id)
    if not row:
        return
    row.state = runtime.state.value
    row.current_option_type = runtime.current_option_type
    row.current_strike = runtime.current_strike
    row.current_instrument_token = runtime.current_instrument_token
    row.current_tradingsymbol = runtime.current_tradingsymbol
    row.entry_price = runtime.entry_price
    row.entry_time = runtime.entry_time
    row.highest_premium = runtime.highest_premium
    row.trade_count = runtime.trade_count
    row.last_exit_time = runtime.last_exit_time
    await db.commit()


# ── Session Logs ─────────────────────────────────────────────────────


async def log_event(
    db: AsyncSession,
    session_id: int,
    user_id: int,
    event_type: str,
    *,
    option_type: str | None = None,
    strike: float | None = None,
    instrument_token: str | None = None,
    entry_price: float | None = None,
    exit_price: float | None = None,
    quantity: int | None = None,
    pnl_points: float | None = None,
    pnl_amount: float | None = None,
    order_id: str | None = None,
    underlying_price: float | None = None,
    trigger_snapshot: dict | None = None,
) -> ScalpSessionLogDB:
    row = ScalpSessionLogDB(
        session_id=session_id,
        user_id=user_id,
        event_type=event_type,
        option_type=option_type,
        strike=strike,
        instrument_token=instrument_token,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        pnl_points=pnl_points,
        pnl_amount=pnl_amount,
        order_id=order_id,
        underlying_price=underlying_price,
        trigger_snapshot=trigger_snapshot,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def backfill_entry_price(
    db: AsyncSession,
    session_id: int,
    entry_price: float,
) -> int | None:
    """Set entry_price on the most recent entry_* log row for this session
    that still has a NULL entry_price. Returns the log id updated, or None.

    Entries log BEFORE the fill arrives, so entry_price is not yet known.
    The first premium tick establishes it and we patch the log row so P&L
    analysis later can pair entry with exit cleanly.
    """
    result = await db.execute(
        select(ScalpSessionLogDB)
        .where(ScalpSessionLogDB.session_id == session_id)
        .where(ScalpSessionLogDB.event_type.in_(["entry_ce", "entry_pe"]))
        .where(ScalpSessionLogDB.entry_price.is_(None))
        .order_by(ScalpSessionLogDB.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    row.entry_price = entry_price
    await db.commit()
    return row.id


async def get_session_logs(
    db: AsyncSession,
    session_id: int,
    limit: int = 50,
) -> list[ScalpSessionLogDB]:
    result = await db.execute(
        select(ScalpSessionLogDB)
        .where(ScalpSessionLogDB.session_id == session_id)
        .order_by(ScalpSessionLogDB.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_user_logs(
    db: AsyncSession,
    user_id: int,
    limit: int = 50,
) -> list[ScalpSessionLogDB]:
    result = await db.execute(
        select(ScalpSessionLogDB)
        .where(ScalpSessionLogDB.user_id == user_id)
        .order_by(ScalpSessionLogDB.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_session_pnl_summary(
    db: AsyncSession,
    session_id: int,
) -> dict:
    """Aggregate P&L from exit events."""
    exit_events = ["exit_sl", "exit_target", "exit_trail", "exit_reversal", "exit_squareoff"]
    result = await db.execute(
        select(
            func.count(ScalpSessionLogDB.id).label("total_exits"),
            func.sum(ScalpSessionLogDB.pnl_amount).label("total_pnl"),
            func.count(
                func.nullif(ScalpSessionLogDB.pnl_amount > 0, False)
            ).label("wins"),
            func.count(
                func.nullif(ScalpSessionLogDB.pnl_amount < 0, False)
            ).label("losses"),
        )
        .where(ScalpSessionLogDB.session_id == session_id)
        .where(ScalpSessionLogDB.event_type.in_(exit_events))
    )
    row = result.one()
    return {
        "total_exits": row.total_exits or 0,
        "total_pnl": float(row.total_pnl or 0),
        "wins": row.wins or 0,
        "losses": row.losses or 0,
    }
