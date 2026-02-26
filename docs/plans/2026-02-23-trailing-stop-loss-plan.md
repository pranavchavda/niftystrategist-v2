# Trailing Stop-Loss Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `trailing_stop` trigger type to the trade monitor that automatically raises the stop-loss level as price increases.

**Architecture:** New trigger type in the existing monitor rule engine. The evaluator is a pure function that returns a `trigger_config_update` side-effect when `highest_price` changes. The daemon persists the update to DB and updates the in-memory rule. No DB schema changes needed — `trigger_config` is JSONB.

**Tech Stack:** Python 3.12, Pydantic, pytest, asyncio, SQLAlchemy (async)

**Design doc:** `docs/plans/2026-02-23-trailing-stop-loss-design.md`

---

## Task 1: Add TrailingStopTrigger Model + Update MonitorRule Literal

**Files:**
- Modify: `backend/monitor/models.py`
- Test: `backend/tests/monitor/test_models.py`

**Step 1: Write the failing test**

Add to `backend/tests/monitor/test_models.py`:

```python
from monitor.models import TrailingStopTrigger, MonitorRule


class TestTrailingStopTrigger:
    def test_valid_config(self):
        t = TrailingStopTrigger(
            trail_percent=15.0,
            initial_price=1770.0,
            highest_price=1850.0,
        )
        assert t.trail_percent == 15.0
        assert t.reference == "ltp"

    def test_custom_reference(self):
        t = TrailingStopTrigger(
            trail_percent=10.0,
            initial_price=100.0,
            highest_price=100.0,
            reference="high",
        )
        assert t.reference == "high"


class TestMonitorRuleTrailingStop:
    def test_trailing_stop_trigger_type_accepted(self):
        rule = MonitorRule(
            id=1,
            user_id=999,
            name="test trailing",
            trigger_type="trailing_stop",
            trigger_config={
                "trail_percent": 15.0,
                "initial_price": 100.0,
                "highest_price": 110.0,
            },
            action_type="place_order",
            action_config={
                "symbol": "X",
                "transaction_type": "SELL",
                "quantity": 1,
                "order_type": "MARKET",
                "product": "I",
                "price": None,
            },
            instrument_token="NSE_EQ|TEST",
        )
        assert rule.trigger_type == "trailing_stop"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/monitor/test_models.py -v -k "trailing" --no-header`
Expected: FAIL — `TrailingStopTrigger` not importable, `"trailing_stop"` rejected by Literal

**Step 3: Write minimal implementation**

In `backend/monitor/models.py`, add `TrailingStopTrigger` after `CompoundTrigger` (after line 50):

```python
class TrailingStopTrigger(BaseModel):
    trail_percent: float
    initial_price: float
    highest_price: float
    reference: Literal["ltp", "bid", "ask", "open", "high", "low"] = "ltp"
```

Update `MonitorRule.trigger_type` (line 77) from:
```python
    trigger_type: Literal["price", "time", "indicator", "order_status", "compound"]
```
to:
```python
    trigger_type: Literal["price", "time", "indicator", "order_status", "compound", "trailing_stop"]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/monitor/test_models.py -v -k "trailing" --no-header`
Expected: PASS (2 tests)

**Step 5: Run full model tests to check no regressions**

Run: `cd backend && python -m pytest tests/monitor/test_models.py -v --no-header`
Expected: All pass

**Step 6: Commit**

```
feat(monitor): add TrailingStopTrigger model
```

---

## Task 2: Add evaluate_trailing_stop_trigger + Extend RuleResult

**Files:**
- Modify: `backend/monitor/rule_evaluator.py`
- Create: `backend/tests/monitor/test_rule_evaluator_trailing.py`

**Step 1: Write the failing tests**

Create `backend/tests/monitor/test_rule_evaluator_trailing.py`:

