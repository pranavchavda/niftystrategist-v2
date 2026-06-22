"""Conviction Accumulation strategy template (Score-9 "let it run" play).

For a high-conviction long: enter an initial tranche on a breakout, then add
equal tranches on dips at pre-identified levels (e.g. session VWAP, prior
support). Hold to a wide trailing stop or the close — there is NO fixed target,
this is a ride-the-trend play. A shared stop sits below the day's low.

Quantity-safe by design: each tranche is SELF-CONTAINED. A tranche's entry
activates only ITS OWN paired stop + square-off (each sized to that tranche's
quantity), gated off until the entry fills. So an exit can never sell more than
was actually bought — no rogue-short risk if some dips never fill. When the
shared stop level is hit, every *filled* tranche's stop fires independently and
the position flattens exactly. (Mirrors the laddered self-contained pattern in
utbot-scalp-options-ladder; honours the exits-start-disabled invariant.)

Long-only for v1 — the framework this came from (Score-9 momentum names) is
inherently bullish; the COALINDIA / ATGL examples were both longs.
"""
from __future__ import annotations

from typing import Any

from strategies.sizing import compute_accumulation_quantity
from strategies.templates import RuleSpec, StrategyPlan, StrategyTemplate


class ConvictionAccumulateTemplate(StrategyTemplate):
    name = "conviction-accumulate"
    description = (
        "Conviction accumulation (long) — initial tranche on breakout, equal "
        "add-on tranches on dips (VWAP/support), shared stop below day low, hold "
        "to a wide trail or square-off. No fixed target. Each tranche carries its "
        "own gated stop + square-off (quantity-safe)."
    )
    required_params = ["capital", "entry", "sl"]
    optional_params = {
        "dip_levels": [],          # add-on buy prices below entry (e.g. VWAP, support)
        "risk_percent": 2.0,       # worst-case risk if ALL tranches fill
        "trail_percent": 0.0,      # 0 = no trail (pure hold-to-close); e.g. 5.0
        "squareoff_time": "15:15",
        "product": "I",
    }

    def plan(self, symbol: str, params: dict[str, Any]) -> StrategyPlan:
        p = self.validate_params(params)
        capital = p["capital"]
        entry = float(p["entry"])
        sl = float(p["sl"])
        risk_pct = p["risk_percent"]
        trail_pct = float(p["trail_percent"] or 0.0)
        squareoff = p["squareoff_time"]
        product = p["product"]

        dip_levels = [float(d) for d in (p.get("dip_levels") or [])]

        # ── Validation ──────────────────────────────────────────────────────
        if sl >= entry:
            raise ValueError(
                f"Stop ({sl}) must be below the entry ({entry}) for a long "
                "accumulation."
            )
        for d in dip_levels:
            if not (sl < d < entry):
                raise ValueError(
                    f"Dip level {d} must sit between the stop ({sl}) and the "
                    f"entry ({entry}). Dips are pullback adds below the breakout, "
                    "above the stop."
                )

        # Tranche entry prices: initial breakout first, then dips high→low so the
        # nearest dip is tranche 1. Equal quantity at each.
        entries = [entry] + sorted(dip_levels, reverse=True)
        n = len(entries)
        qty = compute_accumulation_quantity(
            capital, risk_pct, entries, sl, product=product
        )

        trail_label = f"trail {trail_pct}%" if trail_pct > 0 else "hold to close"
        plan = StrategyPlan(
            template_name=self.name,
            symbol=symbol,
            summary=(
                f"Conviction accumulate {symbol}: {n} tranches × {qty} "
                f"(entry {entry}" + (f" + dips {dip_levels}" if dip_levels else "")
                + f"), shared SL {sl}, {trail_label}, square-off {squareoff}"
            ),
            params=p,
        )

        # Dip-add entries arm only AFTER the breakout fires — so we never buy a
        # dip in a name that never broke out (catching a falling knife). The
        # initial breakout entry activates every dip entry plus its own exits.
        dip_entry_roles = [f"entry_{i}" for i in range(1, n)]

        rules: list[RuleSpec] = []
        for i, price in enumerate(entries):
            r_entry = f"entry_{i}"
            r_sl = f"sl_{i}"
            r_sqoff = f"sqoff_{i}"
            r_trail = f"trail_{i}"

            # This tranche's exits — all gated, activated when the entry fills.
            this_exits = [r_sl, r_sqoff]
            if trail_pct > 0:
                this_exits.append(r_trail)

            # Entry: breakout (gte) for the initial tranche, dip (lte) for adds.
            if i == 0:
                entry_cond = "gte"
                entry_label = f"Breakout Entry ≥ {price}"
                # Breakout also arms the dip-add entries.
                entry_activates = this_exits + dip_entry_roles
            else:
                entry_cond = "lte"
                entry_label = f"Dip Add #{i} ≤ {price}"
                entry_activates = this_exits
            rules.append(RuleSpec(
                name=f"{symbol} Accumulate {entry_label}",
                trigger_type="price",
                trigger_config={"condition": entry_cond, "price": price, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "BUY",
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role=r_entry,
                # Dip entries (i>0) start disabled — armed by the breakout.
                enabled=(i == 0),
                activates_roles=entry_activates,
            ))

            # Shared stop level, sized to this tranche. Disabled until entry fills.
            # The stop means the conviction thesis is invalidated, so it also
            # tears down any remaining un-filled dip adds — once stopped out we
            # stay flat, we don't re-enter on a later bounce through a dip level.
            rules.append(RuleSpec(
                name=f"{symbol} Accumulate SL @ {sl} (tranche {i})",
                trigger_type="price",
                trigger_config={"condition": "lte", "price": sl, "reference": "ltp"},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "SELL",
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role=r_sl,
                enabled=False,
                kills_roles=[x for x in this_exits if x != r_sl] + dip_entry_roles,
            ))

            # Per-tranche square-off, sized to this tranche. Disabled until entry
            # fills. Square-off = end of day, so it also kills remaining dip adds
            # (no fresh entries after we've begun flattening for the close).
            rules.append(RuleSpec(
                name=f"{symbol} Accumulate Square-Off @ {squareoff} (tranche {i})",
                trigger_type="time",
                trigger_config={"at": squareoff, "on_days": ["mon", "tue", "wed", "thu", "fri"], "market_only": True},
                action_type="place_order",
                action_config={
                    "symbol": symbol, "transaction_type": "SELL",
                    "quantity": qty, "order_type": "MARKET", "product": product,
                },
                role=r_sqoff,
                enabled=False,
                kills_roles=[x for x in this_exits if x != r_sqoff] + dip_entry_roles,
            ))

            # Optional per-tranche trailing stop (anchored at this entry).
            if trail_pct > 0:
                rules.append(RuleSpec(
                    name=f"{symbol} Accumulate Trail {trail_pct}% (tranche {i})",
                    trigger_type="trailing_stop",
                    trigger_config={
                        "trail_percent": trail_pct, "initial_price": price,
                        "highest_price": price, "direction": "long", "reference": "ltp",
                    },
                    action_type="place_order",
                    action_config={
                        "symbol": symbol, "transaction_type": "SELL",
                        "quantity": qty, "order_type": "MARKET", "product": product,
                    },
                    role=r_trail,
                    enabled=False,
                    kills_roles=[x for x in this_exits if x != r_trail],
                ))

        plan.rules = rules
        return plan
