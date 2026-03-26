# nf-options — Options Trading (Base Features)

Options trading tool supporting both index options (NIFTY, BANKNIFTY) and stock options (~200 F&O-eligible stocks). For multi-leg spread orders, see `nf-options-spread.md`.

## Subcommands

### chain
Show option chain from instruments cache.

```bash
nf-options chain SYMBOL [--expiry DDMMM] [--json]
```

### live-chain
Live option chain with greeks from Upstox API.

```bash
nf-options live-chain SYMBOL YYYY-MM-DD [--json]
```

### greeks
Option greeks (delta, gamma, theta, vega, IV) via Upstox v3 API.

```bash
nf-options greeks SYMBOL [--expiry DDMMM|YYYY-MM-DD] [--strikes 25000 25500] [--type CE|PE] [--json]
```

### expiries
Show upcoming expiry dates for a symbol.

```bash
nf-options expiries SYMBOL [--json]
```

### quote
Get a single option quote.

```bash
nf-options quote SYMBOL EXPIRY STRIKE CE|PE [--json]
```

### buy / sell
Place a single option order (HITL-protected).

```bash
nf-options buy|sell SYMBOL EXPIRY STRIKE CE|PE LOTS [--price P] [--type MARKET|LIMIT] [--dry-run] [--json]
```

`--dry-run` includes: charges breakdown, funds sufficiency check, break-even premium, max loss calculation, live LTP.

### charges
Estimate F&O charges for an options trade.

```bash
nf-options charges SYMBOL EXPIRY STRIKE CE|PE LOTS [--side BUY|SELL] [--price P] [--exit-price P] [--json]
```

`--exit-price` adds round-trip cost estimate (entry + exit).

### positions
View all open F&O positions with P&L.

```bash
nf-options positions [--json]
```

### plan
Trade planner — finds optimal strikes based on capital and bias.

```bash
nf-options plan SYMBOL --expiry YYYY-MM-DD [--side buy|sell] [--bias bullish|bearish] [--capital N] [--lots N] [--json]
```

Shows: ATM/ITM/OTM candidates, affordability by capital, charges per candidate.

### fno-symbols
List all F&O-eligible stock symbols.

```bash
nf-options fno-symbols [--json]
```

## Key Notes

- **Stock options**: Monthly expiry (last Thursday), physical delivery on expiry
- **Index options**: Weekly expiry, cash settlement
- **Lot sizes**: Vary by symbol (NIFTY=50, BANKNIFTY=15, stocks vary)
- **For multi-leg spreads with margin benefit**: Use `nf-options spread` instead of separate buy/sell
