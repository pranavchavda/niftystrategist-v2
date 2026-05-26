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
from pydantic import BaseModel, Field

from auth import User, get_current_user, requires_permission
from api.upstox_oauth import get_user_upstox_token
from database.models import User as DBUser
from database.session import get_db_session

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
    top: int = Field(10, ge=1, le=50)
    min_score: int = Field(0, ge=0, le=8)
    deep: int = Field(15, ge=1, le=50)
    news: bool = False
    debug: Optional[str] = None  # single-symbol diagnostic mode

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
    """Run nf-morning-scan with the requested options and return parsed JSON."""
    if req.auto_deploy and not req.capital:
        raise HTTPException(400, "capital is required when auto_deploy is set")

    env = await _build_env(user)

    args: list[str] = [str(_CLI_DIR / "nf-morning-scan"), "--json",
                        "--universe", req.universe,
                        "--top", str(req.top),
                        "--min-score", str(req.min_score),
                        "--deep", str(req.deep)]
    if req.news:
        args.append("--news")
    if req.debug:
        args += ["--debug", req.debug]
    if req.auto_deploy:
        args += ["--auto-deploy", req.auto_deploy,
                 "--capital", str(req.capital),
                 "--risk-percent", str(req.risk_percent)]
        if req.dry_run:
            args.append("--dry-run")

    stdout = await _run_cli(args, env, _SCAN_TIMEOUT)
    objs = _parse_json_objects(stdout)
    if not objs:
        raise HTTPException(502, "Scanner returned no parseable output")

    result: dict[str, Any] = {"scan": objs[0]}
    # Second object (if present) is the auto-deploy summary.
    for obj in objs[1:]:
        if "auto_deploy" in obj:
            result["auto_deploy"] = obj["auto_deploy"]
    return result


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
