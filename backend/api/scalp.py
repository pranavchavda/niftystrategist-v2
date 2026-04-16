"""Scalp session management API — CRUD for stateful options scalping sessions."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import User, get_current_user
from database.session import get_db_context
from monitor import scalp_crud
from monitor.scalp_models import UNDERLYING_INSTRUMENT_MAP, ScalpState

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    name: str
    underlying: str
    expiry: str
    lots: int = 1
    product: str = "I"
    indicator_timeframe: str = "1m"
    utbot_period: int = 10
    utbot_sensitivity: float = 1.0
    sl_points: Optional[float] = None
    target_points: Optional[float] = None
    trail_percent: Optional[float] = None
    squareoff_time: str = "15:15"
    max_trades: int = 20
    cooldown_seconds: int = 60


class UpdateSessionRequest(BaseModel):
    name: Optional[str] = None
    underlying: Optional[str] = None
    expiry: Optional[str] = None
    lots: Optional[int] = None
    product: Optional[str] = None
    indicator_timeframe: Optional[str] = None
    utbot_period: Optional[int] = None
    utbot_sensitivity: Optional[float] = None
    sl_points: Optional[float] = None
    target_points: Optional[float] = None
    trail_percent: Optional[float] = None
    squareoff_time: Optional[str] = None
    max_trades: Optional[int] = None
    cooldown_seconds: Optional[int] = None
    enabled: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_session(row) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "name": row.name,
        "enabled": row.enabled,
        "underlying": row.underlying,
        "underlying_instrument_token": row.underlying_instrument_token,
        "expiry": row.expiry,
        "lots": row.lots,
        "product": row.product,
        "indicator_timeframe": row.indicator_timeframe,
        "utbot_period": row.utbot_period,
        "utbot_sensitivity": row.utbot_sensitivity,
        "sl_points": row.sl_points,
        "target_points": row.target_points,
        "trail_percent": row.trail_percent,
        "squareoff_time": row.squareoff_time,
        "max_trades": row.max_trades,
        "cooldown_seconds": row.cooldown_seconds,
        # Runtime state
        "state": row.state,
        "current_option_type": row.current_option_type,
        "current_strike": row.current_strike,
        "current_instrument_token": row.current_instrument_token,
        "current_tradingsymbol": row.current_tradingsymbol,
        "entry_price": row.entry_price,
        "entry_time": row.entry_time.isoformat() if row.entry_time else None,
        "highest_premium": row.highest_premium,
        "trade_count": row.trade_count or 0,
        "last_exit_time": row.last_exit_time.isoformat() if row.last_exit_time else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_log(log) -> dict:
    return {
        "id": log.id,
        "event_type": log.event_type,
        "option_type": log.option_type,
        "strike": log.strike,
        "entry_price": log.entry_price,
        "exit_price": log.exit_price,
        "quantity": log.quantity,
        "pnl_points": log.pnl_points,
        "pnl_amount": log.pnl_amount,
        "order_id": log.order_id,
        "underlying_price": log.underlying_price,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


# ---------------------------------------------------------------------------
# GET /sessions — list user's scalp sessions
# ---------------------------------------------------------------------------
@router.get("/sessions")
async def api_list_sessions(
    active: Optional[bool] = Query(default=None, description="Filter enabled sessions only"),
    user: User = Depends(get_current_user),
):
    """List the current user's scalp sessions."""
    async with get_db_context() as session:
        rows = await scalp_crud.list_sessions(session, user.id, enabled_only=bool(active))
        return {"sessions": [_serialize_session(r) for r in rows]}


# ---------------------------------------------------------------------------
# POST /sessions — create a scalp session
# ---------------------------------------------------------------------------
@router.post("/sessions")
async def api_create_session(
    body: CreateSessionRequest,
    user: User = Depends(get_current_user),
):
    """Create a new scalp session for the current user."""
    underlying_upper = body.underlying.upper()
    if underlying_upper not in UNDERLYING_INSTRUMENT_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown underlying '{body.underlying}'. Valid: {', '.join(sorted(set(UNDERLYING_INSTRUMENT_MAP.values()), key=str))}",
        )
    underlying_instrument_token = UNDERLYING_INSTRUMENT_MAP[underlying_upper]

    async with get_db_context() as session:
        row = await scalp_crud.create_session(
            db=session,
            user_id=user.id,
            name=body.name,
            underlying=underlying_upper,
            underlying_instrument_token=underlying_instrument_token,
            expiry=body.expiry,
            lots=body.lots,
            product=body.product,
            indicator_timeframe=body.indicator_timeframe,
            utbot_period=body.utbot_period,
            utbot_sensitivity=body.utbot_sensitivity,
            sl_points=body.sl_points,
            target_points=body.target_points,
            trail_percent=body.trail_percent,
            squareoff_time=body.squareoff_time,
            max_trades=body.max_trades,
            cooldown_seconds=body.cooldown_seconds,
        )
        return _serialize_session(row)


