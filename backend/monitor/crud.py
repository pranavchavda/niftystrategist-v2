"""CRUD operations for monitor rules and logs."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import MonitorRule as MonitorRuleDB, MonitorLog as MonitorLogDB, utc_now
from monitor.models import MonitorRule as MonitorRuleSchema

logger = logging.getLogger(__name__)


class ExitStackingError(ValueError):
    """Raised when a new exit-side rule would stack with an existing
    exit rule of a different type on the same symbol+position-side.

    Origin: 2026-05-08 FINCABLES — an OCO SL (price ≤ X) and a
    standalone Trailing SL (long, 1.5%) both fired in the same tick,
    double-sold, flipped LONG → SHORT. SAFETY-3 in the orchestrator
    prompt is the interim guard; this exception is the server-side
    enforcement.
    """
    def __init__(self, message: str, conflicts: list):
        super().__init__(message)
        self.conflicts = conflicts


# Map role → exit type bucket. None = not an exit rule (entry/etc).
_EXIT_TYPE_BUCKETS: dict[str, str] = {
    "sl_long": "stop", "sl_short": "stop",
    "target_long": "target", "target_short": "target",
    "trailing_long": "trail", "trailing_short": "trail",
    "squareoff": "squareoff",
}


def _classify_exit_type(rule_or_attrs) -> str | None:
    """Classify a rule into stop/target/trail/squareoff/None.

    Accepts either a MonitorRuleDB row or a dict of {role, name,
    trigger_type, action_config}. Falls back to name + trigger_type
    inference when role is unset (e.g. role-less rules created via
    add-oco / add-trailing).
    """
    role = getattr(rule_or_attrs, "role", None) or rule_or_attrs.get("role") if isinstance(rule_or_attrs, dict) else getattr(rule_or_attrs, "role", None)
    if role and role in _EXIT_TYPE_BUCKETS:
        return _EXIT_TYPE_BUCKETS[role]
    if isinstance(rule_or_attrs, dict):
        name = (rule_or_attrs.get("name") or "").lower()
        trigger_type = rule_or_attrs.get("trigger_type")
    else:
        name = (getattr(rule_or_attrs, "name", "") or "").lower()
        trigger_type = getattr(rule_or_attrs, "trigger_type", None)
    if trigger_type == "trailing_stop":
        return "trail"
    if trigger_type == "time":
        return "squareoff"
    if "stop-loss" in name or "stop loss" in name or " sl " in name or "oco stop" in name or name.endswith(" sl"):
        return "stop"
    if "target" in name:
        return "target"
    return None


def _derive_position_side(rule_or_attrs) -> str | None:
    """For an exit rule, return the side of the underlying position.

    SELL exit ⇒ position is LONG. BUY exit ⇒ position is SHORT.
    Used to scope conflict detection: a SELL trail on RELIANCE shouldn't
    conflict with a BUY trail on RELIANCE (those exit different positions).
    """
    role = getattr(rule_or_attrs, "role", None) if not isinstance(rule_or_attrs, dict) else rule_or_attrs.get("role")
    if role:
        if "_long" in role:
            return "LONG"
        if "_short" in role:
            return "SHORT"
    if isinstance(rule_or_attrs, dict):
        ac = rule_or_attrs.get("action_config") or {}
    else:
        ac = getattr(rule_or_attrs, "action_config", None) or {}
    tx = ac.get("transaction_type")
    if tx == "SELL":
        return "LONG"
    if tx == "BUY":
        return "SHORT"
    return None


async def _check_exit_stacking(
    session: AsyncSession,
    user_id: int,
    symbol: str | None,
    instrument_token: str | None,
    new_class: str,
    new_side: str,
    force: bool,
    new_action_config: dict | None = None,
) -> list[int]:
    """Detect and resolve exit-rule stacking conflicts.

    Same-type (e.g. new trail replacing existing trail): auto-disables
    the old rules (returns their IDs so the caller can log/audit).
    Cross-type (e.g. new trail when an OCO SL exists): raises
    ExitStackingError unless ``force`` is set.

    Rules listed in the new rule's ``also_cancel_rules`` are skipped —
    they're explicitly OCO-linked, the kill chain handles mutual
    exclusion, so they don't count as conflicting stack. This is what
    makes legitimate OCO pairs (SL+target) coexist without tripping
    the cross-type check.
    """
    if not symbol and not instrument_token:
        return []
    already_linked = set((new_action_config or {}).get("also_cancel_rules") or [])

    stmt = select(MonitorRuleDB).where(
        MonitorRuleDB.user_id == user_id,
        MonitorRuleDB.enabled == True,  # noqa: E712
        MonitorRuleDB.action_type == "place_order",
    )
    if symbol:
        stmt = stmt.where(MonitorRuleDB.symbol == symbol)
    elif instrument_token:
        stmt = stmt.where(MonitorRuleDB.instrument_token == instrument_token)
    result = await session.execute(stmt)
    existing = list(result.scalars().all())

    # Same position side AND not OCO-linked from the new rule.
    same_side = [
        r for r in existing
        if _derive_position_side(r) == new_side and r.id not in already_linked
    ]
    same_class = [r for r in same_side if _classify_exit_type(r) == new_class]
    diff_class = [
        r for r in same_side
        if _classify_exit_type(r) is not None and _classify_exit_type(r) != new_class
    ]

    if diff_class and not force:
        details = ", ".join(
            f"#{r.id} ({_classify_exit_type(r)}: {r.name!r})" for r in diff_class
        )
        raise ExitStackingError(
            f"Cannot stack {new_class} exit on "
            f"{symbol or instrument_token} {new_side}: existing exit rules "
            f"of different type would also fire on the same position: {details}. "
            "Disable them first or pass force=True / --force.",
            conflicts=[r.id for r in diff_class],
        )

    # Auto-cancel same-type (replacement) — covers the legitimate
    # "tighten the trail" workflow: agent calls add-trailing again with
    # a tighter percent, and the old trail rule is silently superseded.
    disabled_ids: list[int] = []
    for r in same_class:
        r.enabled = False
        r.updated_at = utc_now()
        disabled_ids.append(r.id)
    return disabled_ids


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
    force: bool = False,
) -> MonitorRuleDB:
    """Create a new monitor rule.

    Stacking guard: when creating a standalone exit-side rule (no
    ``strategy_name``), checks for existing enabled exit rules on the
    same symbol+side. Same exit-type (trail vs trail) auto-cancels the
    old; different exit-type (trail vs SL) raises ExitStackingError
    unless ``force=True``. Strategy-template rules bypass the check
    entirely — a single ORB deployment is allowed to set sl + target +
    trail + squareoff together by design.
    """
    if action_type == "place_order" and not strategy_name and enabled:
        attrs = {
            "role": role, "name": name,
            "trigger_type": trigger_type, "action_config": action_config,
        }
        new_class = _classify_exit_type(attrs)
        new_side = _derive_position_side(attrs)
        if new_class and new_side:
            disabled = await _check_exit_stacking(
                session, user_id, symbol, instrument_token,
                new_class, new_side, force,
                new_action_config=action_config,
            )
            if disabled:
                logger.warning(
                    "Auto-disabled %d existing %s rule(s) %s on %s %s "
                    "(replaced by new rule %r)",
                    len(disabled), new_class, disabled,
                    symbol or instrument_token, new_side, name,
                )

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
