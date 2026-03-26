# nf-quote — Live Quotes, Historical Data & Symbol Search

Fetch live stock quotes, historical OHLCV candle data, and search for NSE symbols.

## Usage

### Live Quote
```bash
nf-quote SYMBOL [SYMBOL2 ...] [--json]
```
Shows: LTP, change, % change, open, high, low, close, volume.

### Historical OHLCV
```bash
nf-quote SYMBOL --historical [--interval 1minute|5minute|15minute|30minute|day] [--days 30] [--json]
```
Returns OHLCV candle data. Default: daily candles for 30 days.

### Search Symbols
```bash
nf-quote --search TERM [--json]
```
Search any NSE stock by name or symbol (8000+ available). Returns matching symbols with company names and ISINs.

### List Nifty 50
```bash
nf-quote --list [--json]
```
Show all Nifty 50 constituent symbols (curated list).

## Examples

```bash
nf-quote RELIANCE                     # Live quote
nf-quote RELIANCE TCS INFY            # Multiple quotes
nf-quote RELIANCE --historical --days 60  # 60 days of daily candles
nf-quote RELIANCE --historical --interval 15minute --days 5  # Intraday candles
nf-quote --search "pharma"            # Find pharma stocks
nf-quote --search "TATA"              # Find Tata group stocks
```

## When to use
- **Quick price check**: `nf-quote RELIANCE`
- **Before placing orders**: Get current LTP for limit price decisions
- **Technical analysis input**: Use `nf-analyze` instead (wraps quotes + indicators)
- **Finding a symbol**: `nf-quote --search TERM` for any NSE stock
