import React, { useState, useEffect } from 'react';
import {
  BellAlertIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline';

const SEVERITY_CONFIG = {
  critical: {
    icon: XCircleIcon,
    bg: 'bg-red-50 dark:bg-red-900/20',
    border: 'border-red-200 dark:border-red-800',
    text: 'text-red-700 dark:text-red-300',
    badge: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
  },
  high: {
    icon: ExclamationTriangleIcon,
    bg: 'bg-orange-50 dark:bg-orange-900/20',
    border: 'border-orange-200 dark:border-orange-800',
    text: 'text-orange-700 dark:text-orange-300',
    badge: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
  },
  medium: {
    icon: ExclamationTriangleIcon,
    bg: 'bg-yellow-50 dark:bg-yellow-900/20',
    border: 'border-yellow-200 dark:border-yellow-800',
    text: 'text-yellow-700 dark:text-yellow-300',
    badge: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
  },
  low: {
    icon: BellAlertIcon,
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    border: 'border-blue-200 dark:border-blue-800',
    text: 'text-blue-700 dark:text-blue-300',
    badge: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
  }
};

export default function AlertsPage({ authToken }) {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('unacknowledged'); // all, unacknowledged

  const fetchAlerts = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (filter === 'unacknowledged') {
        params.set('unacknowledged_only', 'true');
      }
      params.set('limit', '50');

      const res = await fetch(`/api/inventory/alerts?${params.toString()}`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (!res.ok) throw new Error('Failed to fetch alerts');

      const data = await res.json();
      setAlerts(data.alerts || []);
    } catch (err) {
      console.error('Alerts fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const acknowledgeAlert = async (alertId) => {
    try {
      const res = await fetch(`/api/inventory/alerts/${alertId}/acknowledge`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (!res.ok) throw new Error('Failed to acknowledge alert');

      // Refresh alerts
      fetchAlerts();
    } catch (err) {
      console.error('Acknowledge error:', err);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [filter]);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            Inventory Alerts
          </h2>
          <span className="px-2 py-0.5 text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200 rounded-full">
            {alerts.length} alerts
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Filter */}
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 text-sm"
          >
            <option value="unacknowledged">Unacknowledged</option>
            <option value="all">All Alerts</option>
          </select>

          {/* Refresh */}
          <button
            onClick={fetchAlerts}
            disabled={loading}
            className="p-2 text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
          >
            <ArrowPathIcon className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-600">
          {error}
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <ArrowPathIcon className="h-8 w-8 text-emerald-500 animate-spin" />
        </div>
      )}

      {/* Alerts List */}
      {!loading && !error && (
        <div className="space-y-4">
          {alerts.length === 0 ? (
            <div className="text-center py-12">
              <CheckCircleIcon className="h-12 w-12 text-emerald-500 mx-auto mb-4" />
              <p className="text-zinc-500 dark:text-zinc-400">
                No {filter === 'unacknowledged' ? 'unacknowledged ' : ''}alerts
              </p>
            </div>
          ) : (
            alerts.map((alert) => {
              const config = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.medium;
              const Icon = config.icon;

              return (
                <div
                  key={alert.id}
                  className={`${config.bg} ${config.border} border rounded-lg p-4`}
                >
                  <div className="flex items-start gap-4">
                    <Icon className={`h-6 w-6 ${config.text} flex-shrink-0 mt-0.5`} />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${config.badge}`}>
                          {alert.severity.toUpperCase()}
                        </span>
                        <span className="text-xs text-zinc-500">
                          {alert.alert_type.replace(/_/g, ' ')}
                        </span>
                      </div>

                      <h3 className={`font-medium ${config.text}`}>
                        {alert.title}
                      </h3>

                      <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
                        {alert.message}
                      </p>

                      {alert.recommended_action && (
                        <p className="text-sm text-zinc-500 dark:text-zinc-500 mt-2 italic">
                          Recommendation: {alert.recommended_action}
                        </p>
                      )}

                      <div className="flex items-center justify-between mt-3">
                        <div className="flex items-center gap-4 text-xs text-zinc-500">
                          <span>SKU: {alert.sku}</span>
                          {alert.warehouse_id && <span>Warehouse: {alert.warehouse_id}</span>}
                          {alert.days_until_stockout != null && (
                            <span className="font-medium text-red-600">
                              {alert.days_until_stockout} days to stockout
                            </span>
                          )}
                        </div>

                        {!alert.is_acknowledged && (
                          <button
                            onClick={() => acknowledgeAlert(alert.id)}
                            className="text-xs px-3 py-1 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded hover:bg-zinc-50 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300"
                          >
                            Acknowledge
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
