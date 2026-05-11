import { useMemo } from 'react';
import { ActivityIcon, ReceiptIcon } from 'lucide-react';
import type { Position, TradesData, LiveTrade } from './mock-data';

const fmtINR = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

interface TradeStatsPanelProps {
  trades: TradesData | null;
  positions: Position[];
}

interface TradeBuckets {
  total: number;
  buyValue: number;
  sellValue: number;
  intradayCount: number;
  deliveryCount: number;
  optionsCount: number;
  futuresCount: number;
  equityCount: number;
}

function bucketTrades(trades: LiveTrade[]): TradeBuckets {
  const out: TradeBuckets = {
    total: trades.length,
    buyValue: 0,
    sellValue: 0,
    intradayCount: 0,
    deliveryCount: 0,
    optionsCount: 0,
    futuresCount: 0,
    equityCount: 0,
  };
  for (const t of trades) {
    const value = t.average_price * t.quantity;
    if (t.transaction_type === 'BUY') out.buyValue += value;
    else out.sellValue += value;

    if (t.product === 'I' || t.product === 'MIS') out.intradayCount += 1;
    else if (t.product === 'D' || t.product === 'CNC') out.deliveryCount += 1;

    const ex = (t.exchange || '').toUpperCase();
    const sym = (t.symbol || '').toUpperCase();
    const isFno = ex === 'NFO' || ex === 'BFO' || ex === 'MCX';
    if (isFno) {
      if (sym.endsWith('CE') || sym.endsWith('PE') || sym.includes(' CE ') || sym.includes(' PE ')) {
        out.optionsCount += 1;
      } else if (sym.includes('FUT')) {
        out.futuresCount += 1;
      } else {
        out.optionsCount += 1; // default F&O bucket → options (most common)
      }
    } else {
      out.equityCount += 1;
    }
  }
  return out;
}

interface RowProps {
  label: string;
  value: string;
  tone?: 'neutral' | 'positive' | 'negative' | 'warn';
}

function StatRow({ label, value, tone = 'neutral' }: RowProps) {
  const color =
    tone === 'positive'
      ? 'text-green-600 dark:text-green-400'
      : tone === 'negative'
        ? 'text-red-600 dark:text-red-400'
        : tone === 'warn'
          ? 'text-amber-600 dark:text-amber-400'
          : 'text-zinc-700 dark:text-zinc-300';
  return (
    <div className="flex items-center justify-between text-[11px] py-0.5">
      <span className="text-zinc-500 dark:text-zinc-400">{label}</span>
      <span className={`font-semibold tabular-nums ${color}`}>{value}</span>
    </div>
  );
}

export default function TradeStatsPanel({ trades, positions }: TradeStatsPanelProps) {
  const buckets = useMemo(
    () => bucketTrades(trades?.trades ?? []),
    [trades],
  );

  // P&L breakdown from open positions
  const pnlBreakdown = useMemo(() => {
    let gross = 0;
    let charges = 0;
    let positionsWithCharges = 0;
    for (const p of positions) {
      gross += p.pnl;
      if (p.charges) {
        charges += p.charges.total;
        positionsWithCharges += 1;
      }
    }
    return {
      gross,
      charges,
      net: gross - charges,
      positionsWithCharges,
    };
  }, [positions]);

  const netFlow = buckets.buyValue - buckets.sellValue;

  return (
    <div className="flex flex-col h-full min-h-0 bg-white/40 dark:bg-zinc-900/40 rounded-lg border border-zinc-200/50 dark:border-zinc-800/50 p-3 gap-3">
      {/* Today's Activity */}
      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <ActivityIcon className="h-3.5 w-3.5 text-zinc-400" />
          <span className="text-xs font-bold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Today's Activity</span>
        </div>
        {buckets.total === 0 ? (
          <div className="text-xs text-zinc-400 py-1">No trades today</div>
        ) : (
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
            <StatRow label="Trades" value={String(buckets.total)} />
            <StatRow label="Net flow" value={fmtINR(netFlow)} tone={netFlow >= 0 ? 'negative' : 'positive'} />
            <StatRow label="Buy value" value={fmtINR(buckets.buyValue)} />
            <StatRow label="Sell value" value={fmtINR(buckets.sellValue)} />
            <StatRow label="Intraday" value={String(buckets.intradayCount)} />
            <StatRow label="Delivery" value={String(buckets.deliveryCount)} />
            <StatRow label="Options" value={String(buckets.optionsCount)} />
            <StatRow label="Futures" value={String(buckets.futuresCount)} />
          </div>
        )}
      </div>

      {/* P&L Breakdown */}
      <div className="border-t border-zinc-200/50 dark:border-zinc-800/50 pt-2">
        <div className="flex items-center gap-1.5 mb-2">
          <ReceiptIcon className="h-3.5 w-3.5 text-zinc-400" />
          <span className="text-xs font-bold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Open P&L (after charges)</span>
        </div>
        {positions.length === 0 ? (
          <div className="text-xs text-zinc-400 py-1">No open positions</div>
        ) : (
          <div className="space-y-0.5">
            <StatRow
              label="Gross P&L"
              value={`${pnlBreakdown.gross >= 0 ? '+' : ''}${fmtINR(pnlBreakdown.gross)}`}
              tone={pnlBreakdown.gross >= 0 ? 'positive' : 'negative'}
            />
            <StatRow
              label={`Est. charges${pnlBreakdown.positionsWithCharges < positions.length ? ` (${pnlBreakdown.positionsWithCharges}/${positions.length})` : ''}`}
              value={`-${fmtINR(pnlBreakdown.charges)}`}
              tone="warn"
            />
            <div className="flex items-center justify-between border-t border-zinc-200/50 dark:border-zinc-800/50 pt-1 mt-1 text-xs">
              <span className="font-semibold text-zinc-600 dark:text-zinc-300">Net P&L</span>
              <span
                className={`font-bold tabular-nums ${
                  pnlBreakdown.net >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                }`}
              >
                {pnlBreakdown.net >= 0 ? '+' : ''}{fmtINR(pnlBreakdown.net)}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
