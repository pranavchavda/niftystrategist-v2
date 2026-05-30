"""Backtest job manager.

Runs backtests as background tasks against the live engine code. The HTTP
endpoint enqueues a row in ``backtest_jobs``, fires an asyncio task, and
returns the job id immediately. The frontend then either polls
``GET /api/backtest/jobs/{id}`` or subscribes to
``GET /api/backtest/jobs/{id}/stream`` (SSE) for progress + cancel.

The DB row is the source of truth for status + progress. SSE just polls
the row every 500 ms and emits change events. Single source of truth keeps
restart recovery free — a partially completed job comes back unchanged
after the API restarts (the worker dies, but the row remains; the user
will see status=running stalled, can re-trigger by deleting + recreating).

We deliberately don't use an in-process queue / pub-sub for progress —
the row is enough at the volume we expect (one user, a few jobs at a
time). If we ever need many concurrent subscribers per job, swap the
poll loop for an asyncpg LISTEN / NOTIFY broadcast.
"""
from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime
from typing import Any, AsyncIterator

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BacktestJob, utc_now
from database.session import get_db_context

logger = logging.getLogger(__name__)


# How often the SSE handler re-reads the job row. 500 ms feels live without
# punishing the DB.
_SSE_POLL_INTERVAL_S = 0.5

# How often the engine flushes its in-memory progress to DB. Engine emits
# every PROGRESS_BATCH bars (≈200); we additionally throttle here to avoid
# hammering Postgres on a 10k-bar run.
_DB_PROGRESS_THROTTLE_S = 0.5


# ──────────────────────────────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────────────────────────────


