import React, { useState } from 'react';
import {
  ChevronDownIcon,
  ChevronUpIcon,
  SparklesIcon,
  LogOutIcon,
  ChevronRightIcon,
} from 'lucide-react';
import { Badge } from '../catalyst/badge';
import type { Position } from './mock-data';

const fmt = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

const fmtDecimal = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(n);

interface PositionsTableProps {
  positions: Position[];
  holdings: Position[];
  onSymbolSelect: (symbol: string) => void;
  onAskAI: (symbol: string, context: object) => void;
}

type Tab = 'positions' | 'holdings';
type SortKey = 'symbol' | 'pnl' | 'pnlPct' | 'dayChangePct' | 'holdDays';
type SortDir = 'asc' | 'desc';

export default function PositionsTable({ positions, holdings, onSymbolSelect, onAskAI }: PositionsTableProps) {
  const [activeTab, setActiveTab] = useState<Tab>('positions');
  const [sortKey, setSortKey] = useState<SortKey>('pnlPct');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const data = activeTab === 'positions' ? positions : holdings;

  const sorted = [...data].sort((a, b) => {
    const aVal = a[sortKey] ?? 0;
    const bVal = b[sortKey] ?? 0;
    if (typeof aVal === 'string') return sortDir === 'asc' ? aVal.localeCompare(bVal as string) : (bVal as string).localeCompare(aVal);
    return sortDir === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
  });

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('desc'); }
  };

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return <ChevronDownIcon className="h-3 w-3 text-zinc-300 dark:text-zinc-600 opacity-0 group-hover:opacity-100 transition-opacity" />;
    return sortDir === 'desc'
      ? <ChevronDownIcon className="h-3 w-3 text-amber-500" />
      : <ChevronUpIcon className="h-3 w-3 text-amber-500" />;
  };

  // Summary
  const totalInvested = data.reduce((s, p) => s + p.avgPrice * p.qty, 0);
  const totalCurrent = data.reduce((s, p) => s + p.ltp * p.qty, 0);
  const totalPnl = data.reduce((s, p) => s + p.pnl, 0);
  const totalPnlPct = totalInvested > 0 ? (totalPnl / totalInvested) * 100 : 0;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Tabs + Summary */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-200/50 dark:border-zinc-800/50 flex-shrink-0">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveTab('positions')}
            className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
              activeTab === 'positions'
                ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
                : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
            }`}
          >
            Open ({positions.length})
          </button>
          <button
            onClick={() => setActiveTab('holdings')}
            className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
              activeTab === 'holdings'
                ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
                : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
            }`}
          >
            Holdings ({holdings.length})
          </button>
        </div>

        {/* Summary */}
        <div className="flex items-center gap-4 text-xs">
          <span className="hidden lg:inline text-zinc-500">Invested: <span className="font-semibold text-zinc-700 dark:text-zinc-300 tabular-nums">{fmt(totalInvested)}</span></span>
          <span className="hidden lg:inline text-zinc-500">Current: <span className="font-semibold text-zinc-700 dark:text-zinc-300 tabular-nums">{fmt(totalCurrent)}</span></span>
          <span className={`font-bold tabular-nums ${totalPnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
            {totalPnl >= 0 ? '+' : ''}{fmt(totalPnl)} ({totalPnl >= 0 ? '+' : ''}{totalPnlPct.toFixed(2)}%)
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-y-auto custom-scrollbar min-h-0">
        {sorted.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-zinc-400">
            <p className="text-sm">No {activeTab === 'positions' ? 'open positions' : 'holdings'}</p>
            <p className="text-xs mt-1">Start trading to see your {activeTab} here</p>
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-zinc-50/95 dark:bg-zinc-900/95 backdrop-blur-sm z-10">
              <tr className="border-b border-zinc-200/50 dark:border-zinc-800/50">
                <th className="text-left py-2 px-3 font-semibold text-zinc-500 dark:text-zinc-400 w-8"></th>
                <th className="group text-left py-2 px-2 font-semibold text-zinc-500 dark:text-zinc-400 cursor-pointer select-none" onClick={() => toggleSort('symbol')}>
                  <div className="flex items-center gap-1">Symbol <SortIcon col="symbol" /></div>
                </th>
                <th className="hidden lg:table-cell text-right py-2 px-2 font-semibold text-zinc-500 dark:text-zinc-400">Qty</th>
                <th className="hidden xl:table-cell text-right py-2 px-2 font-semibold text-zinc-500 dark:text-zinc-400">Avg Price</th>
                <th className="text-right py-2 px-2 font-semibold text-zinc-500 dark:text-zinc-400">LTP</th>
                <th className="group text-right py-2 px-2 font-semibold text-zinc-500 dark:text-zinc-400 cursor-pointer select-none" onClick={() => toggleSort('pnl')}>
                  <div className="flex items-center justify-end gap-1">P&L <SortIcon col="pnl" /></div>
                </th>
                <th className="group text-right py-2 px-2 font-semibold text-zinc-500 dark:text-zinc-400 cursor-pointer select-none" onClick={() => toggleSort('pnlPct')}>
                  <div className="flex items-center justify-end gap-1">P&L % <SortIcon col="pnlPct" /></div>
                </th>
                <th className="hidden xl:table-cell group text-right py-2 px-2 font-semibold text-zinc-500 dark:text-zinc-400 cursor-pointer select-none" onClick={() => toggleSort('dayChangePct')}>
                  <div className="flex items-center justify-end gap-1">Day <SortIcon col="dayChangePct" /></div>
                </th>
                <th className="hidden xl:table-cell group text-right py-2 px-2 font-semibold text-zinc-500 dark:text-zinc-400 cursor-pointer select-none" onClick={() => toggleSort('holdDays')}>
                  <div className="flex items-center justify-end gap-1">Days <SortIcon col="holdDays" /></div>
                </th>
                <th className="text-right py-2 px-3 font-semibold text-zinc-500 dark:text-zinc-400">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((pos) => {
                const isExpanded = expandedRow === pos.symbol;
                const rowBg = pos.pnl >= 0
                  ? 'hover:bg-green-50/30 dark:hover:bg-green-950/10'
                  : 'hover:bg-red-50/30 dark:hover:bg-red-950/10';

                return (
                  <React.Fragment key={pos.symbol}>
                    {/* Main Row */}
                    <tr className={`group border-b border-zinc-100 dark:border-zinc-800/50 transition-colors ${rowBg}`}>
                      <td className="py-2.5 px-3 w-8">
                        <button
                          onClick={() => setExpandedRow(isExpanded ? null : pos.symbol)}
                          className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
                        >
                          <ChevronRightIcon className={`h-3 w-3 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                        </button>
                      </td>
                      <td
                        className="py-2.5 px-2 cursor-pointer"
                        onClick={() => onSymbolSelect(pos.symbol)}
                      >
                        <span className="font-bold text-zinc-800 dark:text-zinc-200 hover:text-amber-600 dark:hover:text-amber-400 transition-colors">
                          {pos.symbol}
                        </span>
                      </td>
                      <td className="hidden lg:table-cell py-2.5 px-2 text-right text-zinc-600 dark:text-zinc-400 tabular-nums">
                        {pos.qty}
                      </td>
                      <td className="hidden xl:table-cell py-2.5 px-2 text-right text-zinc-600 dark:text-zinc-400 tabular-nums">
                        {fmtDecimal(pos.avgPrice)}
                      </td>
                      <td className="py-2.5 px-2 text-right font-semibold text-zinc-800 dark:text-zinc-200 tabular-nums">
                        {fmtDecimal(pos.ltp)}
                      </td>
                      <td className={`py-2.5 px-2 text-right font-bold tabular-nums ${pos.pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                        {pos.pnl >= 0 ? '+' : ''}{fmt(pos.pnl)}
                      </td>
                      <td className={`py-2.5 px-2 text-right font-semibold tabular-nums ${pos.pnlPct >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                        {pos.pnlPct >= 0 ? '+' : ''}{pos.pnlPct.toFixed(2)}%
                      </td>
                      <td className={`hidden xl:table-cell py-2.5 px-2 text-right tabular-nums ${pos.dayChangePct >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                        {pos.dayChangePct >= 0 ? '+' : ''}{pos.dayChangePct.toFixed(2)}%
                      </td>
                      <td className="hidden xl:table-cell py-2.5 px-2 text-right text-zinc-500 tabular-nums">
                        {pos.holdDays != null ? `${pos.holdDays}d` : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => onAskAI(pos.symbol, { type: 'position', data: pos })}
                            className="p-1 rounded hover:bg-amber-50 dark:hover:bg-amber-900/30 transition-colors"
                            title="Ask AI"
                          >
                            <SparklesIcon className="h-3.5 w-3.5 text-amber-600" />
                          </button>
                          {activeTab === 'positions' && (
                            <button
                              className="p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors"
                              title="Exit Position"
                            >
                              <LogOutIcon className="h-3.5 w-3.5 text-red-500" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>

                    {/* Expanded Detail */}
                    {isExpanded && (
                      <tr>
                        <td colSpan={10} className="px-8 py-2.5 bg-zinc-50/50 dark:bg-zinc-800/20 border-b border-zinc-200/50 dark:border-zinc-800/50 animate-slide-in-bottom">
                          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-[11px]">
                            <span className="text-zinc-500">Company: <span className="text-zinc-700 dark:text-zinc-300 font-medium">{pos.company}</span></span>
                            {pos.stopLoss && (
                              <span className="text-zinc-500">SL: <span className="text-red-500 font-semibold tabular-nums">{fmtDecimal(pos.stopLoss)}</span></span>
                            )}
                            {pos.target && (
                              <span className="text-zinc-500">Target: <span className="text-green-500 font-semibold tabular-nums">{fmtDecimal(pos.target)}</span></span>
                            )}
                            <span className="text-zinc-500">Value: <span className="text-zinc-700 dark:text-zinc-300 font-semibold tabular-nums">{fmt(pos.ltp * pos.qty)}</span></span>
                            {pos.stopLoss && (
                              <span className="text-zinc-500">
                                Risk: <Badge color={Math.abs((pos.ltp - pos.stopLoss) / pos.ltp * 100) < 2 ? 'red' : 'amber'}>
                                  {((pos.ltp - pos.stopLoss) / pos.ltp * 100).toFixed(1)}% to SL
                                </Badge>
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