```python
"""Tests for evaluate_trailing_stop_trigger — pure function, no I/O."""
from monitor.models import MonitorRule
from monitor.rule_evaluator import evaluate_trailing_stop_trigger


def _make_trailing_rule(
    trail_percent: float = 15.0,
    initial_price: float = 1000.0,
    highest_price: float = 1000.0,
    reference: str = "ltp",
) -> MonitorRule:
    return MonitorRule(
        id=1,
        user_id=999,
        name="test trailing",
        trigger_type="trailing_stop",
        trigger_config={
            "trail_percent": trail_percent,
            "initial_price": initial_price,
            "highest_price": highest_price,
            "reference": reference,
        },
        action_type="place_order",
        action_config={
            "symbol": "X",
            "transaction_type": "SELL",
            "quantity": 1,
            "order_type": "MARKET",
            "product": "I",
            "price": None,
        },
        instrument_token="NSE_EQ|TEST",
    )


# ── Fires when price drops below stop level ─────────────────────────

class TestTrailingStopFires:
    def test_fires_at_stop_level(self):
        """15% trail from 1000 = stop at 850. Price at 850 should fire."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 850.0})
        assert fired is True
        assert update is None

    def test_fires_below_stop_level(self):
        """Price well below stop should fire."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 800.0})
        assert fired is True

    def test_fires_with_updated_highest(self):
        """After highest_price moved to 1200, stop is 1020. Price at 1020 fires."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1200.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1020.0})
        assert fired is True


# ── Does not fire when price is above stop ───────────────────────────

class TestTrailingStopDoesNotFire:
    def test_no_fire_above_stop(self):
        """Price above stop level should not fire."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 900.0})
        assert fired is False
        assert update is None

    def test_no_fire_at_highest(self):
        """Price at highest should not fire (stop is 15% below)."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1000.0})
        assert fired is False
        assert update is None


# ── Updates highest_price when price rises ───────────────────────────

class TestTrailingStopUpdatesHighest:
    def test_updates_highest_when_price_rises(self):
        """When price exceeds highest_price, return updated config."""
        rule = _make_trailing_rule(trail_percent=15.0, initial_price=1000.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1100.0})
        assert fired is False
        assert update is not None
        assert update["highest_price"] == 1100.0
        # Other fields preserved
        assert update["trail_percent"] == 15.0
        assert update["initial_price"] == 1000.0
        assert update["reference"] == "ltp"

    def test_no_update_when_price_equals_highest(self):
        """Same price as highest — no update needed."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 1000.0})
        assert update is None

    def test_no_update_when_price_drops(self):
        """Price drops but above stop — no update, no fire."""
        rule = _make_trailing_rule(trail_percent=15.0, highest_price=1000.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 900.0})
        assert update is None


# ── Edge cases ───────────────────────────────────────────────────────

class TestTrailingStopEdgeCases:
    def test_missing_reference_field_returns_no_fire(self):
        """If market_data doesn't have the reference field, don't fire."""
        rule = _make_trailing_rule(reference="bid")
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 500.0})
        assert fired is False
        assert update is None

    def test_custom_reference_field(self):
        """Use 'high' as reference instead of 'ltp'."""
        rule = _make_trailing_rule(trail_percent=10.0, highest_price=100.0, reference="high")
        fired, update = evaluate_trailing_stop_trigger(rule, {"high": 110.0, "ltp": 105.0})
        assert fired is False
        assert update is not None
        assert update["highest_price"] == 110.0

    def test_zero_trail_percent_fires_on_any_drop(self):
        """0% trail means stop == highest. Any drop fires."""
        rule = _make_trailing_rule(trail_percent=0.0, highest_price=100.0)
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 99.99})
        assert fired is True

    def test_small_trail_precision(self):
        """Verify floating point doesn't cause false fires."""
        rule = _make_trailing_rule(trail_percent=1.0, highest_price=100.0)
        # Stop at 99.0. Price at 99.01 should NOT fire.
        fired, update = evaluate_trailing_stop_trigger(rule, {"ltp": 99.01})
        assert fired is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/monitor/test_rule_evaluator_trailing.py -v --no-header 2>&1 | head -5`
Expected: ImportError — `evaluate_trailing_stop_trigger` not found

**Step 3: Write the evaluator and extend RuleResult**

In `backend/monitor/rule_evaluator.py`:

1. Add import (after line 18, in the imports from monitor.models):
```python
    TrailingStopTrigger,
```

2. Add the evaluator function (after the price trigger section, before time triggers ~line 77):

