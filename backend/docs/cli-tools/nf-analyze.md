# nf-analyze — Technical Analysis

Full technical analysis with RSI, MACD, moving averages, Bollinger Bands, and trading signals.

## Usage

### Single Stock Analysis
```bash
nf-analyze SYMBOL [--interval 15minute|30minute|day] [--json]
```

Shows:
- **Price action**: Current price, day change, support/resistance levels
- **RSI**: Overbought (>70) / Oversold (<30) signals
- **MACD**: Signal line crossovers, histogram momentum
- **Moving Averages**: SMA/EMA 20, 50, 200 with golden/death cross detection
- **Bollinger Bands**: Upper/lower bands, squeeze detection
- **Trading Signals**: Consolidated buy/sell/neutral recommendation

### Compare Multiple Stocks
```bash
nf-analyze SYMBOL1 SYMBOL2 [SYMBOL3 ...] --compare [--json]
```

Side-by-side signal comparison for 2-5 stocks. Shows which stocks have the strongest signals.

## Examples

```bash
nf-analyze RELIANCE                       # Full analysis on daily timeframe
nf-analyze RELIANCE --interval 15minute   # Intraday analysis
nf-analyze RELIANCE TCS --compare         # Compare two stocks
nf-analyze SBIN ICICIBANK HDFCBANK --compare --json  # Compare banks, JSON output
```

## When to use vs other tools
- **Quick price**: `nf-quote` (no indicators)
- **Full analysis with signals**: `nf-analyze` (this tool)
- **Morning screening**: `nf-morning-scan` (scans entire universe)
- **Backtesting a strategy**: `nf-backtest`
