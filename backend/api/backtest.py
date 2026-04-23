"""Backtest API — run strategy backtests against historical data."""

import asyncio
import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import User, get_current_user
from api.upstox_oauth import get_user_upstox_token
from services.upstox_client import UpstoxClient
from strategies.templates import list_templates, get_template
from backtesting.engine import BacktestEngine, run_backtest_for_day
from backtesting.fno_engine import run_fno_backtest, LegTrade
from backtesting.metrics import compute_metrics
from backtesting.scalp_equity import (
    run_scalp_equity_backtest,
    ScalpBacktestResult,
)
from monitor.scalp_models import ScalpSessionConfig, SessionMode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class BacktestRequest(BaseModel):
    template: str
    symbol: str
    params: dict = {}
    days: int = 30
    interval: str = "15minute"


class FnOBacktestRequest(BaseModel):
    template: str
    params: dict = {}
    days: int = 10
    interval: str = "5minute"


class ScalpBacktestRequest(BaseModel):
    """Scalp-style equity backtest request.

    Mirrors ScalpSessionConfig so a live session can be pasted in, a
    backtest run, and a "save as session" performed with zero field
    remapping.
    """
    symbol: str
    days: int = 30
    interval: str = "5minute"
    session_mode: str = "equity_intraday"

    primary_indicator: str = "utbot"
    primary_params: dict | None = None
    confirm_indicator: str | None = None
    confirm_params: dict | None = None
    indicator_timeframe: str | None = None  # if unset, derived from interval

    sl_points: float | None = None
    target_points: float | None = None
    trail_points: float | None = None
    trail_percent: float | None = None
    trail_arm_points: float | None = None
    squareoff_time: str = "15:15"
    max_trades: int = 20
    cooldown_seconds: int = 60
    quantity: int
    slippage_bps: float = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_by_day(candles: list[dict]) -> dict[str, list[dict]]:
    """Split candles into per-day groups."""
    days: dict[str, list[dict]] = defaultdict(list)
    for c in candles:
        ts = BacktestEngine._parse_timestamp(c["timestamp"])
        day_key = ts.strftime("%Y-%m-%d")
        days[day_key].append(c)
    return dict(sorted(days.items()))


def _build_rules_for_day(
    template,
    symbol: str,
    day_candles: list[dict],
    params: dict,
    strategy_name: str,
) -> list:
    """Build strategy rules for a single day, auto-deriving per-day params.

    Each strategy needs certain price-based params that vary daily.  When users
    backtest, they can't supply a fixed ``entry`` or ``sl`` — we derive them
    from the day's opening candles so the backtest is realistic.
    """
    if not day_candles:
        return []

    day_params = dict(params)
    day_open = day_candles[0]["open"]
    day_high = day_candles[0]["high"]
    day_low = day_candles[0]["low"]
    sl_pct = float(day_params.get("sl_pct", day_params.get("risk_percent", 2.0)))

    if strategy_name == "orb":
        # Use first candle as the opening range
        if "range_high" not in day_params or "range_low" not in day_params:
            day_params["range_high"] = day_high
            day_params["range_low"] = day_low

    elif strategy_name == "breakout":
        # Derive entry/sl from opening candle + percentage offsets
        if "entry" not in day_params or "sl" not in day_params:
            entry_pct = float(day_params.get("entry_pct", 0.5))
            day_params["entry"] = round(day_open * (1 + entry_pct / 100), 2)
            day_params["sl"] = round(day_params["entry"] * (1 - sl_pct / 100), 2)

    elif strategy_name == "mean-reversion":
        # SL derived from open price + percentage
        if "sl" not in day_params:
            side = day_params.get("side", "long")
            if side == "short":
                day_params["sl"] = round(day_open * (1 + sl_pct / 100), 2)
            else:
                day_params["sl"] = round(day_open * (1 - sl_pct / 100), 2)

    elif strategy_name == "vwap-bounce":
        # Approximate VWAP as open price; derive SL from percentage
        if "vwap" not in day_params:
            # Compute simple VWAP from available candles (sum of hlc/3 * vol / sum vol)
            total_vol = sum(c["volume"] for c in day_candles)
            if total_vol > 0:
                day_params["vwap"] = round(
                    sum(((c["high"] + c["low"] + c["close"]) / 3) * c["volume"] for c in day_candles) / total_vol, 2
                )
            else:
                day_params["vwap"] = round(day_open, 2)
        if "sl" not in day_params:
            day_params["sl"] = round(day_open * (1 - sl_pct / 100), 2)

    elif strategy_name == "scalp":
        # Derive entry/sl from opening price + percentage
        if "entry" not in day_params or "sl" not in day_params:
            entry_pct = float(day_params.get("entry_pct", 0.3))
            day_params["entry"] = round(day_open * (1 + entry_pct / 100), 2)
            day_params["sl"] = round(day_params["entry"] * (1 - sl_pct / 100), 2)

    try:
        plan = template.plan(symbol, day_params)
        return plan.rules
    except ValueError:
        return []


