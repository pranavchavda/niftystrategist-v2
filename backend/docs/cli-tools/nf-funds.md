# nf-funds — Available Margin & Buying Power

View available funds, used margin, and buying power across equity and commodity segments.

## Usage

```bash
nf-funds [--json]
```

Shows:
- **Available margin**: Cash available for trading
- **Used margin**: Currently blocked for open positions/orders
- **Payin amount**: Funds added today
- **Opening balance**: Start-of-day balance
- Breakdown by segment (equity, commodity)

## When to use
- **Before placing orders**: Check if you have enough margin
- **During trading**: Monitor how much margin is used vs available
- **For margin calculations**: Use `nf-margin` instead (pre-order calculation for specific instruments)
- **In the dashboard**: The TopStrip component also shows this data via `/api/cockpit/funds`