```python
# ── Trailing stop triggers ──────────────────────────────────────────

def evaluate_trailing_stop_trigger(
    rule: MonitorRule,
    market_data: dict,
) -> tuple[bool, dict | None]:
    """Evaluate a trailing stop-loss trigger.

    Returns (fired, trigger_config_update).
    - fired=True when price drops to or below the trailing stop level.
    - trigger_config_update is non-None when highest_price needs updating.
    """
    cfg = TrailingStopTrigger(**rule.trigger_config)

    current = market_data.get(cfg.reference)
    if current is None:
        return False, None

    stop_price = cfg.highest_price * (1 - cfg.trail_percent / 100)

    # Check if price has dropped to/below the stop level
    if current <= stop_price:
        return True, None

    # Check if we have a new high
    if current > cfg.highest_price:
        updated = rule.trigger_config.copy()
        updated["highest_price"] = current
        return False, updated

    return False, None
```

3. Add `trigger_config_update` field to `RuleResult` (line 271, after `rules_to_cancel`):
```python
    trigger_config_update: dict | None = None
```

4. In `evaluate_rule()`, add the trailing_stop dispatch (after the compound block, before `result.fired = fired`). The trailing_stop case is different — it returns a tuple:

After the compound elif block (after line 317), add:
```python
    elif rule.trigger_type == "trailing_stop":
        fired, config_update = evaluate_trailing_stop_trigger(rule, ctx.market_data)
        result.trigger_config_update = config_update
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/monitor/test_rule_evaluator_trailing.py -v --no-header`
Expected: All 11 tests PASS

**Step 5: Run full evaluator tests to check no regressions**

Run: `cd backend && python -m pytest tests/monitor/test_rule_evaluator_price.py tests/monitor/test_rule_evaluator_toplevel.py tests/monitor/test_rule_evaluator_compound.py -v --no-header`
Expected: All pass

**Step 6: Commit**

```
feat(monitor): add trailing stop evaluator + RuleResult.trigger_config_update
```

---

## Task 3: Add Trailing Stop Dispatch Test in Top-Level Evaluator

**Files:**
- Modify: `backend/tests/monitor/test_rule_evaluator_toplevel.py`

**Step 1: Write the test**

Add to `backend/tests/monitor/test_rule_evaluator_toplevel.py`:

```python
# ── Trailing stop dispatch ─────────────────────────────────────────

class TestTrailingStopDispatch:
    def test_trailing_stop_fires_through_evaluate_rule(self):
        """trailing_stop trigger type dispatches correctly and fires."""
        rule = MonitorRule(
            id=20,
            user_id=999,
            name="trailing test",
            trigger_type="trailing_stop",
            trigger_config={
                "trail_percent": 10.0,
                "initial_price": 100.0,
                "highest_price": 100.0,
            },
            action_type="place_order",
            action_config={
                "symbol": "X",
                "transaction_type": "SELL",
                "quantity": 5,
                "order_type": "MARKET",
                "product": "D",
                "price": None,
            },
            instrument_token="NSE_EQ|TEST",
        )
        # Stop at 90.0 (10% below 100). Price at 85 fires.
        ctx = EvalContext(market_data={"ltp": 85.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is True
        assert result.action_type == "place_order"
        assert result.trigger_config_update is None

    def test_trailing_stop_updates_highest_through_evaluate_rule(self):
        """trailing_stop returns trigger_config_update when price rises."""
        rule = MonitorRule(
            id=21,
            user_id=999,
            name="trailing test",
            trigger_type="trailing_stop",
            trigger_config={
                "trail_percent": 10.0,
                "initial_price": 100.0,
                "highest_price": 100.0,
            },
            action_type="place_order",
            action_config={
                "symbol": "X",
                "transaction_type": "SELL",
                "quantity": 5,
                "order_type": "MARKET",
                "product": "D",
                "price": None,
            },
            instrument_token="NSE_EQ|TEST",
        )
        ctx = EvalContext(market_data={"ltp": 120.0})
        result = evaluate_rule(rule, ctx)
        assert result.fired is False
        assert result.trigger_config_update is not None
        assert result.trigger_config_update["highest_price"] == 120.0
```

