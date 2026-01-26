import React, { useState, useEffect } from 'react';
import ScrollableTable from './ScrollableTable';

export default function PriceAlertsPage({ authToken }) {
  const [violations, setViolations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('active');
  const [summary, setSummary] = useState(null);
  const [minSimilarity, setMinSimilarity] = useState(0);
  const [sortBy, setSortBy] = useState('similarity');
  const [loadingButtons, setLoadingButtons] = useState({}); // Track loading state per button

  const fetchViolations = async () => {
    try {
      setLoading(true);
      const resolved = filter === 'resolved' ? 'true' : 'false';
      const response = await fetch(`/api/price-monitor/map-violations/violations?resolved=${resolved}&limit=100`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (response.ok) {
        const data = await response.json();
        setViolations(data.violations || []);
        setSummary(data.summary || null);
      } else {
        alert('Failed to fetch violations');
      }
    } catch (error) {
      console.error('Error fetching violations:', error);
      alert('Error loading violations');
    } finally {
      setLoading(false);
    }
  };

  const resolveViolation = async (violationId) => {
    try {
      const response = await fetch(`/api/price-monitor/map-violations/violations/resolve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ violation_id: violationId, resolved_by: 'User' })
      });

      if (response.ok) {
        alert('Violation resolved successfully');
        fetchViolations();
      } else {
        alert('Failed to resolve violation');
      }
    } catch (error) {
      console.error('Error resolving violation:', error);
      alert('Error resolving violation');
    }
  };

  const verifyMatch = async (matchId, violationId) => {
    if (!matchId) {
      alert('No product match associated with this violation');
      return;
    }

    // Set loading state
    setLoadingButtons(prev => ({ ...prev, [`${violationId}_verify`]: true }));

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
        // Optimistically update the violation to hide verify button
        setViolations(prevViolations =>
          prevViolations.map(v =>
            v.id === violationId && v.product_matches
              ? { ...v, product_matches: { ...v.product_matches, is_manual_match: true } }
              : v
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
        delete newState[`${violationId}_verify`];
        return newState;
      });
    }
  };

  const rejectMatch = async (matchId, violationId) => {
    if (!matchId) {
      alert('No product match associated with this violation');
      return;
    }

    if (!confirm('Unmatch this product pair? This will prevent them from being auto-matched in the future and remove this violation.')) return;

    // Set loading state
    setLoadingButtons(prev => ({ ...prev, [`${violationId}_reject`]: true }));

    try {
      const response = await fetch('/api/price-monitor/product-matching/reject', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          match_id: matchId,
          reason: 'Unmatched via Price Alerts',
          rejected_by: 'User'
        })
      });

      if (response.ok) {
        // Optimistically remove the violation from the list
        setViolations(prevViolations => prevViolations.filter(v => v.id !== violationId));
      } else {
        const error = await response.json();
        alert(error.detail || 'Failed to unmatch');
      }
    } catch (error) {
      console.error('Error unmatching:', error);
      alert('Error unmatching');
    } finally {
      // Clear loading state
      setLoadingButtons(prev => {
        const newState = { ...prev };
        delete newState[`${violationId}_reject`];
        return newState;
      });
    }
  };

  // Filter and sort violations
  const processedViolations = violations
    .filter(violation => {
      const matchScore = violation.product_matches?.is_manual_match ? 1.0 : (violation.product_matches?.overall_score || 0);
      const similarityPercent = matchScore * 100;
      return similarityPercent >= minSimilarity;
    })
    .sort((a, b) => {
      const isManualA = a.product_match?.is_manual_match || false;
      const isManualB = b.product_match?.is_manual_match || false;

      if (isManualA && !isManualB) return -1;
      if (!isManualA && isManualB) return 1;

      if (sortBy === 'similarity') {
        const scoreA = isManualA ? 1.0 : (a.product_match?.overall_score || 0);
        const scoreB = isManualB ? 1.0 : (b.product_match?.overall_score || 0);
        return scoreB - scoreA;
      } else {
        const severityOrder = { severe: 3, moderate: 2, minor: 1 };
        const severityA = severityOrder[a.severity] || 0;
        const severityB = severityOrder[b.severity] || 0;
        return severityB - severityA;
      }
    });

  // Calculate filtered revenue impact
  const filteredRevenueImpact = processedViolations.reduce((total, violation) => {
    return total + Math.abs(parseFloat(violation.price_change || 0));
  }, 0);

  const getSeverityBadgeColor = (severity) => {
    if (severity === 'severe') return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
    if (severity === 'moderate') return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400';
    if (severity === 'minor') return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400';
    return 'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-400';
  };

  const getSimilarityBadgeColor = (violation) => {
    if (violation.product_matches?.is_manual_match) return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400';
    const score = violation.product_matches?.overall_score || 0;
    if (score >= 0.8) return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400';
    if (score >= 0.7) return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400';
    if (score >= 0.6) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400';
    return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
  };

  useEffect(() => {
    fetchViolations();
  }, [filter]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        <div className="ml-4 text-zinc-500 dark:text-zinc-400">Loading violations...</div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6">
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Price Alerts</h1>
          <p className="mt-2 text-zinc-600 dark:text-zinc-400">
            Monitor and manage price change alerts and MAP violations
          </p>
        </div>

        {/* Controls */}
        <div className="flex flex-col sm:flex-row gap-3 w-full lg:w-auto">
          {/* Status Filter */}
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-700 dark:text-white"
          >
            <option value="active">Active Violations</option>
            <option value="resolved">Resolved Violations</option>
          </select>

          {/* Sort By */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-700 dark:text-white"
          >
            <option value="similarity">Sort by Similarity</option>
            <option value="severity">Sort by Severity</option>
          </select>

          {/* Similarity Filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-zinc-600 dark:text-zinc-400 whitespace-nowrap">Min Similarity:</span>
            <select
              value={minSimilarity}
              onChange={(e) => setMinSimilarity(parseInt(e.target.value))}
              className="px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-700 dark:text-white"
            >
              <option value={0}>All (0%+)</option>
              <option value={50}>50%+</option>
              <option value={60}>60%+</option>
              <option value={70}>70%+</option>
              <option value={80}>80%+</option>
              <option value={90}>90%+</option>
            </select>
          </div>

          <button
            onClick={fetchViolations}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Summary Statistics */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-6 gap-4 mb-6">
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-zinc-900 dark:text-white">{processedViolations.length}</div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Shown ({violations.length} total)</div>
          </div>
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-blue-600">
              {processedViolations.length > 0
                ? ((processedViolations.reduce((sum, v) => sum + (v.product_match?.is_manual_match ? 1.0 : (v.product_match?.overall_score || 0)), 0) / processedViolations.length) * 100).toFixed(1) + '%'
                : '0%'
              }
            </div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Avg Similarity</div>
          </div>
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-red-600">{processedViolations.filter(v => v.severity === 'severe').length}</div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Severe</div>
          </div>
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-orange-600">{processedViolations.filter(v => v.severity === 'moderate').length}</div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Moderate</div>
          </div>
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-yellow-600">{processedViolations.filter(v => v.severity === 'minor').length}</div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Minor</div>
          </div>
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4">
            <div className="text-2xl font-bold text-green-600">${filteredRevenueImpact.toFixed(2)}</div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Revenue Impact</div>
          </div>
        </div>
      )}

      {processedViolations.length > 0 ? (
        <div className="bg-white dark:bg-zinc-900 ring-1 ring-zinc-200 dark:ring-zinc-800 rounded-xl overflow-hidden">
          <ScrollableTable>
            <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800">
              <thead className="bg-zinc-50 dark:bg-zinc-800">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                    Product
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                    Competitor
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                    Similarity
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                    Severity
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                    Price Violation
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                    Detected
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800">
                {processedViolations.map((violation) => (
                  <tr key={violation.id}>
                    <td className="px-6 py-4 text-sm">
                      <div className="font-medium text-zinc-900 dark:text-white">
                        {violation.product_matches?.idc_products?.handle ? (
                          <a
                            href={`https://idrinkcoffee.com/products/${violation.product_matches.idc_products.handle}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 hover:underline"
                          >
                            {violation.product_matches.idc_products.title || 'Unknown Product'}
                          </a>
                        ) : (
                          violation.product_matches?.idc_products?.title || 'Unknown Product'
                        )}
                      </div>
                      <div className="text-zinc-500 dark:text-zinc-400 text-xs">
                        {violation.product_matches?.idc_products?.vendor} • SKU: {violation.product_matches?.idc_products?.sku}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <div className="font-medium text-zinc-900 dark:text-white">
                        {violation.product_matches?.competitor_products?.product_url ? (
                          <a
                            href={violation.product_matches.competitor_products.product_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 hover:underline"
                          >
                            {violation.product_matches.competitor_products.title || 'Unknown Product'}
                          </a>
                        ) : (
                          violation.product_matches?.competitor_products?.title || 'Unknown Product'
                        )}
                      </div>
                      <div className="text-zinc-500 dark:text-zinc-400 text-xs">
                        {violation.product_matches?.competitor_products?.competitors?.name || 'Unknown'} • ${parseFloat(violation.product_matches?.competitor_products?.price || 0).toFixed(2)}
                      </div>
                      <div className="text-zinc-500 dark:text-zinc-400 text-xs">
                        {violation.product_matches?.competitor_products?.competitors?.domain}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${getSimilarityBadgeColor(violation)}`}>
                          {violation.product_matches?.is_manual_match ? '100.0%' : ((violation.product_matches?.overall_score || 0) * 100).toFixed(1) + '%'}
                        </span>
                        {violation.product_matches?.is_manual_match && (
                          <span className="text-xs text-blue-600 dark:text-blue-400 font-medium">📌 Manual</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${getSeverityBadgeColor(violation.severity)}`}>
                        {violation.severity}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <div>
                        <span className="text-zinc-500 dark:text-zinc-400">MAP: ${parseFloat(violation.old_price || 0).toFixed(2)}</span>
                        {' → '}
                        <span className="text-red-600 font-medium">
                          ${parseFloat(violation.new_price || 0).toFixed(2)}
                        </span>
                      </div>
                      <div className="text-xs text-red-600">
                        -{((parseFloat(violation.old_price || 0) - parseFloat(violation.new_price || 0)) / parseFloat(violation.old_price || 1) * 100).toFixed(1)}% (${parseFloat(violation.price_change || 0).toFixed(2)})
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-zinc-500 dark:text-zinc-400">
                      {violation.created_at ? new Date(violation.created_at).toLocaleString() : 'Unknown'}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex gap-2">
                        {violation.product_match_id && !violation.product_matches?.is_manual_match && (
                          <button
                            onClick={() => verifyMatch(violation.product_match_id, violation.id)}
                            disabled={loadingButtons[`${violation.id}_verify`]}
                            className="px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:bg-green-400 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5"
                            title="Verify the product match"
                          >
                            {loadingButtons[`${violation.id}_verify`] ? (
                              <>
                                <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                Verifying...
                              </>
                            ) : (
                              <>✓ Verify Match</>
                            )}
                          </button>
                        )}
                        {violation.product_match_id && (
                          <button
                            onClick={() => rejectMatch(violation.product_match_id, violation.id)}
                            disabled={loadingButtons[`${violation.id}_reject`]}
                            className="px-3 py-1.5 bg-orange-600 hover:bg-orange-700 disabled:bg-orange-400 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5"
                            title="Unmatch and prevent future auto-matching"
                          >
                            {loadingButtons[`${violation.id}_reject`] ? (
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
                        )}
                        <button
                          onClick={() => resolveViolation(violation.id)}
                          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
                          title="Mark violation as resolved"
                        >
                          Resolve
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTable>
        </div>
      ) : (
        <div className="bg-white dark:bg-zinc-900 ring-1 ring-zinc-200 dark:ring-zinc-800 rounded-xl p-12 text-center">
          <div className="text-zinc-500 dark:text-zinc-400">
            <h3 className="text-lg font-medium mb-2">
              {filter === 'active' ? 'No active violations found' : 'No resolved violations found'}
            </h3>
            <p className="mb-4">
              {filter === 'active'
                ? 'MAP violations will appear here when competitors price below your minimum advertised price.'
                : 'Resolved violations will appear here once you mark active violations as resolved.'
              }
            </p>
            <button
              onClick={fetchViolations}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {loading ? 'Loading...' : 'Refresh'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}