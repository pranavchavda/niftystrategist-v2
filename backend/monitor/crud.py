"""CRUD operations for monitor rules and logs."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import MonitorRule as MonitorRuleDB, MonitorLog as MonitorLogDB, utc_now
from monitor.models import MonitorRule as MonitorRuleSchema


async def create_rule(
    session: AsyncSession,
    user_id: int,
    name: str,
    trigger_type: str,
    trigger_config: dict,
    action_type: str,
    action_config: dict,
    instrument_token: str | None = None,
    symbol: str | None = None,
    linked_trade_id: int | None = None,
    linked_order_id: str | None = None,
    max_fires: int | None = None,
    expires_at: datetime | None = None,
) -> MonitorRuleDB:
    """Create a new monitor rule."""
    rule = MonitorRuleDB(
        user_id=user_id,
        name=name,
        enabled=True,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        action_type=action_type,
        action_config=action_config,
        instrument_token=instrument_token,
        symbol=symbol,
        linked_trade_id=linked_trade_id,
        linked_order_id=linked_order_id,
        max_fires=max_fires,
        expires_at=expires_at,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


async def list_rules(
    session: AsyncSession,
    user_id: int,
    enabled_only: bool = False,
) -> list[MonitorRuleDB]:
    """List rules for a user."""
    stmt = select(MonitorRuleDB).where(MonitorRuleDB.user_id == user_id)
    if enabled_only:
        stmt = stmt.where(MonitorRuleDB.enabled == True)  # noqa: E712
    stmt = stmt.order_by(MonitorRuleDB.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_rule(session: AsyncSession, rule_id: int) -> MonitorRuleDB | None:
    """Get a single rule by ID."""
    return await session.get(MonitorRuleDB, rule_id)


async def update_rule(session: AsyncSession, rule_id: int, **kwargs) -> MonitorRuleDB | None:
    """Update a rule's fields."""
    rule = await session.get(MonitorRuleDB, rule_id)
    if not rule:
        return None
    for key, value in kwargs.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    rule.updated_at = utc_now()
    await session.commit()
    await session.refresh(rule)
    return rule


async def enable_rule(session: AsyncSession, rule_id: int) -> MonitorRuleDB | None:
    """Enable a rule."""
    return await update_rule(session, rule_id, enabled=True)


async def disable_rule(session: AsyncSession, rule_id: int) -> MonitorRuleDB | None:
    """Disable a rule."""
    return await update_rule(session, rule_id, enabled=False)


async def delete_rule(session: AsyncSession, rule_id: int) -> bool:
    """Delete a rule. Returns True if deleted."""
    rule = await session.get(MonitorRuleDB, rule_id)
    if not rule:
        return False
    await session.delete(rule)
    await session.commit()
    return True


async def record_fire(
    session: AsyncSession,
    rule_id: int,
    user_id: int,
    trigger_snapshot: dict | None,
    action_taken: str,
    action_result: dict | None,
) -> MonitorLogDB:
    """Log a rule firing and update the rule's fire_count/fired_at."""
    log = MonitorLogDB(
        user_id=user_id,
        rule_id=rule_id,
        trigger_snapshot=trigger_snapshot,
        action_taken=action_taken,
        action_result=action_result,
    )
    session.add(log)

    # Update fire count on the rule
    rule = await session.get(MonitorRuleDB, rule_id)
    if rule:
        rule.fire_count = (rule.fire_count or 0) + 1
        rule.fired_at = utc_now()
        # Auto-disable if max fires reached
        if rule.max_fires is not None and rule.fire_count >= rule.max_fires:
            rule.enabled = False

    await session.commit()
    await session.refresh(log)
    return log


async def get_logs(
    session: AsyncSession,
    user_id: int,
    rule_id: int | None = None,
    limit: int = 20,
) -> list[MonitorLogDB]:
    """Get recent monitor logs."""
    stmt = select(MonitorLogDB).where(MonitorLogDB.user_id == user_id)
    if rule_id is not None:
        stmt = stmt.where(MonitorLogDB.rule_id == rule_id)
    stmt = stmt.order_by(MonitorLogDB.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_active_rules_for_daemon(session: AsyncSession) -> list[MonitorRuleDB]:
    """Get all enabled rules across all users (for the daemon to load)."""
    stmt = (
        select(MonitorRuleDB)
        .where(MonitorRuleDB.enabled == True)  # noqa: E712
        .order_by(MonitorRuleDB.user_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def db_rule_to_schema(db_rule: MonitorRuleDB) -> MonitorRuleSchema:
    """Convert a SQLAlchemy MonitorRule to the Pydantic MonitorRule schema."""
    return MonitorRuleSchema(
        id=db_rule.id,
        user_id=db_rule.user_id,
        name=db_rule.name,
        enabled=db_rule.enabled,
        trigger_type=db_rule.trigger_type,
        trigger_config=db_rule.trigger_config,
        action_type=db_rule.action_type,
        action_config=db_rule.action_config,
        instrument_token=db_rule.instrument_token,
        symbol=db_rule.symbol,
        linked_trade_id=db_rule.linked_trade_id,
        linked_order_id=db_rule.linked_order_id,
        fire_count=db_rule.fire_count or 0,
        max_fires=db_rule.max_fires,
        expires_at=db_rule.expires_at,
        fired_at=db_rule.fired_at,
    )