**Step 2: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/monitor/test_rule_evaluator_toplevel.py -v -k "trailing" --no-header`
Expected: PASS (2 tests)

**Step 3: Run full top-level tests**

Run: `cd backend && python -m pytest tests/monitor/test_rule_evaluator_toplevel.py -v --no-header`
Expected: All pass

**Step 4: Commit**

```
test(monitor): add trailing_stop dispatch tests for evaluate_rule
```

---

## Task 4: Update UserManager to Subscribe Trailing Stop Instruments

**Files:**
- Modify: `backend/monitor/user_manager.py` (line 41)
- Test: `backend/tests/monitor/test_user_manager.py`

**Step 1: Write the failing test**

Add to `backend/tests/monitor/test_user_manager.py` (find the existing tests for `extract_instruments_from_rules`):

```python
def test_trailing_stop_extracts_instrument():
    """trailing_stop rules should extract instrument tokens for subscription."""
    from monitor.user_manager import extract_instruments_from_rules
    from monitor.models import MonitorRule

    rule = MonitorRule(
        id=1,
        user_id=999,
        name="trailing test",
        trigger_type="trailing_stop",
        trigger_config={
            "trail_percent": 15.0,
            "initial_price": 100.0,
            "highest_price": 100.0,
        },
        action_type="place_order",
        action_config={
            "symbol": "X",
            "transaction_type": "SELL",
            "quantity": 1,
            "order_type": "MARKET",
            "product": "I",
            "price": None,
        },
        instrument_token="NSE_EQ|TEST123",
    )
    instruments = extract_instruments_from_rules([rule])
    assert "NSE_EQ|TEST123" in instruments
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/monitor/test_user_manager.py -v -k "trailing" --no-header`
Expected: FAIL — trailing_stop not in the tuple check, so instrument not extracted

**Step 3: Write the fix**

In `backend/monitor/user_manager.py` line 41, change:
```python
        if rule.trigger_type in ("price", "indicator", "compound"):
```
to:
```python
        if rule.trigger_type in ("price", "indicator", "compound", "trailing_stop"):
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/monitor/test_user_manager.py -v -k "trailing" --no-header`
Expected: PASS

**Step 5: Run full user manager tests**

Run: `cd backend && python -m pytest tests/monitor/test_user_manager.py -v --no-header`
Expected: All pass

**Step 6: Commit**

```
feat(monitor): subscribe to market data for trailing_stop rules
```

---

## Task 5: Update Daemon to Handle trigger_config_update

**Files:**
- Modify: `backend/monitor/daemon.py`
- Modify: `backend/tests/monitor/test_daemon.py`

**Step 1: Write the failing tests**

Add to `backend/tests/monitor/test_daemon.py`:

```python
# ── Test: _on_tick evaluates trailing_stop rules ─────────────────────


@pytest.mark.asyncio
async def test_on_tick_evaluates_trailing_stop_rules():
    """A market tick triggers trailing_stop rule evaluation."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    rule = _make_rule(
        rule_id=1,
        user_id=999,
        trigger_type="trailing_stop",
        instrument_token="NSE_EQ|A",
        trigger_config={
            "trail_percent": 15.0,
            "initial_price": 1000.0,
            "highest_price": 1000.0,
        },
    )

    session_obj = _make_user_session(999, rules=[rule])
    daemon._user_manager = MagicMock()
    daemon._user_manager.get_session.return_value = session_obj
    daemon._rules_by_user = {999: [rule]}

    with patch.object(daemon, "_evaluate_and_execute", new_callable=AsyncMock) as mock_exec:
        await daemon._on_tick(999, "NSE_EQ|A", {"ltp": 850.0})

    mock_exec.assert_awaited_once()


# ── Test: _evaluate_and_execute persists trigger_config_update ────────


@pytest.mark.asyncio
async def test_evaluate_and_execute_persists_trigger_config_update():
    """When evaluate_rule returns trigger_config_update, daemon persists it."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    rule = _make_rule(
        rule_id=5,
        user_id=999,
        trigger_type="trailing_stop",
        trigger_config={
            "trail_percent": 15.0,
            "initial_price": 1000.0,
            "highest_price": 1000.0,
        },
    )

    updated_config = {
        "trail_percent": 15.0,
        "initial_price": 1000.0,
        "highest_price": 1100.0,
        "reference": "ltp",
    }

    not_fired_result = RuleResult(
        rule_id=5,
        fired=False,
        trigger_config_update=updated_config,
    )

    ctx = EvalContext(market_data={"ltp": 1100.0}, now=datetime.utcnow())

    with patch("monitor.daemon.evaluate_rule", return_value=not_fired_result), \
         patch("monitor.daemon.get_db_context") as mock_ctx, \
         patch("monitor.daemon.crud") as mock_crud:

        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_crud.update_rule = AsyncMock()

        await daemon._evaluate_and_execute(rule, ctx)

    # Should persist the trigger_config_update to DB
    mock_crud.update_rule.assert_awaited_once_with(
        mock_session, 5, trigger_config=updated_config
    )
    # Should update in-memory rule
    assert rule.trigger_config == updated_config


