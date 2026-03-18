"""Strategy templates API — list, deploy, manage pre-built trading strategies."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import User, get_current_user
from database.session import get_db_context
from services.instruments_cache import get_instrument_key
from strategies.templates import list_templates, get_template
from monitor.crud import create_rule, update_rule, list_rules, list_rules_by_group, delete_rules_by_group

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class DeployRequest(BaseModel):
    template: str
    symbol: str = ""
    params: dict = {}
    dry_run: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today_close_utc() -> datetime:
    """Return today's 15:30 IST as naive UTC (10:00 UTC)."""
    now = datetime.utcnow()
    close = now.replace(hour=10, minute=0, second=0, microsecond=0)
    if now > close:
        close += timedelta(days=1)
    return close


def _serialize_rule(rule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "enabled": rule.enabled,
        "trigger_type": rule.trigger_type,
        "trigger_config": rule.trigger_config,
        "action_type": rule.action_type,
        "action_config": rule.action_config,
        "symbol": rule.symbol,
        "instrument_token": rule.instrument_token,
        "fire_count": rule.fire_count or 0,
        "max_fires": rule.max_fires,
        "group_id": getattr(rule, "group_id", None),
        "strategy_name": getattr(rule, "strategy_name", None),
        "expires_at": rule.expires_at.isoformat() if rule.expires_at else None,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
    }


# ---------------------------------------------------------------------------
# GET /api/strategies/list — list available templates
# ---------------------------------------------------------------------------
@router.get("/list")
async def api_list_templates():
    """List all available strategy templates (public, no auth)."""
    return {"templates": list_templates()}


# ---------------------------------------------------------------------------
# POST /api/strategies/deploy — deploy a strategy
# ---------------------------------------------------------------------------
@router.post("/deploy")
async def api_deploy_strategy(
    body: DeployRequest,
    user: User = Depends(get_current_user),
):
    """Deploy a strategy template as monitor rules."""
    template = get_template(body.template)
    if not template:
        names = [t["name"] for t in list_templates()]
        raise HTTPException(
            status_code=400,
            detail=f"Unknown template: {body.template}. Available: {', '.join(names)}",
        )

    is_fno = getattr(template, "category", "equity") == "fno"

    # Coerce numeric-looking param values (frontend sends strings from inputs)
    coerced_params = {}
    for k, v in body.params.items():
        if isinstance(v, str) and v.replace(".", "", 1).replace("-", "", 1).isdigit():
            try:
                coerced_params[k] = int(v) if "." not in v else float(v)
            except ValueError:
                coerced_params[k] = v
        else:
            coerced_params[k] = v
    body.params = coerced_params

    # Extract symbol from body or params
    symbol = body.symbol or body.params.get("symbol") or body.params.get("underlying", "")

    # Resolve instrument_token for equity templates
    instrument_token = None
    if not is_fno:
        instrument_token = get_instrument_key(symbol)
        if not instrument_token:
            raise HTTPException(
                status_code=400,
                detail=f"Could not resolve instrument key for {body.symbol}",
            )

    # Generate the plan
    try:
        plan = template.plan(symbol, body.params)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Dry run — return plan preview
    if body.dry_run:
        rules_preview = []
        for spec in plan.rules:
            rules_preview.append({
                "name": spec.name,
                "role": spec.role,
                "trigger_type": spec.trigger_type,
                "trigger_config": spec.trigger_config,
                "action_type": spec.action_type,
                "action_config": spec.action_config,
                "max_fires": spec.max_fires,
                "expires": spec.expires,
            })
        return {
            "dry_run": True,
            "template": plan.template_name,
            "symbol": plan.symbol,
            "group_id": plan.group_id,
            "summary": plan.summary,
            "rules_count": len(plan.rules),
            "rules": rules_preview,
        }

    # Deploy — create all rules
    expires_at = _today_close_utc()
    created_rules = []

    async with get_db_context() as session:
        for spec in plan.rules:
            # For F&O, each rule may have its own instrument_token in action_config
            rule_instrument_token = instrument_token
            if is_fno:
                rule_instrument_token = spec.action_config.get("instrument_token")

            rule = await create_rule(
                session=session,
                user_id=user.id,
                name=spec.name,
                trigger_type=spec.trigger_type,
                trigger_config=spec.trigger_config,
                action_type=spec.action_type,
                action_config=spec.action_config,
                instrument_token=rule_instrument_token,
                symbol=symbol,
                max_fires=spec.max_fires,
                expires_at=expires_at,
                group_id=plan.group_id,
                strategy_name=plan.template_name,
                enabled=spec.enabled,
                role=spec.role,
            )
            created_rules.append(rule)

        # Wire kill chains (also_cancel_rules) and activate chains
        # (also_enable_rules) by resolving role names → rule IDs.
        role_to_id = {}
        for spec, rule in zip(plan.rules, created_rules):
            if spec.role:
                role_to_id[spec.role] = rule.id

        for spec, rule in zip(plan.rules, created_rules):
            updates = {}
            if spec.kills_roles:
                cancel_ids = [role_to_id[r] for r in spec.kills_roles if r in role_to_id]
                if cancel_ids:
                    updates["also_cancel_rules"] = cancel_ids
            if spec.activates_roles:
                enable_ids = [role_to_id[r] for r in spec.activates_roles if r in role_to_id]
                if enable_ids:
                    updates["also_enable_rules"] = enable_ids
            if updates:
                merged = dict(rule.action_config or {})
                merged.update(updates)
                await update_rule(session, rule.id, action_config=merged)
                rule.action_config = merged

    return {
        "deployed": True,
        "template": plan.template_name,
        "symbol": plan.symbol,
        "group_id": plan.group_id,
        "summary": plan.summary,
        "rules_count": len(created_rules),
        "rules": [_serialize_rule(r) for r in created_rules],
    }


# ---------------------------------------------------------------------------
# GET /api/strategies/active — list active strategy groups
# ---------------------------------------------------------------------------
@router.get("/active")
async def api_active_strategies(
    user: User = Depends(get_current_user),
):
    """List deployed strategy groups for the current user."""
    async with get_db_context() as session:
        all_rules = await list_rules(session, user.id)

    # Group by group_id where strategy_name is set
    groups: dict[str, list] = {}
    for r in all_rules:
        gid = getattr(r, "group_id", None)
        sname = getattr(r, "strategy_name", None)
        if gid and sname:
            groups.setdefault(gid, []).append(r)

    strategies = []
    for gid, rules in groups.items():
        strategies.append({
            "group_id": gid,
            "template_name": getattr(rules[0], "strategy_name", None),
            "symbol": rules[0].symbol,
            "rules_count": len(rules),
            "active_count": sum(1 for r in rules if r.enabled),
            "total_fires": sum(r.fire_count or 0 for r in rules),
            "rules": [_serialize_rule(r) for r in rules],
        })

    return {"strategies": strategies}


# ---------------------------------------------------------------------------
# DELETE /api/strategies/{group_id} — tear down a strategy
# ---------------------------------------------------------------------------
@router.delete("/{group_id}")
async def api_delete_strategy(
    group_id: str,
    user: User = Depends(get_current_user),
):
    """Delete all rules belonging to a strategy group."""
    async with get_db_context() as session:
        count = await delete_rules_by_group(session, user.id, group_id)

    if count == 0:
        raise HTTPException(status_code=404, detail=f"No rules found for group {group_id}")

    return {"deleted": count, "group_id": group_id}
