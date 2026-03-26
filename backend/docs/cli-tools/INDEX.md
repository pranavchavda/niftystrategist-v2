# CLI Tools Reference

All trading operations in NiftyStrategist use CLI tools in `backend/cli-tools/`, invoked by the orchestrator via `execute_bash`. Use `--json` for structured output and `--help` for any tool's full syntax.

## Tool Selection Guide

### Market Data & Analysis
| Need | Tool |
|------|------|
| Is market open? When does it close? | `nf-market-status` |
| Upcoming holidays, is date X a holiday? | `nf-market-status --holidays` |
| Exchange session times for a date | `nf-market-status --timings YYYY-MM-DD` |
| Live stock quote | `nf-quote SYMBOL` |
| Historical OHLCV candles | `nf-quote SYMBOL --historical` |
| Search for a stock symbol | `nf-quote --search TERM` |
| Technical analysis (RSI, MACD, signals) | `nf-analyze SYMBOL` |
| Compare multiple stocks | `nf-analyze SYM1 SYM2 --compare` |
| Morning momentum scanner | `nf-morning-scan` |

### Portfolio & Funds
| Need | Tool |
|------|------|
| Full portfolio summary | `nf-portfolio` |
| Single position details | `nf-portfolio --position SYMBOL` |
| Position size calculator | `nf-portfolio --calc-size SYMBOL --risk N --sl N` |
| Convert intraday to delivery | `nf-portfolio convert SYMBOL QTY --from I --to D` |
| Available margin / buying power | `nf-funds` |
| Pre-order margin check | `nf-margin SYMBOL QTY` |
| User profile / active segments | `nf-profile` |

### Orders (Equity)
| Need | Tool |
|------|------|
| Place equity order | `nf-order buy/sell SYMBOL QTY` |
| Modify pending order | `nf-order modify ORDER_ID --price P` |
| Cancel single order | `nf-order cancel ORDER_ID` |
| Cancel all open orders | `nf-order cancel-all` |
| Exit ALL positions (panic) | `nf-order exit-all` |
| View open orders | `nf-order list` |
| Order details / status | `nf-order detail ORDER_ID` |
| Order state history | `nf-order history ORDER_ID` |
| Order trade fills | `nf-order trades ORDER_ID` |

### GTT Orders (Server-Side Persistent)
| Need | Tool |
|------|------|
| Set-and-forget stop-loss | `nf-gtt place SYMBOL SELL QTY --stoploss PRICE` |
| OCO (target + stoploss) | `nf-gtt place SYMBOL SELL QTY --target P --stoploss P` |
| Entry trigger (buy on dip) | `nf-gtt place SYMBOL BUY QTY --trigger PRICE` |
| Trailing trigger | `nf-gtt place SYMBOL BUY QTY --trigger P --trailing GAP` |
| View all GTT orders | `nf-gtt list` |
| Modify GTT trigger/qty | `nf-gtt modify GTT_ID --trigger P` |
| Cancel GTT order | `nf-gtt cancel GTT_ID` |

### Options (F&O)
| Need | Tool |
|------|------|
| Option chain | `nf-options chain SYMBOL` |
| Live chain with greeks | `nf-options live-chain SYMBOL YYYY-MM-DD` |
| Option greeks | `nf-options greeks SYMBOL --expiry X` |
| Expiry dates | `nf-options expiries SYMBOL` |
| Place single option order | `nf-options buy/sell SYMBOL EXPIRY STRIKE CE/PE LOTS` |
| **Multi-leg spread (Strategy Builder)** | `nf-options spread SYMBOL --expiry X --legs BUY:STRIKE:CE SELL:STRIKE:CE` |
| F&O charges estimate | `nf-options charges SYMBOL EXPIRY STRIKE CE/PE LOTS` |
| F&O positions | `nf-options positions` |
| Trade planner (strike selection) | `nf-options plan SYMBOL --expiry X` |
| F&O-eligible symbols | `nf-options fno-symbols` |

### Trades & P&L
| Need | Tool |
|------|------|
| Today's executed trades | `nf-trades` |
| Historical trades | `nf-trades history` |
| Trade charges (brokerage, STT) | `nf-trades charges --days 7` |
| P&L report (buy/sell averages) | `nf-trades report` |
| Pre-trade brokerage estimate | `nf-brokerage SYMBOL QTY` |

### Monitoring & Automation
| Need | Tool |
|------|------|
| Price/indicator trigger rules | `nf-monitor add-rule` |
| OCO stop-loss + target | `nf-monitor add-oco` |
| Trailing stop-loss | `nf-monitor add-trailing` |
| Strategy template deployment | `nf-strategy deploy TEMPLATE` |
| Watchlist with price alerts | `nf-watchlist` |

## GTT vs Monitor vs Spread — When to Use What

| Feature | nf-gtt | nf-monitor | nf-options spread |
|---------|--------|------------|-------------------|
| Use case | Simple SL/target | Complex conditions | Multi-leg F&O |
| Execution | Server-side | Client-side daemon | Immediate basket |
| Price triggers | Yes | Yes | N/A (immediate) |
| Indicator triggers | No | Yes (RSI, MACD) | No |
| Spread margin benefit | No | No | Yes |
| Survives disconnects | Yes | Depends on daemon | N/A |
| Trailing stop | Yes | Yes | No |
