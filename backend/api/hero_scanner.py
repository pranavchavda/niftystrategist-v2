"""Hero Scanner API — UI-facing wrapper around the `nf-morning-scan` CLI tool.

Exposes the Morning Momentum Scanner to the frontend "Hero Scanner" page so
every CLI option (universe, top N, min-score, deep count, news, debug,
auto-deploy) is usable without the chat agent. Also relays single-stock order
placement through `nf-order` for fast manual entries from the results table.

Endpoints:
  POST /api/hero-scanner/scan    Run nf-morning-scan, return parsed JSON
  POST /api/hero-scanner/order   Place / preview an order via nf-order

Both run the CLI as a subprocess with the same env the orchestrator's
execute_bash builds (NF_ACCESS_TOKEN, NF_USER_ID, NF_ORDER_NODE_URL, venv PATH)
so behaviour is identical to the agent path.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from auth import User, get_current_user, requires_permission
from api.upstox_oauth import get_user_upstox_token
from database.models import User as DBUser
from database.session import get_db_session, get_db_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hero-scanner", tags=["hero-scanner"])

# backend/ — cli-tools/ resolve relative to here, same cwd as execute_bash.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_CLI_DIR = _BACKEND_DIR / "cli-tools"
_VENV_BIN = _BACKEND_DIR / "venv" / "bin"

# Generous: Phase 2 deep analysis + Phase 4 auto-deploy (one nf-strategy
# subprocess per candidate, ~30s each) can run several minutes for top 10.
_SCAN_TIMEOUT = 360
_ORDER_TIMEOUT = 45


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    universe: Literal["nifty50", "nifty100", "nifty500", "niftytotal"] = "nifty50"
    # Optional sector filter — comma-separated NSE Industry labels or aliases
    # (e.g. "Information Technology", "tech", "pharma"). None = all sectors.
    sector: Optional[str] = None
    top: int = Field(10, ge=1, le=50)
    min_score: int = Field(0, ge=0, le=8)
    deep: int = Field(15, ge=1, le=50)
    news: bool = False
    debug: Optional[str] = None  # single-symbol diagnostic mode

    # Signal-match — backtest each candidate across all 10 scalp indicators and
    # fold the result into scoring (untradeable eliminated, agnostic bonused),
    # adding best_signal + classification per candidate. Adds ~15-30s.
    with_signal_match: bool = False
    signal_match_days: int = Field(15, ge=5, le=60)

    # Phase 4 — auto-deploy a strategy template on the top candidates.
    auto_deploy: Optional[Literal["orb", "breakout", "mean-reversion",
                                  "vwap-bounce", "scalp"]] = None
    capital: Optional[float] = Field(None, gt=0)
    risk_percent: float = Field(2.0, gt=0, le=100)
    dry_run: bool = False


class OrderRequest(BaseModel):
    symbol: str
    action: Literal["buy", "sell"]
    quantity: int = Field(..., ge=1)
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    price: Optional[float] = Field(None, gt=0)
    product: Literal["I", "D"] = "I"  # Intraday / Delivery
    dry_run: bool = True  # default to preview — caller must opt into live


class DeploySessionRequest(BaseModel):
    """Create a live equity scalp session from a signal-match recommendation.

    The caller sends budget + risk + stop, NOT a share count — the server fetches
    a live LTP and computes the quantity, so a stale or hand-crafted client number
    can't size a live session. Quantity is the binding minimum of the budget cap
    (capital / LTP) and the risk cap (risk / stop-distance). The stop is enforced
    via ``sl_points`` (the trailing stop alone does NOT bound a losing trade — it
    only arms once price moves favorably), so the risk number is real.
    """
    symbol: str
    indicator: str
    direction: Literal["long", "short", "both"] = "both"
    budget: float = Field(..., gt=0)                       # capital cap (₹)
    risk_per_trade: Optional[float] = Field(None, gt=0)    # max ₹ loss per trade
    stop_pct: float = Field(1.0, gt=0, le=20)              # SL distance as % of price
    trail: bool = True                                      # also trail winners at stop_pct
    max_trades: int = Field(3, ge=1, le=20)
    squareoff_time: str = "15:15"
    timeframe: Literal["1m", "3m", "5m", "10m", "15m", "30m"] = "5m"
    confirm_indicator: Optional[str] = None
    # enabled=False ⇒ created paused (must be enabled on the Sessions page);
    # the UI forces an explicit choice rather than defaulting to live.
    enabled: bool = False
    dry_run: bool = True  # default to sizing preview — caller must opt into create


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

async def _build_env(user: User) -> dict[str, str]:
    """Build the CLI subprocess env: live token + user id + order node URL.

    Mirrors `agents/orchestrator.py` execute_bash. Raises 401 if the user has
    no usable Upstox token (expired with no TOTP credentials configured).
    """
    token = await get_user_upstox_token(user.id)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Upstox session expired. Re-authenticate Upstox in "
                   "Settings (or save TOTP credentials for auto-refresh).",
        )

    order_node_url: Optional[str] = None
    async with get_db_session() as db:
        db_user = await db.get(DBUser, user.id)
        if db_user:
            order_node_url = db_user.order_node_url

    env = os.environ.copy()
    env["PATH"] = f"{_VENV_BIN}:{env.get('PATH', '')}"
    env["VIRTUAL_ENV"] = str(_BACKEND_DIR / "venv")
    # Fail-closed marker for cli-tools (see base.py:init_client).
    env["NF_AGENT_SUBPROCESS"] = "1"
    env["NF_ACCESS_TOKEN"] = token
    env["NF_USER_ID"] = str(user.id)
    if order_node_url:
        env["NF_ORDER_NODE_URL"] = order_node_url
    return env


def _sse(payload: dict[str, Any]) -> str:
    """Format one SSE `data:` event (JSON payload, blank-line terminated)."""
    return f"data: {json.dumps(payload)}\n\n"


async def _run_cli_streaming(args: list[str], env: dict[str, str], timeout: int):
    """Run a cli-tools/ command as an SSE generator.

    The scan can run for several minutes (deep analysis, signal-match, news).
    A plain request would be killed by Cloudflare's ~100s proxy timeout (524,
    served as an HTML error page → the UI's `res.json()` blows up). Streaming
    `text/event-stream` keeps the connection alive: a `progress` event every
    15s feeds the proxy so it never idles out, then a terminal `result` or
    `error` event carries the payload. Mirrors the chat / backtest SSE path,
    which already survives Cloudflare on this box.
    """
    cmd = [str(_VENV_BIN / "python"), *args]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(_BACKEND_DIR),
        env=env,
    )
    comm = asyncio.ensure_future(proc.communicate())
    waited = 0
    try:
        while True:
            try:
                # shield so a heartbeat timeout doesn't cancel the subprocess.
                stdout_b, stderr_b = await asyncio.wait_for(
                    asyncio.shield(comm), timeout=15)
                break
            except asyncio.TimeoutError:
                waited += 15
                if waited >= timeout:
                    proc.kill()
                    await comm
                    yield _sse({"type": "error",
                                "detail": f"Scan timed out after {timeout}s"})
                    return
                yield _sse({"type": "progress", "elapsed": waited})
    except asyncio.CancelledError:
        # Client disconnected (closed tab / navigated away) — don't orphan the CLI.
        proc.kill()
        raise

    stdout = stdout_b.decode("utf-8", "replace")
    stderr = stderr_b.decode("utf-8", "replace")

    if proc.returncode != 0:
        msg = stderr.strip() or stdout.strip() or "CLI command failed"
        msg = msg.replace("❌", "").strip()
        logger.warning("hero-scanner CLI failed (%s): %s", args, msg[:300])
        yield _sse({"type": "error", "detail": msg[:400]})
        return

    objs = _parse_json_objects(stdout)
    if not objs:
        yield _sse({"type": "error", "detail": "Scanner returned no parseable output"})
        return

    result: dict[str, Any] = {"type": "result", "scan": objs[0]}
    # Second object (if present) is the auto-deploy summary.
    for obj in objs[1:]:
        if "auto_deploy" in obj:
            result["auto_deploy"] = obj["auto_deploy"]
    yield _sse(result)


async def _run_cli(args: list[str], env: dict[str, str], timeout: int) -> str:
    """Run a cli-tools/ command, return stdout. Raises HTTPException on error."""
    cmd = [str(_VENV_BIN / "python"), *args]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(_BACKEND_DIR),
        env=env,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise HTTPException(504, f"CLI timed out after {timeout}s")

    stdout = stdout_b.decode("utf-8", "replace")
    stderr = stderr_b.decode("utf-8", "replace")

    if proc.returncode != 0:
        # nf tools print_error writes "❌ ..." to stderr and exits 1.
        msg = stderr.strip() or stdout.strip() or "CLI command failed"
        msg = msg.replace("❌", "").strip()
        logger.warning("hero-scanner CLI failed (%s): %s", args, msg[:300])
        raise HTTPException(502, msg[:400])

    return stdout


def _parse_json_objects(text: str) -> list[dict[str, Any]]:
    """Parse one or more concatenated JSON objects from CLI stdout.

    `nf-morning-scan --json --auto-deploy` prints two separate objects (scan
    result, then deploy result). raw_decode walks them one at a time.
    """
    decoder = json.JSONDecoder()
    objs: list[dict[str, Any]] = []
    idx = 0
    n = len(text)
    while idx < n:
        while idx < n and text[idx] in " \t\r\n":
            idx += 1
        if idx >= n:
            break
        try:
            obj, end = decoder.raw_decode(text, idx)
        except json.JSONDecodeError:
            break
        objs.append(obj)
        idx = end
    return objs


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/scan")
async def run_scan(req: ScanRequest, user: User = Depends(get_current_user)):
    """Run nf-morning-scan and stream the result over SSE.

    Returns `text/event-stream`: zero or more `{"type": "progress", ...}`
    heartbeat events while the CLI runs, then exactly one terminal event —
    `{"type": "result", "scan": {...}}` or `{"type": "error", "detail": ...}`.
    Streaming (not a single blocking JSON response) is what keeps Cloudflare's
    ~100s proxy timeout from 524-ing long scans. Setup errors (bad request,
    expired token) still surface as ordinary JSON HTTP errors before the
    stream opens, so the frontend's `!res.ok` branch handles them.
    """
    if req.auto_deploy and not req.capital:
        raise HTTPException(400, "capital is required when auto_deploy is set")

    # Resolve the token/env up front so a 401 is a normal JSON error, not an
    # SSE event the client would have to special-case.
    env = await _build_env(user)

    args: list[str] = [str(_CLI_DIR / "nf-morning-scan"), "--json",
                        "--universe", req.universe,
                        "--top", str(req.top),
                        "--min-score", str(req.min_score),
                        "--deep", str(req.deep)]
    if req.sector:
        args += ["--sector", req.sector]
    if req.news:
        args.append("--news")
    if req.with_signal_match:
        args += ["--with-signal-match", "--signal-match-days", str(req.signal_match_days)]
    if req.debug:
        args += ["--debug", req.debug]
    if req.auto_deploy:
        args += ["--auto-deploy", req.auto_deploy,
                 "--capital", str(req.capital),
                 "--risk-percent", str(req.risk_percent)]
        if req.dry_run:
            args.append("--dry-run")

    return StreamingResponse(
        _run_cli_streaming(args, env, _SCAN_TIMEOUT),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/order")
async def place_order(
    req: OrderRequest,
    user: User = Depends(requires_permission("settings.access")),
):
    """Place (or dry-run preview) an order via nf-order.

    Gated by `settings.access` (the permission the trading routes use) so a
    bare JWT can't fire live orders by POSTing `dry_run: false` directly —
    the frontend route guard alone is not a server-side control.

    The Hero Scanner UI calls this twice per order: once with dry_run=true to
    show a preview, then once with dry_run=false on explicit confirmation.
    """
    if req.order_type == "LIMIT" and req.price is None:
        raise HTTPException(400, "Limit orders require a price")

    env = await _build_env(user)

    args: list[str] = [str(_CLI_DIR / "nf-order"), req.action,
                        req.symbol.upper(), str(req.quantity),
                        "--type", req.order_type,
                        "--product", req.product,
                        "--json"]
    if req.price is not None:
        args += ["--price", str(req.price)]
    if req.dry_run:
        args.append("--dry-run")

    stdout = await _run_cli(args, env, _ORDER_TIMEOUT)
    objs = _parse_json_objects(stdout)
    if not objs:
        raise HTTPException(502, "Order command returned no parseable output")
    return objs[0]


@router.post("/deploy-session")
async def deploy_session(
    req: DeploySessionRequest,
    user: User = Depends(requires_permission("settings.access")),
):
    """Size and (optionally) create a live equity scalp session.

    Two-step like the order flow: call with ``dry_run=true`` to get the
    server-computed sizing (live LTP → quantity, SL, est. loss), show it, then
    ``dry_run=false`` to actually create the session. Gated by ``settings.access``
    so a bare JWT can't stand up a live trading session by POSTing directly.

    The session is created with ``enabled`` exactly as requested — the UI makes
    the user choose "create paused" vs "create & start"; we never silently go live.
    """
    from services.instruments_cache import get_instrument_key
    from monitor import scalp_crud

    symbol = req.symbol.upper()
    instrument_key = get_instrument_key(symbol)
    if not instrument_key:
        raise HTTPException(400, f"Equity symbol '{symbol}' not found in instruments cache")

    # Live LTP — single source of truth for sizing.
    from api.cockpit import get_market_data_client
    try:
        client = await get_market_data_client(user)
        quote = await client.get_quote(symbol)
        ltp = float(quote.get("ltp") or 0)
    except Exception as e:
        logger.warning("deploy-session: quote failed for %s: %s", symbol, e)
        raise HTTPException(502, f"Could not fetch a live price for {symbol}: {e}")
    if ltp <= 0:
        raise HTTPException(502, f"No live price available for {symbol}")

    # Sizing: binding minimum of the budget cap and the risk cap.
    stop_distance = ltp * req.stop_pct / 100.0
    qty_budget = int(req.budget // ltp)
    if qty_budget < 1:
        raise HTTPException(
            400, f"Budget ₹{req.budget:,.0f} is too small for one share of {symbol} at ₹{ltp:,.2f}")

    qty = qty_budget
    binding = "budget"
    qty_risk: Optional[int] = None
    if req.risk_per_trade is not None and stop_distance > 0:
        qty_risk = int(req.risk_per_trade // stop_distance)
        if qty_risk < 1:
            raise HTTPException(
                400,
                f"Risk ₹{req.risk_per_trade:,.0f} at a {req.stop_pct}% stop "
                f"(₹{stop_distance:,.2f}/share) is too small for one share")
        if qty_risk < qty:
            qty, binding = qty_risk, "risk"

    sl_points = round(stop_distance, 2)
    est_loss_per_trade = round(qty * sl_points, 2)
    sizing = {
        "ltp": round(ltp, 2),
        "quantity": qty,
        "qty_from_budget": qty_budget,
        "qty_from_risk": qty_risk,
        "binding_constraint": binding,
        "notional": round(qty * ltp, 2),
        "stop_pct": req.stop_pct,
        "sl_points": sl_points,
        "est_max_loss_per_trade": est_loss_per_trade,
        "est_max_loss_day": round(est_loss_per_trade * req.max_trades, 2),
        "max_trades": req.max_trades,
    }

    if req.dry_run:
        return {"sizing": sizing, "created": None}

    # Create. primary_params=None + timeframe match the scan basis so the live
    # session is the same config the recommendation was backtested on.
    name = f"signal-{symbol}-{req.indicator}"
    async with get_db_context() as session:
        row = await scalp_crud.create_session(
            db=session,
            user_id=user.id,
            name=name,
            session_mode="equity_intraday",
            underlying=symbol,
            underlying_instrument_token=instrument_key,
            expiry="",
            quantity=qty,
            product="I",
            indicator_timeframe=req.timeframe,
            primary_indicator=req.indicator,
            primary_params=None,
            confirm_indicator=req.confirm_indicator,
            sl_points=sl_points,
            trail_percent=(req.stop_pct if req.trail else None),
            squareoff_time=req.squareoff_time,
            entry_side=req.direction,
            max_trades=req.max_trades,
            cooldown_seconds=60,
            enabled=req.enabled,
        )
        created = {
            "id": row.id,
            "name": row.name,
            "enabled": row.enabled,
            "underlying": row.underlying,
            "quantity": row.quantity,
            "primary_indicator": row.primary_indicator,
            "entry_side": getattr(row, "entry_side", req.direction),
            "sl_points": row.sl_points,
            "trail_percent": row.trail_percent,
            "max_trades": row.max_trades,
            "state": row.state,
        }
    return {"sizing": sizing, "created": created}
