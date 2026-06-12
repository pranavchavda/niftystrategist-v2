"""Tests for monitor rule CRUD operations using in-memory SQLite."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from database.models import Base, utc_now


@pytest_asyncio.fixture
async def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Create a test user (MonitorRule has FK to users)
        from database.models import User
        user = User(id=999, email="test@test.com", name="Test User")
        session.add(user)
        await session.commit()
        yield session
    await engine.dispose()


def _rule_kwargs(name="test-rule", **overrides):
    defaults = dict(
        user_id=999,
        name=name,
        trigger_type="price",
        trigger_config={"condition": "lte", "price": 2400, "reference": "ltp"},
        action_type="place_order",
        action_config={
            "symbol": "RELIANCE",
            "transaction_type": "SELL",
            "quantity": 10,
            "order_type": "MARKET",
            "product": "I",
            "price": None,
        },
        instrument_token="NSE_EQ|INE002A01018",
        symbol="RELIANCE",
    )
    defaults.update(overrides)
    return defaults


@pytest.mark.asyncio
async def test_create_rule(db_session):
    from monitor.crud import create_rule

    rule = await create_rule(db_session, **_rule_kwargs())
    assert rule.id is not None
    assert rule.name == "test-rule"
    assert rule.enabled is True
    assert rule.fire_count == 0


@pytest.mark.asyncio
async def test_list_rules(db_session):
    from monitor.crud import create_rule, list_rules

    await create_rule(db_session, **_rule_kwargs("rule-1"))
    await create_rule(db_session, **_rule_kwargs("rule-2"))
    rules = await list_rules(db_session, user_id=999)
    assert len(rules) == 2


@pytest.mark.asyncio
async def test_list_rules_enabled_only(db_session):
    from monitor.crud import create_rule, list_rules, disable_rule

    r1 = await create_rule(db_session, **_rule_kwargs("active"))
    r2 = await create_rule(db_session, **_rule_kwargs("disabled"))
    await disable_rule(db_session, r2.id)
    rules = await list_rules(db_session, user_id=999, enabled_only=True)
    assert len(rules) == 1
    assert rules[0].name == "active"


@pytest.mark.asyncio
async def test_get_rule(db_session):
    from monitor.crud import create_rule, get_rule

    created = await create_rule(db_session, **_rule_kwargs())
    fetched = await get_rule(db_session, created.id)
    assert fetched is not None
    assert fetched.name == "test-rule"


@pytest.mark.asyncio
async def test_get_rule_not_found(db_session):
    from monitor.crud import get_rule

    assert await get_rule(db_session, 9999) is None


@pytest.mark.asyncio
async def test_update_rule(db_session):
    from monitor.crud import create_rule, update_rule, get_rule

    r = await create_rule(db_session, **_rule_kwargs())
    updated = await update_rule(db_session, r.id, name="new-name", symbol="TCS")
    assert updated is not None
    assert updated.name == "new-name"
    assert updated.symbol == "TCS"
    # Verify persisted
    fetched = await get_rule(db_session, r.id)
    assert fetched.name == "new-name"


@pytest.mark.asyncio
async def test_update_rule_not_found(db_session):
    from monitor.crud import update_rule

    result = await update_rule(db_session, 9999, name="nope")
    assert result is None


@pytest.mark.asyncio
async def test_enable_disable_rule(db_session):
    from monitor.crud import create_rule, disable_rule, enable_rule, get_rule

    r = await create_rule(db_session, **_rule_kwargs())
    await disable_rule(db_session, r.id)
    r = await get_rule(db_session, r.id)
    assert r.enabled is False
    await enable_rule(db_session, r.id)
    r = await get_rule(db_session, r.id)
    assert r.enabled is True


@pytest.mark.asyncio
async def test_delete_rule(db_session):
    from monitor.crud import create_rule, delete_rule, get_rule

    r = await create_rule(db_session, **_rule_kwargs())
    assert await delete_rule(db_session, r.id) is True
    assert await get_rule(db_session, r.id) is None


@pytest.mark.asyncio
async def test_delete_nonexistent(db_session):
    from monitor.crud import delete_rule

    assert await delete_rule(db_session, 9999) is False


@pytest.mark.asyncio
async def test_record_fire(db_session):
    """record_fire is pure logging — does NOT update rule state."""
    from monitor.crud import create_rule, record_fire, get_rule

    r = await create_rule(db_session, **_rule_kwargs(max_fires=2))
    log = await record_fire(
        db_session, r.id, 999, {"ltp": 2350}, "place_order", {"order_id": "ORD1"}
    )
    assert log.id is not None
    assert log.action_taken == "place_order"
    r = await get_rule(db_session, r.id)
    assert r.fire_count == 0  # record_fire does NOT increment fire_count
    assert r.enabled is True


@pytest.mark.asyncio
async def test_sync_rule_fire_state(db_session):
    """sync_rule_fire_state persists daemon's authoritative state to DB."""
    from monitor.crud import create_rule, sync_rule_fire_state, get_rule

    r = await create_rule(db_session, **_rule_kwargs(max_fires=2))
    await sync_rule_fire_state(
        db_session, r.id, fire_count=1, enabled=True, stamp_fired_at=True
    )
    r = await get_rule(db_session, r.id)
    assert r.fire_count == 1
    assert r.fired_at is not None
    assert r.enabled is True  # Still enabled (1 < 2)


