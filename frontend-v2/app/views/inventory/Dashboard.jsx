import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ExclamationTriangleIcon,
  CubeIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon
} from '@heroicons/react/24/outline';

export default function Dashboard({ authToken }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [stockoutRisks, setStockoutRisks] = useState([]);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch dashboard summary
      const summaryRes = await fetch('/api/inventory/dashboard/summary', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (!summaryRes.ok) throw new Error('Failed to fetch summary');
      const summaryData = await summaryRes.json();
      setSummary(summaryData);

      // Fetch stockout risks
      const risksRes = await fetch('/api/inventory/alerts/stockout-risks?threshold_days=14&limit=10', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (risksRes.ok) {
        const risksData = await risksRes.json();
        setStockoutRisks(risksData.risks || []);
      }
    } catch (err) {
      console.error('Dashboard fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return 'text-red-600 bg-red-50 dark:bg-red-900/20';
      case 'high': return 'text-orange-600 bg-orange-50 dark:bg-orange-900/20';
      case 'medium': return 'text-yellow-600 bg-yellow-50 dark:bg-yellow-900/20';
      default: return 'text-zinc-600 bg-zinc-50 dark:bg-zinc-800';
    }
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-28 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
            ))}
          </div>
          <div className="h-64 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-red-600">
            <XCircleIcon className="h-5 w-5" />
            <span className="font-medium">Error loading dashboard</span>
          </div>
          <p className="mt-2 text-sm text-red-500">{error}</p>
          <button
            onClick={fetchDashboardData}
            className="mt-3 text-sm text-red-600 hover:text-red-700 underline"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Total Active SKUs */}
        <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Active SKUs</p>
              <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mt-1">
                {summary?.total_active_skus?.toLocaleString() || '—'}
              </p>
            </div>
            <div className="p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg">
              <CubeIcon className="h-6 w-6 text-emerald-600" />
            </div>
          </div>
        </div>

        {/* Stockout Risks (14 days) */}
        <div
          className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-5 cursor-pointer hover:border-orange-300 transition-colors"
          onClick={() => navigate('/inventory/alerts')}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Stockout Risk (14d)</p>
              <p className="text-2xl font-semibold text-orange-600 mt-1">
                {summary?.stockout_risks_14d || 0}
              </p>
            </div>
            <div className="p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
              <ExclamationTriangleIcon className="h-6 w-6 text-orange-600" />
            </div>
          </div>
        </div>

        {/* Critical Risks (7 days) */}
        <div
          className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-5 cursor-pointer hover:border-red-300 transition-colors"
          onClick={() => navigate('/inventory/alerts')}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Critical (7d)</p>
              <p className="text-2xl font-semibold text-red-600 mt-1">
                {summary?.critical_risks_7d || 0}
              </p>
            </div>
            <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
              <ArrowTrendingDownIcon className="h-6 w-6 text-red-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Stockout Risks List */}
      <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
        <div className="px-5 py-4 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            Stockout Risks
          </h2>
          <button
            onClick={() => navigate('/inventory/alerts')}
            className="text-sm text-emerald-600 hover:text-emerald-700"
          >
            View all
          </button>
        </div>

        {stockoutRisks.length === 0 ? (
          <div className="p-8 text-center">
            <CheckCircleIcon className="h-12 w-12 text-emerald-500 mx-auto mb-3" />
            <p className="text-zinc-600 dark:text-zinc-400">
              No stockout risks detected
            </p>
            <p className="text-sm text-zinc-500 dark:text-zinc-500 mt-1">
              All forecasted inventory levels are healthy
            </p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {stockoutRisks.map((risk, idx) => (
              <div
                key={idx}
                className="px-5 py-4 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 cursor-pointer transition-colors"
                onClick={() => navigate(`/inventory/forecasts/${risk.sku}`)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <span className={`px-2.5 py-1 text-xs font-medium rounded-full ${getSeverityColor(risk.severity)}`}>
                      {risk.severity.toUpperCase()}
                    </span>
                    <div>
                      <p className="font-medium text-zinc-900 dark:text-zinc-100">
                        {risk.sku}
                      </p>
                      <p className="text-sm text-zinc-500 dark:text-zinc-400">
                        {risk.current_inventory} units on hand
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {risk.days_until_stockout} days
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      until stockout
                    </p>
                  </div>
                </div>
                {risk.reorder_recommendation && (
                  <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400 pl-20">
                    {risk.reorder_recommendation}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button
          onClick={() => navigate('/inventory/lookup')}
          className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-5 hover:border-emerald-300 transition-colors text-left"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg">
              <CubeIcon className="h-5 w-5 text-emerald-600" />
            </div>
            <div>
              <p className="font-medium text-zinc-900 dark:text-zinc-100">
                Forecast a SKU
              </p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                Generate demand prediction for any product
              </p>
            </div>
          </div>
        </button>

        <button
          onClick={() => navigate('/inventory/history')}
          className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-5 hover:border-emerald-300 transition-colors text-left"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg">
              <ClockIcon className="h-5 w-5 text-emerald-600" />
            </div>
            <div>
              <p className="font-medium text-zinc-900 dark:text-zinc-100">
                View Sales History
              </p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                Analyze historical sales patterns
              </p>
            </div>
          </div>
        </button>
      </div>

      {/* Sample Size Note */}
      {summary?.sample_size && (
        <p className="text-xs text-zinc-400 text-center">
          Dashboard stats based on sample of {summary.sample_size} SKUs.
          Last updated: {new Date(summary.last_updated).toLocaleString()}
        </p>
      )}
    </div>
  );
}
