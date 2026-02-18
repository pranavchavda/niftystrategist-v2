"""Monitor rules API — CRUD for IFTTT-style trade monitoring rules."""

import logging
from datetime import datetime
from typing import Optional


def _strip_tz(dt: Optional[datetime]) -> Optional[datetime]:
    """Strip timezone info to get a naive UTC datetime for the DB."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import User, get_current_user
from database.session import get_db_context
from services.instruments_cache import search_symbols, get_instrument_key
from monitor.crud import (
    create_rule, list_rules, get_rule, update_rule,
    enable_rule, disable_rule, delete_rule, get_logs,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class CreateRuleRequest(BaseModel):
    name: str
    trigger_type: str
    trigger_config: dict
    action_type: str
    action_config: dict
    symbol: Optional[str] = None
    instrument_token: Optional[str] = None
    linked_trade_id: Optional[int] = None
    linked_order_id: Optional[str] = None
    max_fires: Optional[int] = None
    expires_at: Optional[datetime] = None


class CreateOCORequest(BaseModel):
    symbol: str
    qty: int
    product: str = "I"
    sl: float
    target: float
    linked_trade_id: Optional[int] = None
    expires_at: Optional[datetime] = None


class UpdateRuleRequest(BaseModel):
    enabled: Optional[bool] = None
    name: Optional[str] = None
    trigger_config: Optional[dict] = None
    action_config: Optional[dict] = None
    max_fires: Optional[int] = None
    expires_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_rule(rule) -> dict:
    return {
        "id": rule.id,
        "user_id": rule.user_id,
        "name": rule.name,
        "enabled": rule.enabled,
        "trigger_type": rule.trigger_type,
        "trigger_config": rule.trigger_config,
        "action_type": rule.action_type,
        "action_config": rule.action_config,
        "symbol": rule.symbol,
        "instrument_token": rule.instrument_token,
        "linked_trade_id": rule.linked_trade_id,
        "linked_order_id": rule.linked_order_id,
        "fire_count": rule.fire_count or 0,
        "max_fires": rule.max_fires,
        "expires_at": rule.expires_at.isoformat() if rule.expires_at else None,
        "fired_at": rule.fired_at.isoformat() if rule.fired_at else None,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def _serialize_log(log) -> dict:
    return {
        "id": log.id,
        "rule_id": log.rule_id,
        "user_id": log.user_id,
        "trigger_snapshot": log.trigger_snapshot,
        "action_taken": log.action_taken,
        "action_result": log.action_result,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


# ---------------------------------------------------------------------------
# GET /symbols — search NSE symbols (for autocomplete)
# ---------------------------------------------------------------------------
@router.get("/symbols")
async def api_search_symbols(
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
):
    """Search NSE symbols by name or ticker for autocomplete."""
    results = search_symbols(q, limit=limit)
    for r in results:
        r["instrument_key"] = get_instrument_key(r["symbol"])
    return {"results": results}


# ---------------------------------------------------------------------------
# GET /rules — list user's rules
# ---------------------------------------------------------------------------
@router.get("/rules")
async def api_list_rules(
    active: Optional[bool] = Query(default=None, description="Filter enabled rules only"),
    user: User = Depends(get_current_user),
):
    """List the current user's monitor rules."""
    async with get_db_context() as session:
        rules = await list_rules(session, user.id, enabled_only=bool(active))
        return {"rules": [_serialize_rule(r) for r in rules]}


# ---------------------------------------------------------------------------
# POST /rules — create a single rule
# ---------------------------------------------------------------------------
@router.post("/rules")
async def api_create_rule(
    body: CreateRuleRequest,
    user: User = Depends(get_current_user),
):
    """Create a new monitor rule for the current user."""
    async with get_db_context() as session:
        rule = await create_rule(
            session=session,
            user_id=user.id,
            name=body.name,
            trigger_type=body.trigger_type,
            trigger_config=body.trigger_config,
            action_type=body.action_type,
            action_config=body.action_config,
            symbol=body.symbol,
            instrument_token=body.instrument_token,
            linked_trade_id=body.linked_trade_id,
            linked_order_id=body.linked_order_id,
            max_fires=body.max_fires,
            expires_at=_strip_tz(body.expires_at),
        )
        return _serialize_rule(rule)