@pytest.mark.asyncio
async def test_sync_rule_fire_state_sibling_not_stamped(db_session):
    """Chain/OCO-sibling syncs must NOT stamp fired_at on a never-fired rule.

    Regression: when an OCO SL fired, the cancelled target sibling got
    fired_at stamped via the chain sync, making it look like the target
    hit (2026-06-12 JBMA incident).
    """
    from monitor.crud import create_rule, sync_rule_fire_state, get_rule

    r = await create_rule(db_session, **_rule_kwargs(max_fires=1))
    # Default stamp_fired_at=False — the sibling-cancel path.
    await sync_rule_fire_state(db_session, r.id, fire_count=0, enabled=False)
    r = await get_rule(db_session, r.id)
    assert r.fire_count == 0
    assert r.enabled is False
    assert r.fired_at is None  # never fired, must not look fired


@pytest.mark.asyncio
async def test_sync_rule_fire_state_disables(db_session):
    """sync_rule_fire_state can persist disabled state from daemon."""
    from monitor.crud import create_rule, sync_rule_fire_state, get_rule

    r = await create_rule(db_session, **_rule_kwargs(max_fires=1))
    await sync_rule_fire_state(db_session, r.id, fire_count=1, enabled=False)
    r = await get_rule(db_session, r.id)
    assert r.fire_count == 1
    assert r.enabled is False


@pytest.mark.asyncio
async def test_record_fire_does_not_increment_count(db_session):
    """Multiple record_fire calls should NOT change fire_count (daemon owns it)."""
    from monitor.crud import create_rule, record_fire, get_rule

    r = await create_rule(db_session, **_rule_kwargs(max_fires=5))
    await record_fire(db_session, r.id, 999, {}, "place_order", {})
    await record_fire(db_session, r.id, 999, {}, "place_order", {})
    await record_fire(db_session, r.id, 999, {}, "place_order", {})
    r = await get_rule(db_session, r.id)
    assert r.fire_count == 0  # Unchanged — daemon is the authority
    assert r.enabled is True  # Still enabled (3 < 5)


@pytest.mark.asyncio
async def test_get_logs(db_session):
    from monitor.crud import create_rule, record_fire, get_logs

    r = await create_rule(db_session, **_rule_kwargs())
    await record_fire(db_session, r.id, 999, {}, "place_order", {})
    await record_fire(db_session, r.id, 999, {}, "cancel_order", {})
    logs = await get_logs(db_session, user_id=999)
    assert len(logs) == 2


