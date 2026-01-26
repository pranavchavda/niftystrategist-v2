import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ChartBarSquareIcon,
  ArrowPathIcon,
  MagnifyingGlassIcon
} from '@heroicons/react/24/outline';

export default function ForecastsPage({ authToken }) {
  const { sku } = useParams();
  const navigate = useNavigate();
  const [searchSku, setSearchSku] = useState(sku || '');
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchForecast = async (skuToFetch) => {
    if (!skuToFetch) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/inventory/forecasts/${skuToFetch}?horizon_days=30`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (!res.ok) throw new Error('Failed to fetch forecast');

      const data = await res.json();
      setForecast(data);
    } catch (err) {
      console.error('Forecast fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchSku) {
      navigate(`/inventory/forecasts/${searchSku}`);
      fetchForecast(searchSku);
    }
  };

  // Fetch on mount if SKU provided
  React.useEffect(() => {
    if (sku) {
      fetchForecast(sku);
    }
  }, [sku]);

  return (
    <div className="p-6 space-y-6">
      {/* Search Bar */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="flex-1 relative">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-400" />
          <input
            type="text"
            value={searchSku}
            onChange={(e) => setSearchSku(e.target.value.toUpperCase())}
            placeholder="Enter SKU to forecast (e.g., BES870XL)"
            className="w-full pl-10 pr-4 py-2.5 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !searchSku}
          className="px-4 py-2.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {loading ? (
            <ArrowPathIcon className="h-5 w-5 animate-spin" />
          ) : (
            <ChartBarSquareIcon className="h-5 w-5" />
          )}
          Forecast
        </button>
      </form>

      {/* Error State */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-600">
          {error}
        </div>
      )}

      {/* Forecast Results */}
      {forecast && (
        <div className="space-y-6">
          {/* Summary Card */}
          <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
              Forecast for {forecast.sku}
            </h2>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-zinc-500">Current Inventory</p>
                <p className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                  {forecast.current_inventory} units
                </p>
              </div>
              <div>
                <p className="text-sm text-zinc-500">Days Until Stockout</p>
                <p className={`text-xl font-semibold ${
                  forecast.days_until_stockout <= 7 ? 'text-red-600' :
                  forecast.days_until_stockout <= 14 ? 'text-orange-600' :
                  forecast.days_until_stockout ? 'text-yellow-600' : 'text-emerald-600'
                }`}>
                  {forecast.days_until_stockout ?? 'None in forecast period'}
                </p>
              </div>
              <div>
                <p className="text-sm text-zinc-500">Model Accuracy (MAPE)</p>
                <p className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                  {forecast.mape ? `${forecast.mape}%` : 'N/A'}
                </p>
              </div>
              <div>
                <p className="text-sm text-zinc-500">Forecast Horizon</p>
                <p className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                  {forecast.forecast_horizon_days} days
                </p>
              </div>
            </div>

            {forecast.reorder_recommendation && (
              <div className="mt-4 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                  {forecast.reorder_recommendation}
                </p>
              </div>
            )}
          </div>

          {/* Forecast Table */}
          <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
            <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800">
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">Daily Forecast</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-zinc-50 dark:bg-zinc-800">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Date</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-zinc-500 uppercase">Predicted</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-zinc-500 uppercase">Low</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-zinc-500 uppercase">High</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-zinc-500 uppercase">Trend</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                  {forecast.forecasts?.slice(0, 14).map((day, idx) => (
                    <tr key={idx} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                      <td className="px-4 py-3 text-sm text-zinc-900 dark:text-zinc-100">
                        {new Date(day.forecast_date).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-medium text-zinc-900 dark:text-zinc-100">
                        {day.predicted_units}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-zinc-500">
                        {day.confidence_low}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-zinc-500">
                        {day.confidence_high}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-zinc-500">
                        {day.trend_component > 0 ? '+' : ''}{day.trend_component}
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
      {!forecast && !loading && !error && (
        <div className="text-center py-12">
          <ChartBarSquareIcon className="h-12 w-12 text-zinc-300 mx-auto mb-4" />
          <p className="text-zinc-500 dark:text-zinc-400">
            Enter a SKU above to generate a demand forecast
          </p>
        </div>
      )}
    </div>
  );
}
