"""Intraday sector-flow sensor — the pure core.

Layer 1 of the sector-direction edge (Pranav, 2026-06-27). The thesis: a sector
moving decisively as a BLOC intraday is a tradeable directional signal (long the
strongest / short the weakest constituents), and the alpha is catching it EARLY —
while breadth is still EXPANDING — not after the index has already printed the move.

Motivating miss: Thu 2026-06-25, IT sold off in the back half of the day with no
fresh catalyst (pure positioning unwind of a 2-day counter-trend bounce off the
06-23 Accenture news). NS never sensed it because nothing watched the sector
develop intraday — sector posture was only ever read at the 9:20 briefing.

KEY DESIGN — decisiveness is the DERIVATIVE, not the level. "6 of 10 names below
their open" is drift if it's been 6/10 for an hour; "3/10 → 7/10 in 30 min with a
widening median" is a decisive bloc move. So the core number is Δbreadth over a
trailing window, not breadth itself.

Pure — no I/O. The live CLI (`nf-sector-flow`) and the historical replay
(`scripts/replay_sector_flow.py`) both feed this the same shapes, so the metric
is identical in production and in validation. Thresholds are deliberately NOT
baked in as verdicts here — the core emits continuous metrics; the CLI applies
tunable cutoffs that we set from the backtest (validation-first), not by hand.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

# A constituent counts toward up/down breadth only if it has moved more than this
# (% from session open) — filters flat names so breadth reflects conviction, not
# noise. Tunable; set from the backtest.
DEFAULT_MOVE_THRESHOLD = 0.3

# Trailing window (in bars) over which acceleration (Δbreadth) is measured.
# 2 bars of 15-min candles = 30 min — the "is it developing right now" horizon.
DEFAULT_WINDOW_BARS = 2


@dataclass
class SectorSnapshot:
    """One sector's directional-breadth reading at a single point in the session."""
    sector: str
    as_of: str                      # "HH:MM"
    n: int                          # constituents with data at this point
    up_frac: float                  # fraction moved > +threshold from open
    down_frac: float                # fraction moved < -threshold from open
    net_breadth: float              # up_frac - down_frac, in [-1, +1]
    median_move: float              # median % from open across constituents
    mean_move: float
    # Filled once the snapshot is part of a timeline (None for the first `window` bars):
    d_net_breadth: Optional[float] = None   # Δ net_breadth over the trailing window
    d_median: Optional[float] = None        # Δ median_move over the trailing window
    accelerating: Optional[bool] = None     # breadth expanding in its own direction
    decisiveness: Optional[float] = None     # |net_breadth| × max(0, aligned Δbreadth), a sortable "act now" score

    def as_dict(self) -> dict:
        return {
            "sector": self.sector, "as_of": self.as_of, "n": self.n,
            "up_frac": round(self.up_frac, 3), "down_frac": round(self.down_frac, 3),
            "net_breadth": round(self.net_breadth, 3),
            "median_move": round(self.median_move, 3), "mean_move": round(self.mean_move, 3),
            "d_net_breadth": None if self.d_net_breadth is None else round(self.d_net_breadth, 3),
            "d_median": None if self.d_median is None else round(self.d_median, 3),
            "accelerating": self.accelerating,
            "decisiveness": None if self.decisiveness is None else round(self.decisiveness, 4),
        }


def pct_from_open(close: float, day_open: float) -> float:
    """Percent move of a constituent from its session open. Raises on a bad open."""
    if day_open <= 0:
        raise ValueError("day_open must be > 0")
    return (close - day_open) / day_open * 100.0


def sector_snapshot(sector: str, as_of: str, pct_moves: dict[str, float],
                    *, threshold: float = DEFAULT_MOVE_THRESHOLD) -> SectorSnapshot:
    """Directional-breadth snapshot from {symbol: pct_from_open} at one instant.

    A name above +threshold counts up, below -threshold counts down; flat names
    count toward n but neither side (so a sector where everything is dead-flat
    reads net_breadth 0, not a spurious split).
    """
    n = len(pct_moves)
    if n == 0:
        return SectorSnapshot(sector, as_of, 0, 0.0, 0.0, 0.0, 0.0, 0.0)
    vals = list(pct_moves.values())
    n_up = sum(1 for v in vals if v > threshold)
    n_down = sum(1 for v in vals if v < -threshold)
    up_frac = n_up / n
    down_frac = n_down / n
    return SectorSnapshot(
        sector=sector, as_of=as_of, n=n,
        up_frac=up_frac, down_frac=down_frac,
        net_breadth=up_frac - down_frac,
        median_move=statistics.median(vals),
        mean_move=statistics.fmean(vals),
    )