async def enqueue_job(
    *, user_id: int, kind: str, name: str, config: dict
) -> BacktestJob:
    """Insert a queued job row and return it. Caller is expected to fire
    ``asyncio.create_task(run_job(job.id))`` after this returns."""
    async with get_db_context() as session:
        job = BacktestJob(
            user_id=user_id,
            kind=kind,
            name=name or f"{kind} {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            config=config,
            status="queued",
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


async def get_job(job_id: int, user_id: int | None = None) -> BacktestJob | None:
    async with get_db_context() as session:
        stmt = select(BacktestJob).where(BacktestJob.id == job_id)
        if user_id is not None:
            stmt = stmt.where(BacktestJob.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def list_jobs(user_id: int, limit: int = 50) -> list[BacktestJob]:
    async with get_db_context() as session:
        result = await session.execute(
            select(BacktestJob)
            .where(BacktestJob.user_id == user_id)
            .order_by(BacktestJob.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def cancel_job(job_id: int, user_id: int) -> bool:
    """Set cancel_requested=true. The worker sees it on the next bar batch
    and exits cleanly. Returns True if the row was found and the cancel
    request was honoured (status was running or queued)."""
    async with get_db_context() as session:
        result = await session.execute(
            select(BacktestJob).where(
                BacktestJob.id == job_id,
                BacktestJob.user_id == user_id,
            )
        )
        job = result.scalar_one_or_none()
        if job is None:
            return False
        if job.status in ("completed", "failed", "cancelled"):
            return False
        job.cancel_requested = True
        await session.commit()
        return True


async def delete_job(job_id: int, user_id: int) -> str | None:
    """Remove a backtest job from history.

    Returns one of:
    * ``"cancelled"`` — job was running/queued, cancel requested (worker
      will exit on next checkpoint; row stays so the user sees the
      cancellation reflected). Identical to ``cancel_job``.
    * ``"deleted"`` — job was terminal (completed/failed/cancelled) and was
      hard-deleted from the table.
    * ``None`` — no matching job for this user.

    The split keeps the cancel path safe (don't yank a row out from under a
    running worker) while letting users prune stale runs from their list.
    """
    async with get_db_context() as session:
        result = await session.execute(
            select(BacktestJob).where(
                BacktestJob.id == job_id,
                BacktestJob.user_id == user_id,
            )
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        if job.status in ("completed", "failed", "cancelled"):
            await session.delete(job)
            await session.commit()
            return "deleted"
        # Active run — fall back to soft cancel.
        job.cancel_requested = True
        await session.commit()
        return "cancelled"


async def delete_terminal_jobs(user_id: int) -> int:
    """Hard-delete every terminal job for a user. Active rows (queued,
    running) are preserved so a clear-history click can't accidentally
    abandon a worker mid-replay. Returns the number of rows removed.
    """
    from sqlalchemy import delete as sa_delete
    async with get_db_context() as session:
        stmt = sa_delete(BacktestJob).where(
            BacktestJob.user_id == user_id,
            BacktestJob.status.in_(("completed", "failed", "cancelled")),
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount or 0


async def _update_progress(
    job_id: int,
    *,
    done: int | None = None,
    total: int | None = None,
    message: str | None = None,
) -> None:
    """Upsert the progress fields. Called from the worker between bar batches."""
    values: dict[str, Any] = {}
    if done is not None:
        values["progress_done"] = done
    if total is not None:
        values["progress_total"] = total
    if message is not None:
        values["progress_message"] = message
    if not values:
        return
    async with get_db_context() as session:
        await session.execute(
            update(BacktestJob).where(BacktestJob.id == job_id).values(**values)
        )
        await session.commit()


async def _check_cancel(job_id: int) -> bool:
    async with get_db_context() as session:
        result = await session.execute(
            select(BacktestJob.cancel_requested).where(BacktestJob.id == job_id)
        )
        row = result.scalar_one_or_none()
        return bool(row)


async def _mark_running(job_id: int) -> None:
    async with get_db_context() as session:
        await session.execute(
            update(BacktestJob)
            .where(BacktestJob.id == job_id)
            .values(status="running", started_at=utc_now())
        )
        await session.commit()


async def _mark_completed(job_id: int, result: dict) -> None:
    async with get_db_context() as session:
        await session.execute(
            update(BacktestJob)
            .where(BacktestJob.id == job_id)
            .values(status="completed", result=result, completed_at=utc_now())
        )
        await session.commit()


async def _mark_failed(job_id: int, message: str, tb: str) -> None:
    async with get_db_context() as session:
        await session.execute(
            update(BacktestJob)
            .where(BacktestJob.id == job_id)
            .values(
                status="failed",
                error_message=message[:1900],  # column is TEXT, but trim huge stacks
                error_traceback=tb,
                completed_at=utc_now(),
            )
        )
        await session.commit()


async def _mark_cancelled(job_id: int) -> None:
    async with get_db_context() as session:
        await session.execute(
            update(BacktestJob)
            .where(BacktestJob.id == job_id)
            .values(status="cancelled", completed_at=utc_now())
        )
        await session.commit()


# ──────────────────────────────────────────────────────────────────────
# Worker — dispatch + execute
# ──────────────────────────────────────────────────────────────────────


async def run_job(job_id: int) -> None:
    """Top-level worker entry. Fired via asyncio.create_task() from the
    POST /api/backtest/jobs handler. Owns the entire lifecycle of the row:
    running → completed | failed | cancelled.
    """
    job = await get_job(job_id)
    if job is None:
        logger.error("run_job: job %d not found", job_id)
        return
    if job.status != "queued":
        logger.warning("run_job: job %d is %s, not queued — skipping", job_id, job.status)
        return

    await _mark_running(job_id)

    try:
        # Each kind has its own handler. Engines are sync, so we offload to
        # a thread; progress / cancel callbacks bridge back to the loop via
        # asyncio.run_coroutine_threadsafe.
        result = await _dispatch(job_id, job.kind, job.user_id, job.config)
        if result is None:
            # Cancelled — handler already marked the row.
            return
        await _mark_completed(job_id, result)
    except asyncio.CancelledError:
        # If the asyncio task itself is cancelled (server shutdown etc.),
        # leave the row in 'running' so a restarted worker can clean it up.
        # We don't try to mark it cancelled here because that'd lie about
        # the user's intent.
        raise
    except Exception as e:
        logger.exception("backtest job %d failed", job_id)
        await _mark_failed(job_id, str(e), traceback.format_exc())


async def _dispatch(
    job_id: int, kind: str, user_id: int, config: dict
) -> dict | None:
    """Run the engine matching ``kind`` and return a JSON-serialisable result.

    Returns None when the job was cancelled mid-run (the handler is
    responsible for calling ``_mark_cancelled`` in that case).
    """
    if kind == "scalp":
        return await _run_scalp(job_id, user_id, config)
    if kind == "equity":
        return await _run_equity(job_id, user_id, config)
    if kind == "fno":
        return await _run_fno(job_id, user_id, config)
    raise ValueError(f"unknown backtest kind: {kind}")


# ──────────────────────────────────────────────────────────────────────
# Per-kind handlers
#
# These mirror the existing api/backtest.py logic but accept a job_id and
# wire progress + cancel through to the engines. The non-job endpoints
# (POST /run, /run-fno, /scalp) stay as-is until the frontend is fully
# migrated to jobs.
# ──────────────────────────────────────────────────────────────────────


async def _run_scalp(job_id: int, user_id: int, config: dict) -> dict | None:
    """Dispatch a scalp backtest by mode.

    options_scalp goes through ``_run_scalp_options`` (two-pass: plan → fetch
    legs in parallel → bar-replay). Equity modes stay on the single-pass
    underlying-only replay.
    """
    session_mode = config.get("session_mode", "equity_intraday")
    if session_mode == "options_scalp":
        return await _run_scalp_options(job_id, user_id, config)

    from api.upstox_oauth import get_user_upstox_token
    from services.upstox_client import UpstoxClient
    from backtesting.scalp_equity import run_scalp_equity_backtest
    from monitor.scalp_models import ScalpSessionConfig
    from api.backtest import _scalp_result_to_dict, _INTERVAL_TO_TIMEFRAME, fetch_with_warmup

    symbol = config["symbol"]
    interval = config.get("interval", "5minute")
    days = int(config.get("days", 30))

    await _update_progress(job_id, message=f"Fetching {days}d of {interval} candles for {symbol}")

    token = await get_user_upstox_token(user_id)
    if not token:
        raise ValueError("Upstox token not available — please authenticate via Settings")

    client = UpstoxClient(access_token=token, user_id=user_id)
    # Fetch the requested window plus a warm-up prefix so indicators are
    # converged before the first tradable bar.
    ohlcv, warmup_bars = await fetch_with_warmup(client, symbol, interval, days)
    if not ohlcv:
        raise ValueError(f"No historical data for {symbol}")

    candles = [
        {"timestamp": c.timestamp, "open": c.open, "high": c.high,
         "low": c.low, "close": c.close, "volume": c.volume}
        for c in ohlcv
    ]
    await _update_progress(job_id, total=len(candles), done=0,
                           message=f"Replaying {len(candles)} bars")

    tf = config.get("indicator_timeframe") or _INTERVAL_TO_TIMEFRAME[interval]
    cfg = ScalpSessionConfig(
        name=f"backtest-{symbol}",
        user_id=user_id,
        session_mode=session_mode,
        underlying=symbol,
        indicator_timeframe=tf,
        primary_indicator=config.get("primary_indicator", "utbot"),
        primary_params=config.get("primary_params"),
        confirm_indicator=config.get("confirm_indicator"),
        confirm_params=config.get("confirm_params"),
        sl_points=config.get("sl_points"),
        target_points=config.get("target_points"),
        trail_points=config.get("trail_points"),
        trail_percent=config.get("trail_percent"),
        trail_arm_points=config.get("trail_arm_points"),
        squareoff_time=config.get("squareoff_time", "15:09"),
        max_trades=int(config.get("max_trades", 20)),
        cooldown_seconds=int(config.get("cooldown_seconds", 60)),
        entry_side=config.get("entry_side", "both"),
        quantity=int(config["quantity"]),
    )

    progress, cancel = _make_callbacks(job_id)

    def _go():
        return run_scalp_equity_backtest(
            candles, cfg, symbol=symbol, interval=interval,
            slippage_bps=float(config.get("slippage_bps", 0.0)),
            progress_cb=progress, cancel_check=cancel,
            warmup_bars=warmup_bars,
        )

    result = await asyncio.to_thread(_go)
    if await _check_cancel(job_id):
        await _mark_cancelled(job_id)
        return None
    return _scalp_result_to_dict(result)


async def _run_scalp_options(job_id: int, user_id: int, config: dict) -> dict | None:
    """Options scalp backtest — plan ATM legs from underlying signal, fetch
    each leg in parallel, then bar-replay underlying + premium legs.

    Mirrors live ``ScalpSessionManager`` options_scalp flow: BUY ATM CE on
    bullish primary flip, BUY ATM PE on bearish, manage SL/target/trail in
    premium space, squareoff at cutoff. Underlying drives the signal even
    while a leg is held — opposite-flip exits use the leg's bar close.
    """
    from api.upstox_oauth import get_user_upstox_token
    from services.upstox_client import UpstoxClient
    from backtesting.scalp_options import (
        plan_atm_legs, run_scalp_options_backtest,
    )
    from monitor.scalp_models import ScalpSessionConfig
    from api.backtest import (
        _scalp_options_result_to_dict, _INTERVAL_TO_TIMEFRAME,
    )

    underlying = config.get("underlying") or config.get("symbol")
    if not underlying:
        raise ValueError("'underlying' is required for options_scalp backtest")
    expiry = config.get("expiry")
    if not expiry:
        raise ValueError("'expiry' is required for options_scalp backtest")

    interval = config.get("interval", "5minute")
    days = int(config.get("days", 5))
    lots = int(config.get("lots", 1))

    await _update_progress(
        job_id, message=f"Fetching {days}d of {interval} candles for {underlying}",
    )

    token = await get_user_upstox_token(user_id)
    if not token:
        raise ValueError("Upstox token not available — please authenticate via Settings")

    client = UpstoxClient(access_token=token, user_id=user_id)
    # Warm-up prefix on the UNDERLYING so the signal indicators are converged
    # before the first tradable bar. Option legs are fetched for the eval
    # window only (below) — they're consumed only when a position is held.
    from api.backtest import fetch_with_warmup
    ohlcv, warmup_bars = await fetch_with_warmup(client, underlying, interval, days)
    if not ohlcv:
        raise ValueError(f"No historical data for {underlying}")

    underlying_candles = [
        {"timestamp": c.timestamp, "open": c.open, "high": c.high,
         "low": c.low, "close": c.close, "volume": c.volume}
        for c in ohlcv
    ]

    tf = config.get("indicator_timeframe") or _INTERVAL_TO_TIMEFRAME[interval]
    cfg = ScalpSessionConfig(
        name=f"backtest-{underlying}",
        user_id=user_id,
        session_mode="options_scalp",
        underlying=underlying,
        expiry=expiry,
        lots=lots,
        indicator_timeframe=tf,
        primary_indicator=config.get("primary_indicator", "utbot"),
        primary_params=config.get("primary_params"),
        confirm_indicator=config.get("confirm_indicator"),
        confirm_params=config.get("confirm_params"),
        sl_points=config.get("sl_points"),
        target_points=config.get("target_points"),
        trail_points=config.get("trail_points"),
        trail_percent=config.get("trail_percent"),
        trail_arm_points=config.get("trail_arm_points"),
        squareoff_time=config.get("squareoff_time", "15:09"),
        max_trades=int(config.get("max_trades", 20)),
        cooldown_seconds=int(config.get("cooldown_seconds", 60)),
        entry_side=config.get("entry_side", "both"),
    )

    # Pass 1 — plan which option legs the replay will need.
    await _update_progress(job_id, message="Planning ATM legs from underlying signal")
    plans = await asyncio.to_thread(
        plan_atm_legs, underlying_candles, cfg, interval, warmup_bars,
    )
    if not plans:
        # No flips that pass confirm gate — return empty result so the user
        # sees diagnostics rather than an error.
        empty = await asyncio.to_thread(
            run_scalp_options_backtest,
            underlying_candles, {}, cfg,
            interval=interval,
            slippage_bps=float(config.get("slippage_bps", 0.0)),
            warmup_bars=warmup_bars,
        )
        return _scalp_options_result_to_dict(empty)

    unique_keys: dict[str, str] = {}  # instrument_key → tradingsymbol
    for p in plans:
        unique_keys.setdefault(p.instrument_key, p.tradingsymbol)

    await _update_progress(
        job_id, total=len(unique_keys), done=0,
        message=f"Fetching {len(unique_keys)} option legs in parallel",
    )

    async def _fetch_leg(ik: str) -> tuple[str, list[dict]]:
        try:
            leg_ohlcv = await client.get_historical_data(
                symbol=underlying, interval=interval, days=days,
                instrument_key=ik,
            )
            return ik, [
                {"timestamp": c.timestamp, "open": c.open, "high": c.high,
                 "low": c.low, "close": c.close, "volume": c.volume}
                for c in leg_ohlcv
            ]
        except Exception as e:
            logger.warning("scalp options: fetch failed for %s: %s", ik, e)
            return ik, []

    fetched = await asyncio.gather(*[_fetch_leg(ik) for ik in unique_keys])
    leg_candles_by_key = {ik: data for ik, data in fetched}

    if await _check_cancel(job_id):
        await _mark_cancelled(job_id)
        return None

    await _update_progress(
        job_id, total=len(underlying_candles), done=0,
        message=f"Replaying {len(underlying_candles)} bars across {len(unique_keys)} legs",
    )

    progress, cancel = _make_callbacks(job_id)

    def _go():
        return run_scalp_options_backtest(
            underlying_candles, leg_candles_by_key, cfg,
            interval=interval,
            slippage_bps=float(config.get("slippage_bps", 0.0)),
            progress_cb=progress, cancel_check=cancel,
            warmup_bars=warmup_bars,
        )

    result = await asyncio.to_thread(_go)
    if await _check_cancel(job_id):
        await _mark_cancelled(job_id)
        return None
    return _scalp_options_result_to_dict(result)


async def _run_equity(job_id: int, user_id: int, config: dict) -> dict | None:
    """Template-mode equity backtest (orb, breakout, ema-cross, etc.)."""
    from api.upstox_oauth import get_user_upstox_token
    from services.upstox_client import UpstoxClient
    from strategies.templates import get_template, list_templates
    from backtesting.engine import BacktestEngine, run_backtest_for_day
    from backtesting.metrics import compute_metrics
    from api.backtest import _split_by_day, _build_rules_for_day, _trade_to_dict

    template_name = config["template"]
    template = get_template(template_name)
    if not template:
        names = [t["name"] for t in list_templates()]
        raise ValueError(f"Unknown template: {template_name}. Available: {', '.join(names)}")

    if getattr(template, "category", "equity") != "equity":
        raise ValueError("F&O backtesting goes through kind='fno'")

    symbol = config["symbol"]
    interval = config.get("interval", "15minute")
    days = int(config.get("days", 30))

    await _update_progress(job_id, message=f"Fetching {days}d of {interval} candles for {symbol}")
    token = await get_user_upstox_token(user_id)
    if not token:
        raise ValueError("Upstox token not available")

    client = UpstoxClient(access_token=token, user_id=user_id)
    ohlcv = await client.get_historical_data(symbol, interval=interval, days=days)
    if not ohlcv:
        raise ValueError(f"No historical data for {symbol}")

    candles = [
        {"timestamp": c.timestamp, "open": c.open, "high": c.high,
         "low": c.low, "close": c.close, "volume": c.volume}
        for c in ohlcv
    ]

    params = {k: v for k, v in (config.get("params") or {}).items() if v is not None and v != ""}
    params.setdefault("capital", 100_000)
    params.setdefault("risk_percent", 2.0)
    params.setdefault("rr_ratio", 2.0)
    params.setdefault("trail_percent", 1.5)
    params.setdefault("side", "both")

    day_groups = _split_by_day(candles)
    capital = float(params.get("capital", 100_000))

    progress, cancel = _make_callbacks(job_id)
    total_days = len(day_groups)
    await _update_progress(job_id, total=total_days, done=0,
                           message=f"Replaying {total_days} trading days")

    def _go():
        trades: list = []
        for idx, (day_key, day_candles) in enumerate(day_groups.items()):
            if cancel():
                break
            if len(day_candles) < 2:
                continue
            rules = _build_rules_for_day(template, symbol, day_candles, params, template_name)
            if not rules:
                continue
            sim_candles = day_candles[1:] if template_name == "orb" else day_candles
            result = run_backtest_for_day(
                sim_candles, rules, symbol, template_name, capital,
            )
            trades.extend(result.trades)
            progress(idx + 1, total_days)
        return trades

    all_trades = await asyncio.to_thread(_go)
    if await _check_cancel(job_id):
        await _mark_cancelled(job_id)
        return None

    metrics = compute_metrics(all_trades, capital)
    equity_curve = [capital]
    for t in all_trades:
        equity_curve.append(round(equity_curve[-1] + t.pnl, 2))

    return {
        "symbol": symbol,
        "strategy": template_name,
        "days": len(day_groups),
        "interval": interval,
        "trades": [_trade_to_dict(t) for t in all_trades],
        "metrics": metrics,
        "equity_curve": equity_curve,
        "initial_capital": capital,
    }


async def _run_fno(job_id: int, user_id: int, config: dict) -> dict | None:
    """F&O multi-leg backtest (straddle, strangle, iron condor, etc.)."""
    from api.upstox_oauth import get_user_upstox_token
    from services.upstox_client import UpstoxClient
    from strategies.templates import get_template
    from backtesting.fno_engine import run_fno_backtest
    from api.backtest import _leg_trade_to_dict, _set_fno_sl_prices

    template_name = config["template"]
    template = get_template(template_name)
    if not template:
        raise ValueError(f"Unknown template: {template_name}")
    if getattr(template, "category", "equity") != "fno":
        raise ValueError("Use kind='equity' for equity strategies")

    interval = config.get("interval", "5minute")
    days = int(config.get("days", 10))

    params = {k: v for k, v in (config.get("params") or {}).items() if v is not None and v != ""}
    params.setdefault("capital", 100_000)
    underlying = params.get("underlying", "")
    if not underlying:
        raise ValueError("'underlying' is required for F&O backtest")

    plan = template.plan(underlying, params)
    if not plan.rules:
        raise ValueError("Strategy generated no rules")

    inst_keys: set[str] = set()
    for r in plan.rules:
        ik = r.action_config.get("instrument_token")
        if ik:
            inst_keys.add(ik)
    if not inst_keys:
        raise ValueError("No instrument_tokens in strategy rules")

    await _update_progress(
        job_id,
        total=len(inst_keys),
        done=0,
        message=f"Fetching {len(inst_keys)} legs in parallel",
    )
    token = await get_user_upstox_token(user_id)
    if not token:
        raise ValueError("Upstox token not available")

    client = UpstoxClient(access_token=token, user_id=user_id)

    async def _fetch_one(ik: str) -> tuple[str, list[dict]]:
        ohlcv = await client.get_historical_data(
            symbol=underlying, interval=interval, days=days, instrument_key=ik,
        )
        return ik, [
            {"timestamp": c.timestamp, "open": c.open, "high": c.high,
             "low": c.low, "close": c.close, "volume": c.volume}
            for c in ohlcv
        ]

    # Parallel fetch — was sequential in the old endpoint (audit item).
    fetched = await asyncio.gather(*[_fetch_one(ik) for ik in inst_keys])
    leg_candles = {ik: data for ik, data in fetched}
    if not any(leg_candles.values()):
        raise ValueError("No historical data for any option leg")

    if await _check_cancel(job_id):
        await _mark_cancelled(job_id)
        return None

    _set_fno_sl_prices(plan.rules, leg_candles, params)

    capital = float(params.get("capital", 100_000))
    await _update_progress(job_id, message="Running multi-leg replay")

    progress, cancel = _make_callbacks(job_id)

    def _go():
        return run_fno_backtest(
            leg_candles=leg_candles,
            rules=plan.rules,
            strategy_name=template_name,
            underlying=underlying,
            initial_capital=capital,
            progress_cb=progress,
            cancel_check=cancel,
        )

    result = await asyncio.to_thread(_go)
    if await _check_cancel(job_id):
        await _mark_cancelled(job_id)
        return None

    return {
        "strategy": result.strategy,
        "underlying": result.underlying,
        "days_traded": result.days_traded,
        "interval": interval,
        "metrics": result.metrics,
        "equity_curve": result.equity_curve,
        "initial_capital": result.initial_capital,
        "total_charges": result.total_charges,
        "day_results": [
            {
                "date": dr.date,
                "gross_pnl": dr.gross_pnl,
                "charges": dr.total_charges,
                "net_pnl": dr.net_pnl,
                "legs": [_leg_trade_to_dict(lt) for lt in dr.leg_trades],
            }
            for dr in result.day_results
        ],
        "all_leg_trades": [_leg_trade_to_dict(lt) for lt in result.all_leg_trades],
    }


# ──────────────────────────────────────────────────────────────────────
# Callback bridges (sync engine → async progress/cancel I/O)
# ──────────────────────────────────────────────────────────────────────


def _make_callbacks(job_id: int):
    """Return ``(progress_cb, cancel_check)`` callables suitable for an
    engine running in a worker thread.

    progress_cb writes to DB at most once every _DB_PROGRESS_THROTTLE_S
    seconds — engines emit far more often than that.

    cancel_check reads the row's cancel_requested flag, also throttled to
    avoid hammering the DB.
    """
    loop = asyncio.get_running_loop()
    last_progress_emit = [0.0]
    cached_cancel = [False, 0.0]  # value, last-checked-monotonic

    def progress_cb(done: int, total: int) -> None:
        import time
        now = time.monotonic()
        if now - last_progress_emit[0] < _DB_PROGRESS_THROTTLE_S:
            return
        last_progress_emit[0] = now
        # Fire-and-forget; we don't want progress writes to block the engine.
        try:
            asyncio.run_coroutine_threadsafe(
                _update_progress(job_id, done=done, total=total),
                loop,
            )
        except Exception:
            pass

    def cancel_check() -> bool:
        import time
        now = time.monotonic()
        if cached_cancel[0]:
            return True
        if now - cached_cancel[1] < _DB_PROGRESS_THROTTLE_S:
            return cached_cancel[0]
        cached_cancel[1] = now
        try:
            fut = asyncio.run_coroutine_threadsafe(_check_cancel(job_id), loop)
            cached_cancel[0] = fut.result(timeout=2.0)
        except Exception:
            cached_cancel[0] = False
        return cached_cancel[0]

    return progress_cb, cancel_check


# ──────────────────────────────────────────────────────────────────────
# SSE — emit job state changes until the job hits a terminal status
# ──────────────────────────────────────────────────────────────────────


def _job_to_event(job: BacktestJob) -> dict:
    """Snapshot what the SSE consumer needs. Excludes ``result`` until the
    terminal ``completed`` event so we don't send the whole result blob on
    every poll tick."""
    base = {
        "id": job.id,
        "kind": job.kind,
        "name": job.name,
        "status": job.status,
        "progress_done": job.progress_done,
        "progress_total": job.progress_total,
        "progress_message": job.progress_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "cancel_requested": job.cancel_requested,
    }
    if job.status == "completed":
        base["result"] = job.result
    if job.status == "failed":
        base["error_message"] = job.error_message
    return base


async def stream_job_progress(
    job_id: int, user_id: int
) -> AsyncIterator[bytes]:
    """SSE generator. Polls the row, yields ``data: {...}\\n\\n`` events on
    state changes, and exits when the job reaches a terminal status.

    Heartbeats every 15s via SSE comments (``: ping\\n\\n``) to keep
    intermediate proxies (Caddy) from closing idle connections."""
    import json
    last_snapshot: dict | None = None
    last_heartbeat = asyncio.get_event_loop().time()
    while True:
        job = await get_job(job_id, user_id=user_id)
        if job is None:
            yield b'data: {"error":"not found"}\n\n'
            return
        snapshot = _job_to_event(job)
        if snapshot != last_snapshot:
            payload = json.dumps(snapshot)
            yield f"data: {payload}\n\n".encode("utf-8")
            last_snapshot = snapshot
        if job.status in ("completed", "failed", "cancelled"):
            return
        # Heartbeat
        now = asyncio.get_event_loop().time()
        if now - last_heartbeat > 15:
            yield b": ping\n\n"
            last_heartbeat = now
        await asyncio.sleep(_SSE_POLL_INTERVAL_S)
