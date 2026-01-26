import React, { useState, useEffect } from 'react';

export default function MonitorSettingsPage({ authToken }) {
  const [monitoredBrands, setMonitoredBrands] = useState([]);
  const [competitors, setCompetitors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [competitorsLoading, setCompetitorsLoading] = useState(false);
  const [showAddBrandForm, setShowAddBrandForm] = useState(false);
  const [showAddCompetitorForm, setShowAddCompetitorForm] = useState(false);
  const [newBrandName, setNewBrandName] = useState('');
  const [newCompetitor, setNewCompetitor] = useState({ name: '', domain: '', collections: '' });
  const [submitting, setSubmitting] = useState(false);

  const fetchMonitoredBrands = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/price-monitor/settings/monitored-brands', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (response.ok) {
        const data = await response.json();
        setMonitoredBrands(data.brands || []);
      } else {
        alert('Failed to fetch monitored brands');
      }
    } catch (error) {
      console.error('Error fetching monitored brands:', error);
      alert('Error loading monitored brands');
    } finally {
      setLoading(false);
    }
  };

  const fetchCompetitors = async () => {
    try {
      setCompetitorsLoading(true);
      const response = await fetch('/api/price-monitor/competitors', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (response.ok) {
        const data = await response.json();
        setCompetitors(data.competitors || []);
      } else {
        alert('Failed to fetch competitors');
      }
    } catch (error) {
      console.error('Error fetching competitors:', error);
      alert('Error loading competitors');
    } finally {
      setCompetitorsLoading(false);
    }
  };

  const addBrand = async (e) => {
    e.preventDefault();
    if (!newBrandName.trim()) {
      alert('Please enter a brand name');
      return;
    }

    try {
      setSubmitting(true);
      const response = await fetch('/api/price-monitor/settings/monitored-brands', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          brand_name: newBrandName.trim(),
          is_active: true
        }),
      });

      if (response.ok) {
        alert('Brand added successfully');
        setNewBrandName('');
        setShowAddBrandForm(false);
        fetchMonitoredBrands();
      } else {
        const error = await response.json();
        alert(error.error || 'Failed to add brand');
      }
    } catch (error) {
      console.error('Error adding brand:', error);
      alert('Error adding brand');
    } finally {
      setSubmitting(false);
    }
  };

  const toggleBrand = async (brandId, currentStatus) => {
    try {
      const response = await fetch(`/api/price-monitor/settings/monitored-brands/${brandId}/toggle`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          is_active: !currentStatus
        }),
      });

      if (response.ok) {
        alert(`Brand ${!currentStatus ? 'activated' : 'deactivated'} successfully`);
        fetchMonitoredBrands();
      } else {
        alert('Failed to update brand status');
      }
    } catch (error) {
      console.error('Error toggling brand:', error);
      alert('Error updating brand status');
    }
  };

  const deleteBrand = async (brandId, brandName) => {
    if (!confirm(`Are you sure you want to delete "${brandName}"? This will remove all associated product data.`)) {
      return;
    }

    try {
      const response = await fetch(`/api/price-monitor/settings/monitored-brands/${brandId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (response.ok) {
        alert('Brand deleted successfully');
        fetchMonitoredBrands();
      } else {
        alert('Failed to delete brand');
      }
    } catch (error) {
      console.error('Error deleting brand:', error);
      alert('Error deleting brand');
    }
  };

  const addCompetitor = async (e) => {
    e.preventDefault();
    if (!newCompetitor.name.trim() || !newCompetitor.domain.trim()) {
      alert('Please enter competitor name and domain');
      return;
    }

    try {
      setSubmitting(true);
      const collections = newCompetitor.collections.split(',').map(c => c.trim()).filter(c => c);

      const response = await fetch('/api/price-monitor/competitors', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          name: newCompetitor.name.trim(),
          domain: newCompetitor.domain.trim().replace(/^https?:\/\//, '').replace(/\/$/, ''),
          collections: collections.length > 0 ? collections : ['products'],
          is_active: true
        }),
      });

      if (response.ok) {
        alert('Competitor added successfully');
        setNewCompetitor({ name: '', domain: '', collections: '' });
        setShowAddCompetitorForm(false);
        fetchCompetitors();
      } else {
        const error = await response.json();
        alert(error.error || 'Failed to add competitor');
      }
    } catch (error) {
      console.error('Error adding competitor:', error);
      alert('Error adding competitor');
    } finally {
      setSubmitting(false);
    }
  };

  const runScraping = async (competitorId, competitorName) => {
    try {
      const response = await fetch('/api/price-monitor/scraping/start-scrape', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ competitor_id: competitorId })
      });

      if (response.ok) {
        alert(`Started scraping ${competitorName}`);
      } else {
        alert('Failed to start scraping');
      }
    } catch (error) {
      console.error('Error starting scraping:', error);
      alert('Error starting scraping');
    }
  };

  const syncProducts = async () => {
    try {
      const activeBrands = monitoredBrands.filter(b => b.is_active).map(b => b.brand_name);
      if (activeBrands.length === 0) {
        alert('No active brands to sync');
        return;
      }

      const response = await fetch('/api/price-monitor/shopify-sync-safe/sync-idc-products-safe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ brands: activeBrands, force: true })
      });

      if (response.ok) {
        const result = await response.json();
        alert(`Synced products: ${result.total_products_created} created, ${result.total_products_updated} updated, ${result.manual_matches_preserved} manual matches preserved`);
      } else {
        alert('Failed to sync products');
      }
    } catch (error) {
      console.error('Error syncing products:', error);
      alert('Error syncing products');
    }
  };

  useEffect(() => {
    fetchMonitoredBrands();
    fetchCompetitors();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        <div className="ml-4 text-zinc-500 dark:text-zinc-400">Loading settings...</div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Monitor Settings</h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Configure which brands to monitor for MAP compliance from your iDC store
        </p>
      </div>

      {/* Monitored Brands Section */}
      <div className="bg-white dark:bg-zinc-900 rounded-xl ring-1 ring-zinc-200 dark:ring-zinc-800 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-medium text-zinc-900 dark:text-white">
              Monitored Brands
            </h3>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
              Select which brands to monitor for MAP compliance. Products from these brands will be synchronized from your Shopify store.
            </p>
          </div>
          <button
            onClick={() => setShowAddBrandForm(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            Add Brand
          </button>
        </div>

        {monitoredBrands.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {monitoredBrands.map((brand) => (
              <div
                key={brand.id}
                className="flex flex-col p-4 border border-zinc-200 dark:border-zinc-700 rounded-lg min-h-[120px]"
              >
                <div className="flex items-center mb-3">
                  <input
                    type="checkbox"
                    checked={brand.is_active}
                    onChange={() => toggleBrand(brand.id, brand.is_active)}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-zinc-300 dark:border-zinc-600 rounded"
                  />
                  <div className="ml-3 flex-1">
                    <label className="text-sm font-medium text-zinc-900 dark:text-white block">
                      {brand.brand_name}
                    </label>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      {brand._count?.idc_products || 0} products
                    </p>
                  </div>
                </div>
                <div className="flex items-center justify-between mt-auto">
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    brand.is_active
                      ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                      : 'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-400'
                  }`}>
                    {brand.is_active ? 'Active' : 'Inactive'}
                  </span>
                  <button
                    onClick={() => deleteBrand(brand.id, brand.brand_name)}
                    className="px-3 py-1 text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 font-medium"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-zinc-500 dark:text-zinc-400 mb-4">
              No brands configured for monitoring
            </p>
            <button
              onClick={() => setShowAddBrandForm(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
            >
              Add Your First Brand
            </button>
          </div>
        )}

        {/* Add Brand Form */}
        {showAddBrandForm && (
          <div className="mt-6 p-4 border border-zinc-200 dark:border-zinc-700 rounded-lg bg-zinc-50 dark:bg-zinc-800">
            <h4 className="text-md font-medium text-zinc-900 dark:text-white mb-3">
              Add New Brand to Monitor
            </h4>
            <form onSubmit={addBrand} className="flex gap-3">
              <input
                type="text"
                value={newBrandName}
                onChange={(e) => setNewBrandName(e.target.value)}
                placeholder="e.g., ECM, Profitec, Eureka"
                className="flex-1 px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-900 dark:text-white"
                required
              />
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {submitting ? 'Adding...' : 'Add'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowAddBrandForm(false);
                  setNewBrandName('');
                }}
                className="px-4 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg font-medium hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
              >
                Cancel
              </button>
            </form>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-2">
              Brand names should match the vendor names in your Shopify store exactly.
            </p>
          </div>
        )}
      </div>

      {/* Competitors Management */}
      <div className="bg-white dark:bg-zinc-900 rounded-xl ring-1 ring-zinc-200 dark:ring-zinc-800 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-medium text-zinc-900 dark:text-white">
              Competitor Management
            </h3>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
              Configure competitors to monitor for pricing data
            </p>
          </div>
          <button
            onClick={() => setShowAddCompetitorForm(true)}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors"
          >
            Add Competitor
          </button>
        </div>

        {competitorsLoading ? (
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-3/4"></div>
            <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-1/2"></div>
          </div>
        ) : competitors.length > 0 ? (
          <div className="space-y-4">
            {competitors.map((competitor) => (
              <div
                key={competitor.id}
                className="flex items-center justify-between p-4 border border-zinc-200 dark:border-zinc-700 rounded-lg"
              >
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-medium text-zinc-900 dark:text-white">
                        {competitor.name}
                      </h4>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">
                        {competitor.domain}
                      </p>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">
                        Collections: {competitor.collections?.join(', ') || 'None'}
                      </p>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">
                        Products: {competitor.total_products || 0} •
                        Last scraped: {competitor.last_scraped_at
                          ? new Date(competitor.last_scraped_at).toLocaleDateString()
                          : 'Never'}
                      </p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        competitor.is_active
                          ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-400'
                      }`}>
                        {competitor.is_active ? 'Active' : 'Inactive'}
                      </span>
                      <button
                        onClick={() => runScraping(competitor.id, competitor.name)}
                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
                      >
                        Scrape Now
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-zinc-500 dark:text-zinc-400 mb-4">
              No competitors configured
            </p>
            <button
              onClick={() => setShowAddCompetitorForm(true)}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors"
            >
              Add Your First Competitor
            </button>
          </div>
        )}

        {/* Add Competitor Form */}
        {showAddCompetitorForm && (
          <div className="mt-6 p-4 border border-zinc-200 dark:border-zinc-700 rounded-lg bg-zinc-50 dark:bg-zinc-800">
            <h4 className="text-md font-medium text-zinc-900 dark:text-white mb-3">
              Add New Competitor
            </h4>
            <form onSubmit={addCompetitor} className="space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <input
                  type="text"
                  value={newCompetitor.name}
                  onChange={(e) => setNewCompetitor({...newCompetitor, name: e.target.value})}
                  placeholder="Competitor name (e.g., Whole Latte Love)"
                  className="px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-900 dark:text-white"
                  required
                />
                <input
                  type="text"
                  value={newCompetitor.domain}
                  onChange={(e) => setNewCompetitor({...newCompetitor, domain: e.target.value})}
                  placeholder="Domain (e.g., wholelattelove.com)"
                  className="px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-900 dark:text-white"
                  required
                />
              </div>
              <input
                type="text"
                value={newCompetitor.collections}
                onChange={(e) => setNewCompetitor({...newCompetitor, collections: e.target.value})}
                placeholder="Collections to scrape (e.g., ecm, espresso-machines)"
                className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-900 dark:text-white"
              />
              <div className="flex gap-3">
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  {submitting ? 'Adding...' : 'Add Competitor'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowAddCompetitorForm(false);
                    setNewCompetitor({ name: '', domain: '', collections: '' });
                  }}
                  className="px-4 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg font-medium hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-2">
              Collections are paths like 'ecm' or 'espresso-machines' that exist on the competitor's website.
            </p>
          </div>
        )}
      </div>

      {/* Sync Actions */}
      <div className="bg-white dark:bg-zinc-900 rounded-xl ring-1 ring-zinc-200 dark:ring-zinc-800 p-6">
        <h3 className="text-lg font-medium text-zinc-900 dark:text-white mb-4">
          Synchronization
        </h3>
        <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
          Sync products from your Shopify store for the monitored brands.
        </p>
        <button
          onClick={syncProducts}
          className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors"
        >
          Sync Products from Shopify
        </button>
      </div>
    </div>
  );
}