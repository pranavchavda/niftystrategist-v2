# nf-order — Order Management

Place, view, modify, and cancel stock orders. Supports equity and F&O orders.

## Subcommands

### buy / sell
Place a buy or sell order.

```bash
nf-order buy SYMBOL QTY [--type MARKET|LIMIT] [--price P] [--product D|I] [--amo] [--dry-run] [--json]
nf-order sell SYMBOL QTY [--type MARKET|LIMIT] [--price P] [--product D|I] [--amo] [--dry-run] [--json]
```

- `--product D` = Delivery/CNC (full margin, hold overnight) — DEFAULT
- `--product I` = Intraday/MIS (lower margin ~5x leverage, auto-squared-off at 3:15-3:25 PM IST)
- `--amo` = Force after-market order (auto-detected if market is closed when omitted)
- `--dry-run` = Preview order without executing (shows estimated value, current LTP)

### modify
Modify an existing pending/open order's price, quantity, or type.

```bash
nf-order modify ORDER_ID [--quantity N] [--price P] [--type MARKET|LIMIT] [--trigger-price P] [--json]
```

Must specify at least one of: `--quantity`, `--price`, `--type`, `--trigger-price`. This replaces the old cancel-and-replace workflow.

### detail
Show full details for a specific order by ID.

```bash
nf-order detail ORDER_ID [--json]
```

Shows: symbol, action, quantity (filled/pending), order type, price, average price, trigger price, status, status message, product, validity, exchange, timestamps.

### history
Show the complete state transition history of an order (placed -> modified -> filled/rejected).

```bash
nf-order history ORDER_ID [--json]
```

Useful for debugging why an order was rejected or understanding partial fills.

### trades
Show trade fills (execution details) for a specific order.

```bash
nf-order trades ORDER_ID [--json]
```

Shows trade ID, symbol, action, quantity, execution price, exchange, timestamp. Useful for partial fill analysis.

### list
Show open or all recent orders.

```bash
nf-order list [--all] [--limit N] [--json]
```

Default shows only open/pending orders. `--all` shows filled, rejected, cancelled too.

### cancel
Cancel a single open order.

```bash
nf-order cancel ORDER_ID [--json]
```

### cancel-all
Cancel all open orders at once (bulk cancel).

```bash
nf-order cancel-all [--tag TAG] [--segment EQ|FO] [--json]
```

- `--tag` = Only cancel orders with this tag (useful for cancelling spread baskets)
- `--segment` = Only cancel equity or F&O orders

### exit-all
Exit ALL open positions immediately (panic button).

```bash
nf-order exit-all [--json]
```

**Use with extreme caution.** This places market orders to close every open position (both intraday and delivery). Intended for emergency risk management situations.

## When to use which tool

| Scenario | Tool |
|----------|------|
| Place a single equity order | `nf-order buy/sell` |
| Place an F&O option order | `nf-options buy/sell` (resolves instrument keys) |
| Place a multi-leg spread | `nf-options spread` (uses multi-order API with basket benefit) |
| Modify a pending order's price | `nf-order modify ORDER_ID --price X` |
| Check why an order was rejected | `nf-order history ORDER_ID` |
| Cancel all open orders before market close | `nf-order cancel-all` |
| Emergency exit everything | `nf-order exit-all` |
| Set-and-forget stop-loss/target | `nf-gtt` (server-side, persists across sessions) |
| Complex conditional triggers | `nf-monitor` (client-side, supports indicators, compounds) |
