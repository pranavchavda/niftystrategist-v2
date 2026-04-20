"""Scalp session management API — CRUD for stateful options scalping sessions."""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import User, get_current_user
from database.session import get_db_context
from monitor import scalp_crud
from monitor.scalp_models import UNDERLYING_INSTRUMENT_MAP, ScalpState, SessionMode
from services.instruments_cache import get_instrument_key

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    name: str
    session_mode: str = "options_scalp"
    underlying: str
    expiry: str = ""              # Required for options modes
    lots: int = 1                 # Used by options modes
    quantity: Optional[int] = None  # Used by equity modes
    product: str = "I"
    indicator_timeframe: str = "1m"
    utbot_period: int = 10
    utbot_sensitivity: float = 1.0
    sl_points: Optional[float] = None
    target_points: Optional[float] = None
    trail_percent: Optional[float] = None
    trail_points: Optional[float] = None
    trail_arm_points: Optional[float] = None
    squareoff_time: str = "15:15"
    max_trades: int = 20
    cooldown_seconds: int = 60
    primary_indicator: Optional[str] = None
    primary_params: Optional[dict] = None
    confirm_indicator: Optional[str] = None
    confirm_params: Optional[dict] = None


class UpdateSessionRequest(BaseModel):
    name: Optional[str] = None
    session_mode: Optional[str] = None
    underlying: Optional[str] = None
    expiry: Optional[str] = None
    lots: Optional[int] = None
    quantity: Optional[int] = None
    product: Optional[str] = None
    indicator_timeframe: Optional[str] = None
    utbot_period: Optional[int] = None
    utbot_sensitivity: Optional[float] = None
    sl_points: Optional[float] = None
    target_points: Optional[float] = None
    trail_percent: Optional[float] = None
    trail_points: Optional[float] = None
    trail_arm_points: Optional[float] = None
    squareoff_time: Optional[str] = None
    max_trades: Optional[int] = None
    cooldown_seconds: Optional[int] = None
    enabled: Optional[bool] = None
    primary_indicator: Optional[str] = None
    primary_params: Optional[dict] = None
    confirm_indicator: Optional[str] = None
    confirm_params: Optional[dict] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso_utc(dt: datetime | None) -> str | None:
    """ISO-format a naive UTC datetime with an explicit +00:00 suffix so that
    browsers parse it as UTC instead of local time. All DB datetimes here are
    naive TIMESTAMP-without-time-zone storing UTC instants (see CLAUDE.md)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _serialize_session(row) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "name": row.name,
        "enabled": row.enabled,
        "session_mode": row.session_mode or "options_scalp",
        "underlying": row.underlying,
        "underlying_instrument_token": row.underlying_instrument_token,
        "expiry": row.expiry,
        "lots": row.lots,
        "quantity": row.quantity,
        "product": row.product,
        "indicator_timeframe": row.indicator_timeframe,
        "utbot_period": row.utbot_period,
        "utbot_sensitivity": row.utbot_sensitivity,
        "primary_indicator": row.primary_indicator or "utbot",
        "primary_params": row.primary_params,
        "confirm_indicator": row.confirm_indicator,
        "confirm_params": row.confirm_params,
        "sl_points": row.sl_points,
        "target_points": row.target_points,
        "trail_percent": row.trail_percent,
        "trail_points": row.trail_points,
        "trail_arm_points": row.trail_arm_points,
        "pending_action": row.pending_action,
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
        "entry_time": _iso_utc(row.entry_time),
        "highest_premium": row.highest_premium,
        "trade_count": row.trade_count or 0,
        "last_exit_time": _iso_utc(row.last_exit_time),
        "created_at": _iso_utc(row.created_at),
        "updated_at": _iso_utc(row.updated_at),
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
        "created_at": _iso_utc(log.created_at),
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
    """Create a new scalp session for the current user.

    Resolves underlying_instrument_token differently per mode:
    - options_scalp: looks up the index token in UNDERLYING_INSTRUMENT_MAP
    - equity_intraday/equity_swing: resolves the equity symbol via the
      instruments cache (NSE_EQ|...).
    """
    valid_modes = {m.value for m in SessionMode}
    if body.session_mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown session_mode '{body.session_mode}'. Valid: {', '.join(sorted(valid_modes))}",
        )

    underlying_upper = body.underlying.upper()
    if body.session_mode == SessionMode.OPTIONS_SCALP.value:
        if underlying_upper not in UNDERLYING_INSTRUMENT_MAP:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown underlying '{body.underlying}' for options_scalp. "
                       f"Valid: {', '.join(sorted(UNDERLYING_INSTRUMENT_MAP.keys()))}",
            )
        underlying_instrument_token = UNDERLYING_INSTRUMENT_MAP[underlying_upper]
        if not body.expiry:
            raise HTTPException(status_code=400, detail="expiry is required for options_scalp")
    else:
        # Equity modes: resolve the symbol via instruments cache.
        instrument_key = get_instrument_key(underlying_upper)
        if not instrument_key:
            raise HTTPException(
                status_code=400,
                detail=f"Equity symbol '{body.underlying}' not found in instruments cache",
            )
        underlying_instrument_token = instrument_key
        if not body.quantity or body.quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="quantity (>0) is required for equity modes",
            )

    async with get_db_context() as session:
        row = await scalp_crud.create_session(
            db=session,
            user_id=user.id,
            name=body.name,
            session_mode=body.session_mode,
            underlying=underlying_upper,
            underlying_instrument_token=underlying_instrument_token,
            expiry=body.expiry,
            lots=body.lots,
            quantity=body.quantity,
            product=body.product,
            indicator_timeframe=body.indicator_timeframe,
            utbot_period=body.utbot_period,
            utbot_sensitivity=body.utbot_sensitivity,
            primary_indicator=body.primary_indicator or "utbot",
            primary_params=(
                body.primary_params
                if body.primary_params
                else (
                    {"period": body.utbot_period, "sensitivity": body.utbot_sensitivity}
                    if (body.primary_indicator or "utbot") == "utbot"
                    else None
                )
            ),
            confirm_indicator=body.confirm_indicator,
            confirm_params=body.confirm_params,
            sl_points=body.sl_points,
            target_points=body.target_points,
            trail_percent=body.trail_percent,
            trail_points=body.trail_points,
            trail_arm_points=body.trail_arm_points,
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
            if body.enabled is False and row.state != ScalpState.IDLE.value:
                # HOLDING session — daemon must exit before disable takes effect.
                # Keep enabled=true so daemon still sees it; flag the exit.
                await scalp_crud.set_pending_action(
                    session, session_id, "exit_and_disable",
                )
                await session.refresh(row)
                logger.info(
                    "Session %d: disable requested while HOLDING (%s) — "
                    "scheduled exit_and_disable",
                    session_id, row.state,
                )
            else:
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
        if body.quantity is not None:
            updates["quantity"] = body.quantity
        if body.session_mode is not None:
            updates["session_mode"] = body.session_mode
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
        if body.trail_points is not None:
            updates["trail_points"] = body.trail_points
        if body.trail_arm_points is not None:
            updates["trail_arm_points"] = body.trail_arm_points
        if body.squareoff_time is not None:
            updates["squareoff_time"] = body.squareoff_time
        if body.max_trades is not None:
            updates["max_trades"] = body.max_trades
        if body.cooldown_seconds is not None:
            updates["cooldown_seconds"] = body.cooldown_seconds
        if body.primary_indicator is not None:
            updates["primary_indicator"] = body.primary_indicator
        if body.primary_params is not None:
            updates["primary_params"] = body.primary_params
        if body.confirm_indicator is not None:
            # Empty string clears the confirm filter; null does too.
            updates["confirm_indicator"] = body.confirm_indicator or None
        if body.confirm_params is not None:
            updates["confirm_params"] = body.confirm_params

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
    """Delete a scalp session. Only the session owner can delete it.

    If the session is HOLDING a position, the delete is deferred: the
    daemon will exit first, then remove the row on the next poll cycle.
    """
    async with get_db_context() as session:
        row = await scalp_crud.get_session(session, session_id)
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        if row.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your session")

        if row.state != ScalpState.IDLE.value:
            await scalp_crud.set_pending_action(
                session, session_id, "exit_and_delete",
            )
            logger.info(
                "Session %d: delete requested while HOLDING (%s) — "
                "scheduled exit_and_delete",
                session_id, row.state,
            )
            return {"deleted": session_id, "status": "exit_pending"}

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
# GET /logs — event logs across all the user's sessions
# ---------------------------------------------------------------------------
@router.get("/logs")
async def api_get_user_logs(
    limit: int = Query(default=100, ge=1, le=500, description="Max log entries"),
    user: User = Depends(get_current_user),
):
    """Get event logs across all of the current user's scalp sessions."""
    async with get_db_context() as session:
        rows = await scalp_crud.list_sessions(session, user.id, enabled_only=False)
        name_map = {r.id: r.name for r in rows}
        logs = await scalp_crud.get_user_logs(session, user.id, limit=limit)
        out = []
        for l in logs:
            item = _serialize_log(l)
            item["session_id"] = l.session_id
            item["session_name"] = name_map.get(l.session_id, f"Session {l.session_id}")
            out.append(item)
        return {"logs": out}


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
    """Force-exit a scalp session. If HOLDING, the daemon places a real SELL
    on its next poll (exit_and_disable). If already IDLE, just disables."""
    async with get_db_context() as session:
        row = await scalp_crud.get_session(session, session_id)
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        if row.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your session")

        if row.state != ScalpState.IDLE.value:
            await scalp_crud.set_pending_action(
                session, session_id, "exit_and_disable",
            )
            await session.refresh(row)
            logger.info("Manual exit (HOLDING) for session %d — scheduled", session_id)
        else:
            await scalp_crud.update_session(session, session_id, enabled=False)
            await session.refresh(row)
            logger.info("Manual exit (IDLE) for session %d — disabled directly", session_id)
        return _serialize_session(row)
