import React, { useState, useEffect } from 'react';
import { Loader2, AlertCircle } from 'lucide-react';
import HomeBannerCard from '../../components/cms/HomeBannerCard';
import HomeBannerEditor from '../../components/cms/HomeBannerEditor';
import ResponsiveBreadcrumb from '../../components/Breadcrumb';

/**
 * HomeBannersPage Component
 * CMS page for managing homepage main banners (CA + US markets)
 */
export default function HomeBannersPage({ authToken }) {
  const [banners, setBanners] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingBanner, setEditingBanner] = useState(null);
  const [showEditor, setShowEditor] = useState(false);
  const [selectedMarket, setSelectedMarket] = useState('all'); // 'all', 'ca', 'us'

  useEffect(() => {
    loadBanners();
  }, [authToken]);

  const loadBanners = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch('/api/cms/home-banners', {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to load banners');
      }

      const data = await response.json();
      setBanners(data.banners || []);
    } catch (err) {
      setError(err.message || 'Failed to load banners');
    } finally {
      setLoading(false);
    }
  };

  const handleEditBanner = (banner) => {
    setEditingBanner(banner);
    setShowEditor(true);
  };

  const handleSaveBanner = (updatedBanner) => {
    // Reload banners to get fresh data
    loadBanners();
  };

  const handleCloseEditor = () => {
    setShowEditor(false);
    setEditingBanner(null);
  };

  // Filter banners by selected market
  const filteredBanners = selectedMarket === 'all'
    ? banners
    : banners.filter(b => b.market.toLowerCase() === selectedMarket);

  // Separate primary and secondary banners
  const primaryBanners = filteredBanners.filter(b => b.type === 'Primary');
  const secondaryBanners = filteredBanners.filter(b => b.type === 'Secondary');

  const breadcrumbItems = [
    { label: 'CMS', href: '/cms' },
    { label: 'Home Banners', current: true },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <div className="mb-6">
        <ResponsiveBreadcrumb items={breadcrumbItems} />
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">
          Home Page Banners
        </h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          Manage hero banners and secondary promotional banners on the homepage
        </p>
      </div>

      {/* Market Filter */}
      <div className="mb-6 flex gap-2">
        <button
          onClick={() => setSelectedMarket('all')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            selectedMarket === 'all'
              ? 'bg-blue-600 text-white'
              : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'
          }`}
        >
          All Markets
        </button>
        <button
          onClick={() => setSelectedMarket('ca')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            selectedMarket === 'ca'
              ? 'bg-blue-600 text-white'
              : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'
          }`}
        >
          🇨🇦 Canada
        </button>
        <button
          onClick={() => setSelectedMarket('us')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            selectedMarket === 'us'
              ? 'bg-blue-600 text-white'
              : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'
          }`}
        >
          🇺🇸 United States
        </button>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          <span className="ml-3 text-zinc-600 dark:text-zinc-400">Loading banners...</span>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex gap-3">
          <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-600 dark:text-red-400">Error loading banners</p>
            <p className="text-sm text-red-600 dark:text-red-400 mt-1">{error}</p>
            <button
              onClick={loadBanners}
              className="mt-2 text-sm font-medium text-red-600 dark:text-red-400 hover:underline"
            >
              Try again
            </button>
          </div>
        </div>
      )}

      {/* Banners Grid */}
      {!loading && !error && (
        <div className="space-y-8">
          {/* Primary Banners */}
          <div>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
              Primary Hero Banners ({primaryBanners.length})
            </h2>
            {primaryBanners.length === 0 ? (
              <div className="text-center py-8 bg-zinc-50 dark:bg-zinc-800 rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700">
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  No primary banners found for selected market
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {primaryBanners.map((banner) => (
                  <HomeBannerCard
                    key={banner.id}
                    banner={banner}
                    onEdit={handleEditBanner}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Secondary Banners */}
          <div>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
              Secondary Promotional Banners ({secondaryBanners.length})
            </h2>
            {secondaryBanners.length === 0 ? (
              <div className="text-center py-8 bg-zinc-50 dark:bg-zinc-800 rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700">
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  No secondary banners found for selected market
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {secondaryBanners.map((banner) => (
                  <HomeBannerCard
                    key={banner.id}
                    banner={banner}
                    onEdit={handleEditBanner}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Banner Editor Modal */}
      {showEditor && editingBanner && (
        <HomeBannerEditor
          banner={editingBanner}
          onClose={handleCloseEditor}
          onSave={handleSaveBanner}
          authToken={authToken}
        />
      )}
    </div>
  );
}
