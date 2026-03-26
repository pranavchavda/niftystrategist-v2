# nf-brokerage — Pre-Trade Charges Estimate

Estimate brokerage and all charges (STT, GST, stamp duty, transaction charges) before placing an equity order. Uses Upstox's Charge API.

## Usage

```bash
nf-brokerage SYMBOL QTY [--side BUY|SELL] [--product D|I] [--price P] [--json]
```

- Default side: BUY
- Default product: D (Delivery)
- Price: Uses current LTP if not specified

## Examples

```bash
nf-brokerage RELIANCE 10                    # Delivery buy estimate
nf-brokerage RELIANCE 10 --side SELL        # Sell charges (includes STT)
nf-brokerage RELIANCE 10 --product I        # Intraday charges
nf-brokerage RELIANCE 10 --price 1450       # With specific price
```

## When to use
- **Equity orders**: Use this tool
- **F&O charges**: Use `nf-options charges` instead (different rate structure)
- **Margin requirement**: Use `nf-margin` instead (checks if you can afford it)