# ---------------------------------------------------------------------------
# GET /sessions/{session_id} — session detail
# ---------------------------------------------------------------------------
@router.get("/sessions/{session_id}")
async def api_get_session(
    session_id: int,
    user: User = Depends(get_current_user),
):
    """Get a single scalp session with current state."""
    async with get_db_context() as session:
        row = await scalp_crud.get_session(session, session_id)
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        if row.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your session")
        return _serialize_session(row)


# ---------------------------------------------------------------------------
# PATCH /sessions/{session_id} — update config or toggle enabled
# ---------------------------------------------------------------------------
@router.patch("/sessions/{session_id}")
async def api_update_session(
    session_id: int,
    body: UpdateSessionRequest,
    user: User = Depends(get_current_user),
):
    """Update a scalp session's config fields. Cannot update runtime state."""
    async with get_db_context() as session:
        row = await scalp_crud.get_session(session, session_id)
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        if row.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your session")

        updates = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.enabled is not None:
            updates["enabled"] = body.enabled
        if body.underlying is not None:
            upper = body.underlying.upper()
            if upper not in UNDERLYING_INSTRUMENT_MAP:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown underlying '{body.underlying}'. Valid: {', '.join(sorted(set(UNDERLYING_INSTRUMENT_MAP.values()), key=str))}",
                )
            updates["underlying"] = upper
            updates["underlying_instrument_token"] = UNDERLYING_INSTRUMENT_MAP[upper]
        if body.expiry is not None:
            updates["expiry"] = body.expiry
        if body.lots is not None:
            updates["lots"] = body.lots
        if body.product is not None:
            updates["product"] = body.product
        if body.indicator_timeframe is not None:
            updates["indicator_timeframe"] = body.indicator_timeframe
        if body.utbot_period is not None:
            updates["utbot_period"] = body.utbot_period
        if body.utbot_sensitivity is not None:
            updates["utbot_sensitivity"] = body.utbot_sensitivity
        if body.sl_points is not None:
            updates["sl_points"] = body.sl_points
        if body.target_points is not None:
            updates["target_points"] = body.target_points
        if body.trail_percent is not None:
            updates["trail_percent"] = body.trail_percent
        if body.squareoff_time is not None:
            updates["squareoff_time"] = body.squareoff_time
        if body.max_trades is not None:
            updates["max_trades"] = body.max_trades
        if body.cooldown_seconds is not None:
            updates["cooldown_seconds"] = body.cooldown_seconds

        if not updates:
            return _serialize_session(row)

        updated = await scalp_crud.update_session(session, session_id, **updates)
        return _serialize_session(updated)


# ---------------------------------------------------------------------------
# DELETE /sessions/{session_id} — delete a session
# ---------------------------------------------------------------------------
@router.delete("/sessions/{session_id}")
async def api_delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
):
    """Delete a scalp session. Only the session owner can delete it."""
    async with get_db_context() as session:
        row = await scalp_crud.get_session(session, session_id)
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        if row.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your session")

        await scalp_crud.delete_session(session, session_id)
        return {"deleted": session_id}


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/logs — event logs for a session
# ---------------------------------------------------------------------------
@router.get("/sessions/{session_id}/logs")
async def api_get_session_logs(
    session_id: int,
    limit: int = Query(default=50, ge=1, le=500, description="Max log entries"),
    user: User = Depends(get_current_user),
):
    """Get event logs for a scalp session."""
    async with get_db_context() as session:
        row = await scalp_crud.get_session(session, session_id)
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        if row.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your session")

        logs = await scalp_crud.get_session_logs(session, session_id, limit=limit)
        return {"logs": [_serialize_log(l) for l in logs]}


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/pnl — P&L summary
# ---------------------------------------------------------------------------
@router.get("/sessions/{session_id}/pnl")
async def api_get_session_pnl(
    session_id: int,
    user: User = Depends(get_current_user),
):
    """Get aggregated P&L summary for a scalp session."""
    async with get_db_context() as session:
        row = await scalp_crud.get_session(session, session_id)
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        if row.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your session")

        pnl = await scalp_crud.get_session_pnl_summary(session, session_id)
        return pnl


# ---------------------------------------------------------------------------
# POST /sessions/{session_id}/manual-exit — force exit
# ---------------------------------------------------------------------------
@router.post("/sessions/{session_id}/manual-exit")
async def api_manual_exit(
    session_id: int,
    user: User = Depends(get_current_user),
):
    """Force-exit a scalp session by setting enabled=False and state=IDLE.

    The daemon will pick up the state change on its next poll.
    For the actual broker-side exit, use nf-options sell.
    """
    async with get_db_context() as session:
        row = await scalp_crud.get_session(session, session_id)
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        if row.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your session")

        updated = await scalp_crud.update_session(
            session,
            session_id,
            enabled=False,
            state=ScalpState.IDLE.value,
        )
        logger.info("Manual exit for session %d (user %d)", session_id, user.id)
        return _serialize_session(updated)
