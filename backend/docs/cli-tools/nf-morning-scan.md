# nf-morning-scan — Morning Momentum Scanner

Scan the market for high-probability intraday trade candidates. Best run 9:20-9:30 AM IST, just after market open.

## Usage

```bash
nf-morning-scan [--universe nifty50|nifty100|nifty500] [--top N] [--min-score N] [--news] [--json]
```

- `--universe`: Stock universe to scan (default: nifty500). Use nifty50 for faster scans.
- `--top`: Show top N candidates (default: 10)
- `--min-score`: Minimum score threshold
- `--news`: Include market news context via Perplexity

### Debug Mode
```bash
nf-morning-scan --debug SYMBOL
```
Show all raw indicator values for a single stock (gap %, relative strength, RVOL-T, RSI, VWAP).

## Scoring Methodology

Two-phase analysis:
1. **Phase 1 (fast)**: Gap analysis, relative strength vs NIFTY
2. **Phase 2 (detailed)**: RSI, VWAP proximity, RVOL-T (volume relative to time-of-day average)

Outputs trade candidates with setup type suggestions:
- **ORB breakout**: Stock gapped and holding range
- **VWAP pullback**: Stock pulled back to VWAP support
- **Momentum continuation**: Strong trend with volume confirmation

## When to use
- **Morning routine**: Run at 9:20-9:30 IST to find day's best candidates
- **Quick scan**: `nf-morning-scan --universe nifty50 --top 5`
- **Deep scan**: `nf-morning-scan --universe nifty500 --top 20 --news`
- **After scanning**: Use `nf-analyze` for detailed analysis on top picks, then `nf-order` or `nf-strategy` to trade
