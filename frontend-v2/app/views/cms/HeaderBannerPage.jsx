import React, { useState, useEffect } from 'react';
import { Loader2, AlertCircle, PencilIcon } from 'lucide-react';
import TextLinkEditor from '../../components/cms/TextLinkEditor';
import ResponsiveBreadcrumb from '../../components/Breadcrumb';

/**
 * HeaderBannerPage Component
 * CMS page for managing header top banner links (CA + US markets)
 */
export default function HeaderBannerPage({ authToken }) {
  const [headerBanner, setHeaderBanner] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingLink, setEditingLink] = useState(null);
  const [editingPosition, setEditingPosition] = useState(null);
  const [showEditor, setShowEditor] = useState(false);
  const [selectedMarket, setSelectedMarket] = useState('ca'); // 'ca' or 'us'

  useEffect(() => {
    loadHeaderBanner();
  }, [authToken]);

  const loadHeaderBanner = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch('/api/cms/header-banner', {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to load header banner');
      }

      const data = await response.json();
      setHeaderBanner(data);
    } catch (err) {
      setError(err.message || 'Failed to load header banner');
    } finally {
      setLoading(false);
    }
  };

  const handleEditLink = (link, position) => {
    setEditingLink(link);
    setEditingPosition(position);
    setShowEditor(true);
  };

  const handleSaveLink = () => {
    // Reload header banner to get fresh data
    loadHeaderBanner();
  };

  const handleCloseEditor = () => {
    setShowEditor(false);
    setEditingLink(null);
    setEditingPosition(null);
  };

  const breadcrumbItems = [
    { label: 'CMS', href: '/cms' },
    { label: 'Header Banner', current: true },
  ];

  const renderLinkCard = (link, position, label) => {
    if (!link) {
      return (
        <div className="p-4 bg-zinc-50 dark:bg-zinc-800 border border-dashed border-zinc-300 dark:border-zinc-700 rounded-lg">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">No link set</p>
        </div>
      );
    }

    return (
      <div className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg overflow-hidden hover:shadow-md transition-shadow">
        <div className="p-4">
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-1">
                {label}
              </h3>
              {link.has_image && (
                <span className="inline-block px-2 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 rounded text-xs font-medium">
                  Has Icon
                </span>
              )}
            </div>
            <button
              onClick={() => handleEditLink(link, position)}
              className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors"
            >
              <PencilIcon className="h-3 w-3" />
              Edit
            </button>
          </div>

          <div className="space-y-2">
            <div>
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">Text:</span>
              <p className="text-sm text-zinc-900 dark:text-zinc-100 mt-0.5">{link.link_text}</p>
            </div>
            <div>
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">Link:</span>
              <p className="text-sm text-blue-600 dark:text-blue-400 mt-0.5 font-mono break-all">
                {link.link_location}
              </p>
            </div>
            <div>
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">Handle:</span>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5 font-mono">
                {link.handle}
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <div className="mb-6">
        <ResponsiveBreadcrumb items={breadcrumbItems} />
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">
          Header Top Banner
        </h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          Manage promotional links in the top navigation bar (3 positions per market)
        </p>
      </div>

      {/* Market Selector */}
      <div className="mb-6 flex gap-2">
        <button
          onClick={() => setSelectedMarket('ca')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            selectedMarket === 'ca'
              ? 'bg-blue-600 text-white'
              : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'
          }`}
        >
          🇨🇦 Canada Market
        </button>
        <button
          onClick={() => setSelectedMarket('us')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            selectedMarket === 'us'
              ? 'bg-blue-600 text-white'
              : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'
          }`}
        >
          🇺🇸 United States Market
        </button>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          <span className="ml-3 text-zinc-600 dark:text-zinc-400">Loading header banner...</span>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex gap-3">
          <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-600 dark:text-red-400">Error loading header banner</p>
            <p className="text-sm text-red-600 dark:text-red-400 mt-1">{error}</p>
            <button
              onClick={loadHeaderBanner}
              className="mt-2 text-sm font-medium text-red-600 dark:text-red-400 hover:underline"
            >
              Try again
            </button>
          </div>
        </div>
      )}

      {/* Header Banner Links */}
      {!loading && !error && headerBanner && (
        <div className="space-y-8">
          {/* Visual Layout Preview */}
          <div className="bg-gradient-to-r from-blue-600 to-blue-700 p-4 rounded-lg">
            <div className="grid grid-cols-3 gap-4 text-white text-xs text-center">
              <div className="opacity-75">← Left</div>
              <div className="font-semibold">Center</div>
              <div className="opacity-75">Right →</div>
            </div>
          </div>

          {/* Links Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {selectedMarket === 'ca' ? (
              <>
                {renderLinkCard(headerBanner.links.ca.left, 'left_link', 'Left Position')}
                {renderLinkCard(headerBanner.links.ca.center, 'centre_link', 'Center Position')}
                {renderLinkCard(headerBanner.links.ca.right, 'right_link', 'Right Position')}
              </>
            ) : (
              <>
                {renderLinkCard(headerBanner.links.us.left, 'us_left_link', 'Left Position')}
                {renderLinkCard(headerBanner.links.us.center, 'us_center_link', 'Center Position')}
                {renderLinkCard(headerBanner.links.us.right, 'us_right_link', 'Right Position')}
              </>
            )}
          </div>

          {/* Info Note */}
          <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
            <p className="text-sm text-blue-700 dark:text-blue-300">
              <strong>Note:</strong> These links appear in the top navigation bar of the website.
              The left position typically shows shipping info, center shows current promotions,
              and right shows commercial/business links.
            </p>
          </div>
        </div>
      )}

      {/* Text Link Editor Modal */}
      {showEditor && editingLink && (
        <TextLinkEditor
          textLink={editingLink}
          position={editingPosition}
          onClose={handleCloseEditor}
          onSave={handleSaveLink}
          authToken={authToken}
        />
      )}
    </div>
  );
}
