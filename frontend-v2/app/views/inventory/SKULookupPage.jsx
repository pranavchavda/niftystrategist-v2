import React, { useState, useEffect } from 'react';
import {
  MagnifyingGlassIcon,
  ArrowPathIcon,
  CubeIcon,
  BuildingStorefrontIcon
} from '@heroicons/react/24/outline';

export default function SKULookupPage({ authToken }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [skus, setSkus] = useState([]);
  const [inventory, setInventory] = useState(null);
  const [selectedSku, setSelectedSku] = useState(null);
  const [loading, setLoading] = useState(false);
  const [inventoryLoading, setInventoryLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch all SKUs on mount
  useEffect(() => {
    fetchSkus();
  }, []);

  const fetchSkus = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/inventory/skus', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (!res.ok) throw new Error('Failed to fetch SKUs');

      const data = await res.json();
      setSkus(data.skus || []);
    } catch (err) {
      console.error('SKU fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchInventory = async (sku) => {
    setInventoryLoading(true);
    setSelectedSku(sku);
    setInventory(null);

    try {
      const res = await fetch(`/api/inventory/inventory/${sku}`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (!res.ok) throw new Error('Failed to fetch inventory');

      const data = await res.json();
      setInventory(data);
    } catch (err) {
      console.error('Inventory fetch error:', err);
      setError(err.message);
    } finally {
      setInventoryLoading(false);
    }
  };

  // Filter SKUs based on search term
  const filteredSkus = skus.filter(sku =>
    sku.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* SKU List */}
        <div className="lg:col-span-1 bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
          <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search SKUs..."
                className="w-full pl-10 pr-4 py-2 border border-zinc-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
              />
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-zinc-500">
              <span>{filteredSkus.length} SKUs</span>
              <button
                onClick={fetchSkus}
                disabled={loading}
                className="flex items-center gap-1 hover:text-emerald-600"
              >
                <ArrowPathIcon className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
          </div>

          <div className="max-h-[600px] overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <ArrowPathIcon className="h-6 w-6 text-emerald-500 animate-spin" />
              </div>
            ) : filteredSkus.length === 0 ? (
              <div className="text-center py-8 text-zinc-500">
                {searchTerm ? 'No matching SKUs' : 'No SKUs found'}
              </div>
            ) : (
              <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {filteredSkus.slice(0, 100).map((sku) => (
                  <button
                    key={sku}
                    onClick={() => fetchInventory(sku)}
                    className={`w-full px-4 py-3 text-left hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors ${
                      selectedSku === sku ? 'bg-emerald-50 dark:bg-emerald-900/20 border-l-2 border-emerald-500' : ''
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <CubeIcon className="h-5 w-5 text-zinc-400" />
                      <span className="font-medium text-zinc-900 dark:text-zinc-100 text-sm">
                        {sku}
                      </span>
                    </div>
                  </button>
                ))}
                {filteredSkus.length > 100 && (
                  <div className="px-4 py-3 text-xs text-zinc-500 text-center">
                    Showing first 100 of {filteredSkus.length} SKUs
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Inventory Details */}
        <div className="lg:col-span-2">
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-600 mb-4">
              {error}
            </div>
          )}

          {inventoryLoading ? (
            <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-8 flex items-center justify-center">
              <ArrowPathIcon className="h-8 w-8 text-emerald-500 animate-spin" />
            </div>
          ) : inventory ? (
            <div className="space-y-4">
              {/* Header */}
              <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
                <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
                  {inventory.sku}
                </h2>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-zinc-500">Total On Hand</p>
                    <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                      {inventory.total_on_hand || 0}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-zinc-500">Total Available</p>
                    <p className="text-2xl font-semibold text-emerald-600">
                      {inventory.total_available || 0}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-zinc-500">Total Committed</p>
                    <p className="text-2xl font-semibold text-orange-600">
                      {inventory.total_committed || 0}
                    </p>
                  </div>
                </div>
              </div>

              {/* Warehouse Breakdown */}
              <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
                <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800">
                  <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">
                    Warehouse Breakdown
                  </h3>
                </div>

                {inventory.warehouses?.length > 0 ? (
                  <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
                    {inventory.warehouses.map((wh, idx) => (
                      <div key={idx} className="px-6 py-4">
                        <div className="flex items-center gap-3 mb-3">
                          <BuildingStorefrontIcon className="h-5 w-5 text-zinc-400" />
                          <span className="font-medium text-zinc-900 dark:text-zinc-100">
                            {wh.warehouse_name || wh.warehouse_id}
                          </span>
                        </div>

                        <div className="grid grid-cols-3 gap-4 ml-8">
                          <div>
                            <p className="text-xs text-zinc-500">On Hand</p>
                            <p className="text-lg font-medium text-zinc-900 dark:text-zinc-100">
                              {wh.quantity_on_hand}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-zinc-500">Available</p>
                            <p className="text-lg font-medium text-emerald-600">
                              {wh.quantity_available}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-zinc-500">Committed</p>
                            <p className="text-lg font-medium text-orange-600">
                              {wh.quantity_committed}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="px-6 py-8 text-center text-zinc-500">
                    No warehouse data available
                  </div>
                )}
              </div>

              {/* Quick Actions */}
              <div className="flex gap-3">
                <a
                  href={`/inventory/forecasts/${inventory.sku}`}
                  className="flex-1 px-4 py-3 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 text-center font-medium"
                >
                  Generate Forecast
                </a>
                <a
                  href={`/inventory/history?sku=${inventory.sku}`}
                  className="flex-1 px-4 py-3 bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-700 text-center font-medium"
                >
                  View Sales History
                </a>
              </div>
            </div>
          ) : (
            <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-12 text-center">
              <CubeIcon className="h-12 w-12 text-zinc-300 mx-auto mb-4" />
              <p className="text-zinc-500 dark:text-zinc-400">
                Select a SKU from the list to view inventory details
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