def _attach_acceleration(timeline: list[SectorSnapshot], window: int) -> None:
    """Fill Δbreadth / Δmedian / accelerating / decisiveness in place.

    decisiveness = |net_breadth| × max(0, Δmedian aligned with the bloc direction).

    The backtest (IT, 06-23→25, 2026-06-27) showed count-breadth SATURATES — with
    a tight correlated sector the names all move together so net_breadth pins near
    ±1 and its derivative is noise. The MAGNITUDE (median % from open) doesn't
    saturate, so the acceleration term keys off Δmedian; net_breadth stays only as
    a PARTICIPATION weight (a broad move scores higher than a one-name move).

    Bloc direction is set by net_breadth's sign (median's sign as a fallback when
    breadth is exactly 0). The aligned-Δmedian gate naturally zeroes out a relief
    bounce — a down-bloc whose median is ticking UP (breadth and magnitude
    diverging) is NOT a fresh down-signal, so it scores 0 even though the sector is
    still net-red. We want the developing move, not the finished or reverting one.
    """
    for i, snap in enumerate(timeline):
        if i < window:
            continue
        prev = timeline[i - window]
        snap.d_net_breadth = snap.net_breadth - prev.net_breadth
        snap.d_median = snap.median_move - prev.median_move
        direction = 1.0 if snap.net_breadth > 0 else (-1.0 if snap.net_breadth < 0
                                                      else (1.0 if snap.median_move >= 0 else -1.0))
        aligned_median = snap.d_median * direction  # >0 ⇒ median extending in the bloc direction
        snap.accelerating = aligned_median > 0 and abs(snap.net_breadth) > 0
        snap.decisiveness = abs(snap.net_breadth) * max(0.0, aligned_median)


def sector_timeline(sector: str, times: list[str],
                    per_symbol_closes: dict[str, dict[str, float]],
                    per_symbol_open: dict[str, float],
                    *, threshold: float = DEFAULT_MOVE_THRESHOLD,
                    window: int = DEFAULT_WINDOW_BARS) -> list[SectorSnapshot]:
    """Full-session timeline of sector snapshots, with acceleration attached.

    ``times``               — ordered "HH:MM" grid (union of all constituents' bars).
    ``per_symbol_closes``   — {symbol: {"HH:MM": close}}; missing bars are
                              forward-filled from the last known close (an illiquid
                              name with a gap in its candles shouldn't drop out of
                              breadth and make it jump around).
    ``per_symbol_open``     — {symbol: session_open}.
    """
    last_close: dict[str, float] = {}
    timeline: list[SectorSnapshot] = []
    for t in times:
        pct_moves: dict[str, float] = {}
        for sym, day_open in per_symbol_open.items():
            closes = per_symbol_closes.get(sym, {})
            if t in closes:
                last_close[sym] = closes[t]
            c = last_close.get(sym)
            if c is None or day_open <= 0:
                continue  # no data yet for this name at/ before t
            pct_moves[sym] = pct_from_open(c, day_open)
        timeline.append(sector_snapshot(sector, t, pct_moves, threshold=threshold))
    _attach_acceleration(timeline, window)
    return timeline


