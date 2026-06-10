"""Higher-timeframe (daily) trend detection — the regime gate for backtest sweeps.

WHY THIS EXISTS: the 2026-06 replication experiment. A recent-window 15-minute
sweep produced 57 "confirmed" combos; rerunning the same grid on the PRIOR
40-day window (``--end-offset-days 40``) killed 6 of the 7 top winners and
crowned different stock-directions — one symbol flipped short→long between
windows. Conclusion: bare indicator combos are *regime-followers* with no
transferable edge of their own. The surviving hypothesis is that **regime
detection is the edge**: gate intraday entries by an independently-detected
daily trend, so a combo only expresses a regime instead of pretending to
predict one. This module supplies that gate to the sweep stack.

NO LOOKAHEAD — the critical invariant: the trend used for date D is computed
ONLY from daily candles up to and including D-1's close. A trade entered at
10:30 on day D cannot know day D's close. Implemented by computing the causal
indicator series over the daily closes and then SHIFTING it one day forward
when building the per-date map (``compute_daily_trend``). Enforced by an
explicit test: a huge up-candle on day D must not make day D itself "up".

Variants (deliberately just three — this is a hypothesis test, not a zoo):

  daily_ema20    — prior close vs its EMA20: above → "up", below → "down".
  daily_ema20_50 — EMA20 vs EMA50 cross state: 20>50 → "up", 20<50 → "down".
  daily_mom3     — sign of 3-day close-to-close momentum.

Insufficient history for a variant's indicator → "flat" (which the gate treats
as block-both — conservative: no detected regime, no trade).

PURE module: no I/O, no network, stdlib only. Sibling of ``ranking.py``.
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime, timedelta
from typing import Callable

# The variants the sweep/CLI may request. Keep this the single source of truth.
HTF_VARIANTS = ["daily_ema20", "daily_ema20_50", "daily_mom3"]


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _candle_date(c) -> date:
    """The calendar date of a daily candle (dict or attribute-style)."""
    ts = c["timestamp"] if isinstance(c, dict) else c.timestamp
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    if isinstance(ts, datetime):
        return ts.date()
    return ts  # already a date


def _candle_close(c) -> float:
    return float(c["close"] if isinstance(c, dict) else c.close)


def _ema_series(values: list[float], period: int) -> list[float | None]:
    """Causal EMA series. ``None`` until the seed SMA has ``period`` values.

    Seeded with the SMA of the first ``period`` closes (the standard
    convention), then recursive — so ``series[i]`` depends only on
    ``values[0..i]``, which is what makes the one-day shift in
    ``compute_daily_trend`` sufficient for no-lookahead.
    """
    n = len(values)
    out: list[float | None] = [None] * n
    if n < period:
        return out
    k = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    out[period - 1] = ema
    for i in range(period, n):
        ema = values[i] * k + ema * (1 - k)
        out[i] = ema
    return out


def _direction_series(closes: list[float], variant: str) -> list[str]:
    """Per-day direction AT THAT DAY'S CLOSE (unshifted — callers must shift).

    ``out[i]`` is what an observer knows at the close of day i. "flat" wherever
    the indicator lacks history (or sits exactly on its reference level).
    """
    n = len(closes)
    out = ["flat"] * n

    if variant == "daily_ema20":
        ema20 = _ema_series(closes, 20)
        for i in range(n):
            e = ema20[i]
            if e is None:
                continue
            out[i] = "up" if closes[i] > e else ("down" if closes[i] < e else "flat")

    elif variant == "daily_ema20_50":
        ema20 = _ema_series(closes, 20)
        ema50 = _ema_series(closes, 50)
        for i in range(n):
            a, b = ema20[i], ema50[i]
            if a is None or b is None:
                continue
            out[i] = "up" if a > b else ("down" if a < b else "flat")

    elif variant == "daily_mom3":
        for i in range(3, n):
            diff = closes[i] - closes[i - 3]
            out[i] = "up" if diff > 0 else ("down" if diff < 0 else "flat")

    else:
        raise ValueError(
            f"unknown HTF trend variant: {variant!r}. Valid: {', '.join(HTF_VARIANTS)}"
        )

    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_daily_trend(daily_candles: list[dict], variant: str) -> dict[date, str]:
    """Map each trading date to the trend KNOWN at that day's open: "up"/"down"/"flat".

    The value for date D is the direction computed from daily closes up to and
    including D-1 — i.e. the unshifted direction series moved one day forward.
    The first date in the series maps to "flat" (no prior close to judge from).

    One extra "ghost" key is added at (last_date + 1 day) carrying the direction
    at the LAST candle's close. Combined with ``make_entry_gate``'s
    most-recent-prior-key fallback, this gives any post-series session (e.g.
    today, whose daily candle doesn't exist yet) the freshest no-lookahead
    value instead of a one-day-stale one. Still zero lookahead: the ghost value
    only ever uses closes strictly before the dates it serves.

    Accepts dict candles ({"timestamp", "close"}) or attribute-style OHLCV
    objects. Duplicate dates keep the last close seen. Raises ValueError on an
    unknown variant.
    """
    rows = sorted(
        {(_candle_date(c)): _candle_close(c) for c in daily_candles}.items()
    )
    if not rows:
        # Still validate the variant so a typo fails loudly, not as an
        # all-flat (block-everything) gate.
        _direction_series([], variant)
        return {}

    dates = [d for d, _ in rows]
    closes = [c for _, c in rows]
    dirs = _direction_series(closes, variant)

    trend: dict[date, str] = {dates[0]: "flat"}  # no prior close → no opinion
    for i in range(1, len(dates)):
        trend[dates[i]] = dirs[i - 1]
    trend[dates[-1] + timedelta(days=1)] = dirs[-1]  # ghost (see docstring)
    return trend


def make_entry_gate(
    trend_by_date: dict[date, str], mode: str = "align"
) -> Callable[[datetime, str], bool]:
    """Build an ``entry_gate`` callable for ``run_scalp_equity_backtest``.

    ``align`` (the only mode): a long entry is allowed only when the entry
    date's trend is "up", a short only when "down". "flat" blocks BOTH —
    conservative: no independently detected regime means no trade, which is
    the whole hypothesis being tested.

    Dates missing from the map (a session day whose daily candle isn't in the
    series, or anything past the ghost key) fall back to the most recent PRIOR
    key — never a later one, so the no-lookahead invariant holds at the gate
    too. A date before the entire series has no information → "flat" → block.
    """
    if mode != "align":
        raise ValueError(f"unknown entry-gate mode: {mode!r} (only 'align' exists)")

    keys = sorted(trend_by_date)

    def gate(ts: datetime, side: str) -> bool:
        d = ts.date() if isinstance(ts, datetime) else ts
        trend = trend_by_date.get(d)
        if trend is None:
            idx = bisect_right(keys, d) - 1
            trend = trend_by_date[keys[idx]] if idx >= 0 else "flat"
        if side == "long":
            return trend == "up"
        if side == "short":
            return trend == "down"
        return False  # unknown side: block (defensive)

    return gate