@pytest.mark.asyncio
async def test_evaluate_and_execute_no_persist_when_no_update():
    """When trigger_config_update is None, no DB write happens."""
    from monitor.daemon import MonitorDaemon

    daemon = MonitorDaemon()

    rule = _make_rule(rule_id=5, user_id=999)
    not_fired_result = RuleResult(rule_id=5, fired=False)

    ctx = EvalContext(market_data={"ltp": 50.0}, now=datetime.utcnow())

    with patch("monitor.daemon.evaluate_rule", return_value=not_fired_result), \
         patch("monitor.daemon.crud") as mock_crud:

        mock_crud.update_rule = AsyncMock()
        await daemon._evaluate_and_execute(rule, ctx)

    mock_crud.update_rule.assert_not_awaited()
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/monitor/test_daemon.py -v -k "trailing or persist" --no-header`
Expected: FAIL — daemon doesn't route trailing_stop or handle trigger_config_update

**Step 3: Implement daemon changes**

In `backend/monitor/daemon.py`:

1. In `_on_tick()` (line 185), change the trigger_type filter from:
```python
            if rule.trigger_type not in ("price", "indicator", "compound"):
```
to:
```python
            if rule.trigger_type not in ("price", "indicator", "compound", "trailing_stop"):
```

2. Rewrite `_evaluate_and_execute()` (starting at line 224) to handle `trigger_config_update`:

```python
    async def _evaluate_and_execute(
        self, rule: MonitorRule, ctx: EvalContext
    ) -> None:
        """Evaluate a rule and execute its action if fired.

        Also persists trigger_config_update (used by trailing_stop to
        track highest_price) to DB and updates the in-memory rule.
        """
        result = evaluate_rule(rule, ctx)

        # Persist trigger_config_update if present (e.g. trailing stop highest_price)
        if result.trigger_config_update is not None:
            try:
                async with get_db_context() as db_session:
                    await crud.update_rule(
                        db_session, rule.id,
                        trigger_config=result.trigger_config_update,
                    )
                # Update in-memory rule so next tick uses new values
                rule.trigger_config = result.trigger_config_update
            except Exception as e:
                logger.error(
                    "Failed to persist trigger_config_update for rule %d: %s",
                    rule.id, e,
                )

        if not result.fired:
            return

        logger.info("Rule %d (%s) FIRED", rule.id, rule.name)

        trigger_snapshot = {
            "market_data": ctx.market_data,
            "now": str(ctx.now),
        }

        async with get_db_context() as db_session:
            await self._action_executor.execute(
                rule, result, trigger_snapshot, db_session
            )
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/monitor/test_daemon.py -v -k "trailing or persist" --no-header`
Expected: PASS (3 tests)

**Step 5: Run full daemon tests**

Run: `cd backend && python -m pytest tests/monitor/test_daemon.py -v --no-header`
Expected: All pass

**Step 6: Commit**

```
feat(monitor): daemon routes trailing_stop ticks + persists highest_price updates
```

---

## Task 6: Add `add-trailing` CLI Subcommand

**Files:**
- Modify: `backend/cli-tools/nf-monitor`

**Step 1: Add the `cmd_add_trailing` function**

Add after `cmd_add_oco` (after line 302) in `backend/cli-tools/nf-monitor`:

```python
def cmd_add_trailing(args):
    """Create a trailing stop-loss rule that auto-adjusts as price rises."""
    from database.session import get_db_context
    from monitor.crud import create_rule
    from services.instruments_cache import get_instrument_key

    user_id = _get_user_id()
    symbol = validate_symbol(args.symbol)
    instrument_token = get_instrument_key(symbol)
    if not instrument_token:
        print_error(f"Could not find instrument key for {symbol}")

    # Fetch current LTP to set initial_price and highest_price
    client = init_client()

    async def _get_ltp():
        quote = await client.get_quote(symbol)
        return quote["ltp"]

    ltp = run_async(_get_ltp())
    if ltp is None:
        print_error(f"Could not fetch LTP for {symbol}")

    trail_pct = args.trail_percent
    stop_price = ltp * (1 - trail_pct / 100)
    name = args.name or f"{symbol} Trailing SL {trail_pct}%"

    trigger_config = {
        "trail_percent": trail_pct,
        "initial_price": ltp,
        "highest_price": ltp,
        "reference": args.reference or "ltp",
    }

    action_config = {
        "symbol": symbol,
        "transaction_type": "SELL",
        "quantity": args.qty,
        "order_type": "MARKET",
        "product": args.product or "I",
    }

    expires_at = None
    if args.expires:
        expires_at = _parse_expires(args.expires)

    async def _create():
        async with get_db_context() as session:
            rule = await create_rule(
                session=session,
                user_id=user_id,
                name=name,
                trigger_type="trailing_stop",
                trigger_config=trigger_config,
                action_type="place_order",
                action_config=action_config,
                instrument_token=instrument_token,
                symbol=symbol,
                max_fires=args.max_fires or 1,
                expires_at=expires_at,
            )
            return rule

    rule = run_async(_create())

    if args.json:
        print_json({
            "created": _rule_to_dict(rule),
            "stop_price": round(stop_price, 2),
            "ltp_at_creation": ltp,
        })
    else:
        print_success(f"Trailing SL rule #{rule.id}: {name}")
        print(f"  Symbol:       {symbol}")
        print(f"  Current LTP:  {ltp}")
        print(f"  Trail:        {trail_pct}%")
        print(f"  Initial Stop: {stop_price:.2f}")
        print(f"  Sell Qty:     {args.qty} ({args.product or 'I'})")
        if expires_at:
            print(f"  Expires:      {expires_at}")
