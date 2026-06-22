"""Backtest sweep orchestration — the engine behind ``nf-backtest-matrix``.

Where ``nf-backtest-scan`` ranks one indicator per stock in-sample, this module
runs a *grid* of combos per symbol — (primary × confirm × interval × exit-variant
× side) — through the same in-process scalp engine, then evaluates each combo with
the statistically-rigorous ``backtesting.ranking`` layers (hard gates → score →
walk-forward train/validate). The deliverable is an out-of-sample-validated
deployment plan, not an in-hindsight one.

It's the importable sibling of the ``nf-backtest-matrix`` CLI (a script without a
``.py`` extension, hence un-importable) — all reusable machinery lives here so it
can be unit-tested with synthetic candles and never touch the network in tests.

Warm-up handling, candle fetch, quantity sizing, and the on-disk cache mirror
``nf-backtest-scan`` (and, transitively, ``api/backtest.py``). Keep
``_WARMUP_TARGET_BARS`` / ``_TF_BARS_PER_DAY`` in sync with those if they change.

KEY INVARIANT: one engine run per combo over the FULL candle window. Train/validate
is a *partition of the resulting trades* by entry date (``ranking.split_trades``),
NOT two separate engine runs — so the validation slice sees the exact same fills
the selection slice did, just on later days.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from backtesting.htf_trend import compute_daily_trend, make_entry_gate
from backtesting.metrics import plausibility_warnings
from backtesting.ranking import (
    _pf_to_float,
    apply_gates,
    combo_score,
    confidence_label,
    gate_summary,
    plateau_flags,
    split_trades,
    validate_combo,
)
from backtesting.scalp_equity import run_scalp_equity_backtest
from backtesting.simulator import Trade
from monitor.scalp_models import ScalpSessionConfig

# ---------------------------------------------------------------------------
# Constants (mirror nf-backtest-scan / api/backtest.py)
# ---------------------------------------------------------------------------

ALL_INDICATORS = [
    "utbot", "halftrend", "ssl_hybrid", "supertrend", "ema_crossover",
    "macd", "qqe_mod", "hilega_milega", "volume_spike", "renko",
]

_INTERVAL_TO_TIMEFRAME = {
    "1minute": "1m", "3minute": "3m", "5minute": "5m", "10minute": "10m",
    "15minute": "15m", "30minute": "30m", "day": "1d",
}

IST = timezone(timedelta(hours=5, minutes=30))

# Warm-up buffer — replicated verbatim from api/backtest.py / nf-backtest-scan so
# this tool's numbers match the /scalp endpoint. Stateful/recursive indicators
# (UTBot, SuperTrend, HalfTrend, SSL Hybrid) need ~150-200 bars to converge; we
# fetch extra history before the requested window and tell the engine to skip it
# (compute-only) so trades fire only in-window but against converged state.
# Keep in sync with api/backtest.py if that changes.
_WARMUP_TARGET_BARS = 200
_TF_BARS_PER_DAY = {
    "1minute": 375, "3minute": 125, "5minute": 75, "10minute": 37,
    "15minute": 25, "30minute": 13, "day": 1,
}

_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cli-tools", ".backtest-cache",
)

# Fraction of distinct in-window trading days held out for walk-forward
# validation — the last ~1/3 of dates. Train on the earlier 2/3, confirm on the
# later 1/3.
_VALIDATION_DAY_FRACTION = 1.0 / 3.0

# Extra calendar days of DAILY candles fetched ahead of the backtest window so
# the HTF trend indicators have warm-up (EMA50 needs ≥50 trading days ≈ 70
# calendar; 120 gives comfortable slack including holidays).
_HTF_DAILY_EXTRA_DAYS = 120


def _warmup_fetch_days(interval: str) -> int:
    """Extra calendar days to fetch so the prefix yields >= _WARMUP_TARGET_BARS bars."""
    bpd = _TF_BARS_PER_DAY.get(interval, 75)
    trading_days = -(-_WARMUP_TARGET_BARS // bpd)  # ceil
    return max(2, round(trading_days * 7 / 5) + 3)


# ---------------------------------------------------------------------------
# Candle fetch (warm-up aware, mirrors nf-backtest-scan / the endpoint)
# ---------------------------------------------------------------------------

async def fetch_candles_with_warmup(client, symbol: str, interval: str, days: int,
                                     end_offset_days: int = 0):
    """Return (candles, warmup_bars). Mirrors nf-backtest-scan / api.backtest.

    ``end_offset_days`` shifts the whole window back in time: the window becomes
    [now - offset - days, now - offset]. This is what makes a true replication
    test possible — rerun a winning grid on the *prior* N days, a window the
    original selection never saw. 0 (default) = the trailing window ending now.

    Network-bound (Upstox historical API). Tests never call this — they pass
    synthetic candles straight to ``run_combo``.
    """
    wdays = _warmup_fetch_days(interval)
    ohlcv = await client.get_historical_data(
        symbol, interval=interval, days=days + end_offset_days + wdays,
    )
    if not ohlcv:
        return [], 0
    window_end = datetime.now(IST) - timedelta(days=end_offset_days)
    cutoff = window_end - timedelta(days=days)

    def _ts(c):
        t = c.timestamp
        return datetime.fromisoformat(t) if isinstance(t, str) else t

    if end_offset_days:
        ohlcv = [c for c in ohlcv if _ts(c) < window_end]
        if not ohlcv:
            return [], 0
    warmup_bars = sum(1 for c in ohlcv if _ts(c) < cutoff)
    candles = [
        {
            "timestamp": c.timestamp, "open": c.open, "high": c.high,
            "low": c.low, "close": c.close, "volume": c.volume,
        }
        for c in ohlcv
    ]
    return candles, warmup_bars


# ---------------------------------------------------------------------------
# Combo grid expansion
# ---------------------------------------------------------------------------

def expand_grid(
    primaries: list[str],
    confirms: list[str] | None,
    intervals: list[str],
    exit_variants: list[dict],
    sides: list[str],
    htf_gates: list[str | None] | None = None,
) -> list[dict]:
    """Cartesian product of the sweep axes into a flat list of combo specs.

    A combo spec is a dict:
      {primary, confirm (None | name), interval, entry_side,
       trail_percent, sl_points, target_points, htf_gate (None | variant)}

    Confirm handling:
      * ``confirms`` is None or empty → SOLO combos only (confirm=None).
      * otherwise → SOLO combos PLUS each primary×confirm pair, *skipping*
        confirm == primary (an indicator confirming itself is a no-op).

    ``exit_variants`` is a list of ``{trail_percent, sl_points, target_points}``
    dicts (the exit grid), so SL/target/trail sweeps multiply in cleanly.

    ``htf_gates`` is the regime-detection axis: each entry is None (ungated —
    the baseline) or an ``htf_trend.HTF_VARIANTS`` name; combos multiply across
    it like any other axis. Default None → [None] (no gate, original grid).
    """
    confirm_options: list[str | None] = [None]
    if confirms:
        confirm_options += list(confirms)
    gate_options: list[str | None] = list(htf_gates) if htf_gates else [None]

    combos: list[dict] = []
    for primary in primaries:
        for confirm in confirm_options:
            if confirm is not None and confirm == primary:
                continue  # an indicator confirming itself is meaningless
            for interval in intervals:
                for ev in exit_variants:
                    for side in sides:
                        for hg in gate_options:
                            combos.append({
                                "primary": primary,
                                "confirm": confirm,
                                "interval": interval,
                                "entry_side": side,
                                "trail_percent": ev.get("trail_percent"),
                                "sl_points": ev.get("sl_points"),
                                "target_points": ev.get("target_points"),
                                "htf_gate": hg,
                            })
    return combos


# ---------------------------------------------------------------------------
# Walk-forward split date from the candle window
# ---------------------------------------------------------------------------

def _in_window_dates(candles: list[dict], warmup_bars: int) -> list[date]:
    """Distinct trading dates present AFTER the warm-up prefix, sorted ascending.

    These are the dates trades can actually fire on (warm-up bars are compute-only),
    so the train/validate split must be computed from them — not the raw fetch.
    """
    tail = candles[warmup_bars:] if warmup_bars else candles

    def _d(c):
        t = c["timestamp"]
        dt = datetime.fromisoformat(t) if isinstance(t, str) else t
        return dt.date()

    return sorted({_d(c) for c in tail})


def compute_split_date(candles: list[dict], warmup_bars: int) -> date | None:
    """The walk-forward split date: start of the last ~1/3 of in-window trading
    days. Trades on dates < this → train; on/after → validate.

    Returns None when there aren't at least 2 distinct trading days (can't split).
    """
    days = _in_window_dates(candles, warmup_bars)
    if len(days) < 2:
        return None
    n_validate = max(1, round(len(days) * _VALIDATION_DAY_FRACTION))
    n_validate = min(n_validate, len(days) - 1)  # always keep ≥1 train day
    return days[len(days) - n_validate]


# ---------------------------------------------------------------------------
# Single combo run (CPU-bound; callers wrap in asyncio.to_thread)
# ---------------------------------------------------------------------------

def run_combo(
    candles: list[dict],
    warmup_bars: int,
    symbol: str,
    combo: dict,
    *,
    quantity: int,
    squareoff: str = "15:15",
    max_trades: int = 3,
    cooldown: int = 60,
    slippage_bps: float = 5.0,
    min_trades: int = 10,
    max_single_trade_share: float = 0.5,
    daily_loss_cap: float | None = None,
    entry_gate: Callable[[datetime, str], bool] | None = None,
) -> dict:
    """Run ONE combo through the scalp engine over the full window, then evaluate
    it with the ranking layers. ONE engine run; train/validate is a partition of
    its trades, not a second run.

    ``entry_gate`` is the materialized callable for the combo's ``htf_gate``
    variant (built once per symbol by ``sweep_symbol``); the engine consults it
    on every would-be entry, and the row reports ``entry_gate_blocks`` so the
    output shows how many entries the regime gate vetoed.

    Returns a row dict carrying: the combo spec, raw net metrics, the gate result
    (``gated`` bool + ``gate_reasons``), the in-sample ``score``, and the
    walk-forward ``validation`` block with a ``confirmed`` flag, ``confidence``
    label, and ``validation_per_day`` (the headline out-of-sample ₹/day). Plus
    ``net_pnl`` set to the VALIDATION net so grid-level plateau detection ranks on
    the honest figure.
    """
    interval = combo["interval"]
    tf = _INTERVAL_TO_TIMEFRAME[interval]
    cfg = ScalpSessionConfig(
        name=f"matrix-{symbol}-{combo['primary']}",
        session_mode="equity_intraday",
        underlying=symbol,
        indicator_timeframe=tf,
        primary_indicator=combo["primary"],
        primary_params=None,
        confirm_indicator=combo.get("confirm"),
        confirm_params=None,
        sl_points=combo.get("sl_points"),
        target_points=combo.get("target_points"),
        trail_percent=combo.get("trail_percent"),
        squareoff_time=squareoff,
        max_trades=max_trades,
        cooldown_seconds=cooldown,
        entry_side=combo["entry_side"],
        quantity=quantity,
    )
    result = run_scalp_equity_backtest(
        candles, cfg, symbol=symbol, interval=interval,
        slippage_bps=slippage_bps, warmup_bars=warmup_bars,
        entry_gate=entry_gate,
    )
    trades = result.trades
    mn = result.metrics_net

    # ── Layer 1: hard gates ────────────────────────────────────────────
    gate_reasons = apply_gates(
        trades, mn,
        min_trades=min_trades,
        max_single_trade_share=max_single_trade_share,
        daily_loss_cap=daily_loss_cap,
    )
    gated = bool(gate_reasons)

    # ── Layer 2: in-sample score (components kept separate) ────────────
    score = combo_score(trades)

    # ── Layer 3: walk-forward split + validation ───────────────────────
    split_date = compute_split_date(candles, warmup_bars)
    if split_date is not None:
        train_trades, validate_trades = split_trades(trades, split_date)
        wf = validate_combo(train_trades, validate_trades)
        val_per_day = wf["validation"]["expectancy_per_day"]
        conf = confidence_label(wf["validation"]["tstat"], wf["validation"]["n_trades"])
    else:
        # Too few days to split — no out-of-sample claim possible.
        wf = {"confirmed": False, "train": None, "validation": None}
        val_per_day = 0.0
        conf = "low"

    return {
        # combo identity
        "symbol": symbol,
        "primary": combo["primary"],
        "confirm": combo.get("confirm"),
        "interval": interval,
        "entry_side": combo["entry_side"],
        "trail_percent": combo.get("trail_percent"),
        "sl_points": combo.get("sl_points"),
        "target_points": combo.get("target_points"),
        "htf_gate": combo.get("htf_gate"),
        # raw net summary
        "profit_factor": _pf_for_json(mn.get("profit_factor", 0.0)),
        "win_rate": round(mn.get("win_rate", 0.0) / 100.0, 4),
        "total_pnl": round(mn.get("net_pnl", 0.0), 2),
        "total_trades": mn.get("total_trades", 0),
        "entry_gate_blocks": result.entry_gate_blocks,
        "split_date": split_date.isoformat() if split_date else None,
        # evaluation layers
        "gated": gated,
        "gate_reasons": gate_reasons,
        "score": score,
        "walk_forward": wf,
        "confirmed": bool(wf.get("confirmed")),
        "confidence": conf,
        "validation_per_day": val_per_day,
        # plateau ranking key = validation net (honest, out-of-sample). Falls
        # back to total net when the window was too short to split.
        "net_pnl": (
            wf["validation"]["net_pnl"] if wf.get("validation")
            else round(mn.get("net_pnl", 0.0), 2)
        ),
    }


def _pf_for_json(pf):
    """Render profit_factor for JSON: keep numbers, pass through "inf" string."""
    f = _pf_to_float(pf)
    if f == float("inf"):
        return "inf"
    return round(f, 2)


# ---------------------------------------------------------------------------
# Caching (per symbol+combo+config+date)
# ---------------------------------------------------------------------------

def _combo_fingerprint(combo: dict, sizing: dict, scan_date: str) -> str:
    """Stable hash of every input that changes a combo's backtest result.

    Includes the full combo spec, the sizing/discipline config, the scan date,
    and the validation-split config — so a cache hit is only ever returned for an
    identical run. (The split fraction is baked in via the module constant; we
    fold it into the payload so bumping it invalidates stale cache entries.)
    """
    payload = {
        "combo": {
            "primary": combo["primary"],
            "confirm": combo.get("confirm"),
            "interval": combo["interval"],
            "entry_side": combo["entry_side"],
            "trail_percent": combo.get("trail_percent"),
            "sl_points": combo.get("sl_points"),
            "target_points": combo.get("target_points"),
            "htf_gate": combo.get("htf_gate"),
        },
        "sizing": sizing,
        "scan_date": scan_date,
        "split_fraction": _VALIDATION_DAY_FRACTION,
    }
    blob = json.dumps(payload, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def _cache_key_name(symbol: str, combo: dict, fp: str) -> str:
    confirm = combo.get("confirm") or "solo"
    gate = combo.get("htf_gate") or "nogate"
    return (
        f"matrix_{symbol}_{combo['primary']}_{confirm}_{combo['interval']}_"
        f"{combo['entry_side']}_{gate}_{fp}.json"
    )


def _cache_read(symbol: str, combo: dict, fp: str, ttl_hours: float):
    path = os.path.join(_CACHE_DIR, _cache_key_name(symbol, combo, fp))
    if not os.path.exists(path):
        return None
    if (time.time() - os.path.getmtime(path)) > ttl_hours * 3600:
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _cache_write(symbol: str, combo: dict, fp: str, row: dict):
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        path = os.path.join(_CACHE_DIR, _cache_key_name(symbol, combo, fp))
        with open(path, "w") as f:
            json.dump(row, f, default=str)
    except OSError:
        pass  # caching is best-effort; never fail the sweep over it


# ---------------------------------------------------------------------------
# Per-symbol orchestration
# ---------------------------------------------------------------------------

async def sweep_symbol(
    client,
    symbol: str,
    combos: list[dict],
    *,
    days: int,
    quantity: int | None,
    capital_per_trade: float,
    squareoff: str,
    max_trades: int,
    cooldown: int,
    slippage_bps: float,
    min_trades: int,
    max_single_trade_share: float,
    daily_loss_cap: float | None,
    sem: asyncio.Semaphore,
    use_cache: bool,
    cache_ttl_hours: float,
    scan_date: str,
    end_offset_days: int = 0,
    verbose: bool = False,
) -> dict | None:
    """Run every combo for one symbol. Candles are fetched ONCE per (symbol,
    interval) and reused across all combos on that interval.

    Returns ``{"symbol": ..., "rows": [...]}`` or None if no candles fetched.
    """
    async with sem:
        # Group combos by interval so we fetch each interval's candles once.
        intervals = sorted({c["interval"] for c in combos})
        candle_cache: dict[str, tuple[list[dict], int]] = {}
        for interval in intervals:
            try:
                candles, warmup = await fetch_candles_with_warmup(
                    client, symbol, interval, days,
                    end_offset_days=end_offset_days,
                )
            except Exception as e:
                if verbose:
                    print(f"  [{symbol}/{interval}] fetch failed: {e}", file=sys.stderr)
                continue
            if candles:
                candle_cache[interval] = (candles, warmup)

        if not candle_cache:
            if verbose:
                print(f"  [{symbol}] no candles for any interval", file=sys.stderr)
            return None

        # HTF trend gates: when any combo asks for one, fetch DAILY candles
        # ONCE per symbol and build each needed variant's per-date trend map.
        # The fetch reaches past the (possibly offset-shifted) window start by
        # _HTF_DAILY_EXTRA_DAYS so EMA50 is converged at the window's first
        # trade; fetching up to *now* is fine even with end_offset_days — the
        # map is keyed by date and each date only ever sees PRIOR days'
        # closes, so later candles can't leak into the shifted window.
        needed_variants = sorted(
            {c.get("htf_gate") for c in combos if c.get("htf_gate")}
        )
        entry_gates: dict[str, Callable] = {}
        if needed_variants:
            try:
                daily = await client.get_historical_data(
                    symbol, interval="day",
                    days=days + end_offset_days + _HTF_DAILY_EXTRA_DAYS,
                )
            except Exception as e:
                daily = None
                if verbose:
                    print(f"  [{symbol}] daily fetch for HTF gate failed: {e}",
                          file=sys.stderr)
            if daily:
                for variant in needed_variants:
                    entry_gates[variant] = make_entry_gate(
                        compute_daily_trend(daily, variant)
                    )

        rows: list[dict] = []
        for combo in combos:
            cc = candle_cache.get(combo["interval"])
            if cc is None:
                continue
            candles, warmup = cc

            # A gated combo without its gate (daily fetch failed) is SKIPPED,
            # not silently run ungated — an unlabelled ungated row would be
            # indistinguishable from the gated one it claims to be.
            hg = combo.get("htf_gate")
            if hg and hg not in entry_gates:
                if verbose:
                    print(f"  [{symbol}/{combo['primary']}] skipped: HTF gate "
                          f"'{hg}' unavailable (daily fetch failed)",
                          file=sys.stderr)
                continue

            # Quantity: fixed, or sized from capital / last close.
            last_close = candles[-1]["close"]
            qty = quantity if quantity is not None else max(
                1, int(capital_per_trade / last_close) if last_close else 1
            )
            sizing = {
                "quantity": qty, "squareoff": squareoff, "max_trades": max_trades,
                "cooldown": cooldown, "slippage_bps": slippage_bps, "days": days,
                "end_offset_days": end_offset_days,
                "min_trades": min_trades,
                "max_single_trade_share": max_single_trade_share,
                "daily_loss_cap": daily_loss_cap,
            }
            fp = _combo_fingerprint(combo, sizing, scan_date)

            if use_cache:
                cached = _cache_read(symbol, combo, fp, cache_ttl_hours)
                if cached is not None:
                    rows.append(cached)
                    continue

            try:
                row = await asyncio.to_thread(
                    run_combo, candles, warmup, symbol, combo,
                    quantity=qty, squareoff=squareoff, max_trades=max_trades,
                    cooldown=cooldown, slippage_bps=slippage_bps,
                    min_trades=min_trades,
                    max_single_trade_share=max_single_trade_share,
                    daily_loss_cap=daily_loss_cap,
                    entry_gate=entry_gates.get(hg) if hg else None,
                )
            except Exception as e:
                if verbose:
                    print(f"  [{symbol}/{combo['primary']}/{combo.get('confirm')}] "
                          f"backtest failed: {e}", file=sys.stderr)
                continue

            if use_cache:
                _cache_write(symbol, combo, fp, row)
            rows.append(row)

        if verbose:
            # stderr, never stdout — stdout must stay clean for --json output.
            print(f"  [{symbol}] {len(rows)}/{len(combos)} combos done",
                  file=sys.stderr)
        return {"symbol": symbol, "rows": rows}


# ---------------------------------------------------------------------------
# Per-symbol assembly: gates → plateau → validation-confirmed ranking
# ---------------------------------------------------------------------------

# Axes the plateau check sweeps for lone-spike winners.
PLATEAU_AXES = ["trail_percent", "sl_points", "target_points"]


def assemble_symbol(
    symbol: str, scan_score, rows: list[dict], *, show_gated: bool = False
) -> dict:
    """Turn a symbol's raw combo rows into a ranked report block.

    Counts surface the multiple-comparisons context (tested / gated / failed
    validation / confirmed), and ``gate_summary`` categorizes WHY combos gated
    out (a counter of reason categories, not 40 unique strings) — so an
    all-gated symbol is debuggable from the output instead of requiring a
    manual sweep.py import. Confirmed combos are ranked by VALIDATION ₹/day —
    the out-of-sample expectancy — with plateau warnings attached.

    ``show_gated=True`` additionally includes the full rows for gated combos
    (``gated_combos``) and gate-survivors that failed walk-forward validation
    (``failed_validation_combos``) — each still carries its combo spec, net
    metrics, gate_reasons, and train/validation blocks from ``run_combo``.
    """
    tested = len(rows)
    gated_rows = [r for r in rows if r["gated"]]
    survived = [r for r in rows if not r["gated"]]
    confirmed = [r for r in survived if r["confirmed"]]
    failed_val_rows = [r for r in survived if not r["confirmed"]]

    # Plateau check runs across ALL surviving rows (so neighbours exist on each
    # axis even if some neighbours weren't confirmed). Annotates in place.
    plateau_flags(survived, PLATEAU_AXES)

    confirmed.sort(key=lambda r: r["validation_per_day"], reverse=True)

    block = {
        "symbol": symbol,
        "scan_score": scan_score,
        "counts": {
            "tested": tested,
            "gated_out": len(gated_rows),
            "failed_validation": len(failed_val_rows),
            "confirmed": len(confirmed),
        },
        "gate_summary": gate_summary(r["gate_reasons"] for r in gated_rows),
        "confirmed_combos": confirmed,
        "best": confirmed[0] if confirmed else None,
    }
    if show_gated:
        block["gated_combos"] = gated_rows
        block["failed_validation_combos"] = failed_val_rows
    return block
