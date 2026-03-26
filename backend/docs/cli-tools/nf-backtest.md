# nf-backtest — Strategy Backtesting

Backtest trading strategy templates against historical data to evaluate performance before live deployment.

## Usage

```bash
nf-backtest --strategy TEMPLATE --symbol SYM [--symbols SYM1,SYM2] [--days 30] \
  [--interval 1minute|5minute|15minute|30minute] [--capital N] [--risk-percent N] \
  [--rr-ratio N] [--trail-percent N] [--side long|short] [--json]
```

## Strategy Templates

- `orb` — Opening Range Breakout
- `breakout` — Price breakout with entry/SL/target
- `mean-reversion` — Mean reversion with RSI/VWAP
- `vwap-bounce` — VWAP support/resistance bounce
- `scalp` — Quick scalping with tight stops

## Strategy-Specific Parameters

- `--entry`, `--sl`, `--target` — Price levels
- `--entry-pct`, `--sl-pct` — Percentage-based levels (for multi-day)
- `--range-high`, `--range-low` — For ORB strategy

## Examples

```bash
# Backtest ORB on RELIANCE, last 30 days, 15-minute candles
nf-backtest --strategy orb --symbol RELIANCE --days 30 --interval 15minute

# Multi-symbol breakout comparison
nf-backtest --strategy breakout --symbols RELIANCE,TCS,INFY --days 60 --capital 100000

# Scalping with tight risk
nf-backtest --strategy scalp --symbol SBIN --interval 5minute --risk-percent 0.5 --rr-ratio 1.5
```

## When to use
- **Before deploying a strategy**: Test historical performance
- **Comparing strategies**: Run same timeframe with different templates
- **Optimizing parameters**: Try different SL%, RR ratios, intervals
- **After backtesting**: Deploy the winning strategy with `nf-strategy deploy`
