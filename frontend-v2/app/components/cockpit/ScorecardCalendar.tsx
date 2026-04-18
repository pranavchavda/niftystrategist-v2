import { useMemo, useState } from 'react';
import { CalendarDaysIcon } from 'lucide-react';
import type { DailyScorecardRow } from '../../hooks/useScorecards';

const fmt = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

const shortDate = (iso: string) => {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
};

const weekday = (iso: string) => new Date(iso + 'T00:00:00').getDay();

function pnlColor(pnl: number, trades: number, maxAbs: number): string {
  if (!trades) return 'bg-zinc-100 dark:bg-zinc-800/40';
  if (pnl === 0) return 'bg-zinc-200 dark:bg-zinc-700';
  const intensity = Math.min(1, Math.abs(pnl) / Math.max(1, maxAbs));
  const step = intensity > 0.75 ? 4 : intensity > 0.5 ? 3 : intensity > 0.25 ? 2 : 1;
  if (pnl > 0) {
    return {
      1: 'bg-green-200 dark:bg-green-900/40',
      2: 'bg-green-300 dark:bg-green-800/60',
      3: 'bg-green-500 dark:bg-green-700',
      4: 'bg-green-600 dark:bg-green-600',
    }[step]!;
  }
  return {
    1: 'bg-red-200 dark:bg-red-900/40',
    2: 'bg-red-300 dark:bg-red-800/60',
    3: 'bg-red-500 dark:bg-red-700',
    4: 'bg-red-600 dark:bg-red-600',
  }[step]!;
}

interface Props {
  scorecards: DailyScorecardRow[];
  isLoading?: boolean;
}

