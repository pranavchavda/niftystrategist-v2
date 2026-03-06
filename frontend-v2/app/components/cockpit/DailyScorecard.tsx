import {
  TrophyIcon,
  TargetIcon,
} from 'lucide-react';
import type { DailyScorecard as ScorecardType } from './mock-data';

const fmt = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

interface DailyScorecardProps {
  scorecard: ScorecardType;
}

export default function DailyScorecard({ scorecard }: DailyScorecardProps) {
  return (
    <div className="border-t border-zinc-200/50 dark:border-zinc-800/50">
      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <TargetIcon className="h-3.5 w-3.5 text-amber-500" />
            <span className="font-semibold text-zinc-700 dark:text-zinc-300">Daily Scorecard</span>
          </div>

          <div className="flex items-center gap-3 text-zinc-500">
            <span>
              <span className="font-bold text-zinc-700 dark:text-zinc-300 tabular-nums">{scorecard.trades}</span> trades
              {scorecard.roundTrips != null && scorecard.roundTrips > 0 && (
                <span className="text-zinc-400"> ({scorecard.roundTrips} round trips)</span>
              )}
            </span>
            {scorecard.roundTrips != null && scorecard.roundTrips > 0 && (
              <>
                <span className="text-zinc-300 dark:text-zinc-700">|</span>
                <span>
                  Win Rate: <span className={`font-bold tabular-nums ${scorecard.winRate >= 50 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{scorecard.winRate}%</span>
                </span>
                <span className="hidden lg:inline text-zinc-300 dark:text-zinc-700">|</span>
                <span className="hidden lg:inline">
                  PF: <span className={`font-bold tabular-nums ${scorecard.profitFactor >= 1.5 ? 'text-green-600 dark:text-green-400' : scorecard.profitFactor >= 1 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'}`}>
                    {scorecard.profitFactor.toFixed(2)}
                  </span>
                </span>
                {scorecard.biggestWin > 0 && (
                  <>
                    <span className="hidden xl:inline text-zinc-300 dark:text-zinc-700">|</span>
                    <span className="hidden xl:inline">
                      <TrophyIcon className="h-3 w-3 inline mr-0.5 text-amber-500" />
                      <span className="font-bold text-green-600 dark:text-green-400 tabular-nums">{fmt(scorecard.biggestWin)}</span>
                    </span>
                  </>
                )}
              </>
            )}
            {scorecard.netPnl != null && scorecard.netPnl !== 0 && (
              <>
                <span className="hidden lg:inline text-zinc-300 dark:text-zinc-700">|</span>
                <span className="hidden lg:inline">
                  Net: <span className={`font-bold tabular-nums ${scorecard.netPnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                    {fmt(scorecard.netPnl)}
                  </span>
                </span>
              </>
            )}
            {scorecard.totalBuyValue != null && scorecard.totalBuyValue > 0 && (
              <>
                <span className="hidden xl:inline text-zinc-300 dark:text-zinc-700">|</span>
                <span className="hidden xl:inline text-zinc-400">
                  Buy {fmt(scorecard.totalBuyValue)} / Sell {fmt(scorecard.totalSellValue ?? 0)}
                </span>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