def _trade_to_dict(t) -> dict:
    return {
        "symbol": t.symbol,
        "side": t.side,
        "entry_price": t.entry_price,
        "entry_time": str(t.entry_time),
        "exit_price": t.exit_price,
        "exit_time": str(t.exit_time),
        "quantity": t.quantity,
        "pnl": t.pnl,
        "pnl_pct": t.pnl_pct,
        "exit_reason": t.exit_reason,
        "holding_minutes": t.holding_minutes,
    }


# ---------------------------------------------------------------------------
# GET /api/backtest/templates — equity templates only
# ---------------------------------------------------------------------------
# Params that are auto-derived per-day during backtesting — move from required to optional
_BACKTEST_AUTO_DERIVED = {"range_high", "range_low", "entry", "sl", "vwap"}

# Extra optional params exposed for backtest tuning
_BACKTEST_EXTRA_OPTIONAL = {
    "breakout": {"entry_pct": 0.5, "sl_pct": 2.0},
    "scalp": {"entry_pct": 0.3, "sl_pct": 2.0},
    "mean-reversion": {"sl_pct": 2.0},
    "vwap-bounce": {"sl_pct": 2.0},
}


@router.get("/templates")
async def api_backtest_templates():
    """List all templates available for backtesting (equity + F&O).

    Adjusts required/optional params: price-level params (entry, sl, vwap)
    are auto-derived per day for equity, so they become optional.
    """
    all_templates = list_templates()
    result = []
    for t in all_templates:
        t = dict(t)  # copy
        if t.get("category", "equity") == "equity":
            # Move auto-derived params to optional
            auto = _BACKTEST_AUTO_DERIVED & set(t["required_params"])
            if auto:
                t["required_params"] = [p for p in t["required_params"] if p not in auto]
                for p in auto:
                    t["optional_params"].setdefault(p, None)
            # Add extra backtest-specific optional params
            extras = _BACKTEST_EXTRA_OPTIONAL.get(t["name"], {})
            for k, v in extras.items():
                t["optional_params"].setdefault(k, v)
        result.append(t)
    return {"templates": result}


