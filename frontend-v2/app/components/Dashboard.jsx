import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart3Icon,
  TrendingUpIcon,
  TrendingDownIcon,
  ShoppingCartIcon,
  DollarSignIcon,
  UsersIcon,
  CalendarIcon,
  CheckCircleIcon,
  MailIcon,
  ClockIcon,
  Loader2Icon,
  AlertTriangleIcon,
  RefreshCwIcon,
  MessageSquareIcon,
  ZapIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  MinusIcon,
  LogOutIcon,
} from 'lucide-react';
import { Card, StatCard } from './Card';
import { Button } from './catalyst/button';
import { Link, useNavigate } from 'react-router';

// Utility functions for the real Dashboard implementation
const formatCurrency = (amount) => {
  if (!amount) return '$0';
  const num = typeof amount === 'string' ? parseFloat(amount.replace(/[^0-9.-]+/g, '')) : amount;
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(num);
};

const formatNumber = (num) => {
  if (!num) return '0';
  const number = typeof num === 'string' ? parseFloat(num.replace(/[^0-9.-]+/g, '')) : num;
  return new Intl.NumberFormat('en-US').format(number);
};

// Trend Indicator Component
const TrendIndicator = ({ comparison, showValue = false }) => {
  if (!comparison) return null;

  const { change_pct, trend } = comparison;
  const isPositive = trend === 'up';
  const isNegative = trend === 'down';

  const Icon = isPositive ? ArrowUpIcon : isNegative ? ArrowDownIcon : MinusIcon;
  const colorClass = isPositive
    ? 'text-green-600 dark:text-green-400'
    : isNegative
    ? 'text-red-600 dark:text-red-400'
    : 'text-zinc-500 dark:text-zinc-400';

  return (
    <span className={`inline-flex items-center gap-1 text-sm font-medium ${colorClass}`}>
      <Icon className="h-3.5 w-3.5" />
      {showValue && <span>{Math.abs(change_pct)}%</span>}
    </span>
  );
};

