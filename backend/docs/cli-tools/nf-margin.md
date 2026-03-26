# nf-margin — Pre-Order Margin Calculator

Calculate required margin before placing orders. Supports equity and F&O, single and multi-instrument calculations. Shows SPAN, exposure, and equity margin breakdowns.

## Usage

```bash
nf-margin SYMBOL QTY [SYMBOL2 QTY2 ...] [--product D|I] [--side BUY|SELL] [--price P] [--json]
```

Arguments are symbol-quantity pairs. You can check margin for multiple instruments at once.

## Examples

```bash
# Single stock, delivery
nf-margin RELIANCE 10                    # ₹14,131

# Single stock, intraday (much lower margin due to leverage)
nf-margin RELIANCE 10 --product I        # ₹2,826 (~5x leverage)

# Multiple stocks
nf-margin RELIANCE 10 TCS 5             # ₹26,018 combined

# Sell margin
nf-margin RELIANCE 10 --side SELL

# With specific price
nf-margin RELIANCE 10 --price 1450
```

## Output

Shows per-instrument breakdown:
- **Equity Margin**: Required for equity delivery trades
- **SPAN Margin**: For F&O (Standard Portfolio Analysis of Risk)
- **Exposure Margin**: Additional margin for F&O
- **Total Margin**: Sum of all margin components

And a summary **Required Margin** for the combined order.

## When to use

| Scenario | Example |
|----------|---------|
| Check if you can afford a trade | `nf-margin RELIANCE 100` then compare with `nf-funds` |
| Compare delivery vs intraday cost | `nf-margin RELIANCE 10` vs `nf-margin RELIANCE 10 --product I` |
| Multi-stock basket margin | `nf-margin RELIANCE 10 TCS 5 INFY 20` |
| Pre-F&O trade check | Use with `nf-options spread --dry-run` for spread margin with benefit |

## Note on Spread Margin

For option spread margin with hedge benefit, use `nf-options spread --dry-run` instead. The margin API called with individual instruments won't show the spread/basket discount — that benefit comes from the multi-order placement via `correlation_id`.