# ---------------------------------------------------------------------------
# POST /api/backtest/run — run a backtest
# ---------------------------------------------------------------------------
@router.post("/run")
async def api_run_backtest(
    body: BacktestRequest,
    user: User = Depends(get_current_user),
):
    """Run a backtest for a strategy template against historical data."""
    # Validate template
    template = get_template(body.template)
    if not template:
        names = [t["name"] for t in list_templates()]
        raise HTTPException(
            status_code=400,
            detail=f"Unknown template: {body.template}. Available: {', '.join(names)}",
        )

    if getattr(template, "category", "equity") != "equity":
        raise HTTPException(status_code=400, detail="F&O backtesting is not yet supported")

    # Validate interval
    valid_intervals = ["1minute", "5minute", "15minute", "30minute"]
    if body.interval not in valid_intervals:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval. Choose from: {', '.join(valid_intervals)}",
        )

    # Get Upstox token for historical data
    token = await get_user_upstox_token(user.id)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Upstox token not available. Please authenticate via Settings.",
        )

    # Fetch historical candles
    try:
        client = UpstoxClient(access_token=token, user_id=user.id)
        ohlcv_list = await client.get_historical_data(
            body.symbol, interval=body.interval, days=body.days,
        )
    except Exception as e:
        logger.error(f"Failed to fetch historical data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch historical data: {e}")

    if not ohlcv_list:
        raise HTTPException(status_code=404, detail=f"No historical data for {body.symbol}")

    # Convert to dicts
    candles = [
        {
            "timestamp": c.timestamp,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        }
        for c in ohlcv_list
    ]

    # Set default params — use `or` to also override empty strings / None / 0
    params = dict(body.params)
    # Remove empty/null values so defaults apply
    params = {k: v for k, v in params.items() if v is not None and v != ""}
    params.setdefault("capital", 100_000)
    params.setdefault("risk_percent", 2.0)
    params.setdefault("rr_ratio", 2.0)
    params.setdefault("trail_percent", 1.5)
    params.setdefault("side", "both")

    # Split by day and run — offloaded to a worker thread so the sync
    # backtest loop doesn't block the event loop (single-worker uvicorn).
    day_groups = _split_by_day(candles)
    capital = params.get("capital", 100_000)

    def _run_all_days() -> list:
        trades: list = []
        for day_key, day_candles in day_groups.items():
            if len(day_candles) < 2:
                continue
            rules = _build_rules_for_day(
                template, body.symbol, day_candles, params, body.template,
            )
            if not rules:
                continue
            sim_candles = day_candles[1:] if body.template == "orb" else day_candles
            result = run_backtest_for_day(
                sim_candles, rules, body.symbol, body.template, capital,
            )
            trades.extend(result.trades)
        return trades

    all_trades = await asyncio.to_thread(_run_all_days)

    metrics = compute_metrics(all_trades, capital)

    # Build equity curve for charting
    equity_curve = [capital]
    for t in all_trades:
        equity_curve.append(round(equity_curve[-1] + t.pnl, 2))

    return {
        "symbol": body.symbol,
        "strategy": body.template,
        "days": len(day_groups),
        "interval": body.interval,
        "trades": [_trade_to_dict(t) for t in all_trades],
        "metrics": metrics,
        "equity_curve": equity_curve,
        "initial_capital": capital,
    }


# ---------------------------------------------------------------------------
# POST /api/backtest/run-fno — run an F&O multi-leg backtest
# ---------------------------------------------------------------------------

def _leg_trade_to_dict(lt: LegTrade) -> dict:
    return {
        "instrument_key": lt.instrument_key,
        "label": lt.label,
        "side": lt.side,
        "quantity": lt.quantity,
        "entry_price": lt.entry_price,
        "exit_price": lt.exit_price,
        "entry_time": str(lt.entry_time),
        "exit_time": str(lt.exit_time),
        "exit_reason": lt.exit_reason,
        "gross_pnl": lt.gross_pnl,
        "charges": lt.charges,
        "net_pnl": lt.net_pnl,
        "holding_minutes": lt.holding_minutes,
    }


