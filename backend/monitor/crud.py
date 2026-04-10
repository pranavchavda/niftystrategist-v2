"""CRUD operations for monitor rules and logs."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_, select, update, delete
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
    group_id: str | None = None,
    strategy_name: str | None = None,
    enabled: bool = True,
    role: str | None = None,
) -> MonitorRuleDB:
    """Create a new monitor rule."""
    rule = MonitorRuleDB(
        user_id=user_id,
        name=name,
        enabled=enabled,
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
        group_id=group_id,
        strategy_name=strategy_name,
        role=role,
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
    """Log a rule firing to MonitorLog.

    Does NOT update rule state (fire_count, enabled) — the daemon owns
    that in-memory and persists it via sync_rule_fire_state().
    """
    log = MonitorLogDB(
        user_id=user_id,
        rule_id=rule_id,
        trigger_snapshot=trigger_snapshot,
        action_taken=action_taken,
        action_result=action_result,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def sync_rule_fire_state(
    session: AsyncSession,
    rule_id: int,
    fire_count: int,
    enabled: bool,
) -> None:
    """Persist the daemon's authoritative fire_count/enabled/fired_at to DB.

    Called from the background fire-and-forget task after order placement.
    The daemon is the single source of truth for fire_count; this just
    syncs the DB so restarts pick up where we left off.
    """
    rule = await session.get(MonitorRuleDB, rule_id)
    if rule:
        rule.fire_count = fire_count
        rule.fired_at = utc_now()
        rule.enabled = enabled
        await session.commit()


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


async def list_rules_by_group(
    session: AsyncSession,
    user_id: int,
    group_id: str,
) -> list[MonitorRuleDB]:
    """List all rules belonging to a strategy group."""
    stmt = (
        select(MonitorRuleDB)
        .where(MonitorRuleDB.user_id == user_id)
        .where(MonitorRuleDB.group_id == group_id)
        .order_by(MonitorRuleDB.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_rules_by_group(
    session: AsyncSession,
    user_id: int,
    group_id: str,
) -> int:
    """Delete all rules in a strategy group. Returns count deleted."""
    stmt = (
        delete(MonitorRuleDB)
        .where(MonitorRuleDB.user_id == user_id)
        .where(MonitorRuleDB.group_id == group_id)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


async def disable_rules_by_group(
    session: AsyncSession,
    user_id: int,
    group_id: str,
) -> int:
    """Disable all rules in a strategy group. Returns count updated."""
    stmt = (
        update(MonitorRuleDB)
        .where(MonitorRuleDB.user_id == user_id)
        .where(MonitorRuleDB.group_id == group_id)
        .values(enabled=False, updated_at=utc_now())
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


async def disable_opposite_direction_rules(
    session: AsyncSession,
    user_id: int,
    group_id: str,
    direction: str,
) -> list[int]:
    """Disable all rules for the opposite direction within a strategy group.

    ``direction`` is "Long" or "Short" (case-insensitive).  Rules whose name
    contains the *opposite* keyword are disabled.

    Returns list of disabled rule IDs (for in-memory sync).
    """
    opposite = "Short" if direction.lower() == "long" else "Long"
    # Fetch IDs first so we can return them for in-memory disabling
    stmt = (
        select(MonitorRuleDB.id)
        .where(MonitorRuleDB.user_id == user_id)
        .where(MonitorRuleDB.group_id == group_id)
        .where(MonitorRuleDB.enabled == True)  # noqa: E712
        .where(MonitorRuleDB.name.ilike(f"%{opposite}%"))
    )
    result = await session.execute(stmt)
    ids = [row[0] for row in result.fetchall()]

    if ids:
        upd = (
            update(MonitorRuleDB)
            .where(MonitorRuleDB.id.in_(ids))
            .values(enabled=False, updated_at=utc_now())
        )
        await session.execute(upd)
        await session.commit()

    return ids


async def get_active_rules_for_daemon(session: AsyncSession) -> list[MonitorRuleDB]:
    """Get all enabled, non-expired rules across all users (for the daemon to load)."""
    stmt = (
        select(MonitorRuleDB)
        .where(MonitorRuleDB.enabled == True)  # noqa: E712
        .where(
            or_(
                MonitorRuleDB.expires_at.is_(None),
                MonitorRuleDB.expires_at > utc_now(),
            )
        )
        .order_by(MonitorRuleDB.user_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def auto_disable_expired_rules(session: AsyncSession) -> int:
    """Disable all enabled rules whose expires_at has passed. Returns count."""
    stmt = (
        update(MonitorRuleDB)
        .where(MonitorRuleDB.enabled == True)  # noqa: E712
        .where(MonitorRuleDB.expires_at.isnot(None))
        .where(MonitorRuleDB.expires_at < utc_now())
        .values(enabled=False, updated_at=utc_now())
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


async def cleanup_stale_rules(session: AsyncSession, disabled_hours: int = 24) -> int:
    """Delete rules that are disabled AND max-fired for over N hours.

    These are "fully spent" rules: they fired all their allowed times,
    were auto-disabled, and have been sitting idle. Safe to remove.
    MonitorLog entries survive (FK is ON DELETE SET NULL).
    Returns count of deleted rules.
    """
    cutoff = utc_now() - timedelta(hours=disabled_hours)
    stmt = (
        delete(MonitorRuleDB)
        .where(MonitorRuleDB.enabled == False)  # noqa: E712
        .where(MonitorRuleDB.max_fires.isnot(None))
        .where(MonitorRuleDB.fire_count >= MonitorRuleDB.max_fires)
        .where(MonitorRuleDB.updated_at < cutoff)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


async def bulk_delete_rules(
    session: AsyncSession, user_id: int, rule_ids: list[int]
) -> tuple[int, list[int]]:
    """Bulk delete rules by ID, scoped to user.

    Returns (deleted_count, not_found_ids).
    """
    stmt = select(MonitorRuleDB.id).where(
        MonitorRuleDB.id.in_(rule_ids),
        MonitorRuleDB.user_id == user_id,
    )
    result = await session.execute(stmt)
    found_ids = {row[0] for row in result.fetchall()}
    not_found = [rid for rid in rule_ids if rid not in found_ids]

    deleted = 0
    if found_ids:
        del_stmt = (
            delete(MonitorRuleDB)
            .where(MonitorRuleDB.id.in_(list(found_ids)))
        )
        result = await session.execute(del_stmt)
        await session.commit()
        deleted = result.rowcount
    return deleted, not_found


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
        group_id=db_rule.group_id,
        strategy_name=db_rule.strategy_name,
        role=db_rule.role,
    )