```

**Step 2: Add the `init_client` import**

At the top of the file (line 18), add `init_client` to the imports from base:

Change:
```python
from base import print_error, print_json, print_success, run_async, validate_symbol  # noqa: E402
```
to:
```python
from base import init_client, print_error, print_json, print_success, run_async, validate_symbol  # noqa: E402
```

**Step 3: Add the argparse subparser**

In the `main()` function, after the `add-oco` parser block (after line 569), add:

```python
    # ---- add-trailing ----
    p_trail = sub.add_parser("add-trailing", help="Create a trailing stop-loss rule")
    p_trail.add_argument("--symbol", required=True, help="Stock symbol")
    p_trail.add_argument("--qty", type=int, required=True, help="Quantity to sell when triggered")
    p_trail.add_argument("--trail-percent", type=float, required=True,
                         help="Trail percentage below highest price (e.g. 15 = 15%%)")
    p_trail.add_argument("--product", choices=["D", "I"], default="I",
                         help="Product type: D=Delivery, I=Intraday (default: I)")
    p_trail.add_argument("--reference", default="ltp",
                         choices=["ltp", "bid", "ask", "open", "high", "low"],
                         help="Price reference (default: ltp)")
    p_trail.add_argument("--name", help="Custom rule name (auto-generated if omitted)")
    p_trail.add_argument("--max-fires", type=int, default=1, help="Max fires (default: 1)")
    p_trail.add_argument("--expires", help="Expiry: 'today' or ISO datetime")
    p_trail.add_argument("--json", action="store_true", help="Output as JSON")
```

**Step 4: Add the command dispatch**

In the `main()` function's command dispatch section (around line 620), add after the `add-oco` elif:

```python
    elif args.command == "add-trailing":
        cmd_add_trailing(args)
```

**Step 5: Update the epilog examples**

Add a trailing stop example to the epilog string (after the add-oco example):

```
  nf-monitor add-trailing --symbol RELIANCE --qty 10 --trail-percent 15 \\
    --product D --expires today --json