@router.post("/run-fno")
async def api_run_fno_backtest(
    body: FnOBacktestRequest,
    user: User = Depends(get_current_user),
):
    """Run an F&O multi-leg backtest.

    Fetches historical candles for each option instrument leg independently,
    then runs the multi-leg engine with per-leg charge deduction.
    """
    template = get_template(body.template)
    if not template:
        raise HTTPException(status_code=400, detail=f"Unknown template: {body.template}")

    if getattr(template, "category", "equity") != "fno":
        raise HTTPException(status_code=400, detail="Use /api/backtest/run for equity strategies")

    valid_intervals = ["1minute", "5minute", "15minute", "30minute"]
    if body.interval not in valid_intervals:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval. Choose from: {', '.join(valid_intervals)}",
        )

    token = await get_user_upstox_token(user.id)
    if not token:
        raise HTTPException(status_code=401, detail="Upstox token not available.")

    # Clean params
    params = {k: v for k, v in body.params.items() if v is not None and v != ""}
    params.setdefault("capital", 100_000)

    # Generate strategy rules (resolves instrument_keys from cache)
    underlying = params.get("underlying", "")
    if not underlying:
        raise HTTPException(status_code=400, detail="'underlying' is required for F&O backtest")

    try:
        plan = template.plan(underlying, params)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not plan.rules:
        raise HTTPException(status_code=400, detail="Strategy generated no rules")

    # Collect unique instrument_keys from rules
    inst_keys: set[str] = set()
    for r in plan.rules:
        ik = r.action_config.get("instrument_token")
        if ik:
            inst_keys.add(ik)

    if not inst_keys:
        raise HTTPException(status_code=400, detail="No instrument_tokens found in strategy rules")

    # Fetch historical candles for each leg
    client = UpstoxClient(access_token=token, user_id=user.id)
    leg_candles: dict[str, list[dict]] = {}

    for ik in inst_keys:
        try:
            ohlcv = await client.get_historical_data(
                symbol=underlying,
                interval=body.interval,
                days=body.days,
                instrument_key=ik,
            )
            leg_candles[ik] = [
                {
                    "timestamp": c.timestamp,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                }
                for c in ohlcv
            ]
            logger.info(f"Fetched {len(ohlcv)} candles for {ik}")
        except Exception as e:
            logger.error(f"Failed to fetch candles for {ik}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch historical data for instrument {ik}: {e}",
            )

    if not any(leg_candles.values()):
        raise HTTPException(status_code=404, detail="No historical data for any option leg")

    # Set SL prices for short straddle/strangle (based on first candle premium)
    _set_fno_sl_prices(plan.rules, leg_candles, params)

    # Run the F&O backtest engine — offload to worker thread so the
    # sync engine loop doesn't block the event loop.
    capital = float(params.get("capital", 100_000))
    result = await asyncio.to_thread(
        run_fno_backtest,
        leg_candles=leg_candles,
        rules=plan.rules,
        strategy_name=body.template,
        underlying=underlying,
        initial_capital=capital,
    )

    # Serialize day results
    day_summaries = []
    for dr in result.day_results:
        day_summaries.append({
            "date": dr.date,
            "gross_pnl": dr.gross_pnl,
            "charges": dr.total_charges,
            "net_pnl": dr.net_pnl,
            "legs": [_leg_trade_to_dict(lt) for lt in dr.leg_trades],
        })

    return {
        "strategy": result.strategy,
        "underlying": result.underlying,
        "days_traded": result.days_traded,
        "interval": body.interval,
        "metrics": result.metrics,
        "equity_curve": result.equity_curve,
        "initial_capital": result.initial_capital,
        "total_charges": result.total_charges,
        "day_results": day_summaries,
        "all_leg_trades": [_leg_trade_to_dict(lt) for lt in result.all_leg_trades],
    }


_INTERVAL_TO_TIMEFRAME = {
    "1minute": "1m", "3minute": "3m", "5minute": "5m", "10minute": "10m",
    "15minute": "15m", "30minute": "30m", "day": "1d",
}


# ---------------------------------------------------------------------------
# POST /api/backtest/scalp — scalp-style equity backtest
# ---------------------------------------------------------------------------

def _scalp_trade_to_dict(t) -> dict:
    return {
        "symbol": t.symbol,
        "side": t.side,
        "entry_price": t.entry_price,
        "entry_time": str(t.entry_time),
        "exit_price": t.exit_price,
        "exit_time": str(t.exit_time),
        "quantity": t.quantity,
        "pnl": t.pnl,
        "pnl_pct": t.pnl_pct,
        "exit_reason": t.exit_reason,
        "holding_minutes": t.holding_minutes,
        "gross_pnl": getattr(t, "_gross_pnl", t.pnl),
        "charges": getattr(t, "_charges_total", 0.0),
    }


def _scalp_result_to_dict(r: ScalpBacktestResult) -> dict:
    # Equity curve using net P&L per trade.
    initial = r.config.get("quantity", 1) * (r.trades[0].entry_price if r.trades else 0)
    initial = initial or 100_000
    curve = [round(initial, 2)]
    for t in r.trades:
        curve.append(round(curve[-1] + t.pnl, 2))

    return {
        "symbol": r.symbol,
        "session_mode": r.session_mode,
        "interval": r.interval,
        "days": r.days,
        "candle_count": r.candle_count,
        "session_days": r.session_days,
        "config": r.config,
        "trades": [_scalp_trade_to_dict(t) for t in r.trades],
        "metrics": r.metrics,
        "metrics_net": r.metrics_net,
        "charges_total": r.charges_total,
        "slippage_total": r.slippage_total,
        "equity_curve": curve,
        "initial_capital": initial,
        "diagnostics": {
            "intra_bar_ambiguity": r.intra_bar_ambiguity,
            "primary_flips": r.primary_flips,
            "confirm_blocks": r.confirm_blocks,
            "cooldown_blocks": r.cooldown_blocks,
            "max_trades_blocks": r.max_trades_blocks,
            "squareoff_exits": r.squareoff_exits,
        },
    }


