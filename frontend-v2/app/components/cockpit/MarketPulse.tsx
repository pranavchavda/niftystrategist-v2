import { TrendingUpIcon, TrendingDownIcon } from 'lucide-react';
import type { MarketIndex } from './mock-data';

interface MarketPulseProps {
  indices: MarketIndex[];
}

export default function MarketPulse({ indices }: MarketPulseProps) {
  return (
    <div className="space-y-1.5">
      <h3 className="text-[10px] font-bold text-zinc-400 dark:text-zinc-500 tracking-[0.15em] uppercase px-1">
        Market Pulse
      </h3>
      <div className="space-y-1">
        {indices.map((idx) => {
          const isUp = idx.change >= 0;
          return (
            <div
              key={idx.name}
              className={`flex items-center justify-between px-2.5 py-2 rounded-lg border transition-colors ${
                isUp
                  ? 'bg-green-50/50 border-green-200/30 dark:bg-green-950/20 dark:border-green-800/20'
                  : 'bg-red-50/50 border-red-200/30 dark:bg-red-950/20 dark:border-red-800/20'
              }`}
            >
              <div className="flex items-center gap-1.5">
                {isUp ? (
                  <TrendingUpIcon className="h-3 w-3 text-green-500" />
                ) : (
                  <TrendingDownIcon className="h-3 w-3 text-red-500" />
                )}
                <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                  {idx.name}
                </span>
              </div>
              <div className="text-right">
                <div className="text-xs font-bold text-zinc-800 dark:text-zinc-200 tabular-nums">
                  {idx.value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </div>
                <div className={`text-[10px] font-semibold tabular-nums ${isUp ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {isUp ? '+' : ''}{idx.change.toFixed(2)} ({isUp ? '+' : ''}{idx.changePct.toFixed(2)}%)
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