```

**Step 6: Verify CLI help works**

Run: `cd backend && python cli-tools/nf-monitor add-trailing --help`
Expected: Shows help text with all options

**Step 7: Commit**

```
feat(monitor): add nf-monitor add-trailing CLI command
```

---

## Task 7: Update `list` Display for Trailing Stop Rules

**Files:**
- Modify: `backend/cli-tools/nf-monitor` (the `cmd_list` function and `_rule_to_dict`)

**Step 1: Enhance list display**

In the `cmd_list` function (around line 305), after the existing table display, the trailing stop rules already display fine since they show `trigger_type` as `trailing_stop`. But we can make `_rule_to_dict` include computed `stop_price` for trailing stop rules.

In `_rule_to_dict` (line 47), add after the `"created_at"` line:

```python
        # Computed fields for trailing stop
        if rule.trigger_type == "trailing_stop":
            tc = rule.trigger_config or {}
            hp = tc.get("highest_price", 0)
            tp = tc.get("trail_percent", 0)
            d["stop_price"] = round(hp * (1 - tp / 100), 2) if hp else None
            d["highest_price"] = hp
```

Note: This requires changing the dict construction to use a variable. Refactor `_rule_to_dict`:

```python
def _rule_to_dict(rule) -> dict:
    """Convert a DB rule object to a JSON-serializable dict."""
    d = {
        "id": rule.id,
        "name": rule.name,
        "enabled": rule.enabled,
        "trigger_type": rule.trigger_type,
        "trigger_config": rule.trigger_config,
        "action_type": rule.action_type,
        "action_config": rule.action_config,
        "symbol": rule.symbol,
        "linked_trade_id": rule.linked_trade_id,
        "linked_order_id": rule.linked_order_id,
        "fire_count": rule.fire_count,
        "max_fires": rule.max_fires,
        "expires_at": str(rule.expires_at) if rule.expires_at else None,
        "fired_at": str(rule.fired_at) if rule.fired_at else None,
        "created_at": str(rule.created_at) if rule.created_at else None,
    }
    # Add computed fields for trailing stop rules
    if rule.trigger_type == "trailing_stop":
        tc = rule.trigger_config or {}
        hp = tc.get("highest_price", 0)
        tp = tc.get("trail_percent", 0)
        d["stop_price"] = round(hp * (1 - tp / 100), 2) if hp else None
        d["highest_price"] = hp
    return d
```

**Step 2: Commit**

```
feat(monitor): show computed stop_price in trailing stop JSON output
```

---

## Task 8: Run Full Test Suite

**Files:** None (verification only)

**Step 1: Run all monitor tests**

Run: `cd backend && python -m pytest tests/monitor/ -v --no-header`
Expected: All tests pass (existing + new trailing stop tests)

**Step 2: Run only trailing-stop tests as a focused check**

Run: `cd backend && python -m pytest tests/monitor/ -v -k "trailing" --no-header`
Expected: All trailing-stop specific tests pass

**Step 3: Commit all work if not already committed**

If any uncommitted changes remain, commit them.

---

## Task 9: Update Orchestrator System Prompt

The orchestrator agent needs to know about the new `add-trailing` CLI command so it can use it when users ask for trailing stop-losses.

**Files:**
- Modify: `backend/agents/orchestrator.py` — find the system prompt section that documents CLI tools

**Step 1: Find the nf-monitor documentation in the system prompt**

Search for `nf-monitor` in `backend/agents/orchestrator.py` and add the new subcommand documentation.

Add to the nf-monitor section of the system prompt:

```
  nf-monitor add-trailing --symbol SYM --qty N --trail-percent PCT [--product D|I] [--expires today] [--json]
    Create a trailing stop-loss rule. Auto-fetches current LTP for initial price.
    The daemon tracks the highest price and fires SELL when price drops trail_percent% below it.
```

**Step 2: Commit**

```
docs(orchestrator): document nf-monitor add-trailing in system prompt
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | TrailingStopTrigger model + MonitorRule Literal | `monitor/models.py` |
| 2 | Evaluator function + RuleResult extension | `monitor/rule_evaluator.py` |
| 3 | Top-level dispatch test | `test_rule_evaluator_toplevel.py` |
| 4 | UserManager instrument subscription | `monitor/user_manager.py` |
| 5 | Daemon routing + persistence | `monitor/daemon.py` |
| 6 | CLI `add-trailing` command | `cli-tools/nf-monitor` |
| 7 | Enhanced list display | `cli-tools/nf-monitor` |
| 8 | Full test suite verification | (none) |
| 9 | Orchestrator system prompt | `agents/orchestrator.py` |
