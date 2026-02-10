import { useCallback, useState, useEffect } from 'react';
import {
  TrendingUpIcon,
  TrendingDownIcon,
  WalletIcon,
  CircleDotIcon,
  RefreshCwIcon,
  AlertTriangleIcon,
} from 'lucide-react';
import { Badge } from '../catalyst/badge';
import type { PortfolioSummary } from './mock-data';

const fmt = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

const pct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;

function timeAgo(date: Date | null): string {
  if (!date) return '';
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ago`;
}

interface TopStripProps {
  portfolio: PortfolioSummary | null;
  marketOpen: boolean;
  onRefresh: () => void;
  autoRefresh?: boolean;
  onToggleAutoRefresh?: () => void;
  lastUpdated?: Date | null;
  isLoading?: boolean;
}

export default function TopStrip({ portfolio, marketOpen, onRefresh, autoRefresh, onToggleAutoRefresh, lastUpdated, isLoading }: TopStripProps) {
  const [refreshing, setRefreshing] = useState(false);
  const [agoText, setAgoText] = useState('');

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    onRefresh();
    setTimeout(() => setRefreshing(false), 1200);
  }, [onRefresh]);

  // Update "time ago" text every 10 seconds
  useEffect(() => {
    setAgoText(timeAgo(lastUpdated ?? null));
    const id = setInterval(() => setAgoText(timeAgo(lastUpdated ?? null)), 10_000);
    return () => clearInterval(id);
  }, [lastUpdated]);

  const spinning = refreshing || isLoading;

  // Loading skeleton when no portfolio data yet
  if (!portfolio) {
    return (
      <div className="flex items-center gap-1 px-3 py-2 border-b border-zinc-200/60 dark:border-zinc-800/60 bg-white/70 dark:bg-zinc-900/70 backdrop-blur-xl">
        <div className="flex-1 min-w-0 flex items-center gap-4">
          <div className="h-4 w-24 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse" />
          <div className="h-4 w-20 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse" />
          <div className="h-4 w-16 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse hidden lg:block" />
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="h-5 w-12 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1 px-3 py-2 border-b border-zinc-200/60 dark:border-zinc-800/60 bg-white/70 dark:bg-zinc-900/70 backdrop-blur-xl">
      {/* Scrollable data items */}
      <div className="flex-1 min-w-0 overflow-x-auto flex items-center gap-1">
        {/* Portfolio Value */}
        <div className="flex items-center gap-2 pr-4 border-r border-zinc-200/50 dark:border-zinc-800/50 flex-shrink-0">
          <WalletIcon className="h-3.5 w-3.5 text-zinc-400" />
          <div className="flex items-baseline gap-1.5">
            <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400 tracking-wide uppercase">Portfolio</span>
            <span className="text-sm font-bold text-zinc-900 dark:text-zinc-100 tabular-nums">{fmt(portfolio.totalValue)}</span>
          </div>
        </div>

        {/* Day P&L */}
        <div className="flex items-center gap-2 px-4 border-r border-zinc-200/50 dark:border-zinc-800/50 flex-shrink-0">
          {portfolio.dayPnl >= 0 ? (
            <TrendingUpIcon className="h-3.5 w-3.5 text-green-500" />
          ) : (
            <TrendingDownIcon className="h-3.5 w-3.5 text-red-500" />
          )}
          <div className="flex items-baseline gap-1.5">
            <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400 tracking-wide uppercase">Day</span>
            <span className={`text-sm font-bold tabular-nums ${portfolio.dayPnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
              {fmt(portfolio.dayPnl)}
            </span>
            <span className={`text-xs tabular-nums ${portfolio.dayPnl >= 0 ? 'text-green-500/80' : 'text-red-500/80'}`}>
              {pct(portfolio.dayPnlPct)}
            </span>
          </div>
        </div>

        {/* Total P&L - hidden below xl */}
        <div className="hidden xl:flex items-center gap-2 px-4 border-r border-zinc-200/50 dark:border-zinc-800/50 flex-shrink-0">
          <div className="flex items-baseline gap-1.5">
            <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400 tracking-wide uppercase">Overall</span>
            <span className={`text-sm font-bold tabular-nums ${portfolio.totalPnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
              {fmt(portfolio.totalPnl)}
            </span>
            <span className={`text-xs tabular-nums ${portfolio.totalPnl >= 0 ? 'text-green-500/80' : 'text-red-500/80'}`}>
              {pct(portfolio.totalPnlPct)}
            </span>
          </div>
        </div>

        {/* Cash - hidden below lg */}
        <div className="hidden lg:flex items-center gap-2 px-4 border-r border-zinc-200/50 dark:border-zinc-800/50 flex-shrink-0">
          <div className="flex items-baseline gap-1.5">
            <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400 tracking-wide uppercase">Cash</span>
            <span className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 tabular-nums">{fmt(portfolio.availableCash)}</span>
          </div>
        </div>
      </div>

      {/* Right side - pinned */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {/* Paper Trading Badge */}
        {portfolio.paperTrading && (
          <Badge color="amber" className="mr-2">
            <AlertTriangleIcon className="h-3 w-3" />
            Paper
          </Badge>
        )}

        {/* Market Status */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-100/80 dark:bg-zinc-800/80">
          <CircleDotIcon className={`h-3 w-3 ${marketOpen ? 'text-green-500 animate-pulse' : 'text-red-400'}`} />
          <span className={`text-xs font-semibold tracking-wide ${marketOpen ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
            {marketOpen ? 'LIVE' : 'CLOSED'}
          </span>
        </div>

        {/* Auto-refresh toggle */}
        {onToggleAutoRefresh && (
          <button
            onClick={onToggleAutoRefresh}
            className={`px-2 py-1 rounded-md text-[10px] font-semibold transition-colors ${
              autoRefresh
                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-400'
            }`}
            title={autoRefresh ? 'Auto-refresh ON (30s)' : 'Auto-refresh OFF'}
          >
            AUTO
          </button>
        )}

        {/* Last updated */}
        {agoText && (
          <span className="text-[10px] text-zinc-400 hidden sm:inline tabular-nums whitespace-nowrap">
            {agoText}
          </span>
        )}

        {/* Refresh */}
        <button
          onClick={handleRefresh}
          className="ml-1 p-1.5 rounded-md text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          title="Refresh data"
        >
          <RefreshCwIcon className={`h-3.5 w-3.5 ${spinning ? 'animate-spin' : ''}`} />
        </button>
      </div>
    </div>
  );
}
