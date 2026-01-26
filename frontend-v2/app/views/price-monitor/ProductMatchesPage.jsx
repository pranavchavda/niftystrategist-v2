import React, { useState, useEffect } from 'react';
import ScrollableTable from './ScrollableTable';

export default function ProductMatchesPage({ authToken }) {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({
    page: 1,
    limit: 50,
    total: 0,
    total_pages: 0,
    has_next: false,
    has_prev: false
  });
  const [showManualMatch, setShowManualMatch] = useState(false);
  const [idcProducts, setIdcProducts] = useState([]);
  const [competitorProducts, setCompetitorProducts] = useState([]);
  const [competitors, setCompetitors] = useState([]);
  const [selectedIdc, setSelectedIdc] = useState('');
  const [selectedCompetitor, setSelectedCompetitor] = useState('');
  const [selectedCompetitorFilter, setSelectedCompetitorFilter] = useState('');
  const [idcSearchTerm, setIdcSearchTerm] = useState('');
  const [competitorSearchTerm, setCompetitorSearchTerm] = useState('');
  const [matchingLoading, setMatchingLoading] = useState(false);
  const [loadingButtons, setLoadingButtons] = useState({}); // Track loading state per button: { matchId: 'verify' | 'reject' | 'delete' }

  const fetchMatches = async (page = 1) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/price-monitor/product-matching/matches?page=${page}&limit=${pagination.limit}`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (response.ok) {
        const data = await response.json();
        setMatches(data.matches || []);
        setPagination(data.pagination || {});
      } else {
        alert('Failed to load product matches');
      }
    } catch (error) {
      console.error('Error fetching matches:', error);
      alert('Error loading matches');
    } finally {
      setLoading(false);
    }
  };

  const fetchProductsForMatching = async () => {
    try {
      const [idcResponse, compResponse, competitorsResponse] = await Promise.all([
        fetch('/api/price-monitor/shopify-sync/idc-products?limit=200', {
          headers: { 'Authorization': `Bearer ${authToken}` }
        }),
        fetch('/api/price-monitor/competitors/products?limit=500', {
          headers: { 'Authorization': `Bearer ${authToken}` }
        }),
        fetch('/api/price-monitor/competitors', {
          headers: { 'Authorization': `Bearer ${authToken}` }
        })
      ]);

      if (idcResponse.ok && compResponse.ok && competitorsResponse.ok) {
        const idcData = await idcResponse.json();
        const compData = await compResponse.json();
        const competitorsData = await competitorsResponse.json();

        setIdcProducts(idcData.products || []);
        setCompetitorProducts(compData.products || []);
        setCompetitors(competitorsData.competitors || []);
      }
    } catch (error) {
      console.error('Error fetching products:', error);
      alert('Failed to load products for matching');
    }
  };

  const createManualMatch = async () => {
    if (!selectedIdc || !selectedCompetitor) {
      alert('Please select both products to match');
      return;
    }

    try {
      setMatchingLoading(true);
      const response = await fetch('/api/price-monitor/product-matching/manual-match', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          idc_product_id: selectedIdc,
          competitor_product_id: selectedCompetitor
        })
      });

      if (response.ok) {
        alert('Manual match created successfully');
        setShowManualMatch(false);
        setSelectedIdc('');
        setSelectedCompetitor('');
        fetchMatches();
      } else {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        console.error('Manual match error:', error);
        alert(`Failed to create manual match: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error creating manual match:', error);
      alert('Error creating manual match');
    } finally {
      setMatchingLoading(false);
    }
  };

  const deleteMatch = async (matchId) => {
    if (!confirm('Are you sure you want to delete this match?')) return;

    // Set loading state
    setLoadingButtons(prev => ({ ...prev, [matchId]: 'delete' }));

    try {
      const response = await fetch(`/api/price-monitor/product-matching/matches/${encodeURIComponent(matchId)}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (response.ok) {
        // Optimistically remove the match from the list
        setMatches(prevMatches => prevMatches.filter(match => match.id !== matchId));
      } else {
        alert('Failed to delete match');
      }
    } catch (error) {
      console.error('Error deleting match:', error);
      alert('Error deleting match');
    } finally {
      // Clear loading state
      setLoadingButtons(prev => {
        const newState = { ...prev };
        delete newState[matchId];
        return newState;
      });
    }
  };

  const verifyMatch = async (matchId) => {
    // Set loading state
    setLoadingButtons(prev => ({ ...prev, [matchId]: 'verify' }));

    try {
      const response = await fetch('/api/price-monitor/product-matching/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ match_id: matchId })
      });

      if (response.ok) {
        // Optimistically update the match in the list
        setMatches(prevMatches =>
          prevMatches.map(match =>
            match.id === matchId
              ? { ...match, is_manual_match: true, confidence_level: 'high' }
              : match
          )
        );
      } else {
        const error = await response.json();
        alert(error.detail || 'Failed to verify match');
      }
    } catch (error) {
      console.error('Error verifying match:', error);
      alert('Error verifying match');
    } finally {
      // Clear loading state
      setLoadingButtons(prev => {
        const newState = { ...prev };
        delete newState[matchId];
        return newState;
      });
    }
  };

  const rejectMatch = async (matchId) => {
    if (!confirm('Unmatch this product pair? This will prevent them from being auto-matched in the future.')) return;

    // Set loading state
    setLoadingButtons(prev => ({ ...prev, [matchId]: 'reject' }));

    try {
      const response = await fetch('/api/price-monitor/product-matching/reject', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          match_id: matchId,
          reason: 'Unmatched via UI',
          rejected_by: 'User'
        })
      });

      if (response.ok) {
        // Optimistically remove the match from the list
        setMatches(prevMatches => prevMatches.filter(match => match.id !== matchId));
      } else {
        const error = await response.json();
        alert(error.detail || 'Failed to reject match');
      }
    } catch (error) {
      console.error('Error rejecting match:', error);
      alert('Error rejecting match');
    } finally {
      // Clear loading state
      setLoadingButtons(prev => {
        const newState = { ...prev };
        delete newState[matchId];
        return newState;
      });
    }
  };

  // Filter and search functions
  const filteredIdcProducts = idcProducts.filter(product =>
    product.title?.toLowerCase().includes(idcSearchTerm.toLowerCase()) ||
    product.vendor?.toLowerCase().includes(idcSearchTerm.toLowerCase()) ||
    (product.sku && product.sku.toLowerCase().includes(idcSearchTerm.toLowerCase()))
  );

  const filteredCompetitorProducts = competitorProducts.filter(product => {
    const matchesSearch = product.title?.toLowerCase().includes(competitorSearchTerm.toLowerCase()) ||
      (product.vendor && product.vendor.toLowerCase().includes(competitorSearchTerm.toLowerCase())) ||
      (product.sku && product.sku.toLowerCase().includes(competitorSearchTerm.toLowerCase()));

    const matchesCompetitor = !selectedCompetitorFilter || product.competitor_id === selectedCompetitorFilter;

    return matchesSearch && matchesCompetitor;
  });

  const getSelectedIdcProduct = () => idcProducts.find(p => p.id === selectedIdc);
  const getSelectedCompetitorProduct = () => competitorProducts.find(p => p.id === selectedCompetitor);

  const getConfidenceBadgeColor = (match) => {
    if (match.is_manual_match) return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400';
    if (match.confidence_level === 'high') return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400';
    if (match.confidence_level === 'medium') return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400';
    if (match.confidence_level === 'low') return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400';
    return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
  };

  const getTypeBadgeColor = (isManual) => {
    return isManual
      ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400'
      : 'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-400';
  };

  useEffect(() => {
    fetchMatches();
  }, []);

  return (
    <div className="p-4 md:p-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Product Matches</h1>
          <p className="mt-2 text-zinc-600 dark:text-zinc-400">
            View and manage product matches between IDC and competitors
          </p>
          {pagination.total > 0 && (
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
              Total: {pagination.total} matches
            </p>
          )}
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <select
            value={pagination.limit}
            onChange={(e) => {
              const newLimit = parseInt(e.target.value);
              setPagination(prev => ({ ...prev, limit: newLimit }));
              fetchMatches(1);
            }}
            className="px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-700 dark:text-white"
          >
            <option value={25}>25 per page</option>
            <option value={50}>50 per page</option>
            <option value={100}>100 per page</option>
          </select>

          <button
            onClick={() => {
              setShowManualMatch(true);
              fetchProductsForMatching();
            }}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors"
          >
            Create Manual Match
          </button>
          <button
            onClick={() => fetchMatches(pagination.page)}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Manual Match Modal */}
      {showManualMatch && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-zinc-900 rounded-xl w-full max-w-6xl max-h-[95vh] overflow-hidden flex flex-col ring-1 ring-zinc-200 dark:ring-zinc-800">
            {/* Header */}
            <div className="p-6 border-b border-zinc-200 dark:border-zinc-800">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Create Manual Product Match</h3>
                <button
                  onClick={() => {
                    setShowManualMatch(false);
                    setSelectedIdc('');
                    setSelectedCompetitor('');
                    setIdcSearchTerm('');
                    setCompetitorSearchTerm('');
                    setSelectedCompetitorFilter('');
                  }}
                  className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 text-2xl leading-none"
                >
                  ×
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-hidden flex">
              {/* Left Panel - IDC Products */}
              <div className="w-1/3 border-r border-zinc-200 dark:border-zinc-800 flex flex-col">
                <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
                  <h4 className="font-medium mb-2 text-zinc-900 dark:text-zinc-100">IDC Products</h4>
                  <input
                    type="text"
                    placeholder="Search IDC products..."
                    value={idcSearchTerm}
                    onChange={(e) => setIdcSearchTerm(e.target.value)}
                    className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-800 dark:text-white"
                  />
                </div>
                <div className="flex-1 overflow-y-auto p-2">
                  {filteredIdcProducts.slice(0, 50).map((product) => (
                    <div
                      key={product.id}
                      onClick={() => setSelectedIdc(product.id)}
                      className={`p-3 mb-2 rounded-lg cursor-pointer border transition-colors ${
                        selectedIdc === product.id
                          ? 'bg-blue-50 border-blue-300 dark:bg-blue-900/20 dark:border-blue-600'
                          : 'bg-zinc-50 border-zinc-200 hover:bg-zinc-100 dark:bg-zinc-800 dark:border-zinc-700 dark:hover:bg-zinc-700'
                      }`}
                    >
                      <div className="font-medium text-sm truncate text-zinc-900 dark:text-zinc-100">{product.title}</div>
                      <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                        {product.vendor} • ${product.price} • {product.sku}
                      </div>
                    </div>
                  ))}
                  {filteredIdcProducts.length > 50 && (
                    <div className="text-center text-sm text-zinc-500 p-2">
                      Showing first 50 results. Use search to narrow down.
                    </div>
                  )}
                </div>
              </div>

              {/* Middle Panel - Preview */}
              <div className="w-1/3 border-r border-zinc-200 dark:border-zinc-800 flex flex-col">
                <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
                  <h4 className="font-medium text-zinc-900 dark:text-zinc-100">Match Preview</h4>
                </div>
                <div className="flex-1 overflow-y-auto p-4">
                  {selectedIdc && selectedCompetitor ? (
                    <div className="space-y-4">
                      {/* IDC Product Preview */}
                      <div className="bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg ring-1 ring-blue-200 dark:ring-blue-800">
                        <div className="text-sm font-medium text-blue-800 dark:text-blue-300 mb-1">IDC Product</div>
                        <div className="font-medium text-zinc-900 dark:text-zinc-100">{getSelectedIdcProduct()?.title}</div>
                        <div className="text-sm text-zinc-600 dark:text-zinc-400">
                          {getSelectedIdcProduct()?.vendor} • ${getSelectedIdcProduct()?.price}
                        </div>
                      </div>

                      {/* VS Indicator */}
                      <div className="text-center text-zinc-400 text-xl">↕ VS ↕</div>

                      {/* Competitor Product Preview */}
                      <div className="bg-orange-50 dark:bg-orange-900/20 p-3 rounded-lg ring-1 ring-orange-200 dark:ring-orange-800">
                        <div className="text-sm font-medium text-orange-800 dark:text-orange-300 mb-1">
                          Competitor Product ({getSelectedCompetitorProduct()?.competitors?.name || 'Unknown'})
                        </div>
                        <div className="font-medium text-zinc-900 dark:text-zinc-100">{getSelectedCompetitorProduct()?.title}</div>
                        <div className="text-sm text-zinc-600 dark:text-zinc-400">
                          {getSelectedCompetitorProduct()?.vendor} • ${getSelectedCompetitorProduct()?.price}
                        </div>
                      </div>

                      {/* Create Match Button */}
                      <div className="pt-4">
                        <button
                          onClick={createManualMatch}
                          disabled={matchingLoading}
                          className="w-full px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                        >
                          {matchingLoading ? 'Creating Match...' : 'Create Manual Match'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center text-zinc-500 dark:text-zinc-400 py-8">
                      Select products from both sides to preview the match
                    </div>
                  )}
                </div>
              </div>

              {/* Right Panel - Competitor Products */}
              <div className="w-1/3 flex flex-col">
                <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
                  <h4 className="font-medium mb-2 text-zinc-900 dark:text-zinc-100">Competitor Products</h4>

                  {/* Competitor Filter */}
                  <select
                    value={selectedCompetitorFilter}
                    onChange={(e) => setSelectedCompetitorFilter(e.target.value)}
                    className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm mb-2 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-800 dark:text-white"
                  >
                    <option value="">All Competitors</option>
                    {competitors.map((competitor) => (
                      <option key={competitor.id} value={competitor.id}>
                        {competitor.name} ({competitor.domain})
                      </option>
                    ))}
                  </select>

                  {/* Search */}
                  <input
                    type="text"
                    placeholder="Search competitor products..."
                    value={competitorSearchTerm}
                    onChange={(e) => setCompetitorSearchTerm(e.target.value)}
                    className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-800 dark:text-white"
                  />
                </div>
                <div className="flex-1 overflow-y-auto p-2">
                  {filteredCompetitorProducts.slice(0, 50).map((product) => (
                    <div
                      key={product.id}
                      onClick={() => setSelectedCompetitor(product.id)}
                      className={`p-3 mb-2 rounded-lg cursor-pointer border transition-colors ${
                        selectedCompetitor === product.id
                          ? 'bg-orange-50 border-orange-300 dark:bg-orange-900/20 dark:border-orange-600'
                          : 'bg-zinc-50 border-zinc-200 hover:bg-zinc-100 dark:bg-zinc-800 dark:border-zinc-700 dark:hover:bg-zinc-700'
                      }`}
                    >
                      <div className="font-medium text-sm truncate text-zinc-900 dark:text-zinc-100">{product.title}</div>
                      <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                        <div>{product.competitors?.name || 'Unknown'}</div>
                        <div>{product.vendor} • ${product.price} • {product.sku}</div>
                      </div>
                    </div>
                  ))}
                  {filteredCompetitorProducts.length > 50 && (
                    <div className="text-center text-sm text-zinc-500 p-2">
                      Showing first 50 results. Use search to narrow down.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Matches Table */}
      {loading ? (
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          <div className="ml-4 text-zinc-500 dark:text-zinc-400">Loading matches...</div>
        </div>
      ) : matches.length > 0 ? (
        <div className="bg-white dark:bg-zinc-900 ring-1 ring-zinc-200 dark:ring-zinc-800 rounded-xl overflow-hidden">
          <ScrollableTable>
            <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800">
            <thead className="bg-zinc-50 dark:bg-zinc-800">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                  IDC Product
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                  Competitor Product
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                  Confidence
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800">
              {matches.map((match) => (
                <tr key={match.id}>
                  <td className="px-6 py-4 text-sm">
                    <div className="font-medium text-zinc-900 dark:text-white">
                      {match.idc_products?.title || 'Unknown Product'}
                    </div>
                    <div className="text-zinc-500 dark:text-zinc-400 text-xs">
                      {match.idc_products?.vendor} • ${match.idc_products?.price} • {match.idc_products?.sku}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <div className="font-medium text-zinc-900 dark:text-white">
                      {match.competitor_products?.title || 'Unknown Product'}
                    </div>
                    <div className="text-zinc-500 dark:text-zinc-400 text-xs">
                      <div className="font-medium text-orange-600 dark:text-orange-400">
                        {match.competitor_products?.competitors?.name || 'Unknown'}
                      </div>
                      <div>{match.competitor_products?.vendor} • ${match.competitor_products?.price}</div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${getConfidenceBadgeColor(match)}`}>
                        {match.is_manual_match ? 'manual (100.0%)' : `${match.confidence_level} (${(match.overall_score * 100).toFixed(1)}%)`}
                      </span>
                      {match.is_manual_match && (
                        <span className="text-xs">📌</span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${getTypeBadgeColor(match.is_manual_match)}`}>
                      {match.is_manual_match ? 'Manual' : 'Auto'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <div className="flex gap-2">
                      {!match.is_manual_match && (
                        <button
                          onClick={() => verifyMatch(match.id)}
                          disabled={loadingButtons[match.id] === 'verify'}
                          className="px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:bg-green-400 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5"
                          title="Verify this match as correct"
                        >
                          {loadingButtons[match.id] === 'verify' ? (
                            <>
                              <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                              </svg>
                              Verifying...
                            </>
                          ) : (
                            <>✓ Verify</>
                          )}
                        </button>
                      )}
                      <button
                        onClick={() => rejectMatch(match.id)}
                        disabled={loadingButtons[match.id] === 'reject'}
                        className="px-3 py-1.5 bg-orange-600 hover:bg-orange-700 disabled:bg-orange-400 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5"
                        title="Unmatch and prevent future auto-matching"
                      >
                        {loadingButtons[match.id] === 'reject' ? (
                          <>
                            <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Unmatching...
                          </>
                        ) : (
                          <>✗ Unmatch</>
                        )}
                      </button>
                      <button
                        onClick={() => deleteMatch(match.id)}
                        disabled={loadingButtons[match.id] === 'delete'}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-700 disabled:bg-red-400 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5"
                        title="Delete this match"
                      >
                        {loadingButtons[match.id] === 'delete' ? (
                          <>
                            <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Deleting...
                          </>
                        ) : (
                          <>Delete</>
                        )}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </ScrollableTable>

          {/* Pagination Controls */}
          {pagination.total_pages > 1 && (
            <div className="bg-white dark:bg-zinc-900 px-4 py-3 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
              <div className="flex-1 flex justify-between sm:hidden">
                <button
                  onClick={() => fetchMatches(pagination.page - 1)}
                  disabled={!pagination.has_prev}
                  className="px-4 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => fetchMatches(pagination.page + 1)}
                  disabled={!pagination.has_next}
                  className="ml-3 px-4 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  Next
                </button>
              </div>
              <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm text-zinc-700 dark:text-zinc-300">
                    Showing{' '}
                    <span className="font-medium">{(pagination.page - 1) * pagination.limit + 1}</span>
                    {' '}to{' '}
                    <span className="font-medium">
                      {Math.min(pagination.page * pagination.limit, pagination.total)}
                    </span>
                    {' '}of{' '}
                    <span className="font-medium">{pagination.total}</span>
                    {' '}results
                  </p>
                </div>
                <div>
                  <nav className="relative z-0 inline-flex rounded-lg shadow-sm -space-x-px">
                    <button
                      onClick={() => fetchMatches(pagination.page - 1)}
                      disabled={!pagination.has_prev}
                      className="relative inline-flex items-center px-2 py-2 rounded-l-lg border border-zinc-300 dark:border-zinc-600 text-sm font-medium disabled:opacity-50"
                    >
                      Previous
                    </button>

                    {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                      const pageNum = i + 1;
                      return (
                        <button
                          key={pageNum}
                          onClick={() => fetchMatches(pageNum)}
                          className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium ${
                            pagination.page === pageNum
                              ? 'bg-blue-50 border-blue-500 text-blue-600 dark:bg-blue-900/20 dark:border-blue-600'
                              : 'bg-white dark:bg-zinc-900 border-zinc-300 dark:border-zinc-600 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800'
                          }`}
                        >
                          {pageNum}
                        </button>
                      );
                    })}

                    <button
                      onClick={() => fetchMatches(pagination.page + 1)}
                      disabled={!pagination.has_next}
                      className="relative inline-flex items-center px-2 py-2 rounded-r-lg border border-zinc-300 dark:border-zinc-600 text-sm font-medium disabled:opacity-50"
                    >
                      Next
                    </button>
                  </nav>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-white dark:bg-zinc-900 ring-1 ring-zinc-200 dark:ring-zinc-800 rounded-xl p-12 text-center">
          <div className="text-zinc-500 dark:text-zinc-400">
            <h3 className="text-lg font-medium mb-2">No product matches found</h3>
            <p className="mb-4">
              Create manual matches or run automatic matching to see results here.
            </p>
            <button
              onClick={() => {
                setShowManualMatch(true);
                fetchProductsForMatching();
              }}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors"
            >
              Create Manual Match
            </button>
          </div>
        </div>
      )}
    </div>
  );
}