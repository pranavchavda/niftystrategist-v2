import { useState } from 'react';
import {
  SearchIcon,
  SparklesIcon,
  BellIcon,
  ShoppingCartIcon,
  BarChart3Icon,
} from 'lucide-react';
import { Area, AreaChart, ResponsiveContainer } from 'recharts';
import type { WatchlistItem } from './mock-data';

interface WatchlistPanelProps {
  watchlists: Record<string, WatchlistItem[]>;
  onSymbolSelect: (symbol: string) => void;
  onAskAI: (symbol: string, context: object) => void;
}

function MiniSparkline({ data, isPositive }: { data: number[]; isPositive: boolean }) {
  const chartData = data.map((v, i) => ({ i, v }));
  const color = isPositive ? '#16a34a' : '#dc2626';

  return (
    <div className="w-12 h-5">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`spark-${isPositive ? 'up' : 'down'}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#spark-${isPositive ? 'up' : 'down'})`}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function WatchlistPanel({ watchlists, onSymbolSelect, onAskAI }: WatchlistPanelProps) {
  const listNames = Object.keys(watchlists);
  const [activeList, setActiveList] = useState(listNames[0] || '');
  const [search, setSearch] = useState('');
  const [hoveredSymbol, setHoveredSymbol] = useState<string | null>(null);

  const items = (watchlists[activeList] || []).filter(
    (item) =>
      item.symbol.toLowerCase().includes(search.toLowerCase()) ||
      item.company.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex flex-col h-full min-h-0">
      <h3 className="text-[10px] font-bold text-zinc-400 dark:text-zinc-500 tracking-[0.15em] uppercase px-1 mb-2 flex-shrink-0">
        Watchlist
      </h3>

      {/* List Tabs */}
      <div className="flex gap-1 mb-2 flex-shrink-0">
        {listNames.map((name) => (
          <button
            key={name}
            onClick={() => setActiveList(name)}
            className={`px-2 py-1 text-[10px] font-semibold rounded-md transition-colors ${
              activeList === name
                ? 'bg-amber-500/15 text-amber-700 dark:text-amber-400'
                : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
            }`}
          >
            {name}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative mb-2 flex-shrink-0">
        <SearchIcon className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-zinc-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter..."
          className="w-full pl-7 pr-2 py-1.5 text-xs bg-zinc-100/80 dark:bg-zinc-800/80 border border-zinc-200/50 dark:border-zinc-700/50 rounded-md text-zinc-700 dark:text-zinc-300 placeholder:text-zinc-400 focus:outline-none focus:ring-1 focus:ring-amber-500/50"
        />
      </div>

      {/* Items */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-0.5 min-h-0">
        {items.map((item) => {
          const isUp = item.changePct >= 0;
          const isHovered = hoveredSymbol === item.symbol;

          return (
            <div
              key={item.symbol}
              className="group relative px-2 py-1.5 rounded-md hover:bg-zinc-100/80 dark:hover:bg-zinc-800/60 cursor-pointer transition-colors"
              onMouseEnter={() => setHoveredSymbol(item.symbol)}
              onMouseLeave={() => setHoveredSymbol(null)}
              onClick={() => onSymbolSelect(item.symbol)}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold text-zinc-800 dark:text-zinc-200">
                      {item.symbol}
                    </span>
                    {(item.alertAbove || item.alertBelow) && (
                      <BellIcon className="h-2.5 w-2.5 text-amber-500" />
                    )}
                  </div>
                  <span className="text-[10px] text-zinc-400 dark:text-zinc-500 truncate block">
                    {item.company}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <MiniSparkline data={item.sparkline} isPositive={isUp} />
                  <div className="text-right min-w-[60px]">
                    <div className="text-xs font-bold text-zinc-800 dark:text-zinc-200 tabular-nums">
                      {item.ltp.toLocaleString('en-IN')}
                    </div>
                    <div className={`text-[10px] font-semibold tabular-nums ${isUp ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                      {isUp ? '+' : ''}{item.changePct.toFixed(2)}%
                    </div>
                  </div>
                </div>
              </div>

              {/* Hover Actions */}
              {isHovered && (
                <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-0.5 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-md shadow-lg p-0.5 z-10 animate-scale-in">
                  <button
                    onClick={(e) => { e.stopPropagation(); onSymbolSelect(item.symbol); }}
                    className="p-1 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                    title="View Chart"
                  >
                    <BarChart3Icon className="h-3 w-3 text-zinc-500" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); }}
                    className="p-1 rounded hover:bg-green-50 dark:hover:bg-green-900/30 transition-colors"
                    title="Buy"
                  >
                    <ShoppingCartIcon className="h-3 w-3 text-green-600" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onAskAI(item.symbol, { type: 'watchlist', data: item });
                    }}
                    className="p-1 rounded hover:bg-amber-50 dark:hover:bg-amber-900/30 transition-colors"
                    title="Ask AI"
                  >
                    <SparklesIcon className="h-3 w-3 text-amber-600" />
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
