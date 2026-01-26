import React, { useState, useEffect } from 'react';
import {
  ArchiveBoxIcon,
  BuildingStorefrontIcon,
  Square2StackIcon,
  ExclamationTriangleIcon,
  ShoppingBagIcon,
  SparklesIcon,
  GlobeAltIcon,
  ShieldExclamationIcon,
} from '@heroicons/react/20/solid';
import { Loader2Icon } from 'lucide-react';

// Real PriceMonitor implementation ported from original ebot
export default function PriceMonitor() {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncLoading, setSyncLoading] = useState(false);
  const [matchingLoading, setMatchingLoading] = useState(false);
  const [scrapingLoading, setScrapingLoading] = useState(false);
  const [violationScanLoading, setViolationScanLoading] = useState(false);
  const [matchingThreshold, setMatchingThreshold] = useState('medium');
  const [lastRuns, setLastRuns] = useState({});
  const [error, setError] = useState(null);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);
      const token = localStorage.getItem('authToken');

      const response = await fetch('/api/price-monitor/dashboard/overview', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setDashboardData(data);
      } else {
        throw new Error(`Failed to load dashboard data: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchLastRuns = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await fetch('/api/price-monitor/job-status/last-runs', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        const data = await response.json();
        setLastRuns(data);
      }
    } catch (error) {
      console.error('Error fetching last runs:', error);
    }
  };

  // Parse various timestamp formats safely: ISO string, ms epoch, or s epoch
  const parseExecutedAt = (executed_at) => {
    if (!executed_at) return null;
    let ts = executed_at;
    // If it's an object like { seconds: 1712345678 }
    if (typeof ts === 'object' && ts !== null) {
      if ('seconds' in ts) ts = ts.seconds * 1000;
      else if ('milliseconds' in ts) ts = ts.milliseconds;
    }
    // If numeric string, coerce
    if (typeof ts === 'string' && /^\d+$/.test(ts)) {
      ts = Number(ts);
    }
    // If seconds resolution, convert to ms
    if (typeof ts === 'number' && ts > 0 && ts < 1e12) {
      ts = ts * 1000;
    }
    const d = new Date(ts);
    if (isNaN(d.getTime())) return null;
    // Treat epoch/ancient dates as invalid (common when value is 0)
    if (d.getFullYear() < 2000) return null;
    return d;
  };

  const formatLastRun = (lastRun) => {
    if (!lastRun) return 'Never';
    const date = parseExecutedAt(lastRun.executed_at);
    if (!date) return 'Never';
    const now = new Date();
    let diffMs = now - date;
    if (diffMs < 0) diffMs = 0; // clamp future timestamps to "just now"
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 60) {
      return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
    } else if (diffHours < 24) {
      return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    } else if (diffDays < 7) {
      return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  // Badge color by recency for better at-a-glance status
  const getLastRunBadgeColor = (lastRun) => {
    if (!lastRun) return 'zinc';
    const date = parseExecutedAt(lastRun.executed_at);
    if (!date) return 'zinc';
    let diffMs = Date.now() - date.getTime();
    if (diffMs < 0) diffMs = 0;
    const diffMins = Math.floor(diffMs / (1000 * 60));
    if (diffMins < 60) return 'green';
    if (diffMins < 60 * 24) return 'amber';
    return 'red';
  };

  const recordJobExecution = async (jobType) => {
    try {
      const token = localStorage.getItem('authToken');
      await fetch('/api/price-monitor/job-status/record', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ job_type: jobType, status: 'completed' })
      });
      // Refresh last runs
      fetchLastRuns();
    } catch (error) {
      console.error('Error recording job execution:', error);
    }
  };

  const syncShopifyProducts = async () => {
    try {
      setSyncLoading(true);
      setError(null);
      const token = localStorage.getItem('authToken');

      const response = await fetch('/api/price-monitor/shopify-sync-safe/sync-idc-products-safe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ force: true })
      });

      if (response.ok) {
        const result = await response.json();
        showToast(`Safe sync complete: ${result.total_products_created} created, ${result.total_products_updated} updated`, 'success');
        await recordJobExecution('shopify_sync');
        fetchDashboardData(); // Refresh dashboard
      } else {
        throw new Error(`Failed to sync Shopify products: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Error syncing products:', error);
      setError(error.message);
      showToast('Error syncing products', 'error');
    } finally {
      setSyncLoading(false);
    }
  };

  const runProductMatching = async () => {
    try {
      setMatchingLoading(true);
      setError(null);
      const token = localStorage.getItem('authToken');

      const response = await fetch('/api/price-monitor/product-matching/auto-match', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          min_confidence: matchingThreshold,
          dry_run: false
        })
      });

      if (response.ok) {
        const result = await response.json();
        showToast(`Found ${result.matches_found} product matches`, 'success');
        fetchDashboardData(); // Refresh dashboard
      } else {
        throw new Error(`Failed to run product matching: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Error running product matching:', error);
      setError(error.message);
      showToast('Error running product matching', 'error');
    } finally {
      setMatchingLoading(false);
    }
  };

  const runCompetitorScraping = async () => {
    try {
      setScrapingLoading(true);
      setError(null);
      const token = localStorage.getItem('authToken');

      // Get the first active competitor for demo
      const competitorsResponse = await fetch('/api/price-monitor/competitors', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!competitorsResponse.ok) {
        throw new Error('Failed to fetch competitors');
      }

      const competitorsData = await competitorsResponse.json();
      const activeCompetitor = competitorsData.competitors.find(c => c.is_active);

      if (!activeCompetitor) {
        throw new Error('No active competitors found');
      }

      const response = await fetch('/api/price-monitor/scraping/start-scrape', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          competitor_id: activeCompetitor.id,
          collections: activeCompetitor.collections.slice(0, 2) // Limit to first 2 collections
        })
      });

      if (response.ok) {
        const result = await response.json();
        showToast(`Started scraping job for ${activeCompetitor.name}`, 'success');
        await recordJobExecution('competitor_scrape');
        fetchDashboardData(); // Refresh dashboard
      } else {
        throw new Error(`Failed to start competitor scraping: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Error running competitor scraping:', error);
      setError(error.message);
      showToast('Error running competitor scraping', 'error');
    } finally {
      setScrapingLoading(false);
    }
  };

  const scanForViolations = async () => {
    try {
      setViolationScanLoading(true);
      setError(null);
      const token = localStorage.getItem('authToken');

      const response = await fetch('/api/price-monitor/map-violations/scan-violations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          create_alerts: true,
          dry_run: false
        })
      });

      if (response.ok) {
        const result = await response.json();
        const violationsMsg = result.violations_found === 1 ? 'violation' : 'violations';
        showToast(`Found ${result.violations_found} MAP ${violationsMsg} from ${result.total_matches_scanned} matches`, 'success');
        await recordJobExecution('violation_scan');
        fetchDashboardData(); // Refresh dashboard
      } else {
        throw new Error(`Failed to scan for violations: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Error scanning for violations:', error);
      setError(error.message);
      showToast('Error scanning for violations', 'error');
    } finally {
      setViolationScanLoading(false);
    }
  };

  // Simple toast notification (can be replaced with a proper toast library)
  const showToast = (message, type = 'info') => {
    console.log(`${type.toUpperCase()}: ${message}`);
    // In a real implementation, you'd use a toast library here
  };

  useEffect(() => {
    fetchDashboardData();
    fetchLastRuns();
  }, []);

  if (loading) {
    return (
      <div className="p-4 md:p-6 bg-zinc-50 dark:bg-zinc-950 min-h-[calc(100vh-56px)]">
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">MAP Enforcement Dashboard</h1>
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 animate-pulse">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white p-6">
              <div className="h-5 w-20 rounded bg-zinc-200 mb-4" />
              <div className="h-8 w-24 rounded bg-zinc-200" />
            </div>
          ))}
        </div>
        <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white p-6 h-32" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 bg-zinc-50 dark:bg-zinc-950 min-h-[calc(100vh-56px)]">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 md:mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100">MAP Enforcement Dashboard</h1>
          <p className="mt-2 text-zinc-600">
            Monitor competitor pricing compliance and MAP violations
          </p>
          {/* TODO(idc): Re-enable automated sync badge when API timestamps are consistent */}
          {false && lastRuns.cron_job && (
            <div className="mt-2">
              <span className={`inline-block px-2 py-1 text-xs font-medium rounded-full ${
                getLastRunBadgeColor(lastRuns.cron_job) === 'green' ? 'bg-green-100 text-green-700' :
                getLastRunBadgeColor(lastRuns.cron_job) === 'amber' ? 'bg-yellow-100 text-yellow-700' :
                'bg-red-100 text-red-700'
              }`}>
                🕐 Automated sync: {formatLastRun(lastRuns.cron_job)}
              </span>
            </div>
          )}
        </div>
        <button
          onClick={fetchDashboardData}
          disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-700 text-white w-full sm:w-auto transition-colors focus-visible:ring-2 ring-indigo-500 ring-offset-2 px-4 py-2 rounded-lg font-medium disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-red-800 font-medium">Error Loading Price Monitor</p>
          <p className="text-red-600 text-sm mt-1">{error}</p>
          <button
            onClick={fetchDashboardData}
            className="mt-3 px-4 py-2 border border-red-300 text-red-700 rounded-md hover:bg-red-50 transition-colors"
          >
            Try Again
          </button>
        </div>
      )}

      {/* Stats Grid */}
      {dashboardData && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm hover:shadow-md transition-shadow hover:-translate-y-0.5 transition-transform">
            <div className="flex items-center justify-between mb-3">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-indigo-500/10 text-indigo-600">
                <ArchiveBoxIcon className="h-5 w-5" />
              </span>
            </div>
            <div className="text-5xl font-semibold tracking-tight text-indigo-600">{dashboardData.total_idc_products || 0}</div>
            <div className="text-xs uppercase text-zinc-500 mt-1">IDC Products</div>
            <div className="text-xs text-zinc-500 mt-1">Monitored products</div>
          </div>

          <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm hover:shadow-md transition-shadow hover:-translate-y-0.5 transition-transform">
            <div className="flex items-center justify-between mb-3">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-green-500/10 text-green-600">
                <BuildingStorefrontIcon className="h-5 w-5" />
              </span>
            </div>
            <div className="text-5xl font-semibold tracking-tight text-green-600">{dashboardData.total_competitor_products || 0}</div>
            <div className="text-xs uppercase text-zinc-500 mt-1">Competitor Products</div>
            <div className="text-xs text-zinc-500 mt-1">From all competitors</div>
          </div>

          <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm hover:shadow-md transition-shadow hover:-translate-y-0.5 transition-transform">
            <div className="flex items-center justify-between mb-3">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-orange-500/10 text-orange-600">
                <Square2StackIcon className="h-5 w-5" />
              </span>
            </div>
            <div className="text-5xl font-semibold tracking-tight text-orange-600">{dashboardData.total_matches || 0}</div>
            <div className="text-xs uppercase text-zinc-500 mt-1">Product Matches</div>
            <div className="text-xs text-zinc-500 mt-1">AI-powered matching</div>
          </div>

          <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm hover:shadow-md transition-shadow hover:-translate-y-0.5 transition-transform">
            <div className="flex items-center justify-between mb-3">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-red-500/10 text-red-600">
                <ExclamationTriangleIcon className="h-5 w-5" />
              </span>
            </div>
            <div className="text-5xl font-semibold tracking-tight text-red-600">{dashboardData.active_violations || 0}</div>
            <div className="text-xs uppercase text-zinc-500 mt-1">Active Violations</div>
            <div className="text-xs text-zinc-500 mt-1">MAP violations</div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6 mb-6 md:mb-8">
        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm hover:shadow-md transition-shadow hover:-translate-y-0.5 transition-transform">
          <div className="-mt-6 -mx-6 mb-4 h-1.5 rounded-t-xl bg-gradient-to-r from-indigo-500/60 to-transparent" />
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-600">
              <ShoppingBagIcon className="h-5 w-5" />
            </span>
            <h3 className="text-lg font-semibold">Sync Shopify Products</h3>
          </div>
          <p className="text-zinc-600 text-sm mb-4 dark:text-zinc-400">
            Import products from your Shopify store and generate embeddings for semantic matching.
          </p>
          {/* TODO(idc): Re-enable last-run once backend returns reliable timestamps */}
          {false && lastRuns.shopify_sync && (
            <p className="text-xs text-zinc-500 mb-3">
              Last run: {formatLastRun(lastRuns.shopify_sync)}
            </p>
          )}
          <button
            onClick={syncShopifyProducts}
            disabled={syncLoading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white transition-colors focus-visible:ring-2 ring-indigo-500 ring-offset-2 px-4 py-2 rounded-lg font-medium disabled:opacity-50"
          >
            {syncLoading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2Icon className="h-4 w-4 animate-spin" />
                Syncing...
              </span>
            ) : (
              'Sync Products'
            )}
          </button>
        </div>

        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm hover:shadow-md transition-shadow hover:-translate-y-0.5 transition-transform">
          <div className="-mt-6 -mx-6 mb-4 h-1.5 rounded-t-xl bg-gradient-to-r from-indigo-500/60 to-transparent" />
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-600">
              <SparklesIcon className="h-5 w-5" />
            </span>
            <h3 className="text-lg font-semibold">Run Product Matching</h3>
          </div>
          <p className="text-zinc-600 text-sm mb-4 dark:text-zinc-400">
            Use AI embeddings to match your products with competitor products.
          </p>

          {/* Confidence Threshold Segmented Control */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
              Confidence Threshold
            </label>
            <div className="inline-flex rounded-lg bg-zinc-100 p-1">
              <button
                type="button"
                disabled={matchingLoading}
                onClick={() => setMatchingThreshold('low')}
                className={`${matchingThreshold === 'low' ? 'bg-white text-zinc-900 shadow border border-zinc-200 dark:border-zinc-800' : 'text-zinc-600'} px-3 py-1.5 text-sm rounded-md transition-colors disabled:opacity-50`}
              >
                Low
              </button>
              <button
                type="button"
                disabled={matchingLoading}
                onClick={() => setMatchingThreshold('medium')}
                className={`${matchingThreshold === 'medium' ? 'bg-white text-zinc-900 shadow border border-zinc-200 dark:border-zinc-800' : 'text-zinc-600'} px-3 py-1.5 text-sm rounded-md transition-colors disabled:opacity-50`}
              >
                Medium
              </button>
              <button
                type="button"
                disabled={matchingLoading}
                onClick={() => setMatchingThreshold('high')}
                className={`${matchingThreshold === 'high' ? 'bg-white text-zinc-900 shadow border border-zinc-200 dark:border-zinc-800' : 'text-zinc-600'} px-3 py-1.5 text-sm rounded-md transition-colors disabled:opacity-50`}
              >
                High
              </button>
            </div>
            <p className="text-xs text-zinc-500 mt-1">
              {matchingThreshold === 'low' && 'Find more potential matches, may include false positives'}
              {matchingThreshold === 'medium' && 'Recommended balance between precision and recall'}
              {matchingThreshold === 'high' && 'Only very confident matches, may miss some valid matches'}
            </p>
          </div>

          <button
            onClick={runProductMatching}
            disabled={matchingLoading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white transition-colors focus-visible:ring-2 ring-indigo-500 ring-offset-2 px-4 py-2 rounded-lg font-medium disabled:opacity-50"
          >
            {matchingLoading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2Icon className="h-4 w-4 animate-spin" />
                Matching...
              </span>
            ) : (
              `Match Products (${matchingThreshold} confidence)`
            )}
          </button>
        </div>

        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm hover:shadow-md transition-shadow hover:-translate-y-0.5 transition-transform">
          <div className="-mt-6 -mx-6 mb-4 h-1.5 rounded-t-xl bg-gradient-to-r from-purple-500/60 to-transparent" />
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/10 text-purple-600">
              <GlobeAltIcon className="h-5 w-5" />
            </span>
            <h3 className="text-lg font-semibold">Scrape Competitors</h3>
          </div>
          <p className="text-zinc-600 text-sm mb-4 dark:text-zinc-400">
            Scrape competitor websites to collect product data and pricing information.
          </p>
          {/* TODO(idc): Re-enable last-run once backend returns reliable timestamps */}
          {false && lastRuns.competitor_scrape && (
            <p className="text-xs text-zinc-500 mb-3">
              Last run: {formatLastRun(lastRuns.competitor_scrape)}
            </p>
          )}
          <button
            onClick={runCompetitorScraping}
            disabled={scrapingLoading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white transition-colors focus-visible:ring-2 ring-indigo-500 ring-offset-2 px-4 py-2 rounded-lg font-medium disabled:opacity-50"
          >
            {scrapingLoading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2Icon className="h-4 w-4 animate-spin" />
                Scraping...
              </span>
            ) : (
              'Start Scraping'
            )}
          </button>
        </div>

        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm hover:shadow-md transition-shadow hover:-translate-y-0.5 transition-transform">
          <div className="-mt-6 -mx-6 mb-4 h-1.5 rounded-t-xl bg-gradient-to-r from-red-500/60 to-transparent" />
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/10 text-red-600">
              <ShieldExclamationIcon className="h-5 w-5" />
            </span>
            <h3 className="text-lg font-semibold">Scan for Violations</h3>
          </div>
          <p className="text-zinc-600 text-sm mb-4 dark:text-zinc-400">
            Scan existing product matches for MAP pricing violations and generate alerts.
          </p>
          {/* TODO(idc): Re-enable last-run once backend returns reliable timestamps */}
          {false && lastRuns.violation_scan && (
            <p className="text-xs text-zinc-500 mb-3">
              Last run: {formatLastRun(lastRuns.violation_scan)}
            </p>
          )}
          <button
            onClick={scanForViolations}
            disabled={violationScanLoading}
            className="w-full bg-red-600 hover:bg-red-700 text-white transition-colors focus-visible:ring-2 ring-red-500 ring-offset-2 px-4 py-2 rounded-lg font-medium disabled:opacity-50"
          >
            {violationScanLoading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2Icon className="h-4 w-4 animate-spin" />
                Scanning...
              </span>
            ) : (
              'Scan Violations'
            )}
          </button>
        </div>
      </div>

      {/* Recent Activity */}
      {dashboardData?.recent_activity && (
        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6">
          <h3 className="text-lg font-semibold mb-4">Recent Activity</h3>
          <div className="relative">
            <div className="absolute left-3 top-0 bottom-0 w-px bg-zinc-200" />
            <div className="space-y-4">
              {dashboardData.recent_activity.map((activity, index) => (
                <div key={index} className="relative pl-8">
                  <span className="absolute left-[9px] top-2 h-2.5 w-2.5 rounded-full bg-zinc-400 ring-2 ring-white" />
                  <div className="font-medium text-zinc-900">{activity.title}</div>
                  <div className="text-sm text-zinc-500">{activity.description}</div>
                  <div className="text-xs text-zinc-400 mt-1">{new Date(activity.created_at).toLocaleDateString()}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {!dashboardData && !loading && !error && (
        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-12 text-center">
          <div className="text-zinc-500">
            <h3 className="text-lg font-medium mb-2">No data available</h3>
            <p className="mb-4">Start by syncing products from Shopify to begin monitoring.</p>
            <button
              onClick={syncShopifyProducts}
              disabled={syncLoading}
              className="bg-indigo-600 hover:bg-indigo-700 text-white transition-colors focus-visible:ring-2 ring-indigo-500 ring-offset-2 px-4 py-2 rounded-lg font-medium disabled:opacity-50"
            >
              {syncLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2Icon className="h-4 w-4 animate-spin" />
                  Syncing...
                </span>
              ) : (
                'Sync Products Now'
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}