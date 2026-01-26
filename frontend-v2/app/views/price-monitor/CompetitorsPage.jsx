import React, { useState, useEffect } from 'react';
import { PlusIcon, PencilIcon, TrashIcon } from '@heroicons/react/20/solid';

export default function CompetitorsPage() {
  const [competitors, setCompetitors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingCompetitor, setEditingCompetitor] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    domain: '',
    collections: '',
    scraping_strategy: 'collections',
    url_patterns: '',
    search_terms: '',
    exclude_patterns: ''
  });
  const [submitting, setSubmitting] = useState(false);
  const [scrapingCompetitors, setScrapingCompetitors] = useState(new Set());

  const authToken = localStorage.getItem('auth_token');

  const fetchCompetitors = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/price-monitor/competitors', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (response.ok) {
        const data = await response.json();
        setCompetitors(data.competitors || []);
      }
    } catch (error) {
      console.error('Error fetching competitors:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name || !formData.domain) {
      alert('Please fill in all required fields');
      return;
    }

    try {
      setSubmitting(true);
      const isEditing = editingCompetitor !== null;
      const url = isEditing
        ? `/api/price-monitor/competitors/${editingCompetitor.id}`
        : '/api/price-monitor/competitors';
      const method = isEditing ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          name: formData.name,
          domain: formData.domain,
          collections: formData.collections.split(',').map(c => c.trim()).filter(c => c),
          scraping_strategy: formData.scraping_strategy,
          url_patterns: formData.url_patterns.split('\n').map(p => p.trim()).filter(p => p),
          search_terms: formData.search_terms.split(',').map(t => t.trim()).filter(t => t),
          exclude_patterns: formData.exclude_patterns.split('\n').map(p => p.trim()).filter(p => p),
          is_active: true
        }),
      });

      if (response.ok) {
        alert(isEditing ? 'Competitor updated successfully' : 'Competitor added successfully');
        setShowDialog(false);
        setEditingCompetitor(null);
        setFormData({ name: '', domain: '', collections: '', scraping_strategy: 'collections', url_patterns: '', search_terms: '', exclude_patterns: '' });
        fetchCompetitors();
      } else {
        alert(`Failed to ${isEditing ? 'update' : 'add'} competitor`);
      }
    } catch (error) {
      console.error('Error saving competitor:', error);
      alert(`Error ${editingCompetitor ? 'updating' : 'adding'} competitor`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (competitor) => {
    setEditingCompetitor(competitor);
    setFormData({
      name: competitor.name,
      domain: competitor.domain,
      collections: competitor.collections ? competitor.collections.join(', ') : '',
      scraping_strategy: competitor.scraping_strategy || 'collections',
      url_patterns: competitor.url_patterns ? competitor.url_patterns.join('\n') : '',
      search_terms: competitor.search_terms ? competitor.search_terms.join(', ') : '',
      exclude_patterns: competitor.exclude_patterns ? competitor.exclude_patterns.join('\n') : ''
    });
    setShowDialog(true);
  };

  const handleDelete = async (competitorId) => {
    if (!confirm('Are you sure you want to delete this competitor?')) return;

    try {
      const response = await fetch(`/api/price-monitor/competitors/${competitorId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (response.ok) {
        alert('Competitor deleted successfully');
        fetchCompetitors();
      }
    } catch (error) {
      console.error('Error deleting competitor:', error);
    }
  };

  const handleScrape = async (competitorId, competitorName) => {
    if (scrapingCompetitors.has(competitorId)) return;

    try {
      setScrapingCompetitors(prev => new Set(prev).add(competitorId));

      const response = await fetch(`/api/price-monitor/scraping/start-scrape`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ competitor_id: competitorId }),
      });

      if (response.ok) {
        const data = await response.json();
        alert(`Started scraping ${competitorName}. Job ID: ${data.job_id}`);
      } else {
        alert(`Failed to start scraping ${competitorName}`);
      }
    } catch (error) {
      console.error('Error starting scrape:', error);
    } finally {
      setTimeout(() => {
        setScrapingCompetitors(prev => {
          const next = new Set(prev);
          next.delete(competitorId);
          return next;
        });
      }, 2000);
    }
  };

  useEffect(() => {
    fetchCompetitors();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        <div className="ml-4 text-zinc-500">Loading competitors...</div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Competitors</h1>
          <p className="mt-1 text-zinc-600 dark:text-zinc-400">
            Manage competitor sites for price monitoring
          </p>
        </div>
        <button
          onClick={() => { setEditingCompetitor(null); setFormData({ name: '', domain: '', collections: '', scraping_strategy: 'collections', url_patterns: '', search_terms: '', exclude_patterns: '' }); setShowDialog(true); }}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-colors"
        >
          <PlusIcon className="w-5 h-5" />
          Add Competitor
        </button>
      </div>

      {competitors.length > 0 ? (
        <div className="bg-white dark:bg-zinc-900 rounded-xl ring-1 ring-zinc-200 dark:ring-zinc-800 overflow-hidden">
          <div className="overflow-x-auto" style={{ WebkitOverflowScrolling: 'touch', touchAction: 'pan-x pan-y' }}>
            <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800">
              <thead className="bg-zinc-50 dark:bg-zinc-800/50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Domain</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Strategy</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Last Scraped</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Products</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800">
                {competitors.map((competitor) => (
                  <tr key={competitor.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {competitor.name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-zinc-500 dark:text-zinc-400">
                      {competitor.domain}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className="px-2 py-1 text-xs font-medium rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
                        {competitor.scraping_strategy || 'collections'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${competitor.is_active ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-400'}`}>
                        {competitor.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-zinc-500 dark:text-zinc-400">
                      {competitor.last_scraped_at ? new Date(competitor.last_scraped_at).toLocaleString() : 'Never'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-zinc-500 dark:text-zinc-400">
                      {competitor.total_products || 0}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <div className="flex items-center gap-2">
                        <button onClick={() => handleEdit(competitor)} className="text-indigo-600 hover:text-indigo-900 dark:hover:text-indigo-400">
                          <PencilIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleScrape(competitor.id, competitor.name)}
                          disabled={scrapingCompetitors.has(competitor.id) || !competitor.is_active}
                          className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs rounded disabled:opacity-50"
                        >
                          {scrapingCompetitors.has(competitor.id) ? 'Scraping...' : 'Scrape'}
                        </button>
                        <button onClick={() => handleDelete(competitor.id)} className="text-red-600 hover:text-red-900 dark:hover:text-red-400">
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-white dark:bg-zinc-900 rounded-xl ring-1 ring-zinc-200 dark:ring-zinc-800 p-12 text-center">
          <h3 className="text-lg font-medium text-zinc-900 dark:text-zinc-100 mb-2">No competitors configured</h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">Add competitor sites to start monitoring their prices against your MAP policies.</p>
          <button
            onClick={() => setShowDialog(true)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-colors"
          >
            Add Your First Competitor
          </button>
        </div>
      )}

      {/* Add/Edit Dialog */}
      {showDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={() => setShowDialog(false)}>
          <div className="bg-white dark:bg-zinc-900 rounded-xl ring-1 ring-zinc-200 dark:ring-zinc-800 max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="p-6">
              <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">
                {editingCompetitor ? 'Edit Competitor' : 'Add Competitor'}
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Name *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-md bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                    placeholder="e.g., Home Coffee Solutions"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Domain *</label>
                  <input
                    type="text"
                    value={formData.domain}
                    onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                    className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-md bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                    placeholder="e.g., homecoffeesolutions.com"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Scraping Strategy</label>
                  <select
                    value={formData.scraping_strategy}
                    onChange={(e) => setFormData({ ...formData, scraping_strategy: e.target.value })}
                    className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-md bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                  >
                    <option value="collections">Collection-based (e.g., /collections/ecm)</option>
                    <option value="url_patterns">URL Pattern Matching</option>
                    <option value="search_terms">Search Term Based</option>
                  </select>
                </div>

                {formData.scraping_strategy === 'collections' && (
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Collections to Monitor</label>
                    <input
                      type="text"
                      value={formData.collections}
                      onChange={(e) => setFormData({ ...formData, collections: e.target.value })}
                      className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-md bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                      placeholder="e.g., ecm,profitec,eureka (comma-separated)"
                    />
                    <p className="text-xs text-zinc-500 mt-1">Collection names from URLs like /collections/ecm</p>
                  </div>
                )}

                {formData.scraping_strategy === 'url_patterns' && (
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">URL Patterns to Scrape</label>
                    <textarea
                      value={formData.url_patterns}
                      onChange={(e) => setFormData({ ...formData, url_patterns: e.target.value })}
                      className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-md bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                      rows="3"
                      placeholder="/products/ecm-*&#10;/espresso-machines/*&#10;/grinders/eureka-*"
                    />
                    <p className="text-xs text-zinc-500 mt-1">One pattern per line. Use * for wildcards.</p>
                  </div>
                )}

                {formData.scraping_strategy === 'search_terms' && (
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Search Terms</label>
                    <input
                      type="text"
                      value={formData.search_terms}
                      onChange={(e) => setFormData({ ...formData, search_terms: e.target.value })}
                      className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-md bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                      placeholder="ECM,Profitec,Eureka,espresso machine,grinder"
                    />
                    <p className="text-xs text-zinc-500 mt-1">Brand names and product categories (comma-separated)</p>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">Exclude Patterns (Optional)</label>
                  <textarea
                    value={formData.exclude_patterns}
                    onChange={(e) => setFormData({ ...formData, exclude_patterns: e.target.value })}
                    className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-md bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                    rows="2"
                    placeholder="/products/sale-*&#10;*clearance*&#10;*discontinued*"
                  />
                  <p className="text-xs text-zinc-500 mt-1">URL patterns to exclude (one per line)</p>
                </div>

                <div className="flex justify-end gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowDialog(false)}
                    className="px-4 py-2 border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300 rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-800"
                    disabled={submitting}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg disabled:opacity-50"
                    disabled={submitting}
                  >
                    {submitting ? 'Saving...' : editingCompetitor ? 'Update Competitor' : 'Add Competitor'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}