@pytest.mark.asyncio
async def test_get_logs_by_rule(db_session):
    from monitor.crud import create_rule, record_fire, get_logs

    r1 = await create_rule(db_session, **_rule_kwargs("rule-1"))
    r2 = await create_rule(db_session, **_rule_kwargs("rule-2"))
    await record_fire(db_session, r1.id, 999, {}, "place_order", {})
    await record_fire(db_session, r2.id, 999, {}, "cancel_order", {})
    logs = await get_logs(db_session, user_id=999, rule_id=r1.id)
    assert len(logs) == 1
    assert logs[0].action_taken == "place_order"


@pytest.mark.asyncio
async def test_get_logs_limit(db_session):
    from monitor.crud import create_rule, record_fire, get_logs

    r = await create_rule(db_session, **_rule_kwargs())
    for i in range(5):
        await record_fire(db_session, r.id, 999, {}, f"action_{i}", {})
    logs = await get_logs(db_session, user_id=999, limit=3)
    assert len(logs) == 3


@pytest.mark.asyncio
async def test_get_active_rules_for_daemon(db_session):
    from monitor.crud import create_rule, disable_rule, get_active_rules_for_daemon

    await create_rule(db_session, **_rule_kwargs("active"))
    r2 = await create_rule(db_session, **_rule_kwargs("disabled"))
    await disable_rule(db_session, r2.id)
    rules = await get_active_rules_for_daemon(db_session)
    assert len(rules) == 1
    assert rules[0].name == "active"


@pytest.mark.asyncio
async def test_db_rule_to_schema(db_session):
    from monitor.crud import create_rule, db_rule_to_schema

    r = await create_rule(db_session, **_rule_kwargs())
    schema = db_rule_to_schema(r)
    assert schema.id == r.id
    assert schema.name == "test-rule"
    assert schema.trigger_type == "price"
    assert schema.user_id == 999
    assert schema.fire_count == 0
    assert schema.enabled is True
    assert schema.instrument_token == "NSE_EQ|INE002A01018"
    assert schema.symbol == "RELIANCE"


# ── Exit-rule stacking guard (2026-05-08 FINCABLES bug) ──────────────


def _exit_rule_kwargs(name, role, transaction_type="SELL", trigger_type="price",
                      trigger_config=None, **overrides):
    """Build kwargs for an exit-side rule (sl/target/trail/squareoff)."""
    if trigger_config is None:
        trigger_config = {"condition": "lte", "price": 2400, "reference": "ltp"}
    base = _rule_kwargs(
        name=name,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        role=role,
    )
    base["action_config"]["transaction_type"] = transaction_type
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_stacking_refused_when_cross_type(db_session):
    """Adding a trail when an SL exists on the same long → refuse."""
    from monitor.crud import create_rule, ExitStackingError
    # Existing standalone SL on RELIANCE LONG (sell exit)
    await create_rule(db_session, **_exit_rule_kwargs(
        "RELIANCE OCO Stop-Loss @ 2400", role=None,
        trigger_config={"condition": "lte", "price": 2400, "reference": "ltp"},
    ))
    # New trailing on the same position should refuse
    with pytest.raises(ExitStackingError) as exc:
        await create_rule(db_session, **_exit_rule_kwargs(
            "RELIANCE Trailing SL 1.5%", role=None,
            trigger_type="trailing_stop",
            trigger_config={"trail_percent": 1.5, "initial_price": 2500,
                            "highest_price": 2500, "direction": "long",
                            "reference": "ltp"},
        ))
    assert exc.value.conflicts  # at least one conflicting rule id


