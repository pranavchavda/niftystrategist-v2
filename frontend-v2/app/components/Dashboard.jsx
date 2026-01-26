import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUpIcon,
  TrendingDownIcon,
  WalletIcon,
  BarChart3Icon,
  ActivityIcon,
  RefreshCwIcon,
  Loader2Icon,
  MessageSquareIcon,
  PieChartIcon,
  IndianRupeeIcon,
  ArrowUpIcon,
  ArrowDownIcon,
} from 'lucide-react';
import { Card, StatCard } from './Card';
import { Button } from './catalyst/button';
import { useNavigate } from 'react-router';

// Utility functions
const formatCurrency = (amount) => {
  if (!amount && amount !== 0) return '₹0';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(amount);
};

const formatNumber = (num) => {
  if (!num && num !== 0) return '0';
  return new Intl.NumberFormat('en-IN').format(num);
};

const formatPercent = (num) => {
  if (!num && num !== 0) return '0%';
  return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
};

// Trading Dashboard Component
const Dashboard = ({ authToken }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [portfolioData, setPortfolioData] = useState(null);
  const [error, setError] = useState(null);

  // Fetch portfolio data from backend
  const fetchPortfolioData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // TODO: Connect to actual portfolio API
      // For now, show placeholder data structure
      const mockData = {
        total_value: 1000000,
        available_cash: 250000,
        invested_value: 750000,
        day_pnl: 12500,
        day_pnl_percentage: 1.25,
        total_pnl: 45000,
        total_pnl_percentage: 4.5,
        positions: [],
        market_status: 'closed',
        last_updated: new Date().toISOString()
      };

      setPortfolioData(mockData);
    } catch (err) {
      console.error('Portfolio fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  useEffect(() => {
    fetchPortfolioData();
  }, [fetchPortfolioData]);

  const isProfitable = (value) => value >= 0;

  return (
    <div className="mx-auto p-4 sm:p-6 lg:p-8 max-w-7xl min-h-screen">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-6 sm:mb-8">
        <div>
          <h1 className="flex items-center gap-3 text-3xl font-bold text-zinc-900 dark:text-zinc-100">
            <BarChart3Icon className="h-8 w-8 text-blue-600 dark:text-blue-500" />
            Trading Dashboard
          </h1>
          <p className="text-zinc-600 dark:text-zinc-400 mt-2">
            Portfolio overview and market insights
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            onClick={fetchPortfolioData}
            disabled={loading}
            color="blue"
            className="gap-2"
          >
            {loading ? (
              <Loader2Icon data-slot="icon" className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCwIcon data-slot="icon" className="h-4 w-4" />
            )}
            {loading ? 'Refreshing...' : 'Refresh'}
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="mb-6 border-red-200 dark:border-red-800/50 bg-red-50 dark:bg-red-900/20">
          <div className="p-4">
            <p className="text-red-800 dark:text-red-200 font-medium">Error Loading Portfolio</p>
            <p className="text-red-600 dark:text-red-300 text-sm mt-1">{error}</p>
            <Button
              onClick={fetchPortfolioData}
              color="red"
              outline
              className="mt-3"
            >
              Try Again
            </Button>
          </div>
        </Card>
      )}

      {/* Loading State */}
      {loading && !portfolioData && (
        <div className="flex flex-col items-center justify-center py-12">
          <Loader2Icon className="h-12 w-12 animate-spin text-blue-600 mb-4" />
          <h3 className="text-xl font-semibold text-zinc-600 dark:text-zinc-400">Loading Portfolio...</h3>
        </div>
      )}

      {/* Dashboard Content */}
      {portfolioData && !loading && (
        <div className="space-y-6 lg:space-y-8">
          {/* Quick Stats Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 lg:gap-6">
            <StatCard
              title="Portfolio Value"
              value={formatCurrency(portfolioData.total_value)}
              description="Total portfolio worth"
              icon={
                <div className="p-3 bg-blue-100 dark:bg-blue-500/20 rounded-full">
                  <WalletIcon className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                </div>
              }
            />

            <StatCard
              title="Available Cash"
              value={formatCurrency(portfolioData.available_cash)}
              description="Ready to invest"
              icon={
                <div className="p-3 bg-green-100 dark:bg-green-500/20 rounded-full">
                  <IndianRupeeIcon className="h-6 w-6 text-green-600 dark:text-green-400" />
                </div>
              }
            />

            <StatCard
              title={
                <div className="flex items-center gap-2">
                  <span>Today's P&L</span>
                  {isProfitable(portfolioData.day_pnl) ? (
                    <ArrowUpIcon className="h-4 w-4 text-green-500" />
                  ) : (
                    <ArrowDownIcon className="h-4 w-4 text-red-500" />
                  )}
                </div>
              }
              value={
                <span className={isProfitable(portfolioData.day_pnl) ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                  {formatCurrency(portfolioData.day_pnl)}
                </span>
              }
              description={formatPercent(portfolioData.day_pnl_percentage)}
              icon={
                <div className={`p-3 rounded-full ${isProfitable(portfolioData.day_pnl) ? 'bg-green-100 dark:bg-green-500/20' : 'bg-red-100 dark:bg-red-500/20'}`}>
                  {isProfitable(portfolioData.day_pnl) ? (
                    <TrendingUpIcon className="h-6 w-6 text-green-600 dark:text-green-400" />
                  ) : (
                    <TrendingDownIcon className="h-6 w-6 text-red-600 dark:text-red-400" />
                  )}
                </div>
              }
            />

            <StatCard
              title={
                <div className="flex items-center gap-2">
                  <span>Total P&L</span>
                  {isProfitable(portfolioData.total_pnl) ? (
                    <ArrowUpIcon className="h-4 w-4 text-green-500" />
                  ) : (
                    <ArrowDownIcon className="h-4 w-4 text-red-500" />
                  )}
                </div>
              }
              value={
                <span className={isProfitable(portfolioData.total_pnl) ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                  {formatCurrency(portfolioData.total_pnl)}
                </span>
              }
              description={formatPercent(portfolioData.total_pnl_percentage)}
              icon={
                <div className={`p-3 rounded-full ${isProfitable(portfolioData.total_pnl) ? 'bg-green-100 dark:bg-green-500/20' : 'bg-red-100 dark:bg-red-500/20'}`}>
                  <ActivityIcon className={`h-6 w-6 ${isProfitable(portfolioData.total_pnl) ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`} />
                </div>
              }
            />
          </div>

          {/* Main Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Positions Section */}
            <Card className="lg:col-span-2 overflow-hidden">
              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 px-6 py-4 border-b border-zinc-200 dark:border-zinc-700/50">
                <h3 className="text-zinc-900 dark:text-zinc-100 flex items-center gap-2 text-lg font-semibold">
                  <PieChartIcon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  Open Positions
                </h3>
              </div>
              <div className="p-6">
                {portfolioData.positions && portfolioData.positions.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-zinc-200 dark:border-zinc-700">
                          <th className="text-left py-2 text-sm font-medium text-zinc-600 dark:text-zinc-400">Symbol</th>
                          <th className="text-right py-2 text-sm font-medium text-zinc-600 dark:text-zinc-400">Qty</th>
                          <th className="text-right py-2 text-sm font-medium text-zinc-600 dark:text-zinc-400">Avg Price</th>
                          <th className="text-right py-2 text-sm font-medium text-zinc-600 dark:text-zinc-400">LTP</th>
                          <th className="text-right py-2 text-sm font-medium text-zinc-600 dark:text-zinc-400">P&L</th>
                        </tr>
                      </thead>
                      <tbody>
                        {portfolioData.positions.map((pos, index) => (
                          <tr key={index} className="border-b border-zinc-100 dark:border-zinc-800">
                            <td className="py-3 font-medium text-zinc-900 dark:text-zinc-100">{pos.symbol}</td>
                            <td className="py-3 text-right text-zinc-700 dark:text-zinc-300">{pos.quantity}</td>
                            <td className="py-3 text-right text-zinc-700 dark:text-zinc-300">{formatCurrency(pos.average_price)}</td>
                            <td className="py-3 text-right text-zinc-700 dark:text-zinc-300">{formatCurrency(pos.current_price)}</td>
                            <td className={`py-3 text-right font-medium ${pos.pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                              {formatCurrency(pos.pnl)} ({formatPercent(pos.pnl_percentage)})
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <PieChartIcon className="h-12 w-12 text-zinc-300 dark:text-zinc-600 mx-auto mb-3" />
                    <p className="text-zinc-500 dark:text-zinc-400">No open positions</p>
                    <p className="text-sm text-zinc-400 dark:text-zinc-500 mt-1">
                      Start a chat to analyze stocks and place trades
                    </p>
                  </div>
                )}
              </div>
            </Card>

            {/* Quick Actions */}
            <Card className="overflow-hidden">
              <div className="bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 px-6 py-4 border-b border-zinc-200 dark:border-zinc-700/50">
                <h3 className="text-zinc-900 dark:text-zinc-100 flex items-center gap-2 text-lg font-semibold">
                  <ActivityIcon className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                  Quick Actions
                </h3>
              </div>
              <div className="p-6 space-y-3">
                <Button
                  outline
                  className="w-full justify-start gap-2"
                  onClick={() => {
                    const newThreadId = `thread_${Date.now()}`;
                    navigate(`/chat/${newThreadId}`);
                  }}
                >
                  <MessageSquareIcon className="h-4 w-4" />
                  Ask Nifty Strategist
                </Button>
                <Button
                  outline
                  className="w-full justify-start gap-2"
                  onClick={fetchPortfolioData}
                  disabled={loading}
                >
                  <RefreshCwIcon className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  Refresh Portfolio
                </Button>
                <div className="pt-4 border-t border-zinc-200 dark:border-zinc-700">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-2">Market Status</p>
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${portfolioData.market_status === 'open' ? 'bg-green-500' : 'bg-red-500'}`}></span>
                    <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300 capitalize">
                      {portfolioData.market_status || 'Unknown'}
                    </span>
                  </div>
                </div>
              </div>
            </Card>
          </div>

          {/* Paper Trading Notice */}
          <Card className="border-amber-200 dark:border-amber-800/50 bg-amber-50 dark:bg-amber-900/20">
            <div className="p-4 flex items-start gap-4">
              <div className="p-2 bg-amber-100 dark:bg-amber-800/30 rounded-full">
                <WalletIcon className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <p className="text-amber-800 dark:text-amber-200 font-medium">Paper Trading Mode</p>
                <p className="text-amber-700 dark:text-amber-300 text-sm mt-1">
                  You are using simulated paper trading with virtual funds. No real money is at risk.
                  Connect your Upstox account in Settings to enable live trading.
                </p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Empty State */}
      {!portfolioData && !loading && !error && (
        <div className="text-center py-12">
          <BarChart3Icon className="h-16 w-16 text-zinc-300 dark:text-zinc-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-zinc-600 dark:text-zinc-400 mb-2">No Portfolio Data</h3>
          <p className="text-zinc-500 dark:text-zinc-500 mb-4">
            Click "Refresh" to load your portfolio data.
          </p>
          <Button onClick={fetchPortfolioData} color="blue">
            Load Portfolio
          </Button>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
