import React, { useState, useEffect, useCallback } from 'react';
import * as Headless from '@headlessui/react';
import {
  PanelLeftCloseIcon,
  PanelLeftOpenIcon,
  ListIcon,
  MessageSquareIcon,
  XIcon,
} from 'lucide-react';
import TopStrip from './cockpit/TopStrip';
import MarketPulse from './cockpit/MarketPulse';
import WatchlistPanel from './cockpit/WatchlistPanel';
import PriceChart from './cockpit/PriceChart';
import PositionsTable from './cockpit/PositionsTable';
import DailyScorecard from './cockpit/DailyScorecard';
import CockpitChat from './cockpit/CockpitChat';
import TradingModeToggle from './TradingModeToggle';
import { useCockpitData } from '../hooks/useCockpitData';
import { useChartData } from '../hooks/useChartData';

const Dashboard = ({ authToken }) => {
  // Left panel collapse state
  const [leftCollapsed, setLeftCollapsed] = useState(() => {
    const saved = localStorage.getItem('cockpit-left-collapsed');
    return saved === 'true';
  });
  // Drawer states
  const [showWatchlistDrawer, setShowWatchlistDrawer] = useState(false);
  const [showChatDrawer, setShowChatDrawer] = useState(false);

  // Active symbol + timeframe for chart
  const [activeSymbol, setActiveSymbol] = useState('NIFTY 50');
  const [activeTimeframe, setActiveTimeframe] = useState('3M');

  // Chat context
  const [chatContext, setChatContext] = useState(null);

  // Auto-refresh toggle (persisted to localStorage)
  const [autoRefresh, setAutoRefresh] = useState(() => {
    const saved = localStorage.getItem('cockpit-auto-refresh');
    return saved !== 'false'; // default true
  });

  // Live data hooks
  const cockpitData = useCockpitData(authToken, autoRefresh);
  // Map timeframe labels to days + interval for the chart hook
  const TIMEFRAME_CONFIG = {
    '1D': { days: 1, interval: '1minute' },
    '5D': { days: 5, interval: '5minute' },
    '1W': { days: 7, interval: 'day' },
    '1M': { days: 30, interval: 'day' },
    '3M': { days: 90, interval: 'day' },
    '6M': { days: 180, interval: 'day' },
    '1Y': { days: 365, interval: 'day' },
  };
  const chartConfig = TIMEFRAME_CONFIG[activeTimeframe] || { days: 90, interval: 'day' };
  const chartResult = useChartData(authToken, activeSymbol, chartConfig.days, chartConfig.interval);

  // Derive market open status from live data
  const marketOpen = cockpitData.marketStatus?.status === 'open' || cockpitData.marketStatus?.status === 'pre_open';

  // Persist collapse states
  useEffect(() => {
    localStorage.setItem('cockpit-left-collapsed', String(leftCollapsed));
  }, [leftCollapsed]);

  // Persist auto-refresh
  useEffect(() => {
    localStorage.setItem('cockpit-auto-refresh', String(autoRefresh));
  }, [autoRefresh]);

  const handleSymbolSelect = useCallback((symbol) => {
    setActiveSymbol(symbol);
  }, []);

  const handleAskAI = useCallback((symbol, context) => {
    setChatContext(`[CONTEXT: ${context.type}] About ${symbol}: ${JSON.stringify(context.data)}\n\n`);
    setShowChatDrawer(true);
  }, []);

  const handleTradingModeChange = useCallback(async () => {
    // Invalidate cached Upstox client so cockpit picks up the new mode
    try {
      await fetch('/api/cockpit/invalidate-client', {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}` },
      });
    } catch (e) {
      console.warn('Failed to invalidate client cache:', e);
    }
    cockpitData.refresh();
  }, [authToken, cockpitData]);

  // Shared watchlist content for both inline panel and drawer
  const watchlistContent = (
    <>
      {/* Market Pulse */}
      <div className="flex-shrink-0 mb-3">
        <MarketPulse indices={cockpitData.indices} />
      </div>

      {/* Divider */}
      <div className="border-t border-zinc-200/40 dark:border-zinc-800/40 my-1 flex-shrink-0" />

      {/* Watchlist */}
      <div className="flex-1 min-h-0">
        <WatchlistPanel
          watchlists={cockpitData.watchlists}
          onSymbolSelect={(symbol) => {
            handleSymbolSelect(symbol);
            setShowWatchlistDrawer(false);
          }}
          onAskAI={handleAskAI}
        />
      </div>
    </>
  );

  return (
    <div className="flex flex-col h-full min-h-0 bg-zinc-50/50 dark:bg-zinc-950/50">
      {/* Top Strip - Portfolio Summary */}
      <TopStrip
        portfolio={cockpitData.portfolio}
        marketOpen={marketOpen}
        onRefresh={cockpitData.refresh}
        autoRefresh={autoRefresh}
        onToggleAutoRefresh={() => setAutoRefresh(prev => !prev)}
        lastUpdated={cockpitData.lastUpdated}
        isLoading={cockpitData.isLoading}
      />

      {/* Error banner */}
      {cockpitData.error && (
        <div className="px-3 py-1.5 bg-red-50 dark:bg-red-900/20 border-b border-red-200/50 dark:border-red-800/50 text-xs text-red-600 dark:text-red-400">
          {cockpitData.error}
        </div>
      )}

      {/* Watchlist Drawer (slides from left, visible below xl) */}
      <Headless.Dialog open={showWatchlistDrawer} onClose={() => setShowWatchlistDrawer(false)} className="xl:hidden">
        <Headless.DialogBackdrop
          transition
          className="fixed inset-0 bg-black/30 transition data-[closed]:opacity-0 data-[enter]:duration-300 data-[enter]:ease-out data-[leave]:duration-200 data-[leave]:ease-in z-40"
        />
        <Headless.DialogPanel
          transition
          className="fixed inset-y-0 left-0 w-[300px] max-w-[85vw] bg-white dark:bg-zinc-900 shadow-xl transition duration-300 ease-in-out data-[closed]:-translate-x-full z-50"
        >
          <div className="flex flex-col h-full min-h-0 p-2">
            <div className="flex items-center justify-between mb-1 flex-shrink-0">
              <span className="text-xs font-bold text-zinc-500 dark:text-zinc-400 tracking-wide uppercase px-1">Watchlist</span>
              <button
                onClick={() => setShowWatchlistDrawer(false)}
                className="p-1 rounded-md text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
              >
                <XIcon className="h-4 w-4" />
              </button>
            </div>

            {/* Trading Mode Toggle (mobile drawer) */}
            <div className="flex-shrink-0 mb-2">
              <TradingModeToggle authToken={authToken} onModeChange={handleTradingModeChange} />
            </div>

            {watchlistContent}
          </div>
        </Headless.DialogPanel>
      </Headless.Dialog>

      {/* Chat Drawer (slides from right) */}
      <Headless.Dialog open={showChatDrawer} onClose={() => setShowChatDrawer(false)}>
        <Headless.DialogBackdrop
          transition
          className="fixed inset-0 bg-black/30 transition data-[closed]:opacity-0 data-[enter]:duration-300 data-[enter]:ease-out data-[leave]:duration-200 data-[leave]:ease-in z-40"
        />
        <Headless.DialogPanel
          transition
          className="fixed inset-y-0 right-0 w-[340px] max-w-[85vw] bg-white dark:bg-zinc-900 shadow-xl transition duration-300 ease-in-out data-[closed]:translate-x-full z-50"
        >
          <CockpitChat
            authToken={authToken}
            contextPrefix={chatContext}
            onClearContext={() => setChatContext(null)}
            onClose={() => setShowChatDrawer(false)}
          />
        </Headless.DialogPanel>
      </Headless.Dialog>

      {/* Main Three-Zone Layout */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* LEFT PANEL - Watchlist + Market Pulse (inline at xl+) */}
        <div
          className={`hidden xl:block flex-shrink-0 border-r border-zinc-200/50 dark:border-zinc-800/50 bg-white/50 dark:bg-zinc-900/50 transition-all duration-300 ${
            leftCollapsed ? 'w-10' : 'w-[280px]'
          }`}
        >
          {leftCollapsed ? (
            <div className="flex flex-col items-center pt-2 gap-1">
              <button
                onClick={() => setLeftCollapsed(false)}
                className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                title="Expand Watchlist"
              >
                <PanelLeftOpenIcon className="h-4 w-4" />
              </button>
              <TradingModeToggle authToken={authToken} isCollapsed onModeChange={handleTradingModeChange} />
            </div>
          ) : (
            <div className="flex flex-col h-full min-h-0 p-2">
              {/* Collapse Button */}
              <div className="flex justify-end mb-1 flex-shrink-0">
                <button
                  onClick={() => setLeftCollapsed(true)}
                  className="p-1 rounded-md text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                  title="Collapse Watchlist"
                >
                  <PanelLeftCloseIcon className="h-3.5 w-3.5" />
                </button>
              </div>

              {/* Trading Mode Toggle */}
              <div className="flex-shrink-0 mb-2">
                <TradingModeToggle authToken={authToken} onModeChange={handleTradingModeChange} />
              </div>

              {watchlistContent}
            </div>
          )}
        </div>

        {/* CENTER PANEL - Chart + Positions + Scorecard */}
        <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden">
          {/* Chart Area — fixed vh height, won't grow or shrink */}
          <div className="h-[50vh] flex-shrink-0 overflow-hidden border-b border-zinc-200/50 dark:border-zinc-800/50">
            <PriceChart
              symbol={activeSymbol}
              data={chartResult.data}
              activeTimeframe={activeTimeframe}
              onTimeframeChange={(tf) => setActiveTimeframe(tf)}
            />
          </div>

          {/* Positions Table — fills remaining space, scrolls internally */}
          <div className="flex-1 min-h-0 overflow-hidden">
            <PositionsTable
              positions={cockpitData.positions}
              holdings={cockpitData.holdings}
              onSymbolSelect={handleSymbolSelect}
              onAskAI={handleAskAI}
            />
          </div>

          {/* Daily Scorecard (pinned to bottom) */}
          {cockpitData.scorecard && <div className="flex-shrink-0"><DailyScorecard scorecard={cockpitData.scorecard} /></div>}
        </div>

      </div>

      {/* FAB - Watchlist (visible below xl) */}
      <button
        onClick={() => setShowWatchlistDrawer(true)}
        className="xl:hidden fixed bottom-6 left-6 z-30 p-3 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 rounded-full shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-110 active:scale-95"
        aria-label="Open Watchlist"
        title="Open Watchlist"
      >
        <ListIcon className="h-5 w-5" />
      </button>

      {/* FAB - Chat */}
      <button
        onClick={() => setShowChatDrawer(true)}
        className="fixed bottom-6 right-6 z-30 p-3 bg-amber-500 text-white rounded-full shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-110 active:scale-95"
        aria-label="Open Chat"
        title="Open Chat"
      >
        <MessageSquareIcon className="h-5 w-5" />
      </button>
    </div>
  );
};

export default Dashboard;