# ── Layer 2: market-aggregate (regime roll) + sector-relative (laggard/leader) ──
#
# The 06-25 backtest (2026-06-28) showed absolute per-sector breadth is mostly
# market BETA — on a broad-down day every sector reads "decisive down". So the
# tradeable signal splits in two:
#   (1) MARKET-AGGREGATE timeline — the same metrics over the whole universe. Its
#       `decisiveness` is an INTRADAY REGIME-ROLL sensor (the tape turning down/up
#       and accelerating mid-session), which NS otherwise only reads at the 9:20
#       pulse. Build it by calling sector_timeline() with the full universe and a
#       label like "MARKET".
#   (2) SECTOR-RELATIVE (sector − market) — strips the beta. `rel_median` (level)
#       identifies the persistent laggard/leader = WHAT to short/long to express a
#       regime call (IT was ~0.35% weaker than market ALL DAY on 06-25, visible
#       from the open). `d_rel_median` (derivative) catches a sector DECOUPLING in
#       real time = the rarer sector-specific event. Both are exposed; we don't
#       collapse them, because "persistent laggard" and "decoupling now" are
#       different trades.


@dataclass
class RelativeSnapshot:
    """A sector's reading NET OF the market, at one point in the session."""
    sector: str
    as_of: str
    rel_median: float                       # sector.median_move − market.median_move
    rel_breadth: float                      # sector.net_breadth − market.net_breadth
    sector_median: float
    market_median: float
    d_rel_median: Optional[float] = None     # Δ rel_median over the trailing window
    decoupling: Optional[bool] = None        # rel gap widening in its own direction
    rel_decisiveness: Optional[float] = None  # |rel_median| × max(0, aligned Δrel_median)

    def as_dict(self) -> dict:
        return {
            "sector": self.sector, "as_of": self.as_of,
            "rel_median": round(self.rel_median, 3), "rel_breadth": round(self.rel_breadth, 3),
            "sector_median": round(self.sector_median, 3), "market_median": round(self.market_median, 3),
            "d_rel_median": None if self.d_rel_median is None else round(self.d_rel_median, 3),
            "decoupling": self.decoupling,
            "rel_decisiveness": None if self.rel_decisiveness is None else round(self.rel_decisiveness, 4),
        }


def relative_timeline(sector_tl: list[SectorSnapshot], market_tl: list[SectorSnapshot],
                      *, window: int = DEFAULT_WINDOW_BARS) -> list[RelativeSnapshot]:
    """Strip market beta: align a sector timeline against the market-aggregate
    timeline (by ``as_of``) and emit the relative reading at each bar.

    ``rel_decisiveness = |rel_median| × max(0, Δrel_median aligned with the gap's
    sign)`` flags a sector pulling AWAY from the market right now (a real
    sector-specific move). A persistent-but-stable gap (high |rel_median|, ~0
    Δrel_median — IT on 06-25) scores low here BY DESIGN: that's a laggard to
    select from `rel_median`, not a fresh decoupling event.
    """
    by_time = {s.as_of: s for s in market_tl}
    out: list[RelativeSnapshot] = []
    for s in sector_tl:
        m = by_time.get(s.as_of)
        if m is None:
            continue
        out.append(RelativeSnapshot(
            sector=s.sector, as_of=s.as_of,
            rel_median=s.median_move - m.median_move,
            rel_breadth=s.net_breadth - m.net_breadth,
            sector_median=s.median_move, market_median=m.median_move,
        ))
    for i, snap in enumerate(out):
        if i < window:
            continue
        snap.d_rel_median = snap.rel_median - out[i - window].rel_median
        direction = 1.0 if snap.rel_median >= 0 else -1.0
        aligned = snap.d_rel_median * direction
        snap.decoupling = aligned > 0
        snap.rel_decisiveness = abs(snap.rel_median) * max(0.0, aligned)
    return out


def persistent_bias(rel_tl: list[RelativeSnapshot]) -> dict:
    """Session-level relative bias for laggard/leader SELECTION (not timing).

    Returns the average and last `rel_median` plus a label. A sector with a
    consistently negative `rel_median` is the laggard (short vehicle for a bearish
    tape); consistently positive is the leader (long vehicle for a bullish one).
    """
    if not rel_tl:
        return {"avg_rel_median": 0.0, "last_rel_median": 0.0, "bias": "neutral", "n_bars": 0}
    vals = [s.rel_median for s in rel_tl]
    avg = statistics.fmean(vals)
    bias = "laggard" if avg <= -0.15 else ("leader" if avg >= 0.15 else "neutral")
    return {"avg_rel_median": round(avg, 3), "last_rel_median": round(vals[-1], 3),
            "bias": bias, "n_bars": len(rel_tl)}