# ---------------------------------------------------------------------------
# POST /oco — create OCO pair (stop-loss + target)
# ---------------------------------------------------------------------------
@router.post("/oco")
async def api_create_oco(
    body: CreateOCORequest,
    user: User = Depends(get_current_user),
):
    """Create a stop-loss + target OCO pair (two linked rules)."""
    async with get_db_context() as session:
        # Step 1: Create the SL rule
        sl_rule = await create_rule(
            session=session,
            user_id=user.id,
            name=f"{body.symbol} OCO Stop-Loss @ {body.sl}",
            trigger_type="price",
            trigger_config={
                "condition": "lte",
                "price": body.sl,
                "reference": "ltp",
            },
            action_type="place_order",
            action_config={
                "symbol": body.symbol,
                "transaction_type": "SELL",
                "quantity": body.qty,
                "order_type": "MARKET",
                "product": body.product,
            },
            symbol=body.symbol,
            linked_trade_id=body.linked_trade_id,
            max_fires=1,
            expires_at=_strip_tz(body.expires_at),
        )

        # Step 2: Create the target rule (cancels SL rule on fire)
        target_rule = await create_rule(
            session=session,
            user_id=user.id,
            name=f"{body.symbol} OCO Target @ {body.target}",
            trigger_type="price",
            trigger_config={
                "condition": "gte",
                "price": body.target,
                "reference": "ltp",
            },
            action_type="place_order",
            action_config={
                "symbol": body.symbol,
                "transaction_type": "SELL",
                "quantity": body.qty,
                "order_type": "MARKET",
                "product": body.product,
                "also_cancel_rule": sl_rule.id,
            },
            symbol=body.symbol,
            linked_trade_id=body.linked_trade_id,
            max_fires=1,
            expires_at=_strip_tz(body.expires_at),
        )

        # Step 3: Update SL rule action to also cancel target rule
        sl_action = sl_rule.action_config.copy()
        sl_action["also_cancel_rule"] = target_rule.id
        sl_rule = await update_rule(session, sl_rule.id, action_config=sl_action)

        return {
            "sl_rule": _serialize_rule(sl_rule),
            "target_rule": _serialize_rule(target_rule),
        }


# ---------------------------------------------------------------------------
# PATCH /rules/{rule_id} — update a rule
# ---------------------------------------------------------------------------
@router.patch("/rules/{rule_id}")
async def api_update_rule(
    rule_id: int,
    body: UpdateRuleRequest,
    user: User = Depends(get_current_user),
):
    """Update a monitor rule. Only the rule's owner can update it."""
    async with get_db_context() as session:
        rule = await get_rule(session, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        if rule.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your rule")

        # Build kwargs from non-None fields
        updates = {}
        if body.enabled is not None:
            updates["enabled"] = body.enabled
        if body.name is not None:
            updates["name"] = body.name
        if body.trigger_config is not None:
            updates["trigger_config"] = body.trigger_config
        if body.action_config is not None:
            updates["action_config"] = body.action_config
        if body.max_fires is not None:
            updates["max_fires"] = body.max_fires
        if body.expires_at is not None:
            updates["expires_at"] = _strip_tz(body.expires_at)

        if not updates:
            return _serialize_rule(rule)

        updated = await update_rule(session, rule_id, **updates)
        return _serialize_rule(updated)


# ---------------------------------------------------------------------------
# DELETE /rules/{rule_id} — delete a rule
# ---------------------------------------------------------------------------
@router.delete("/rules/{rule_id}")
async def api_delete_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
):
    """Delete a monitor rule. Only the rule's owner can delete it."""
    async with get_db_context() as session:
        rule = await get_rule(session, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        if rule.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your rule")

        await delete_rule(session, rule_id)
        return {"deleted": rule_id}


# ---------------------------------------------------------------------------
# GET /logs — get firing history
# ---------------------------------------------------------------------------
@router.get("/logs")
async def api_get_logs(
    rule_id: Optional[int] = Query(default=None, description="Filter by rule ID"),
    limit: int = Query(default=20, ge=1, le=100, description="Max entries"),
    user: User = Depends(get_current_user),
):
    """Get monitor rule firing history for the current user."""
    async with get_db_context() as session:
        logs = await get_logs(session, user.id, rule_id=rule_id, limit=limit)
        return {"logs": [_serialize_log(l) for l in logs]}
