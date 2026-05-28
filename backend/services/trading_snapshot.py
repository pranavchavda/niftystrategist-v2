"""In-process trading-state snapshot builder for the high-frequency awakening agent.

Assembles a digested, decision-ready text dashboard from FRESH live data each
time it is called — never from a transcript. The awakening job builds this
inline (step 1) then injects ``.text`` into the agent's context so the model
reasons over current state immediately, without slow tool round-trips.

Design north star ([[project-high-frequency-trading-agent]], [[project-agent-is-the-alpha]]):
the snapshot is *digested raw data + a few deterministic safety/state alerts* —
NOT opinion/heuristic flags. The agent judges from the data; the snapshot just
directs the cheap model's eye to hard safety facts (unprotected position, risk
used vs cap, already-traded-today, stale/anomalous data).

Account reads (portfolio/positions/funds/trades/rules) use the per-user token.
Public reads (indices, market status, candidate candles) prefer the shared
analytics token — see [[feedback_analytics_token_default]].

Graceful degradation: if assembly throws, ``build_trading_snapshot`` returns a
fallback telling the agent exactly which tools to call by hand. Nothing stops.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from api.upstox_oauth import get_user_upstox_token
from database.models import User
from database.session import get_db_context
from monitor.crud import list_rules
from monitor.indicator_engine import compute_indicator
from services.upstox_client import UpstoxClient
from services.technical_analysis import TechnicalAnalysisService

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


@dataclass
class SnapshotResult:
    """Output of the snapshot builder."""
    ok: bool
    text: str
    alerts: list[str] = field(default_factory=list)
    built_at_ist: str = ""
    scan_source: str = ""
    has_intraday: bool = False
    error: str | None = None


# ── small formatters ───────────────────────────────────────────────────────

def _inr(v: float | None) -> str:
    if v is None:
        return "—"
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e7:
        return f"{sign}₹{a/1e7:.2f}Cr"
    if a >= 1e5:
        return f"{sign}₹{a/1e5:.2f}L"
    if a >= 1000:
        return f"{sign}₹{a/1000:.1f}k"
    return f"{sign}₹{a:.0f}"


def _signed(v: float | None, suffix: str = "") -> str:
    if v is None:
        return "—"
    return f"{v:+.2f}{suffix}"


def _rs2(v: float | None) -> str:
    """Rupee value to 2 decimals — for spreads/levels where ₹0 rounding hurts."""
    return "—" if v is None else f"₹{v:.2f}"


def _compact_qty(n: float | None) -> str:
    if not n:
        return "0"
    if n >= 1e5:
        return f"{n/1e5:.1f}L"
    if n >= 1000:
        return f"{n/1000:.0f}k"
    return f"{int(n)}"


def _depth_digest(d: dict | None, full: bool = False) -> str:
    """One-line order-book read: imbalance ratio (+ spread + resting wall).

    The live microstructure/OFI signal we couldn't backtest but CAN use live.
    `full` adds spread + wall (held names); else imbalance only (candidates).
    """
    if not d:
        return ""
    bq = d.get("total_buy_qty") or sum(q for _, q in d.get("bids", []))
    sq = d.get("total_sell_qty") or sum(q for _, q in d.get("asks", []))
    parts: list[str] = []
    if bq and sq:
        if bq >= sq:
            parts.append(f"OB {bq/sq:.1f}:1 bid-heavy")
        else:
            parts.append(f"OB 1:{sq/bq:.1f} ask-heavy")
    elif not d.get("bids") and not d.get("asks"):
        return ""  # market closed / no depth
    if full:
        if d.get("spread") is not None:
            parts.append(f"spread {_rs2(d['spread'])}")
        # Resting wall: a level whose size dwarfs the rest of the book.
        levels = [(p, q, "bid") for p, q in d.get("bids", [])] + \
                 [(p, q, "ask") for p, q in d.get("asks", [])]
        if len(levels) >= 3:
            mx = max(levels, key=lambda x: x[1])
            rest = [q for p, q, s in levels if (p, q, s) != mx]
            avg_rest = (sum(rest) / len(rest)) if rest else 0
            if avg_rest and mx[1] > 3 * avg_rest:
                parts.append(f"wall {_compact_qty(mx[1])}@{_rs2(mx[0])} {mx[2]}")
    return " · ".join(parts)


def _tod_bucket(t: datetime) -> str:
    """Coarse session phase the model can reason about."""
    hm = t.hour * 60 + t.minute
    if hm < 9 * 60 + 15:
        return "pre-open"
    if hm < 9 * 60 + 45:
        return "opening (9:15–9:45)"
    if hm < 11 * 60 + 30:
        return "morning (9:45–11:30)"
    if hm < 13 * 60 + 30:
        return "midday (11:30–13:30)"
    if hm < 14 * 60 + 45:
        return "afternoon (13:30–14:45)"
    if hm <= 15 * 60 + 30:
        return "close (14:45–15:30)"
    return "after-hours"


# ── client construction ──────────────────────────────────────────────────────

def _market_client(user_id: int, fallback_token: str) -> UpstoxClient:
    """Client for non-user-specific reads — prefers the analytics token."""
    try:
        from services.chart_market_stream import analytics_token_from_env
        token = analytics_token_from_env()
    except Exception:
        token = None
    return UpstoxClient(
        access_token=token or fallback_token,
        paper_trading=False,
        user_id=user_id,
    )


# ── tape-read composite per symbol ───────────────────────────────────────────

async def _tape_read(market: UpstoxClient, symbol: str) -> str:
    """One-line indicator composite: UTBot · MACD · EMA9>21 · RSI · VWAP-pos · Renko.

    A tape line that CONTRADICTS the entry thesis is the key agent cue. Returns
    an empty string if data is unavailable (the model just sees no tape line).
    """
    try:
        candles = await market.get_historical_data(symbol, interval="5minute", days=5)
    except Exception as e:
        logger.debug(f"tape-read candles failed for {symbol}: {e}")
        return ""
    if not candles or len(candles) < 25:
        return ""

    parts: list[str] = []
    try:
        ta = TechnicalAnalysisService()
        ind = ta.calculate_indicators(candles)
        # ATR-sized renko brick so the count is meaningful cross-symbol.
        if ind.atr_14 and ind.atr_14 > 0:
            ind = TechnicalAnalysisService(renko_brick_size=round(ind.atr_14, 2)).calculate_indicators(candles)

        last = candles[-1].close

        if ind.utbot_trend:
            parts.append("UTBot " + ("LONG" if ind.utbot_trend == "long" else "SHORT"))
        if ind.macd_histogram is not None:
            parts.append("MACD " + ("bull" if ind.macd_histogram > 0 else "bear"))
        if ind.rsi_14 is not None:
            parts.append(f"RSI {ind.rsi_14:.0f}")
        if ind.vwap is not None and last is not None:
            parts.append(">VWAP" if last >= ind.vwap else "<VWAP")
        if ind.renko_trend:
            arrow = "↑" if ind.renko_trend == "up" else "↓"
            parts.append(f"Renko {arrow}{ind.renko_brick_count or 0}")
    except Exception as e:
        logger.debug(f"tape-read indicators failed for {symbol}: {e}")

    # EMA9>21 via the monitor engine (TA service exposes 12/26, not 9/21).
    try:
        rows = [c.model_dump() for c in candles]
        ema_diff = compute_indicator("ema_crossover", rows, {"fast": 9, "slow": 21})
        if ema_diff is not None:
            parts.insert(min(2, len(parts)), "EMA9>21" if ema_diff > 0 else "EMA9<21")
    except Exception as e:
        logger.debug(f"tape-read ema failed for {symbol}: {e}")

    return " · ".join(parts)


# ── rule helpers ─────────────────────────────────────────────────────────────

def _rule_symbol(rule) -> str:
    sym = (rule.symbol or "").upper()
    if not sym and isinstance(rule.action_config, dict):
        sym = (rule.action_config.get("symbol") or "").upper()
    return sym


def _rule_side(rule) -> str:
    if isinstance(rule.action_config, dict):
        return (rule.action_config.get("transaction_type") or "").upper()
    return ""


def _rule_trigger_price(rule) -> float | None:
    tc = rule.trigger_config if isinstance(rule.trigger_config, dict) else {}
    p = tc.get("price")
    try:
        return float(p) if p is not None else None
    except (TypeError, ValueError):
        return None


def _intent_line_for(content: str, symbol: str) -> str:
    """Best-effort: pull the agent's thesis line for a symbol from its intent.

    Matches a line beginning with the symbol (``COALINDIA:`` or ``COALINDIA ``).
    Degrades silently — returns "" when nothing matches, so a malformed or
    free-form intent never breaks the snapshot; the verbatim block still shows.
    """
    if not content or not symbol:
        return ""
    sym = symbol.upper()
    for line in content.splitlines():
        s = line.strip()
        head = s.upper()
        if head.startswith(sym + ":") or head.startswith(sym + " "):
            return s.split(":", 1)[1].strip() if ":" in s else s[len(sym):].strip()
    return ""


def _is_protective(rule, pos_symbol: str, pos_side: str) -> bool:
    """A rule that would close/protect this position (opposite-side order)."""
    if not rule.enabled:
        return False
    if _rule_symbol(rule) != pos_symbol:
        return False
    if rule.action_type != "place_order":
        return False
    closing = "SELL" if pos_side == "LONG" else "BUY"
    return _rule_side(rule) == closing


# ── main builder ─────────────────────────────────────────────────────────────

async def build_trading_snapshot(
    user_id: int,
    user_email: str | None = None,
    thread_id: str | None = None,
    scan_rows: list[dict] | None = None,
    run_live_scan: bool = True,
    scan_universe: str = "nifty500",
    scan_top_n: int = 5,
    scan_cache_max_age: float = 360.0,
) -> SnapshotResult:
    """Assemble the trading-state dashboard for ``user_id``.

    Args:
        thread_id: daily-thread id used to pull the agent's latest self-authored
            intent (nf-intent). When omitted, the PRIOR INTENT section is skipped.
        scan_rows: pre-computed candidate rows (from the slow scan cron). When
            provided, used directly. When None and ``run_live_scan`` is True, a
            live scan is run inline (slower — temporary until the cron lands).
    """
    now = datetime.now(IST)
    built_at = now.strftime("%Y-%m-%d %H:%M:%S IST")
    try:
        return await _build(
            user_id, user_email, now, built_at, thread_id,
            scan_rows, run_live_scan, scan_universe, scan_top_n, scan_cache_max_age,
        )
    except Exception as e:
        logger.exception(f"Snapshot build failed for user {user_id}")
        fallback = (
            f"⚠️ SNAPSHOT UNAVAILABLE ({built_at}) — build error: {e}\n\n"
            "FETCH the state yourself now, then decide as you normally would — a "
            "missing snapshot is NOT a reason to sit idle (an unprotected loser "
            "still needs action):\n"
            "  • nf-portfolio              (open positions + P&L)\n"
            "  • nf-funds                  (margin / buying power)\n"
            "  • nf-monitor list           (active protective rules)\n"
            "  • nf-trades today           (booked trades today)\n"
            "  • nf-quote <held symbols>   (live prices)\n"
            "  • nf-market-status          (is the market open?)\n"
            "Verify on freshly-fetched data, not assumptions — then act."
        )
        return SnapshotResult(
            ok=False, text=fallback, alerts=["⚠ snapshot build failed — data unverified"],
            built_at_ist=built_at, error=str(e),
        )


async def _build(user_id, user_email, now, built_at, thread_id, scan_rows,
                 run_live_scan, scan_universe, scan_top_n, scan_cache_max_age) -> SnapshotResult:
    token = await get_user_upstox_token(user_id)
    if not token:
        raise RuntimeError("no valid Upstox token for user")

    live = UpstoxClient(access_token=token, paper_trading=False, user_id=user_id)
    market = _market_client(user_id, token)

    # Concurrent account + market reads; degrade per-call, never whole snapshot.
    portfolio, raw_positions, trades, funds, indices, mkt_status = await asyncio.gather(
        live.get_portfolio(),
        live.get_positions(),
        live.get_trades_for_day(),
        live.get_funds_and_margin(),
        market.get_index_quotes(),
        market.get_market_status_api(),
        return_exceptions=True,
    )

    alerts: list[str] = []
    stale: list[str] = []

    def _ok(x):
        return not isinstance(x, Exception)

    if not _ok(portfolio):
        stale.append("portfolio")
    if not _ok(trades):
        stale.append("trades")
    if not _ok(funds):
        stale.append("funds")

    # Rules + mandate from DB.
    rules = []
    mandate = None
    try:
        async with get_db_context() as db:
            rules = await list_rules(db, user_id, enabled_only=False)
            db_user = await db.get(User, user_id)
            mandate = db_user.trading_mandate if db_user else None
    except Exception as e:
        logger.warning(f"snapshot: rules/mandate load failed: {e}")
        stale.append("rules")

    # Agent's self-authored intent for this daily thread (latest = newest wins).
    intent_content = ""
    intent_ts = ""
    if thread_id:
        try:
            from services.trading_intent import get_latest_intent
            row = await get_latest_intent(thread_id)
            if row:
                intent_content = row.content or ""
                intent_ts = str(row.created_at)
        except Exception as e:
            logger.debug(f"snapshot: intent load failed: {e}")

    L: list[str] = []

    # ── HEADER ────────────────────────────────────────────────────────────
    L.append(f"=== TRADING SNAPSHOT · {built_at} · {_tod_bucket(now)} ===")
    status_str = "unknown"
    if _ok(mkt_status) and mkt_status:
        status_str = mkt_status.get("status", "unknown")
    L.append(f"Market: {status_str}")
    if _ok(indices) and indices:
        idx_bits = []
        for q in indices:
            nm = q.get("name", "?")
            if nm in ("NIFTY 50", "BANK NIFTY", "INDIA VIX"):
                idx_bits.append(f"{nm} {q.get('value')} ({_signed(q.get('changePct'), '%')})")
        if idx_bits:
            L.append("Indices: " + " | ".join(idx_bits))

    # ── MANDATE & RISK BUDGET ────────────────────────────────────────────
    L.append("")
    L.append("--- MANDATE & RISK BUDGET ---")
    day_pnl = portfolio.day_pnl if _ok(portfolio) else None
    realised = sum((getattr(p, "realised", 0) or 0) for p in raw_positions) if _ok(raw_positions) else None
    unrealised = sum((getattr(p, "unrealised", 0) or 0) for p in raw_positions) if _ok(raw_positions) else None
    if realised is not None or unrealised is not None:
        L.append(
            f"P&L today: realised {_inr(realised)} + unrealised {_inr(unrealised)} "
            f"= {_inr((realised or 0) + (unrealised or 0))}"
        )
    elif day_pnl is not None:
        L.append(f"Day P&L: {_inr(day_pnl)}")

    if _ok(funds) and isinstance(funds, dict):
        eq = funds.get("equity", {}) if isinstance(funds.get("equity"), dict) else {}
        L.append(f"Available margin: {_inr(eq.get('available_margin'))} | used {_inr(eq.get('used_margin'))}")

    if mandate:
        cap = mandate.get("daily_loss_cap") or mandate.get("max_daily_loss")
        risk_per = mandate.get("risk_per_trade") or mandate.get("risk_percent")
        cutoff = mandate.get("cutoff_time") or mandate.get("squareoff_time")
        max_trades = mandate.get("max_trades_per_day") or mandate.get("max_trades")
        mbits = []
        if risk_per:
            mbits.append(f"risk/trade {risk_per}")
        if cap:
            mbits.append(f"daily-loss cap {_inr(float(cap)) if str(cap).replace('.','').isdigit() else cap}")
        if max_trades:
            mbits.append(f"max trades {max_trades}")
        if cutoff:
            mbits.append(f"cutoff {cutoff}")
        if mbits:
            L.append("Mandate: " + " | ".join(mbits))
        total_pnl = (realised or 0) + (unrealised or 0)
        if cap:
            try:
                cap_f = float(cap)
                if total_pnl <= -abs(cap_f):
                    alerts.append(f"⚠ daily-loss cap hit ({_inr(total_pnl)} vs cap {_inr(-abs(cap_f))}) — HALT new entries")
            except (TypeError, ValueError):
                pass
    else:
        L.append("Mandate: none set")

    # traded-today set (anti-churn).
    traded_today: set[str] = set()
    if _ok(trades):
        for t in trades:
            s = (t.get("symbol") or "").upper()
            if s:
                traded_today.add(s)
    L.append(f"Trades booked today: {len(trades) if _ok(trades) else '—'}"
             + (f"  ({', '.join(sorted(traded_today))})" if traded_today else ""))

    # ── OPEN POSITIONS (intraday only) ───────────────────────────────────
    # Delivery holdings (product D) are deliberately excluded — they're
    # long-term investments, not trades the 10-min loop manages. The agent's
    # vocabulary is intraday day-trading; surfacing 13+ holdings every wake is
    # noise + cost and would mis-flag investments as "unprotected".
    L.append("")
    L.append("--- OPEN POSITIONS (intraday) ---")
    open_positions = list(portfolio.intraday_positions) if _ok(portfolio) else []

    # entry time = earliest trade for the symbol today.
    entry_times: dict[str, str] = {}
    if _ok(trades):
        for t in trades:
            s = (t.get("symbol") or "").upper()
            ts = t.get("trade_timestamp") or ""
            if s and ts and (s not in entry_times or ts < entry_times[s]):
                entry_times[s] = ts

    if not open_positions:
        L.append("(flat — no open positions)")
    else:
        # Tape-read + order-book depth concurrently for all held names.
        syms = [p.symbol for p in open_positions]
        tape_map, depth_map = {}, {}
        try:
            tapes, depth_map = await asyncio.gather(
                asyncio.gather(*[_tape_read(market, s) for s in syms]),
                market.get_market_depth(syms),
            )
            tape_map = dict(zip(syms, tapes))
        except Exception as e:
            logger.debug(f"position tape/depth reads failed: {e}")

        for p in open_positions:
            sym = p.symbol
            side = getattr(p, "side", "LONG") or "LONG"
            prod = getattr(p, "product", "?")
            protectors = [r for r in rules if _is_protective(r, sym.upper(), side)]
            line = (
                f"• {sym} [{side}/{prod}] qty {p.quantity} @ {_inr(p.average_price)} "
                f"→ LTP {_inr(p.current_price)} | P&L {_inr(p.pnl)} ({_signed(p.pnl_percentage, '%')})"
            )
            L.append(line)

            # dist to nearest protective levels.
            sl_lvls = [(_rule_trigger_price(r), r.id) for r in protectors
                       if (r.role or "").startswith(("sl", "stop")) and _rule_trigger_price(r)]
            tgt_lvls = [(_rule_trigger_price(r), r.id) for r in protectors
                        if (r.role or "").startswith(("target", "tp")) and _rule_trigger_price(r)]
            sub = []
            ltp = p.current_price or 0
            if sl_lvls and ltp:
                lvl, rid = sl_lvls[0]
                dist = (ltp - lvl) / ltp * 100 if side == "LONG" else (lvl - ltp) / ltp * 100
                sub.append(f"SL {_inr(lvl)} ({dist:+.2f}%, rule#{rid})")
            if tgt_lvls and ltp:
                lvl, rid = tgt_lvls[0]
                dist = (lvl - ltp) / ltp * 100 if side == "LONG" else (ltp - lvl) / ltp * 100
                sub.append(f"target {_inr(lvl)} ({dist:+.2f}%, rule#{rid})")
            if not protectors:
                sub.append("NO PROTECTIVE RULE")
                alerts.append(f"⚠ {sym} [{side}] is UNPROTECTED — no active SL/exit rule")
            if entry_times.get(sym.upper()):
                sub.append(f"entry {entry_times[sym.upper()]}")
            if sub:
                L.append("    " + " | ".join(sub))
            tape = tape_map.get(sym, "")
            if tape:
                L.append(f"    tape: {tape}")
            ob = _depth_digest(depth_map.get(sym), full=True)
            if ob:
                L.append(f"    ob:   {ob}")
            intent_tag = _intent_line_for(intent_content, sym)
            if intent_tag:
                L.append(f"    intent: {intent_tag}")

    # ── PRIOR INTENT (agent's own notes — intent only, verify vs live) ───
    if thread_id:
        L.append("")
        if intent_content:
            L.append(f"--- PRIOR INTENT (your notes @ {intent_ts} — verify against LIVE state above) ---")
            L.append(intent_content)
        else:
            L.append("--- PRIOR INTENT ---")
            L.append("(none recorded — use `nf-intent set` to record your thesis)")

    # ── PENDING / PROTECTIVE RULES ───────────────────────────────────────
    L.append("")
    L.append("--- ACTIVE RULES ---")
    active_rules = [r for r in rules if r.enabled]
    if not active_rules:
        L.append("(none active)")
    else:
        for r in active_rules:
            sym = _rule_symbol(r) or "?"
            tp = _rule_trigger_price(r)
            lvl = f" @ {_inr(tp)}" if tp else ""
            L.append(f"• #{r.id} {sym} {r.trigger_type}/{_rule_side(r) or r.action_type}"
                     f"{lvl}  [{r.role or 'rule'}]")
    disabled_armed = [r for r in rules if not r.enabled]
    if disabled_armed:
        L.append(f"(+{len(disabled_armed)} disabled/armed rules)")

    # ── CANDIDATES ───────────────────────────────────────────────────────
    L.append("")
    scan_source = "none"
    rows = scan_rows
    if rows is not None:
        scan_source = "provided"
    elif run_live_scan:
        # Cache-first: read the cron's row if fresh, else scan inline. The cron
        # refreshes nifty500 every ~3 min; accept up to 2× that before falling
        # back so a single missed cron cycle doesn't force a slow inline scan.
        try:
            from services.scan_cache import get_latest_scan
            cached, age = await get_latest_scan(scan_universe, max_age_seconds=scan_cache_max_age)
        except Exception as e:
            logger.debug(f"snapshot: scan cache read failed: {e}")
            cached, age = None, None
        if cached is not None:
            rows = cached
            scan_source = f"cached {age/60:.1f}m ago"
        else:
            try:
                rows, src = await _run_live_scan(scan_universe, scan_top_n)
                scan_source = src + " (inline)"
            except Exception as e:
                logger.warning(f"snapshot: live scan failed: {e}")
                stale.append("scan")
                rows = []

    # Drop names we're already in or have queued — held (intraday + delivery)
    # and any symbol with an enabled place_order rule. Frees the 5 slots for
    # genuinely fresh setups (we pull a deeper list so 5 survive the filter).
    held_syms: set[str] = set()
    if _ok(portfolio):
        held_syms |= {p.symbol.upper() for p in portfolio.intraday_positions}
        held_syms |= {p.symbol.upper() for p in portfolio.positions}
    pending_syms = {_rule_symbol(r) for r in rules
                    if r.enabled and r.action_type == "place_order"}
    pending_syms.discard("")
    excluded = held_syms | pending_syms

    fresh = [c for c in (rows or []) if (c.get("symbol") or "").upper() not in excluded]
    shown = fresh[:scan_top_n]
    n_filtered = len(rows or []) - len(fresh)
    label_extra = f", {n_filtered} held/pending filtered" if n_filtered else ""
    L.append(f"--- CANDIDATES (top {scan_top_n} of {len(fresh)} fresh, scan: {scan_source}{label_extra}) ---")
    if not shown:
        L.append("(no fresh candidates)")
    else:
        cand_depth = {}
        try:
            cand_depth = await market.get_market_depth([c["symbol"] for c in shown])
        except Exception as e:
            logger.debug(f"candidate depth fetch failed: {e}")
        for c in shown:
            sym = (c.get("symbol") or "?").upper()
            q = c.get("quote") or {}
            ltp = q.get("ltp")
            churn = " ⟲traded-today" if sym in traded_today else ""
            bits = [f"score {c.get('total_score', c.get('phase1_score', '?'))}"]
            if c.get("setup"):
                bits.append(str(c["setup"]))
            if ltp:
                bits.append(f"LTP {_inr(ltp)}")
            if c.get("gap_pct") is not None:
                bits.append(f"gap {_signed(c['gap_pct'], '%')}")
            if c.get("rel_strength") is not None:
                bits.append(f"RS {_signed(c['rel_strength'], '%')}")
            if c.get("rsi") is not None:
                bits.append(f"RSI {c['rsi']:.0f}")
            if c.get("above_vwap") is not None:
                bits.append(">VWAP" if c["above_vwap"] else "<VWAP")
            if c.get("rvol_t") is not None:
                bits.append(f"RVOL {c['rvol_t']}x")
            ob = _depth_digest(cand_depth.get(sym))
            if ob:
                bits.append(ob)
            L.append(f"• {sym}{churn}: " + " · ".join(bits))
        if traded_today & {(c.get("symbol") or "").upper() for c in shown}:
            alerts.append("⟲ some candidates already traded today — avoid impulse re-entry")

    # ── ALERTS ────────────────────────────────────────────────────────────
    if stale:
        # Prescriptive, not passive: name the tool that fills each gap so the
        # agent fetches it and still reaches a decision. A partial snapshot is
        # not an excuse to skip the call — inaction can be the expensive choice.
        fetch_for = {
            "portfolio": "nf-portfolio",
            "trades": "nf-trades today",
            "funds": "nf-funds",
            "rules": "nf-monitor list",
            "scan": "nf-morning-scan",
        }
        cmds = ", ".join(dict.fromkeys(fetch_for.get(s, s) for s in stale))
        alerts.append(
            f"⚠ partial data ({', '.join(stale)}) — FETCH it yourself before "
            f"deciding: {cmds}. Don't skip the decision; fill the gap."
        )
    L.append("")
    L.append("--- SAFETY/STATE ALERTS ---")
    if alerts:
        for a in alerts:
            L.append(a)
    else:
        L.append("(none)")

    return SnapshotResult(
        ok=True, text="\n".join(L), alerts=alerts,
        built_at_ist=built_at, scan_source=scan_source,
        has_intraday=bool(open_positions),
    )


# ── live scan (temporary; swap for cached scan_snapshots cron) ────────────────

async def _run_live_scan(universe: str, top_n: int) -> tuple[list[dict], str]:
    """Run nf-morning-scan's run_scan in-process. Loaded via SourceFileLoader
    because the CLI file is extension-less."""
    import importlib.util
    import os
    import sys
    from importlib.machinery import SourceFileLoader

    cli_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "cli-tools")
    # nf-morning-scan does `import base` (cli-tools/base.py) — that dir must be
    # importable when we load it from outside the CLI runtime.
    if cli_dir not in sys.path:
        sys.path.insert(0, cli_dir)
    path = os.path.join(cli_dir, "nf-morning-scan")
    loader = SourceFileLoader("nf_morning_scan", path)
    spec = importlib.util.spec_from_loader("nf_morning_scan", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)

    # Pull a deeper list than we show so enough survive the held/pending filter.
    result = await mod.run_scan(
        top_n=max(top_n * 4, 20), deep_count=max(top_n * 3, 15),
        as_json=True, universe_name=universe,
    )
    final = result[0] if isinstance(result, tuple) else result
    return list(final or []), f"live:{universe}"


# ── Orchestrator injection: gated on open intraday + short TTL cache ──────────

_INJECT_CACHE: dict[int, tuple[float, str | None]] = {}


async def _has_open_intraday(user_id: int, access_token: str | None) -> bool:
    """Cheap gate: does the user hold any open intraday (product I) position?

    One get_positions call. Avoids building the full snapshot (incl. scan)
    when the user is flat — the snapshot is only worth injecting when there's
    a live intraday position to manage.
    """
    if not access_token:
        return False
    try:
        client = UpstoxClient(access_token=access_token, paper_trading=False, user_id=user_id)
        positions = await client.get_positions()
    except Exception as e:
        logger.debug(f"intraday gate check failed for user {user_id}: {e}")
        return False
    for p in positions or []:
        if (getattr(p, "product", "") == "I") and (getattr(p, "quantity", 0) or 0) != 0:
            return True
    return False


async def get_snapshot_for_injection(
    user_id: int,
    thread_id: str | None,
    access_token: str | None,
    ttl_seconds: float = 30.0,
) -> str | None:
    """Snapshot text to inject into the orchestrator, or None when flat.

    Gated on open intraday positions (the snapshot only matters when something
    is live to manage). Short TTL cache so a chatty interactive session holding
    a position doesn't rebuild + re-hit the API every message — awakenings fire
    minutes apart so the cache never masks freshness for them. Negative (flat)
    results are cached too, to skip the gate call on rapid messages.
    """
    import time

    now = time.monotonic()
    hit = _INJECT_CACHE.get(user_id)
    if hit and (now - hit[0]) < ttl_seconds:
        return hit[1]

    if not await _has_open_intraday(user_id, access_token):
        _INJECT_CACHE[user_id] = (now, None)
        return None

    res = await build_trading_snapshot(user_id, thread_id=thread_id, scan_top_n=5)
    text = res.text if (res and res.text) else None
    _INJECT_CACHE[user_id] = (now, text)
    return text
