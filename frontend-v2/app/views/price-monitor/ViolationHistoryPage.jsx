import React, { useState, useEffect } from 'react';

export default function ViolationHistoryPage({ authToken }) {
  const [violations, setViolations] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    brand: '',
    competitor: '',
    startDate: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    endDate: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    groupBy: 'day'
  });

  const fetchStatistics = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        start_date: filters.startDate,
        end_date: filters.endDate,
        group_by: filters.groupBy
      });

      if (filters.brand) params.append('brand', filters.brand);
      if (filters.competitor) params.append('competitor', filters.competitor);

      const response = await fetch(`/api/price-monitor/violation-history/statistics?${params}`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (response.ok) {
        const data = await response.json();
        setStatistics(data);
        setLoading(false);

        fetchRecentViolations();
      } else {
        console.error('Statistics response:', await response.text());
        alert('Failed to fetch violation statistics');
        setLoading(false);
      }
    } catch (error) {
      console.error('Error fetching statistics:', error);
      alert('Error loading violation statistics');
      setLoading(false);
    }
  };

  const fetchRecentViolations = async () => {
    try {
      const response = await fetch(`/api/price-monitor/map-violations/violations?limit=50&resolved=true`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (response.ok) {
        const data = await response.json();
        setViolations(data.violations || []);
      }
    } catch (error) {
      console.error('Error fetching violations:', error);
    } finally {
      setLoading(false);
    }
  };

  const exportData = async (format = 'csv') => {
    try {
      const params = new URLSearchParams({
        format,
        start_date: filters.startDate,
        end_date: filters.endDate
      });

      if (filters.brand) params.append('brand', filters.brand);
      if (filters.competitor) params.append('competitor', filters.competitor);

      const response = await fetch(`/api/price-monitor/violation-history/export?${params}`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `violation-history-${filters.startDate}-to-${filters.endDate}.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        alert(`Exported violation history as ${format.toUpperCase()}`);
      } else {
        alert('Failed to export data');
      }
    } catch (error) {
      console.error('Error exporting data:', error);
      alert('Error exporting violation history');
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const getTypeBadgeColor = (type) => {
    if (type.includes('severe')) return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
    if (type.includes('moderate')) return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400';
    return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400';
  };

  useEffect(() => {
    fetchStatistics();
  }, [filters]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        <div className="ml-4 text-zinc-500 dark:text-zinc-400">Loading violation history...</div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6">
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Violation History</h1>
          <p className="mt-2 text-zinc-600 dark:text-zinc-400">
            Track MAP violation trends and export historical data
          </p>
        </div>

        <button
          onClick={() => exportData('csv')}
          className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <svg className="h-5 w-5 text-zinc-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          <h3 className="font-medium text-zinc-900 dark:text-zinc-100">Filters</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1 text-zinc-700 dark:text-zinc-300">Start Date</label>
            <input
              type="date"
              value={filters.startDate}
              onChange={(e) => handleFilterChange('startDate', e.target.value)}
              className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-zinc-800 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1 text-zinc-700 dark:text-zinc-300">End Date</label>
            <input
              type="date"
              value={filters.endDate}
              onChange={(e) => handleFilterChange('endDate', e.target.value)}
              className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-zinc-800 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1 text-zinc-700 dark:text-zinc-300">Brand</label>
            <select
              value={filters.brand}
              onChange={(e) => handleFilterChange('brand', e.target.value)}
              className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-zinc-800 dark:text-white"
            >
              <option value="">All Brands</option>
              <option value="Profitec">Profitec</option>
              <option value="Eureka">Eureka</option>
              <option value="ECM">ECM</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1 text-zinc-700 dark:text-zinc-300">Competitor</label>
            <select
              value={filters.competitor}
              onChange={(e) => handleFilterChange('competitor', e.target.value)}
              className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-zinc-800 dark:text-white"
            >
              <option value="">All Competitors</option>
              <option value="The Kitchen Barista">The Kitchen Barista</option>
              <option value="HomeCoffeeSolutions.com">HomeCoffeeSolutions.com</option>
              <option value="Cafe Liegeois">Cafe Liegeois</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1 text-zinc-700 dark:text-zinc-300">Group By</label>
            <select
              value={filters.groupBy}
              onChange={(e) => handleFilterChange('groupBy', e.target.value)}
              className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-zinc-800 dark:text-white"
            >
              <option value="day">Daily</option>
              <option value="week">Weekly</option>
              <option value="month">Monthly</option>
            </select>
          </div>
        </div>
      </div>

      {/* Summary Statistics */}
      {statistics?.summary && (
        <div className="grid grid-cols-1 md:grid-cols-6 gap-4 mb-6">
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-zinc-900 dark:text-white">
              {statistics.summary.total_violations}
            </div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Total Violations</div>
          </div>

          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-blue-600">
              {statistics.summary.active_violations}
            </div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Currently Active</div>
          </div>

          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-orange-600">
              {statistics.summary.average_violation_percent?.toFixed(1)}%
            </div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Avg Violation</div>
          </div>

          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-red-600">
              {statistics.summary.max_violation_percent?.toFixed(1)}%
            </div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Max Violation</div>
          </div>

          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-green-600">
              ${statistics.summary.average_violation_amount?.toFixed(2)}
            </div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Avg $ Impact</div>
          </div>

          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-purple-600">
              ${statistics.summary.max_violation_amount?.toFixed(2)}
            </div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Max $ Impact</div>
          </div>
        </div>
      )}

      {/* No Data Message */}
      {statistics && (!statistics.time_series || statistics.time_series.length === 0) && (
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-12 text-center mb-6">
          <div className="text-zinc-500 dark:text-zinc-400">
            <h3 className="text-lg font-medium mb-2">No Violation History Found</h3>
            <p className="mb-4">
              No MAP violations have been recorded for the selected time period.
            </p>
            <p className="text-sm">
              Violations will appear here after running a violation scan. You can trigger a scan from the Price Alerts page or wait for the automated cron job to run.
            </p>
          </div>
        </div>
      )}

      {/* Time Series Chart */}
      {statistics?.time_series && statistics.time_series.length > 0 && (
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <svg className="h-5 w-5 text-zinc-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <h3 className="font-medium text-zinc-900 dark:text-zinc-100">Violation Trends</h3>
          </div>

          <div className="overflow-x-auto" style={{ WebkitOverflowScrolling: 'touch', touchAction: 'pan-x pan-y' }}>
            <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800">
              <thead className="bg-zinc-50 dark:bg-zinc-800">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                    Period
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                    Violations
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                    Avg %
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                    Total Impact
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                    Unique Products
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800">
                {statistics.time_series.slice(0, 10).map((period, idx) => (
                  <tr key={idx}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-zinc-900 dark:text-white">
                      {new Date(period.period).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-zinc-900 dark:text-white">
                      {period.violation_count}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-zinc-900 dark:text-white">
                      {parseFloat(period.avg_violation_pct).toFixed(1)}%
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-zinc-900 dark:text-white">
                      ${parseFloat(period.total_impact).toFixed(2)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-zinc-900 dark:text-white">
                      {period.unique_products}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Violations by Type */}
      {statistics?.by_type && statistics.by_type.length > 0 && (
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6">
          <h3 className="font-medium mb-4 text-zinc-900 dark:text-zinc-100">Violations by Type</h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {statistics.by_type.map((type) => (
              <div key={type.violation_type} className="border border-zinc-200 dark:border-zinc-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-zinc-900 dark:text-zinc-100">
                    {type.violation_type.replace('map_violation_', '').toUpperCase()}
                  </span>
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${getTypeBadgeColor(type.violation_type)}`}>
                    {type._count.id} violations
                  </span>
                </div>
                <div className="text-sm text-zinc-600 dark:text-zinc-400">
                  <div>Avg: {type._avg.violation_percent?.toFixed(1)}%</div>
                  <div>Total: ${type._sum.violation_amount?.toFixed(2)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}