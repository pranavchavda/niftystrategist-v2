# nf-portfolio — Portfolio, Positions & Position Conversion

View portfolio holdings, intraday positions, calculate position sizes, and convert between product types.

## Subcommands

### Default (no flags)
Show full portfolio summary with holdings and intraday positions.

```bash
nf-portfolio [--json]
```

### --position SYMBOL
Show details for a specific position (checks both delivery and intraday).

```bash
nf-portfolio --position RELIANCE [--json]
```

### --calc-size SYMBOL
Calculate recommended position size based on risk parameters.

```bash
nf-portfolio --calc-size RELIANCE --risk 5000 --sl 2 [--json]
```

- `--risk` = Maximum loss amount in rupees (default: 5000)
- `--sl` = Stop loss percentage (default: 2.0%)

### convert
Convert an open position between Intraday (MIS) and Delivery (CNC) product types.

```bash
nf-portfolio convert SYMBOL QTY --from D|I --to D|I [--side BUY|SELL] [--json]
```

**Common use case**: You entered an intraday trade but want to hold it overnight — convert from Intraday to Delivery before 3:15 PM to avoid auto-squareoff.

```bash
# Convert 10 shares from intraday to delivery
nf-portfolio convert RELIANCE 10 --from I --to D

# Convert a sell position
nf-portfolio convert TCS 5 --from D --to I --side SELL
```

**Important**: Position conversion requires the position to exist. The `--side` flag refers to the original transaction type (BUY or SELL) that created the position.

## When to use

| Scenario | Command |
|----------|---------|
| Check overall P&L | `nf-portfolio` |
| How many shares of X do I hold? | `nf-portfolio --position X` |
| How many shares should I buy with ₹5000 risk? | `nf-portfolio --calc-size X --risk 5000 --sl 2` |
| Keep intraday trade overnight | `nf-portfolio convert X QTY --from I --to D` |
| Day-trade a delivery holding | `nf-portfolio convert X QTY --from D --to I` |
