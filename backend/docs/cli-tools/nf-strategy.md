# nf-strategy — Strategy Template Deployment

Deploy pre-built trading strategy templates that create linked sets of monitor rules. Automates entry, exit, stop-loss, and target rule creation.

## Usage

### List Templates
```bash
nf-strategy list [--json]
```

Available templates: `orb`, `breakout`, `mean-reversion`, `vwap-bounce`, `scalp`

### Deploy a Strategy
```bash
nf-strategy deploy TEMPLATE --symbol SYM --capital AMOUNT [options] [--dry-run] [--json]
```

## Templates

### ORB (Opening Range Breakout)
```bash
nf-strategy deploy orb --symbol SYM --capital 50000 --range-high 2460 --range-low 2440 \
  [--enable-reversal] --json
```
Creates entry rules for breakout above range-high and below range-low, with OCO SL+target on each entry.

### Breakout
```bash
nf-strategy deploy breakout --symbol SYM --capital 50000 --entry 1650 --sl 1630 [--target 1690] --json
```

### Mean Reversion
```bash
nf-strategy deploy mean-reversion --symbol SYM --capital 50000 --sl 1850 [--side long|short] --json
```

### F&O Strategy Deployment
```bash
nf-strategy deploy TEMPLATE --underlying SYMBOL --expiry YYYY-MM-DD --lots N \
  --strike STRIKE [--call-strike X --put-strike Y] --json
```

## How It Works

1. Template defines a set of rules (entry, SL, target)
2. `deploy` creates multiple linked monitor rules in the DB
3. Monitor daemon evaluates rules against live data
4. Entry rules start enabled; exit rules start disabled until entry fires
5. OCO linking ensures SL and target cancel each other

## When to use
- **Systematic trading**: Deploy a tested strategy without manual rule creation
- **Quick setup**: One command creates 4-6 linked rules
- **For manual spreads**: Use `nf-options spread` instead (Upstox Strategy Builder)
- **For simple SL/target**: Use `nf-gtt` (simpler, server-side)