export default function ScorecardCalendar({ scorecards, isLoading }: Props) {
  const [hovered, setHovered] = useState<DailyScorecardRow | null>(null);

  const { weeks, totals, maxAbs } = useMemo(() => {
    if (!scorecards.length) return { weeks: [] as (DailyScorecardRow | null)[][], totals: null, maxAbs: 0 };

    const filtered = scorecards.filter((r) => {
      const dow = weekday(r.date);
      return dow >= 1 && dow <= 5;
    });
    const asc = [...filtered].sort((a, b) => a.date.localeCompare(b.date));

    const cols: (DailyScorecardRow | null)[][] = [];
    let cur: (DailyScorecardRow | null)[] = [];
    for (const row of asc) {
      const dow = weekday(row.date);
      if (dow === 1 && cur.length) {
        while (cur.length < 5) cur.push(null);
        cols.push(cur);
        cur = [];
      }
      const targetIdx = dow - 1;
      while (cur.length < targetIdx) cur.push(null);
      cur.push(row);
    }
    if (cur.length) {
      while (cur.length < 5) cur.push(null);
      cols.push(cur);
    }

    const netTotal = asc.reduce((a, x) => a + x.netPnl, 0);
    const tradesTotal = asc.reduce((a, x) => a + x.trades, 0);
    const winsTotal = asc.reduce((a, x) => a + x.wins, 0);
    const lossesTotal = asc.reduce((a, x) => a + x.losses, 0);
    const decidedTotal = winsTotal + lossesTotal;
    const positiveDays = asc.filter((x) => x.netPnl > 0).length;
    const negativeDays = asc.filter((x) => x.netPnl < 0).length;
    const activeDays = asc.filter((x) => x.trades > 0).length;
    const maxAbs = Math.max(1, ...asc.map((r) => Math.abs(r.netPnl)));

    return {
      weeks: cols,
      totals: { netTotal, tradesTotal, winsTotal, lossesTotal, decidedTotal, positiveDays, negativeDays, activeDays },
      maxAbs,
    };
  }, [scorecards]);

  if (isLoading && !scorecards.length) {
    return (
      <div className="border-t border-zinc-200/50 dark:border-zinc-800/50 px-3 py-2 text-xs text-zinc-500">
        Loading calendar…
      </div>
    );
  }
  if (!scorecards.length) return null;

  return (
    <div className="border-t border-zinc-200/50 dark:border-zinc-800/50 px-3 py-2">
      <div className="flex items-start gap-4">
        {/* Header + totals */}
        <div className="flex flex-col gap-1 min-w-[160px]">
          <div className="flex items-center gap-1.5 text-xs">
            <CalendarDaysIcon className="h-3.5 w-3.5 text-amber-500" />
            <span className="font-semibold text-zinc-700 dark:text-zinc-300">
              Intraday · Last {scorecards.length}d
            </span>
          </div>
          {totals && (
            <div className="text-[10px] text-zinc-500 space-y-0.5 tabular-nums">
              <div>
                Net:{' '}
                <span
                  className={`font-bold ${
                    totals.netTotal >= 0
                      ? 'text-green-600 dark:text-green-400'
                      : 'text-red-600 dark:text-red-400'
                  }`}
                >
                  {fmt(totals.netTotal)}
                </span>
              </div>
              <div>
                {totals.activeDays} active ·{' '}
                <span className="text-green-600 dark:text-green-400">{totals.positiveDays}↑</span>{' '}
                <span className="text-red-600 dark:text-red-400">{totals.negativeDays}↓</span>
              </div>
              <div>
                {totals.tradesTotal} round-trips
                {totals.decidedTotal > 0 && (
                  <>
                    {' · '}
                    {Math.round((totals.winsTotal / totals.decidedTotal) * 100)}% WR
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Heatmap: rows = Mon-Fri, columns = weeks */}
        <div className="flex gap-[3px]">
          {weeks.map((col, ci) => (
            <div key={ci} className="flex flex-col gap-[3px]">
              {col.map((row, ri) => {
                if (!row) {
                  return <div key={ri} className="w-3.5 h-3.5 rounded-sm bg-transparent" aria-hidden />;
                }
                return (
                  <div
                    key={ri}
                    className={`w-3.5 h-3.5 rounded-sm cursor-pointer transition-all hover:ring-2 hover:ring-amber-400 ${pnlColor(row.netPnl, row.trades, maxAbs)}`}
                    onMouseEnter={() => setHovered(row)}
                    onMouseLeave={() => setHovered(null)}
                    title={`${shortDate(row.date)} · ${row.trades ? fmt(row.netPnl) : 'no trades'}`}
                  />
                );
              })}
            </div>
          ))}
        </div>

        {/* Hover detail */}
        <div className="flex-1 min-w-0 text-[11px] text-zinc-600 dark:text-zinc-400 tabular-nums">
          {hovered ? (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
              <span className="font-semibold text-zinc-700 dark:text-zinc-300">
                {shortDate(hovered.date)}
              </span>
              {hovered.trades ? (
                <>
                  <span>
                    Net{' '}
                    <span
                      className={`font-bold ${
                        hovered.netPnl >= 0
                          ? 'text-green-600 dark:text-green-400'
                          : 'text-red-600 dark:text-red-400'
                      }`}
                    >
                      {fmt(hovered.netPnl)}
                    </span>
                  </span>
                  <span>
                    {hovered.trades} RT · {hovered.wins}W/{hovered.losses}L · {hovered.winRate}% WR
                  </span>
                  {hovered.profitFactor > 0 && <span>PF {hovered.profitFactor.toFixed(2)}</span>}
                  {hovered.biggestWin > 0 && (
                    <span className="hidden md:inline">
                      Best{' '}
                      <span className="text-green-600 dark:text-green-400">{fmt(hovered.biggestWin)}</span>
                    </span>
                  )}
                  {hovered.biggestLoss > 0 && (
                    <span className="hidden md:inline">
                      Worst{' '}
                      <span className="text-red-600 dark:text-red-400">{fmt(-hovered.biggestLoss)}</span>
                    </span>
                  )}
                </>
              ) : (
                <span className="text-zinc-400">No closed trades</span>
              )}
            </div>
          ) : (
            <span className="text-zinc-400">Hover a day · realized intraday P&amp;L (T+1)</span>
          )}
        </div>
      </div>
    </div>
  );
}