@router.post("/scalp")
async def api_run_scalp_backtest(
    body: ScalpBacktestRequest,
    user: User = Depends(get_current_user),
):
    """Run a scalp-style equity backtest using the same state machine as the
    live scalper. Accepts the same config shape as a ScalpSession so results
    can be converted directly into a live session."""
    if body.session_mode not in (
        SessionMode.EQUITY_INTRADAY.value, SessionMode.EQUITY_SWING.value,
    ):
        raise HTTPException(
            status_code=400,
            detail="session_mode must be equity_intraday or equity_swing",
        )
    if body.interval not in _INTERVAL_TO_TIMEFRAME:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported interval: {body.interval}",
        )
    if body.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be > 0")

    token = await get_user_upstox_token(user.id)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Upstox token not available. Authenticate via Settings.",
        )

    # Fetch historical candles
    try:
        client = UpstoxClient(access_token=token, user_id=user.id)
        ohlcv = await client.get_historical_data(
            body.symbol, interval=body.interval, days=body.days,
        )
    except Exception as e:
        logger.error(f"scalp backtest: failed to fetch candles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch historical data: {e}")

    if not ohlcv:
        raise HTTPException(status_code=404, detail=f"No historical data for {body.symbol}")

    candles = [
        {
            "timestamp": c.timestamp, "open": c.open, "high": c.high,
            "low": c.low, "close": c.close, "volume": c.volume,
        }
        for c in ohlcv
    ]

    # Build config
    tf = body.indicator_timeframe or _INTERVAL_TO_TIMEFRAME[body.interval]
    cfg = ScalpSessionConfig(
        name=f"backtest-{body.symbol}",
        user_id=user.id,
        session_mode=body.session_mode,
        underlying=body.symbol,
        indicator_timeframe=tf,
        primary_indicator=body.primary_indicator,
        primary_params=body.primary_params,
        confirm_indicator=body.confirm_indicator,
        confirm_params=body.confirm_params,
        sl_points=body.sl_points,
        target_points=body.target_points,
        trail_points=body.trail_points,
        trail_percent=body.trail_percent,
        trail_arm_points=body.trail_arm_points,
        squareoff_time=body.squareoff_time,
        max_trades=body.max_trades,
        cooldown_seconds=body.cooldown_seconds,
        quantity=body.quantity,
    )

    # Run — offload to a worker thread so the sync loop doesn't block the event loop.
    try:
        result = await asyncio.to_thread(
            run_scalp_equity_backtest,
            candles, cfg,
            symbol=body.symbol, interval=body.interval,
            slippage_bps=body.slippage_bps,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _scalp_result_to_dict(result)


def _set_fno_sl_prices(
    rules: list,
    leg_candles: dict[str, list[dict]],
    params: dict,
) -> None:
    """Set SL trigger prices for F&O rules that have price=0 (placeholder).

    For short straddle/strangle, SL is set to entry_premium * (1 + sl_percent/100).
    We use the first candle's open as a proxy for entry premium.
    """
    sl_pct = float(params.get("sl_percent", 30))
    for r in rules:
        if r.trigger_type != "price":
            continue
        tc = r.trigger_config
        if tc.get("price", 0) == 0 and tc.get("condition") == "gte":
            # Find the first candle for this leg to get entry premium
            inst_key = r.action_config.get("instrument_token", "")
            candles = leg_candles.get(inst_key, [])
            if candles:
                entry_premium = candles[0]["open"]
                tc["price"] = round(entry_premium * (1 + sl_pct / 100), 2)
                logger.info(
                    f"Set SL price for {r.name}: entry_premium={entry_premium}, "
                    f"SL={tc['price']} (+{sl_pct}%)"
                )
