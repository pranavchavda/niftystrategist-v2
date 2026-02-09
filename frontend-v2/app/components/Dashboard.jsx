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
import {
  mockPortfolio,
  mockPositions,
  mockHoldings,
  mockWatchlists,
  mockIndices,
  mockScorecard,
  mockChatMessages,
  generateMockOHLCV,
} from './cockpit/mock-data';

const Dashboard = ({ authToken }) => {
  // Panel collapse states (for inline panels)
  const [leftCollapsed, setLeftCollapsed] = useState(() => {
    const saved = localStorage.getItem('cockpit-left-collapsed');
    return saved === 'true';
  });
  const [rightCollapsed, setRightCollapsed] = useState(() => {
    const saved = localStorage.getItem('cockpit-right-collapsed');
    return saved === 'true';
  });

  // Drawer states (for responsive breakpoints)
  const [showWatchlistDrawer, setShowWatchlistDrawer] = useState(false);
  const [showChatDrawer, setShowChatDrawer] = useState(false);

  // Active symbol for chart
  const [activeSymbol, setActiveSymbol] = useState('RELIANCE');
  const [chartData, setChartData] = useState(() => generateMockOHLCV(90));

  // Chat context
  const [chatContext, setChatContext] = useState(null);

  // Market status (mock)
  const [marketOpen, setMarketOpen] = useState(true);

  // Persist collapse states
  useEffect(() => {
    localStorage.setItem('cockpit-left-collapsed', String(leftCollapsed));
  }, [leftCollapsed]);

  useEffect(() => {
    localStorage.setItem('cockpit-right-collapsed', String(rightCollapsed));
  }, [rightCollapsed]);

  // Generate new chart data when symbol changes
  useEffect(() => {
    setChartData(generateMockOHLCV(90));
  }, [activeSymbol]);

  const handleSymbolSelect = useCallback((symbol) => {
    setActiveSymbol(symbol);
  }, []);

  const handleAskAI = useCallback((symbol, context) => {
    setChatContext(`[CONTEXT: ${context.type}] About ${symbol}: ${JSON.stringify(context.data)}\n\n`);
    // At narrow widths, open the chat drawer instead of the inline panel
    if (window.innerWidth < 1536) {
      setShowChatDrawer(true);
    } else {
      if (rightCollapsed) setRightCollapsed(false);
    }
  }, [rightCollapsed]);

  const handleRefresh = useCallback(() => {
    // In Phase 2+, this will hit the real API
    console.log('Refreshing cockpit data...');
  }, []);

  // Shared watchlist content for both inline panel and drawer
  const watchlistContent = (
    <>
      {/* Market Pulse */}
      <div className="flex-shrink-0 mb-3">
        <MarketPulse indices={mockIndices} />
      </div>

      {/* Divider */}
      <div className="border-t border-zinc-200/40 dark:border-zinc-800/40 my-1 flex-shrink-0" />

      {/* Watchlist */}
      <div className="flex-1 min-h-0">
        <WatchlistPanel
          watchlists={mockWatchlists}
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
        portfolio={mockPortfolio}
        marketOpen={marketOpen}
        onRefresh={handleRefresh}
      />

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
            {watchlistContent}
          </div>
        </Headless.DialogPanel>
      </Headless.Dialog>

      {/* Chat Drawer (slides from right, visible below 2xl) */}
      <Headless.Dialog open={showChatDrawer} onClose={() => setShowChatDrawer(false)} className="2xl:hidden">
        <Headless.DialogBackdrop
          transition
          className="fixed inset-0 bg-black/30 transition data-[closed]:opacity-0 data-[enter]:duration-300 data-[enter]:ease-out data-[leave]:duration-200 data-[leave]:ease-in z-40"
        />
        <Headless.DialogPanel
          transition
          className="fixed inset-y-0 right-0 w-[340px] max-w-[85vw] bg-white dark:bg-zinc-900 shadow-xl transition duration-300 ease-in-out data-[closed]:translate-x-full z-50"
        >
          <CockpitChat
            messages={mockChatMessages}
            isCollapsed={false}
            onToggleCollapse={() => setShowChatDrawer(false)}
            contextPrefix={chatContext}
            onClearContext={() => setChatContext(null)}
            isDrawer
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
            <div className="flex flex-col items-center pt-2">
              <button
                onClick={() => setLeftCollapsed(false)}
                className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                title="Expand Watchlist"
              >
                <PanelLeftOpenIcon className="h-4 w-4" />
              </button>
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
              {watchlistContent}
            </div>
          )}
        </div>

        {/* CENTER PANEL - Chart + Positions + Scorecard */}
        <div className="flex-1 flex flex-col min-h-0 min-w-0">
          {/* Chart Area (55% height) */}
          <div className="flex-[55] min-h-0 border-b border-zinc-200/50 dark:border-zinc-800/50">
            <PriceChart
              symbol={activeSymbol}
              data={chartData}
            />
          </div>

          {/* Positions Table (flexible) */}
          <div className="flex-[45] min-h-0">
            <PositionsTable
              positions={mockPositions}
              holdings={mockHoldings}
              onSymbolSelect={handleSymbolSelect}
              onAskAI={handleAskAI}
            />
          </div>

          {/* Daily Scorecard (auto height) */}
          <DailyScorecard scorecard={mockScorecard} />
        </div>

        {/* RIGHT PANEL - Cockpit Chat (inline at 2xl+) */}
        <div
          className={`hidden 2xl:block flex-shrink-0 border-l border-zinc-200/50 dark:border-zinc-800/50 bg-white/30 dark:bg-zinc-900/30 transition-all duration-300 ${
            rightCollapsed ? 'w-10' : 'w-[320px]'
          }`}
        >
          <CockpitChat
            messages={mockChatMessages}
            isCollapsed={rightCollapsed}
            onToggleCollapse={() => setRightCollapsed(!rightCollapsed)}
            contextPrefix={chatContext}
            onClearContext={() => setChatContext(null)}
          />
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

      {/* FAB - Chat (visible below 2xl) */}
      <button
        onClick={() => setShowChatDrawer(true)}
        className="2xl:hidden fixed bottom-6 right-6 z-30 p-3 bg-amber-500 text-white rounded-full shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-110 active:scale-95"
        aria-label="Open Chat"
        title="Open Chat"
      >
        <MessageSquareIcon className="h-5 w-5" />
      </button>
    </div>
  );
};

export default Dashboard;
