# nf-options spread — Multi-Leg Strategy Builder

Place multi-leg option spreads as a single basket order with spread margin benefit. Replicates Upstox's Strategy Builder functionality via the API.

## Why Use Spread Orders

When you place spread legs individually (e.g., separate buy and sell calls), the exchange treats them as independent positions and charges full margin for each. When placed as a basket via `place_multi_order` with a shared `correlation_id`, the exchange recognizes the hedge and provides **reduced margin** (spread benefit).

**Example**: A bull call spread might require ₹41,000 margin as a basket vs ₹1,00,000+ if placed as separate legs.

## Usage

```bash
nf-options spread SYMBOL --expiry YYYY-MM-DD --legs SIDE:STRIKE:TYPE [SIDE:STRIKE:TYPE ...] [--lots N] [--product D|I] [--dry-run] [--json]
```

Leg format: `SIDE:STRIKE:TYPE` where:
- SIDE = `BUY` or `SELL` (also accepts `B` / `S`)
- STRIKE = strike price (e.g., `24250`)
- TYPE = `CE` (Call) or `PE` (Put)

## Supported Strategies

### Bull Call Spread (Debit)
Buy lower-strike CE, Sell higher-strike CE. Bullish, defined risk.

```bash
nf-options spread SHREECEM --expiry 2026-04-28 --legs BUY:24250:CE SELL:25000:CE --lots 1 --dry-run
```

### Bear Put Spread (Debit)
Buy higher-strike PE, Sell lower-strike PE. Bearish, defined risk.

```bash
nf-options spread NIFTY --expiry 2026-04-07 --legs BUY:23500:PE SELL:23000:PE --lots 1 --dry-run
```

### Bull Put Spread (Credit)
Sell higher-strike PE, Buy lower-strike PE. Bullish, collect premium.

```bash
nf-options spread NIFTY --expiry 2026-04-07 --legs SELL:23200:PE BUY:23000:PE --lots 1 --dry-run
```

### Bear Call Spread (Credit)
Sell lower-strike CE, Buy higher-strike CE. Bearish, collect premium.

```bash
nf-options spread NIFTY --expiry 2026-04-07 --legs SELL:23000:CE BUY:23500:CE --lots 1 --dry-run
```

### Iron Condor (Credit, 4 legs)
Sell CE + Buy higher CE + Sell PE + Buy lower PE. Neutral, range-bound.

```bash
nf-options spread NIFTY --expiry 2026-04-07 --legs SELL:23200:CE BUY:23400:CE SELL:22800:PE BUY:22600:PE --lots 1 --dry-run
```

### Straddle (2 legs, same strike)
Buy/Sell both CE and PE at the same strike. Volatility play.

```bash
# Long straddle (buy volatility)
nf-options spread NIFTY --expiry 2026-04-07 --legs BUY:23000:CE BUY:23000:PE --lots 1 --dry-run

# Short straddle (sell volatility)
nf-options spread NIFTY --expiry 2026-04-07 --legs SELL:23000:CE SELL:23000:PE --lots 1 --dry-run
```

## Output

The `--dry-run` output shows:
- **Leg details**: Side, strike, type, premium (live LTP), value per leg
- **Net debit/credit**: Total premium paid or received
- **Max Profit**: Maximum possible profit
- **Max Loss**: Maximum possible loss (defined for spreads)
- **Breakeven(s)**: Price point(s) where P&L = 0
- **Risk/Reward**: Ratio of max profit to max loss
- **Estimated charges**: Brokerage, STT, GST per leg
- **Estimated margin**: Combined margin with spread benefit (from margin API)

## Important Notes

- **Spread margin benefit**: Only applies when legs are placed as a basket (via this tool). Individual `nf-options buy` + `nf-options sell` commands will NOT get the benefit.
- **Exit as a basket**: When exiting spread positions, also exit both legs simultaneously to maintain the margin benefit. If you exit one leg first, the remaining leg becomes a naked position with full margin requirement (the "margin trap").
- **Market hours only**: Multi-order placement requires the market to be open.
- **Lot size**: All legs use the same lot size and lot count. The tool resolves the correct lot size for each underlying.
