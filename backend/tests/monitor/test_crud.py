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
    from monitor.crud import create_rule, record_fire, get_rule

    r = await create_rule(db_session, **_rule_kwargs(max_fires=2))
    log = await record_fire(
        db_session, r.id, 999, {"ltp": 2350}, "place_order", {"order_id": "ORD1"}
    )
    assert log.id is not None
    assert log.action_taken == "place_order"
    r = await get_rule(db_session, r.id)
    assert r.fire_count == 1
    assert r.fired_at is not None
    assert r.enabled is True  # Still enabled (1 < 2)


@pytest.mark.asyncio
async def test_record_fire_auto_disables(db_session):
    from monitor.crud import create_rule, record_fire, get_rule

    r = await create_rule(db_session, **_rule_kwargs(max_fires=1))
    await record_fire(db_session, r.id, 999, {}, "place_order", {})
    r = await get_rule(db_session, r.id)
    assert r.fire_count == 1
    assert r.enabled is False  # Auto-disabled


@pytest.mark.asyncio
async def test_record_fire_increments_count(db_session):
    from monitor.crud import create_rule, record_fire, get_rule

    r = await create_rule(db_session, **_rule_kwargs(max_fires=5))
    await record_fire(db_session, r.id, 999, {}, "place_order", {})
    await record_fire(db_session, r.id, 999, {}, "place_order", {})
    await record_fire(db_session, r.id, 999, {}, "place_order", {})
    r = await get_rule(db_session, r.id)
    assert r.fire_count == 3
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
