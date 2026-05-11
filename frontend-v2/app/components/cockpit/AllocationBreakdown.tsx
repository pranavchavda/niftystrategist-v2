import { useMemo } from 'react';
import { PieChartIcon } from 'lucide-react';
import type { Position } from './mock-data';

const fmtINR = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

interface AllocationBreakdownProps {
  holdings: Position[];
  positions: Position[];
  onSymbolSelect?: (symbol: string) => void;
}

const PALETTE = [
  'bg-amber-500',
  'bg-sky-500',
  'bg-emerald-500',
  'bg-violet-500',
  'bg-rose-500',
  'bg-zinc-400',
];

export default function AllocationBreakdown({ holdings, positions, onSymbolSelect }: AllocationBreakdownProps) {
  const slices = useMemo(() => {
    // Combine holdings + open positions (delivery + intraday) — excludes MFs
    const all = [...holdings, ...positions];
    const totalValue = all.reduce((s, p) => s + p.ltp * p.qty, 0);
    if (totalValue <= 0) return { items: [], total: 0 };

    // Aggregate by symbol (in case the same name appears in both)
    const bySymbol = new Map<string, { symbol: string; value: number }>();
    for (const p of all) {
      const value = p.ltp * p.qty;
      const existing = bySymbol.get(p.symbol);
      if (existing) existing.value += value;
      else bySymbol.set(p.symbol, { symbol: p.symbol, value });
    }

    const sorted = [...bySymbol.values()].sort((a, b) => b.value - a.value);
    const top = sorted.slice(0, 5);
    const rest = sorted.slice(5);
    const others = rest.reduce((s, x) => s + x.value, 0);

    const items = top.map((t, i) => ({
      symbol: t.symbol,
      value: t.value,
      pct: (t.value / totalValue) * 100,
      color: PALETTE[i],
    }));
    if (others > 0) {
      items.push({
        symbol: `Others (${rest.length})`,
        value: others,
        pct: (others / totalValue) * 100,
        color: PALETTE[5],
      });
    }
    return { items, total: totalValue };
  }, [holdings, positions]);

  return (
    <div className="flex flex-col h-full min-h-0 bg-white/40 dark:bg-zinc-900/40 rounded-lg border border-zinc-200/50 dark:border-zinc-800/50 p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <PieChartIcon className="h-3.5 w-3.5 text-zinc-400" />
          <span className="text-xs font-bold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Allocation</span>
        </div>
        <span className="text-[10px] text-zinc-400 tabular-nums">{fmtINR(slices.total)}</span>
      </div>

      {slices.items.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-xs text-zinc-400 py-4">
          No holdings to allocate
        </div>
      ) : (
        <>
          {/* Stacked bar */}
          <div className="flex h-2 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800 mb-3">
            {slices.items.map((s) => (
              <div
                key={s.symbol}
                className={`${s.color} transition-all`}
                style={{ width: `${s.pct}%` }}
                title={`${s.symbol}: ${s.pct.toFixed(1)}%`}
              />
            ))}
          </div>

          {/* Legend */}
          <div className="flex flex-col gap-1 overflow-y-auto custom-scrollbar min-h-0">
            {slices.items.map((s) => {
              const clickable = onSymbolSelect && !s.symbol.startsWith('Others');
              return (
                <button
                  key={s.symbol}
                  onClick={clickable ? () => onSymbolSelect(s.symbol) : undefined}
                  disabled={!clickable}
                  className={`flex items-center justify-between gap-2 text-[11px] py-0.5 px-1 rounded ${
                    clickable
                      ? 'hover:bg-zinc-100 dark:hover:bg-zinc-800/60 cursor-pointer'
                      : 'cursor-default'
                  }`}
                >
                  <span className="flex items-center gap-1.5 min-w-0">
                    <span className={`h-2 w-2 rounded-sm flex-shrink-0 ${s.color}`} />
                    <span className="font-medium text-zinc-700 dark:text-zinc-300 truncate">{s.symbol}</span>
                  </span>
                  <span className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-zinc-500 tabular-nums">{fmtINR(s.value)}</span>
                    <span className="font-semibold text-zinc-700 dark:text-zinc-300 tabular-nums w-10 text-right">
                      {s.pct.toFixed(1)}%
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
