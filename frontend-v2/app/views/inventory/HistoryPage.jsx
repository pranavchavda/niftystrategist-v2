import React, { useState } from 'react';
import {
  CalendarDaysIcon,
  ArrowPathIcon,
  MagnifyingGlassIcon,
  ArrowDownTrayIcon
} from '@heroicons/react/24/outline';

export default function HistoryPage({ authToken }) {
  const [sku, setSku] = useState('');
  const [days, setDays] = useState(90);
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchHistory = async (e) => {
    e?.preventDefault();
    if (!sku) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/inventory/history/${sku}?days=${days}`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (!res.ok) throw new Error('Failed to fetch sales history');

      const data = await res.json();
      setHistory(data);
    } catch (err) {
      console.error('History fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  return (
    <div className="p-6 space-y-6">
      {/* Search Form */}
      <form onSubmit={fetchHistory} className="flex flex-wrap gap-3">
        <div className="flex-1 min-w-[200px] relative">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-400" />
          <input
            type="text"
            value={sku}
            onChange={(e) => setSku(e.target.value.toUpperCase())}
            placeholder="Enter SKU (e.g., BES870XL)"
            className="w-full pl-10 pr-4 py-2.5 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
          />
        </div>

        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="px-3 py-2.5 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100"
        >
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
          <option value={180}>Last 180 days</option>
          <option value={365}>Last 365 days</option>
        </select>

        <button
          type="submit"
          disabled={loading || !sku}
          className="px-4 py-2.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {loading ? (
            <ArrowPathIcon className="h-5 w-5 animate-spin" />
          ) : (
            <CalendarDaysIcon className="h-5 w-5" />
          )}
          View History
        </button>
      </form>

      {/* Error State */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-600">
          {error}
        </div>
      )}

      {/* History Results */}
      {history && (
        <div className="space-y-6">
          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
              <p className="text-sm text-zinc-500">Total Units Sold</p>
              <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                {history.summary?.total_units || 0}
              </p>
            </div>
            <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
              <p className="text-sm text-zinc-500">Total Revenue</p>
              <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                ${(history.summary?.total_revenue || 0).toLocaleString()}
              </p>
            </div>
            <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
              <p className="text-sm text-zinc-500">Daily Average</p>
              <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                {(history.summary?.avg_daily_units || 0).toFixed(1)} units
              </p>
            </div>
            <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
              <p className="text-sm text-zinc-500">Data Points</p>
              <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                {history.data?.length || 0} days
              </p>
            </div>
          </div>

          {/* History Table */}
          <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
            <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">
                Sales History for {history.sku}
              </h3>
              <button
                onClick={() => {
                  // Export to CSV
                  const csv = [
                    ['Date', 'Units Sold', 'Revenue'],
                    ...history.data.map(d => [d.date, d.units, d.revenue])
                  ].map(row => row.join(',')).join('\n');

                  const blob = new Blob([csv], { type: 'text/csv' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `${history.sku}_sales_history.csv`;
                  a.click();
                }}
                className="flex items-center gap-2 text-sm text-emerald-600 hover:text-emerald-700"
              >
                <ArrowDownTrayIcon className="h-4 w-4" />
                Export CSV
              </button>
            </div>

            <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
              <table className="w-full">
                <thead className="bg-zinc-50 dark:bg-zinc-800 sticky top-0">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Date</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-zinc-500 uppercase">Units Sold</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-zinc-500 uppercase">Revenue</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-zinc-500 uppercase">Warehouse</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                  {history.data?.map((row, idx) => (
                    <tr key={idx} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                      <td className="px-4 py-3 text-sm text-zinc-900 dark:text-zinc-100">
                        {formatDate(row.date)}
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-medium text-zinc-900 dark:text-zinc-100">
                        {row.units}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-zinc-500">
                        ${row.revenue?.toFixed(2) || '0.00'}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-zinc-500">
                        {row.warehouse_id || 'All'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!history && !loading && !error && (
        <div className="text-center py-12">
          <CalendarDaysIcon className="h-12 w-12 text-zinc-300 mx-auto mb-4" />
          <p className="text-zinc-500 dark:text-zinc-400">
            Enter a SKU above to view historical sales data
          </p>
        </div>
      )}
    </div>
  );
}