// Main Dashboard Component - Real Implementation
const Dashboard = ({ authToken }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [parsedMetrics, setParsedMetrics] = useState(null);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Auto-refresh state
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(300000); // 5 minutes

  // Price monitor state
  const [priceMonitorData, setPriceMonitorData] = useState(null);
  const [priceMonitorLoading, setPriceMonitorLoading] = useState(false);

  // Date picker state - matches original implementation
  const [startDate, setStartDate] = useState(() => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    return yesterday.getFullYear() + '-' +
      String(yesterday.getMonth() + 1).padStart(2, '0') + '-' +
      String(yesterday.getDate()).padStart(2, '0');
  });
  const [endDate, setEndDate] = useState(() => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    return yesterday.getFullYear() + '-' +
      String(yesterday.getMonth() + 1).padStart(2, '0') + '-' +
      String(yesterday.getDate()).padStart(2, '0');
  });

  // Function to parse key metrics from the dashboard response - from original implementation
  const parseMetrics = (responseText) => {
    const metrics = {
      shopify: {},
      ga4: {},
      topProducts: [],
      adCampaigns: []
    };

    try {
      // Extract Shopify revenue
      const revenueMatch = responseText.match(/Total Revenue[:\s]*\$?([\d,]+\.?\d*)/i);
      if (revenueMatch) metrics.shopify.revenue = revenueMatch[1];

      // Extract order count
      const ordersMatch = responseText.match(/Total.*Orders?[:\s]*(\d+)/i);
      if (ordersMatch) metrics.shopify.orders = ordersMatch[1];

      // Extract AOV
      const aovMatch = responseText.match(/Average Order Value.*AOV[:\s]*\$?([\d,]+\.?\d*)/i);
      if (aovMatch) metrics.shopify.aov = aovMatch[1];

      // Extract GA4 active users
      const usersMatch = responseText.match(/Active Users[:\s]*(\d+)/i);
      if (usersMatch) metrics.ga4.users = usersMatch[1];

      // Extract Ad Spend
      const adSpendMatch = responseText.match(/Ad Spend[:\s]*\$?([\d,]+\.?\d*)/i);
      if (adSpendMatch) metrics.ga4.ad_spend = adSpendMatch[1];

      return metrics;
    } catch (error) {
      console.error('Error parsing metrics:', error);
      return null;
    }
  };

  // Function to fetch dashboard data directly from analytics APIs - from original implementation
  const fetchDashboardData = async (queryStartDate = null, queryEndDate = null) => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('authToken') || authToken;

      // Use provided dates or current state dates
      let finalStartDate = queryStartDate || startDate;
      let finalEndDate = queryEndDate || endDate;

      // Ensure start date is not after end date
      if (new Date(finalStartDate) > new Date(finalEndDate)) {
        // Swap them if they're in the wrong order
        [finalStartDate, finalEndDate] = [finalEndDate, finalStartDate];
        // Also update the state to reflect the correction
        setStartDate(finalStartDate);
        setEndDate(finalEndDate);
      }

      // Ensure dates are always strings, not Date objects
      const formatDateToString = (date) => {
        if (date instanceof Date) {
          return date.getFullYear() + '-' +
            String(date.getMonth() + 1).padStart(2, '0') + '-' +
            String(date.getDate()).padStart(2, '0');
        }
        return date; // Already a string
      };

      const params = new URLSearchParams({
        start_date: formatDateToString(finalStartDate),
        end_date: formatDateToString(finalEndDate)
      });

      const response = await fetch(`/api/dashboard/analytics?${params}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch dashboard data: ${response.statusText}`);
      }

      const data = await response.json();

      // Set the structured data
      setDashboardData(data);
      setParsedMetrics({
        shopify: {
          revenue: data.shopify?.revenue || '0',
          orders: data.shopify?.orders?.toString() || '0',
          aov: data.shopify?.aov || '0'
        },
        ga4: {
          users: data.ga4?.users || '0',
          ad_spend: data.ga4?.ad_spend || '0'
        }
      });
      setLastUpdated(new Date().toLocaleString());

    } catch (err) {
      console.error('Dashboard fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Fetch price monitor data
  const fetchPriceMonitorData = useCallback(async () => {
    setPriceMonitorLoading(true);
    try {
      const token = localStorage.getItem('authToken') || authToken;
      const response = await fetch('/api/dashboard/price-monitor', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setPriceMonitorData(data);
      }
    } catch (err) {
      console.error('Price monitor fetch error:', err);
    } finally {
      setPriceMonitorLoading(false);
    }
  }, [authToken]);

  // Auto-refresh effect
  useEffect(() => {
    let intervalId;
    if (autoRefresh) {
      intervalId = setInterval(() => {
        fetchDashboardData();
        fetchPriceMonitorData();
      }, autoRefreshInterval);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [autoRefresh, autoRefreshInterval]);

  // Date helper functions for quick date range selection
  const getQuickDateRange = (range) => {
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    const lastWeek = new Date();
    lastWeek.setDate(today.getDate() - 7);

    const formatDate = (date) => {
      return date.getFullYear() + '-' +
        String(date.getMonth() + 1).padStart(2, '0') + '-' +
        String(date.getDate()).padStart(2, '0');
    };

    switch (range) {
      case 'today':
        return { start: formatDate(today), end: formatDate(today) };
      case 'yesterday':
        return { start: formatDate(yesterday), end: formatDate(yesterday) };
      case 'lastWeek':
        return { start: formatDate(lastWeek), end: formatDate(yesterday) };
      default:
        return { start: startDate, end: endDate };
    }
  };

  // Load dashboard data on component mount
  useEffect(() => {
    fetchDashboardData();
    fetchPriceMonitorData();
  }, [fetchPriceMonitorData]);

  return (
    <div className="mx-auto p-4 sm:p-6 lg:p-8 max-w-7xl min-h-screen">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-6 sm:mb-8">
        <div>
          <h1 className="flex items-center gap-3 text-3xl font-bold text-zinc-900 dark:text-zinc-100">
            <BarChart3Icon className="h-8 w-8 text-blue-600 dark:text-blue-500" />
            Performance Dashboard
          </h1>
          <p className="text-zinc-600 dark:text-zinc-400 mt-2">
            {startDate === endDate ?
              `Data for ${new Date(startDate).toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric'
              })}` :
              `Data from ${new Date(startDate).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
              })} to ${new Date(endDate).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
              })}`
            }
          </p>
          {lastUpdated && (
            <p className="text-sm text-zinc-500 mt-1">
              Last updated: {lastUpdated}
            </p>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Auto-refresh toggle */}
          <div className="flex items-center gap-2">
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-zinc-200 dark:bg-zinc-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
            <span className="text-sm text-zinc-600 dark:text-zinc-400">
              {autoRefresh ? (
                <span className="flex items-center gap-1">
                  <RefreshCwIcon className="h-3 w-3 animate-spin" />
                  Auto
                </span>
              ) : (
                'Auto'
              )}
            </span>
          </div>

          <Button
            onClick={() => {
              fetchDashboardData();
              fetchPriceMonitorData();
            }}
            disabled={loading}
            color="blue"
            className="gap-2"
          >
            {loading ? (
              <Loader2Icon data-slot="icon" className="h-4 w-4 animate-spin" />
            ) : (
              <TrendingUpIcon data-slot="icon" className="h-4 w-4" />
            )}
            {loading ? 'Refreshing...' : 'Refresh Data'}
          </Button>
        </div>
      </div>

      {/* Date Picker */}
      <Card className="mb-6">
        <div className="p-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
              <div className="flex items-center gap-2">
                <CalendarIcon className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />
                <span className="font-medium text-zinc-700 dark:text-zinc-300">Date Range:</span>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-2">
                <div className="flex flex-col">
                  <label className="text-xs text-zinc-500 dark:text-zinc-400 mb-1 font-medium">Start Date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="border border-zinc-300 dark:border-zinc-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <div className="flex items-center justify-center px-2 py-6 sm:py-0">
                  <span className="text-zinc-500 dark:text-zinc-400 font-medium">to</span>
                </div>
                <div className="flex flex-col">
                  <label className="text-xs text-zinc-500 dark:text-zinc-400 mb-1 font-medium">End Date</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="border border-zinc-300 dark:border-zinc-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() => {
                  const { start, end } = getQuickDateRange('today');
                  setStartDate(start);
                  setEndDate(end);
                  fetchDashboardData(start, end);
                }}
                outline
                className="flex-col !py-2 !px-3 h-auto"
              >
                <span className="font-medium">Today</span>
                <span className="text-xs text-zinc-500 dark:text-zinc-400">
                  {new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </span>
              </Button>
              <Button
                onClick={() => {
                  const { start, end } = getQuickDateRange('yesterday');
                  setStartDate(start);
                  setEndDate(end);
                  fetchDashboardData(start, end);
                }}
                outline
                className="flex-col !py-2 !px-3 h-auto"
              >
                <span className="font-medium">Yesterday</span>
                <span className="text-xs text-zinc-500 dark:text-zinc-400">
                  {(() => {
                    const yesterday = new Date();
                    yesterday.setDate(yesterday.getDate() - 1);
                    return yesterday.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                  })()}
                </span>
              </Button>
              <Button
                onClick={() => {
                  const { start, end } = getQuickDateRange('lastWeek');
                  setStartDate(start);
                  setEndDate(end);
                  fetchDashboardData(start, end);
                }}
                outline
                className="flex-col !py-2 !px-3 h-auto"
              >
                <span className="font-medium">Last 7 Days</span>
              </Button>
              <Button
                onClick={() => fetchDashboardData()}
                disabled={loading}
                color="blue"
              >
                Apply Changes
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {/* Error State */}
      {error && (
        <Card className="mb-6 border-red-200 dark:border-red-800/50 bg-red-50 dark:bg-red-900/20">
          <div className="p-4">
            <p className="text-red-800 dark:text-red-200 font-medium">Error Loading Dashboard</p>
            <p className="text-red-600 dark:text-red-300 text-sm mt-1">{error}</p>
            <Button
              onClick={fetchDashboardData}
              color="red"
              outline
              className="mt-3"
            >
              Try Again
            </Button>
          </div>
        </Card>
      )}

      {/* Google Re-Auth Required Banner */}
      {dashboardData?.google_auth_required && (
        <Card className="mb-6 border-amber-200 dark:border-amber-800/50 bg-amber-50 dark:bg-amber-900/20">
          <div className="p-4 flex items-start gap-4">
            <div className="p-2 bg-amber-100 dark:bg-amber-800/30 rounded-full">
              <AlertTriangleIcon className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            </div>
            <div className="flex-1">
              <p className="text-amber-800 dark:text-amber-200 font-medium">Google Re-Authentication Required</p>
              <p className="text-amber-700 dark:text-amber-300 text-sm mt-1">
                Your Google session has expired. To view GA4 analytics, Calendar, Gmail, and Tasks data,
                please log out and log back in to re-authorize with Google.
              </p>
              <Button
                onClick={() => {
                  localStorage.removeItem('authToken');
                  window.location.href = '/';
                }}
                color="amber"
                className="mt-3"
              >
                <LogOutIcon className="h-4 w-4 mr-2" />
                Log Out &amp; Re-authenticate
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Loading State */}
      {loading && !dashboardData && (
        <div className="flex flex-col items-center justify-center py-12">
          <Loader2Icon className="h-12 w-12 animate-spin text-blue-600 mb-4" />
          <h3 className="text-xl font-semibold text-zinc-600">Generating Dashboard...</h3>
          <p className="text-zinc-500 text-center mt-2">
            Fetching data from Shopify and Google Analytics...
            <br />
            This may take a few moments.
          </p>
        </div>
      )}

      {/* Dashboard Content */}
      {dashboardData && !loading && (
        <div className="space-y-6 lg:space-y-8">
          {/* Quick Stats Cards - First Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 lg:gap-6 mb-4">
            <StatCard
              title={
                <div className="flex items-center gap-2">
                  <span>Revenue</span>
                  {dashboardData?.comparisons?.revenue && (
                    <TrendIndicator comparison={dashboardData.comparisons.revenue} showValue={true} />
                  )}
                </div>
              }
              value={parsedMetrics?.shopify?.revenue ? formatCurrency(parsedMetrics.shopify.revenue) : 'Loading...'}
              description={
                dashboardData?.comparisons?.revenue?.previous > 0
                  ? `vs ${formatCurrency(dashboardData.comparisons.revenue.previous)} prev period`
                  : (startDate === endDate
                    ? new Date(startDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
                    : `${new Date(startDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${new Date(endDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}`)
              }
              icon={
                <div className="p-3 bg-green-100 dark:bg-green-500/20 rounded-full">
                  <DollarSignIcon className="h-6 w-6 text-green-600 dark:text-green-400" />
                </div>
              }
            />

            <StatCard
              title={
                <div className="flex items-center gap-2">
                  <span>Orders</span>
                  {dashboardData?.comparisons?.orders && (
                    <TrendIndicator comparison={dashboardData.comparisons.orders} showValue={true} />
                  )}
                </div>
              }
              value={formatNumber(parsedMetrics?.shopify?.orders) || 'Loading...'}
              description={
                dashboardData?.comparisons?.orders?.previous > 0
                  ? `vs ${formatNumber(dashboardData.comparisons.orders.previous)} prev period`
                  : (startDate === endDate
                    ? new Date(startDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
                    : `${new Date(startDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${new Date(endDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}`)
              }
              icon={
                <div className="p-3 bg-blue-100 dark:bg-blue-500/20 rounded-full">
                  <ShoppingCartIcon className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                </div>
              }
            />

            <StatCard
              title={
                <div className="flex items-center gap-2">
                  <span>Visitors</span>
                  {dashboardData?.comparisons?.visitors && (
                    <TrendIndicator comparison={dashboardData.comparisons.visitors} showValue={true} />
                  )}
                </div>
              }
              value={formatNumber(parsedMetrics?.ga4?.users) || 'Loading...'}
              description={
                dashboardData?.comparisons?.visitors?.previous > 0
                  ? `vs ${formatNumber(dashboardData.comparisons.visitors.previous)} prev period`
                  : (startDate === endDate
                    ? new Date(startDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
                    : `${new Date(startDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${new Date(endDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}`)
              }
              icon={
                <div className="p-3 bg-purple-100 dark:bg-purple-500/20 rounded-full">
                  <UsersIcon className="h-6 w-6 text-purple-600 dark:text-purple-400" />
                </div>
              }
            />

            <StatCard
              title={
                <div className="flex items-center gap-2">
                  <span>Ad Spend</span>
                  {dashboardData?.comparisons?.ad_spend && (
                    <TrendIndicator comparison={dashboardData.comparisons.ad_spend} showValue={true} />
                  )}
                </div>
              }
              value={formatCurrency(dashboardData?.google_ads?.cost || dashboardData?.ga4?.ad_spend || '0')}
              description={`ROAS: ${dashboardData?.google_ads?.roas || dashboardData?.ga4?.roas || '0'}x`}
              icon={
                <div className="p-3 bg-orange-100 dark:bg-orange-500/20 rounded-full">
                  <DollarSignIcon className="h-6 w-6 text-orange-600 dark:text-orange-400" />
                </div>
              }
            />
          </div>

          {/* Main Performance Sections */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 lg:gap-8">
            {/* Shopify Performance */}
            <Card className="overflow-hidden">
              <div className="bg-gradient-to-r from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 px-6 py-4 border-b border-zinc-200 dark:border-zinc-700/50">
                <h3 className="text-zinc-900 dark:text-zinc-100 flex items-center gap-2 text-lg font-semibold">
                  <ShoppingCartIcon className="h-5 w-5 text-green-600 dark:text-green-400" />
                  Shopify Performance
                </h3>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                  <div>
                    <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">Revenue</p>
                    <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{formatCurrency(dashboardData?.shopify?.revenue || '0')}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">Orders</p>
                    <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{formatNumber(dashboardData?.shopify?.orders || '0')}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">AOV</p>
                    <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{formatCurrency(dashboardData?.shopify?.aov || '0')}</p>
                  </div>
                </div>

                {dashboardData?.shopify?.top_products && dashboardData.shopify.top_products.length > 0 && (
                  <div>
                    <h4 className="text-zinc-800 dark:text-zinc-200 mb-3 font-semibold">Top Products</h4>
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-zinc-200 dark:border-zinc-700">
                            <th className="text-left py-2 text-sm font-medium text-zinc-600 dark:text-zinc-400">Rank</th>
                            <th className="text-left py-2 text-sm font-medium text-zinc-600 dark:text-zinc-400">Product</th>
                            <th className="text-left py-2 text-sm font-medium text-zinc-600 dark:text-zinc-400">Qty</th>
                            <th className="text-left py-2 text-sm font-medium text-zinc-600 dark:text-zinc-400">Revenue</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dashboardData.shopify.top_products.slice(0, 5).map((product, index) => (
                            <tr key={index} className="border-b border-zinc-100 dark:border-zinc-800">
                              <td className="py-2 text-zinc-700 dark:text-zinc-300">{index + 1}</td>
                              <td className="py-2 font-medium text-zinc-900 dark:text-zinc-100">{product.title || product.name}</td>
                              <td className="py-2 text-zinc-700 dark:text-zinc-300">{product.quantity_sold}</td>
                              <td className="py-2 text-zinc-700 dark:text-zinc-300">{formatCurrency(product.revenue)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </Card>

            {/* GA4 Performance */}
            <Card className="overflow-hidden">
              <div className="bg-gradient-to-r from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 px-6 py-4 border-b border-zinc-200 dark:border-zinc-700/50">
                <h3 className="text-zinc-900 dark:text-zinc-100 flex items-center gap-2 text-lg font-semibold">
                  <BarChart3Icon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  Google Analytics Performance
                </h3>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                  <div>
                    <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">Active Users</p>
                    <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{formatNumber(dashboardData?.ga4?.users || '0')}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">Conversion Rate</p>
                    <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{dashboardData?.ga4?.conversion_rate || '0%'}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">Sessions</p>
                    <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{formatNumber(dashboardData?.ga4?.sessions || dashboardData?.ga4?.users || '0')}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">Bounce Rate</p>
                    <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{dashboardData?.ga4?.bounce_rate || 'N/A'}</p>
                  </div>
                </div>

                {dashboardData?.ga4?.traffic_sources && dashboardData.ga4.traffic_sources.length > 0 && (
                  <div>
                    <h4 className="text-zinc-800 dark:text-zinc-200 mb-3 font-semibold">Top Traffic Sources</h4>
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-zinc-200 dark:border-zinc-700">
                            <th className="text-left py-2 text-sm font-medium text-zinc-600 dark:text-zinc-400">Source</th>
                            <th className="text-left py-2 text-sm font-medium text-zinc-600 dark:text-zinc-400">Users</th>
                            <th className="text-left py-2 text-sm font-medium text-zinc-600 dark:text-zinc-400">Revenue</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dashboardData.ga4.traffic_sources.slice(0, 5).map((source, index) => (
                            <tr key={index} className="border-b border-zinc-100 dark:border-zinc-800">
                              <td className="py-2 font-medium text-zinc-900 dark:text-zinc-100">{source.source}</td>
                              <td className="py-2 text-zinc-700 dark:text-zinc-300">{formatNumber(source.users)}</td>
                              <td className="py-2 text-zinc-700 dark:text-zinc-300">{formatCurrency(source.revenue)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Google Workspace Section */}
          {dashboardData?.workspace && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
              {/* Google Tasks Widget */}
              <Card variant="interactive" className="overflow-hidden">
                <div className="bg-gradient-to-r from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 px-4 py-3 border-b border-zinc-200 dark:border-zinc-700/50">
                  <div className="flex items-center justify-between">
                    <h4 className="text-zinc-900 dark:text-zinc-100 flex items-center gap-2 font-semibold">
                      <CheckCircleIcon className="h-4 w-4 text-green-600 dark:text-green-400" />
                      Google Tasks ({dashboardData.workspace.tasks.count})
                    </h4>
                    <a
                      href="https://tasks.google.com"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-green-700 dark:text-green-400 hover:text-green-800 dark:hover:text-green-300 font-medium"
                    >
                      View All
                    </a>
                  </div>
                </div>
                <div className="p-4 max-h-64 overflow-y-auto">
                  {dashboardData.workspace.tasks.error ? (
                    <p className="text-zinc-500 dark:text-zinc-400 text-sm">{dashboardData.workspace.tasks.error}</p>
                  ) : dashboardData.workspace.tasks.items.length > 0 ? (
                    <div className="space-y-2">
                      {dashboardData.workspace.tasks.items.slice(0, 5).map((task, index) => (
                        <div key={task.id || index} className="border-l-2 border-green-200 dark:border-green-600/50 pl-3 py-1">
                          <a
                            href="https://tasks.google.com"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-green-700 dark:hover:text-green-400 transition-colors"
                          >
                            <p className="font-medium text-sm text-zinc-800 dark:text-zinc-200 hover:text-green-700 dark:hover:text-green-400">{task.title}</p>
                          </a>
                          {task.due && (
                            <p className="text-xs text-zinc-500 dark:text-zinc-400">
                              Due: {new Date(task.due).toLocaleDateString()}
                            </p>
                          )}
                          {task.notes && (
                            <p className="text-xs text-zinc-600 dark:text-zinc-400 line-clamp-2">{task.notes}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-zinc-500 dark:text-zinc-400 text-sm">No pending tasks</p>
                  )}
                </div>
              </Card>

              {/* Recent Emails Widget */}
              <Card variant="interactive" className="overflow-hidden">
                <div className="bg-gradient-to-r from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 px-4 py-3 border-b border-zinc-200 dark:border-zinc-700/50">
                  <div className="flex items-center justify-between">
                    <h4 className="text-zinc-900 dark:text-zinc-100 flex items-center gap-2 font-semibold">
                      <MailIcon className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                      Recent Emails ({dashboardData.workspace.emails.count})
                    </h4>
                    <a
                      href="https://mail.google.com/mail/u/0/#inbox"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-700 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 font-medium"
                    >
                      View All
                    </a>
                  </div>
                </div>
                <div className="p-4 max-h-64 overflow-y-auto">
                  {dashboardData.workspace.emails.error ? (
                    <p className="text-zinc-500 dark:text-zinc-400 text-sm">{dashboardData.workspace.emails.error}</p>
                  ) : dashboardData.workspace.emails.items.length > 0 ? (
                    <div className="space-y-3">
                      {dashboardData.workspace.emails.items.slice(0, 5).map((email, index) => (
                        <div key={email.id || index} className="border-l-2 border-blue-200 dark:border-blue-600/50 pl-3 py-1">
                          <a
                            href={`https://mail.google.com/mail/u/0/#inbox/${email.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-blue-700 dark:hover:text-blue-400 transition-colors"
                          >
                            <p className="font-medium text-sm text-zinc-800 dark:text-zinc-200 hover:text-blue-700 dark:hover:text-blue-400 line-clamp-1">{email.subject}</p>
                          </a>
                          <p className="text-xs text-zinc-600 dark:text-zinc-400 line-clamp-1">{email.from}</p>
                          {email.snippet && (
                            <p className="text-xs text-zinc-500 dark:text-zinc-500 line-clamp-2">{email.snippet}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-zinc-500 dark:text-zinc-400 text-sm">No recent emails</p>
                  )}
                </div>
              </Card>

              {/* Upcoming Calendar Widget */}
              <Card variant="interactive" className="overflow-hidden">
                <div className="bg-gradient-to-r from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-800/20 px-4 py-3 border-b border-zinc-200 dark:border-zinc-700/50">
                  <div className="flex items-center justify-between">
                    <h4 className="text-zinc-900 dark:text-zinc-100 flex items-center gap-2 font-semibold">
                      <ClockIcon className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                      Upcoming Events ({dashboardData.workspace.calendar.count})
                    </h4>
                    <a
                      href="https://calendar.google.com/calendar"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-purple-700 dark:text-purple-400 hover:text-purple-800 dark:hover:text-purple-300 font-medium"
                    >
                      View All
                    </a>
                  </div>
                </div>
                <div className="p-4 max-h-64 overflow-y-auto">
                  {dashboardData.workspace.calendar.error ? (
                    <p className="text-zinc-500 dark:text-zinc-400 text-sm">{dashboardData.workspace.calendar.error}</p>
                  ) : dashboardData.workspace.calendar.items.length > 0 ? (
                    <div className="space-y-3">
                      {dashboardData.workspace.calendar.items.slice(0, 5).map((event, index) => (
                        <div key={event.id || index} className="border-l-2 border-purple-200 dark:border-purple-600/50 pl-3 py-1">
                          {event.htmlLink ? (
                            <a
                              href={event.htmlLink}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="hover:text-purple-700 dark:hover:text-purple-400 transition-colors"
                            >
                              <p className="font-medium text-sm text-zinc-800 dark:text-zinc-200 hover:text-purple-700 dark:hover:text-purple-400 line-clamp-1">{event.summary}</p>
                            </a>
                          ) : (
                            <p className="font-medium text-sm text-zinc-800 dark:text-zinc-200 line-clamp-1">{event.summary}</p>
                          )}
                          <p className="text-xs text-zinc-600 dark:text-zinc-400">
                            {new Date(event.start).toLocaleDateString()} at{' '}
                            {new Date(event.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </p>
                          {event.location && (
                            <p className="text-xs text-zinc-500 dark:text-zinc-500 line-clamp-1">📍 {event.location}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-zinc-500 dark:text-zinc-400 text-sm">No upcoming events</p>
                  )}
                </div>
              </Card>
            </div>
          )}

          {/* Price Monitor & Quick Actions Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Price Monitor Widget */}
            <Card variant="interactive" className="overflow-hidden lg:col-span-2">
              <div className="bg-gradient-to-r from-red-50 to-orange-50 dark:from-red-900/20 dark:to-orange-900/20 px-4 py-3 border-b border-zinc-200 dark:border-zinc-700/50">
                <div className="flex items-center justify-between">
                  <h4 className="text-zinc-900 dark:text-zinc-100 flex items-center gap-2 font-semibold">
                    <AlertTriangleIcon className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                    Price Monitor
                    {priceMonitorData?.stats?.map_violations > 0 && (
                      <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300 rounded-full">
                        {priceMonitorData.stats.map_violations} violations
                      </span>
                    )}
                  </h4>
                  <Link
                    to="/price-monitor"
                    className="text-xs text-orange-700 dark:text-orange-400 hover:text-orange-800 dark:hover:text-orange-300 font-medium"
                  >
                    View All
                  </Link>
                </div>
              </div>
              <div className="p-4">
                {priceMonitorLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2Icon className="h-6 w-6 animate-spin text-orange-600" />
                  </div>
                ) : priceMonitorData ? (
                  <div className="space-y-4">
                    {/* Stats Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                      <div className="text-center p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                        <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                          {priceMonitorData.overview?.total_idc_products || 0}
                        </p>
                        <p className="text-xs text-zinc-500 dark:text-zinc-400">Products</p>
                      </div>
                      <div className="text-center p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                        <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                          {priceMonitorData.overview?.total_matches || 0}
                        </p>
                        <p className="text-xs text-zinc-500 dark:text-zinc-400">Matches</p>
                      </div>
                      <div className="text-center p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                        <p className={`text-2xl font-bold ${(priceMonitorData.overview?.active_violations || 0) > 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                          {priceMonitorData.overview?.active_violations || 0}
                        </p>
                        <p className="text-xs text-zinc-500 dark:text-zinc-400">Violations</p>
                      </div>
                      <div className="text-center p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                        <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                          {priceMonitorData.stats?.competitors_tracked || 0}
                        </p>
                        <p className="text-xs text-zinc-500 dark:text-zinc-400">Competitors</p>
                      </div>
                    </div>

                    {/* Recent Alerts */}
                    {priceMonitorData.recent_alerts && priceMonitorData.recent_alerts.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">Recent Alerts</h5>
                        <div className="space-y-2">
                          {priceMonitorData.recent_alerts.slice(0, 3).map((alert, index) => (
                            <div key={alert.id || index} className="flex items-center justify-between p-2 bg-red-50 dark:bg-red-900/20 rounded-lg text-sm">
                              <div className="flex-1 min-w-0">
                                <p className="font-medium text-zinc-800 dark:text-zinc-200 truncate">{alert.product_title}</p>
                                <p className="text-xs text-zinc-500 dark:text-zinc-400">{alert.competitor}</p>
                              </div>
                              <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-red-100 dark:bg-red-800 text-red-700 dark:text-red-200 rounded">
                                -${Math.abs(alert.price_difference).toFixed(2)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-zinc-500 dark:text-zinc-400 text-sm text-center py-4">
                    No price monitor data available
                  </p>
                )}
              </div>
            </Card>

            {/* Quick Actions Panel */}
            <Card variant="interactive" className="overflow-hidden">
              <div className="bg-gradient-to-r from-indigo-50 to-blue-50 dark:from-indigo-900/20 dark:to-blue-900/20 px-4 py-3 border-b border-zinc-200 dark:border-zinc-700/50">
                <h4 className="text-zinc-900 dark:text-zinc-100 flex items-center gap-2 font-semibold">
                  <ZapIcon className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                  Quick Actions
                </h4>
              </div>
              <div className="p-4 space-y-3">
                <Button
                  outline
                  className="w-full justify-start gap-2"
                  onClick={() => {
                    const newThreadId = `thread_${Date.now()}`;
                    navigate(`/chat/${newThreadId}`);
                  }}
                >
                  <MessageSquareIcon className="h-4 w-4" />
                  Ask EspressoBot
                </Button>
                <Link to="/price-monitor" className="block">
                  <Button outline className="w-full justify-start gap-2">
                    <AlertTriangleIcon className="h-4 w-4" />
                    View MAP Violations
                  </Button>
                </Link>
                <Button
                  outline
                  className="w-full justify-start gap-2"
                  onClick={() => {
                    fetchDashboardData();
                    fetchPriceMonitorData();
                  }}
                  disabled={loading}
                >
                  <RefreshCwIcon className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  Refresh All Data
                </Button>
                <Button outline disabled className="w-full justify-start gap-2 opacity-50 cursor-not-allowed">
                  <BarChart3Icon className="h-4 w-4" />
                  View Reports
                  <span className="ml-auto text-xs text-zinc-400">(Coming Soon)</span>
                </Button>
              </div>
            </Card>
          </div>

          {/* Insights Section */}
          {dashboardData?.insights && dashboardData.insights.length > 0 && (
            <Card className="overflow-hidden">
              <div className="bg-gradient-to-r from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-800/20 px-6 py-4 border-b border-zinc-200 dark:border-zinc-700/50">
                <h3 className="text-zinc-900 dark:text-zinc-100 flex items-center gap-2 text-lg font-semibold">
                  <TrendingUpIcon className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                  Key Insights & Recommendations
                </h3>
              </div>
              <div className="p-6">
                <div className="space-y-3">
                  {dashboardData.insights.map((insight, index) => (
                    <div key={index} className="flex items-start gap-3 p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                      <div className="w-2 h-2 bg-purple-500 dark:bg-purple-400 rounded-full mt-2 flex-shrink-0"></div>
                      <p className="text-zinc-700 dark:text-zinc-300">{insight}</p>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Empty State */}
      {!dashboardData && !loading && !error && (
        <div className="text-center py-12">
          <BarChart3Icon className="h-16 w-16 text-zinc-300 dark:text-zinc-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-zinc-600 dark:text-zinc-400 mb-2">No Dashboard Data</h3>
          <p className="text-zinc-500 dark:text-zinc-500 mb-4">
            Click "Refresh Data" to generate your daily performance report.
          </p>
          <Button
            onClick={fetchDashboardData}
            color="blue"
          >
            Generate Report
          </Button>
        </div>
      )}
    </div>
  );
};

export default Dashboard;