@pytest.mark.asyncio
async def test_stacking_replaces_same_type(db_session):
    """Adding a tighter trail when one exists → auto-disables old."""
    from monitor.crud import create_rule
    old = await create_rule(db_session, **_exit_rule_kwargs(
        "RELIANCE Trailing SL 5%", role="trailing_long",
        trigger_type="trailing_stop",
        trigger_config={"trail_percent": 5, "initial_price": 2500,
                        "highest_price": 2500, "direction": "long",
                        "reference": "ltp"},
    ))
    assert old.enabled is True
    # Add tighter trail → old auto-disabled, new enabled
    new = await create_rule(db_session, **_exit_rule_kwargs(
        "RELIANCE Trailing SL 1.5%", role="trailing_long",
        trigger_type="trailing_stop",
        trigger_config={"trail_percent": 1.5, "initial_price": 2500,
                        "highest_price": 2500, "direction": "long",
                        "reference": "ltp"},
    ))
    assert new.enabled is True
    # Reload old from DB to confirm it was disabled
    from monitor.crud import get_rule
    refreshed = await get_rule(db_session, old.id)
    assert refreshed.enabled is False


@pytest.mark.asyncio
async def test_stacking_force_overrides_refusal(db_session):
    """force=True bypasses the cross-type refusal."""
    from monitor.crud import create_rule
    await create_rule(db_session, **_exit_rule_kwargs(
        "RELIANCE OCO SL @ 2400", role=None,
    ))
    new = await create_rule(db_session, **_exit_rule_kwargs(
        "RELIANCE Trailing SL 1.5%", role=None,
        trigger_type="trailing_stop",
        trigger_config={"trail_percent": 1.5, "initial_price": 2500,
                        "highest_price": 2500, "direction": "long",
                        "reference": "ltp"},
        force=True,
    ))
    assert new.id is not None
    assert new.enabled is True


@pytest.mark.asyncio
async def test_stacking_strategy_template_bypasses_check(db_session):
    """Strategy templates create multiple exit types together by design."""
    from monitor.crud import create_rule
    sl = await create_rule(db_session, **_exit_rule_kwargs(
        "RELIANCE ORB Long SL @ 2400", role="sl_long",
        strategy_name="orb",
    ))
    # Same strategy adds target — should NOT refuse despite cross-type
    target = await create_rule(db_session, **_exit_rule_kwargs(
        "RELIANCE ORB Long Target @ 2700", role="target_long",
        strategy_name="orb",
        trigger_config={"condition": "gte", "price": 2700, "reference": "ltp"},
    ))
    assert sl.enabled is True
    assert target.enabled is True


@pytest.mark.asyncio
async def test_stacking_oco_pair_via_also_cancel_rules(db_session):
    """OCO target whose also_cancel_rules contains the SL bypasses refusal."""
    from monitor.crud import create_rule
    sl = await create_rule(db_session, **_exit_rule_kwargs(
        "RELIANCE OCO SL @ 2400", role=None,
    ))
    # Target rule lists SL in also_cancel_rules — they're explicitly OCO
    target_kwargs = _exit_rule_kwargs(
        "RELIANCE OCO Target @ 2700", role=None,
        trigger_config={"condition": "gte", "price": 2700, "reference": "ltp"},
    )
    target_kwargs["action_config"]["also_cancel_rules"] = [sl.id]
    target = await create_rule(db_session, **target_kwargs)
    assert target.enabled is True
    # SL stays enabled (kill chain handles mutual exclusion at fire time)
    from monitor.crud import get_rule
    refreshed_sl = await get_rule(db_session, sl.id)
    assert refreshed_sl.enabled is True


@pytest.mark.asyncio
async def test_stacking_different_position_sides_dont_conflict(db_session):
    """A LONG exit and a SHORT exit on the same symbol coexist."""
    from monitor.crud import create_rule
    long_sl = await create_rule(db_session, **_exit_rule_kwargs(
        "RELIANCE Long SL @ 2400", role=None, transaction_type="SELL",
    ))
    short_sl = await create_rule(db_session, **_exit_rule_kwargs(
        "RELIANCE Short SL @ 2600", role=None, transaction_type="BUY",
        trigger_config={"condition": "gte", "price": 2600, "reference": "ltp"},
    ))
    assert long_sl.enabled is True
    assert short_sl.enabled is True
