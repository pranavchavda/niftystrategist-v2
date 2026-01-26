import React, { useState, useEffect } from 'react';
import { X, Loader2, AlertCircle, Plus, Trash2, Edit2, ChevronDown, Check } from 'lucide-react';
import { MagnifyingGlassIcon, PhotoIcon } from '@heroicons/react/20/solid';
import { Dialog, DialogTitle, DialogBody, DialogActions } from './catalyst/dialog';
import Breadcrumb from './Breadcrumb';
import LoadingMessage from './LoadingMessage';

/**
 * ComparisonTableEditor Component
 * Modal for editing a comparison table and managing its features and products
 */
export default function ComparisonTableEditor({
  comparisonTableId,
  comparisonTableData,
  onClose,
  onSave,
  authToken,
  breadcrumbContext = null, // Optional breadcrumb context: { categoryPageName: string }
}) {
  const [tableData, setTableData] = useState({
    title: '',
    features: [],
    products: [],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [editingFeatureId, setEditingFeatureId] = useState(null);
  const [expandedFeatures, setExpandedFeatures] = useState({});
  const [activeTab, setActiveTab] = useState('features'); // 'features' or 'products'
  const [productDetails, setProductDetails] = useState({}); // Cache for product details

  // Product picker state
  const [showProductPicker, setShowProductPicker] = useState(false);
  const [productSearchQuery, setProductSearchQuery] = useState('');
  const [searchedProducts, setSearchedProducts] = useState([]);
  const [searchingProducts, setSearchingProducts] = useState(false);

  // Form state for new/editing feature
  const [featureForm, setFeatureForm] = useState({
    feature_name: '',
    feature_key: '',
    display_type: 'text',
  });

  // Initialize with provided data
  useEffect(() => {
    if (comparisonTableData) {
      // Handle nested structure from API
      const fields = comparisonTableData.fields || {};

      // Extract features from references
      const features = fields.features?.references?.map(ref => ({
        id: ref.id,
        feature_name: ref.fields?.feature_name?.value || '',
        feature_key: ref.fields?.feature_key?.value || '',
        display_type: ref.fields?.display_type?.value || 'text'
      })) || [];

      // Extract products (parse JSON string array)
      let products = [];
      if (fields.products?.value) {
        try {
          products = JSON.parse(fields.products.value);
        } catch (e) {
          console.error('Failed to parse products:', e);
        }
      }

      setTableData({
        title: fields.title?.value || comparisonTableData.title || '',
        features,
        products
      });

      // Fetch product details if products exist
      if (products.length > 0) {
        fetchProductDetails(products);
      }
    }
  }, [comparisonTableData]);

  // Fetch product details from Shopify
  const fetchProductDetails = async (productGids) => {
    try {
      const response = await fetch('/api/shopify/products/batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify({ gids: productGids }),
      });

      if (!response.ok) {
        throw new Error('Failed to fetch product details');
      }

      const data = await response.json();
      const detailsMap = {};
      data.products.forEach(product => {
        detailsMap[product.id] = product;
      });
      setProductDetails(detailsMap);
    } catch (err) {
      console.error('Error fetching product details:', err);
      // Don't show error to user - just log it
    }
  };

  // Product search with debouncing
  useEffect(() => {
    if (!productSearchQuery.trim() || !showProductPicker) {
      setSearchedProducts([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        setSearchingProducts(true);
        const response = await fetch(
          `/api/cms/products/search?query=${encodeURIComponent(productSearchQuery)}&limit=20`,
          {
            headers: {
              Authorization: `Bearer ${authToken}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error('Failed to search products');
        }

        const data = await response.json();
        setSearchedProducts(data.products || []);
      } catch (err) {
        console.error('Error searching products:', err);
        setError(err.message);
      } finally {
        setSearchingProducts(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [productSearchQuery, showProductPicker, authToken]);

  const resetFeatureForm = () => {
    setFeatureForm({ feature_name: '', feature_key: '', display_type: 'text' });
    setEditingFeatureId(null);
  };

  const handleAddFeature = () => {
    if (!featureForm.feature_name.trim()) {
      setError('Feature name is required');
      return;
    }
    if (!featureForm.feature_key.trim()) {
      setError('Feature key is required');
      return;
    }

    const newFeature = {
      id: editingFeatureId || `temp_${Date.now()}`,
      feature_name: featureForm.feature_name,
      feature_key: featureForm.feature_key,
      display_type: featureForm.display_type,
    };

    if (editingFeatureId && editingFeatureId !== 'new') {
      // Update existing feature
      setTableData(prev => ({
        ...prev,
        features: prev.features.map(f => f.id === editingFeatureId ? newFeature : f),
      }));
    } else {
      // Add new feature
      setTableData(prev => ({
        ...prev,
        features: [...prev.features, newFeature],
      }));
    }

    resetFeatureForm();
    setError(null);
  };

  const handleEditFeature = (feature) => {
    setFeatureForm({
      feature_name: feature.feature_name,
      feature_key: feature.feature_key,
      display_type: feature.display_type,
    });
    setEditingFeatureId(feature.id);
  };

  const handleDeleteFeature = (featureId) => {
    setTableData(prev => ({
      ...prev,
      features: prev.features.filter(f => f.id !== featureId),
    }));
  };

  const handleRemoveProduct = (productGid) => {
    setTableData(prev => ({
      ...prev,
      products: prev.products.filter(gid => gid !== productGid),
    }));
  };

  const handleAddProduct = () => {
    setShowProductPicker(true);
    setProductSearchQuery('');
    setSearchedProducts([]);
    setError(null);
  };

  const handleSelectProduct = (product) => {
    // Check if product is already added
    if (tableData.products.includes(product.id)) {
      return;
    }

    // Add product GID to the list
    setTableData(prev => ({
      ...prev,
      products: [...prev.products, product.id],
    }));

    // Add product details to cache
    setProductDetails(prev => ({
      ...prev,
      [product.id]: product,
    }));
  };

  const handleSubmit = async () => {
    if (!tableData.title.trim()) {
      setError('Table title is required');
      return;
    }

    if (tableData.features.length === 0) {
      setError('Add at least one feature');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const fields = {
        title: tableData.title,
        features: tableData.features,
        products: tableData.products,
      };

      await onSave(fields);

      setSuccess(true);
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err) {
      setError(err.message || 'Failed to save comparison table');
      setLoading(false);
    }
  };

  const toggleFeatureExpand = (featureId) => {
    setExpandedFeatures(prev => ({
      ...prev,
      [featureId]: !prev[featureId],
    }));
  };

  // Build breadcrumb items
  const breadcrumbItems = () => {
    const items = [
      { label: 'CMS', href: '/cms' },
      { label: 'Category Pages', href: '/cms/category-pages' },
    ];

    if (breadcrumbContext?.categoryPageName) {
      items.push({ label: `Edit "${breadcrumbContext.categoryPageName}"` });
    }

    items.push({ label: 'Comparison Table', current: true });
    return items;
  };

  return (
    <Dialog open={true} onClose={onClose} size="5xl">
      <div className="flex items-center justify-between">
        <DialogTitle>Edit Comparison Table</DialogTitle>
        <button
          onClick={onClose}
          disabled={loading}
          className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors disabled:opacity-50 flex-shrink-0"
        >
          <X className="h-6 w-6 text-zinc-600 dark:text-zinc-400" />
        </button>
      </div>

      <DialogBody className="px-0 py-0">
        <div className="p-4 sm:p-6 space-y-5 sm:space-y-6">
          {/* Breadcrumb Navigation */}
          {breadcrumbContext && (
            <div className="pb-3 border-b border-zinc-200 dark:border-zinc-800">
              <Breadcrumb items={breadcrumbItems()} />
            </div>
          )}
          {/* Error Message */}
          {error && (
            <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex gap-3">
              <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          )}

          {/* Success Message */}
          {success && (
            <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
              <p className="text-sm text-green-600 dark:text-green-400 font-medium">
                Successfully saved! Closing...
              </p>
            </div>
          )}

          {/* Table Title */}
          <div>
            <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
              Table Title <span className="text-red-600 dark:text-red-400">*</span>
            </label>
            <input
              type="text"
              value={tableData.title}
              onChange={(e) => setTableData({ ...tableData, title: e.target.value })}
              placeholder="e.g., Single Dose Grinder Comparison"
              disabled={loading}
              className="w-full min-h-[44px] px-3 py-2.5 sm:py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
          </div>

          <div className="border-t border-zinc-200 dark:border-zinc-800"></div>

          {/* Tab Navigation */}
          <div className="flex gap-1 sm:gap-2 border-b border-zinc-200 dark:border-zinc-700 -mx-4 sm:-mx-0 px-4 sm:px-0 overflow-x-auto">
            <button
              onClick={() => setActiveTab('features')}
              className={`flex-1 sm:flex-none min-h-[44px] px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium transition-colors border-b-2 whitespace-nowrap touch-manipulation ${
                activeTab === 'features'
                  ? 'text-blue-600 dark:text-blue-400 border-blue-600 dark:border-blue-400'
                  : 'text-zinc-600 dark:text-zinc-400 border-transparent hover:text-zinc-900 dark:hover:text-zinc-100 active:text-zinc-950 dark:active:text-zinc-50'
              }`}
            >
              Features ({tableData.features.length})
            </button>
            <button
              onClick={() => setActiveTab('products')}
              className={`flex-1 sm:flex-none min-h-[44px] px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium transition-colors border-b-2 whitespace-nowrap touch-manipulation ${
                activeTab === 'products'
                  ? 'text-blue-600 dark:text-blue-400 border-blue-600 dark:border-blue-400'
                  : 'text-zinc-600 dark:text-zinc-400 border-transparent hover:text-zinc-900 dark:hover:text-zinc-100 active:text-zinc-950 dark:active:text-zinc-50'
              }`}
            >
              Products ({tableData.products.length})
            </button>
          </div>

          {/* Features Tab */}
          {activeTab === 'features' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Comparison Features
                </h3>
                {!editingFeatureId && (
                  <button
                    onClick={() => setEditingFeatureId('new')}
                    disabled={loading}
                    className="w-full sm:w-auto min-h-[36px] px-3 py-1.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded text-xs font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-1 touch-manipulation"
                  >
                    <Plus className="h-3 w-3" />
                    Add Feature
                  </button>
                )}
              </div>

              {/* Add/Edit Feature Form */}
              {editingFeatureId && (
                <div className="mb-4 p-4 bg-zinc-50 dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700">
                  <div className="space-y-3 mb-3">
                    <div>
                      <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                        Feature Name <span className="text-red-600 dark:text-red-400">*</span>
                      </label>
                      <input
                        type="text"
                        value={featureForm.feature_name}
                        onChange={(e) => setFeatureForm({ ...featureForm, feature_name: e.target.value })}
                        placeholder="e.g., Burr Size"
                        disabled={loading}
                        className="w-full min-h-[44px] px-3 py-2.5 sm:py-2 bg-white dark:bg-zinc-700 border border-zinc-300 dark:border-zinc-600 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                      />
                      <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                        Display name shown in the comparison table
                      </p>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                        Metafield Key <span className="text-red-600 dark:text-red-400">*</span>
                      </label>
                      <input
                        type="text"
                        value={featureForm.feature_key}
                        onChange={(e) => setFeatureForm({ ...featureForm, feature_key: e.target.value })}
                        placeholder="e.g., burr_size"
                        disabled={loading}
                        className="w-full min-h-[44px] px-3 py-2.5 sm:py-2 bg-white dark:bg-zinc-700 border border-zinc-300 dark:border-zinc-600 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 font-mono"
                      />
                      <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                        Product metafield to pull data from (must match custom.XXX namespace)
                      </p>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                        Display Type <span className="text-red-600 dark:text-red-400">*</span>
                      </label>
                      <select
                        value={featureForm.display_type}
                        onChange={(e) => setFeatureForm({ ...featureForm, display_type: e.target.value })}
                        disabled={loading}
                        className="w-full min-h-[44px] px-3 py-2.5 sm:py-2 bg-white dark:bg-zinc-700 border border-zinc-300 dark:border-zinc-600 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                      >
                        <option value="text">Text</option>
                        <option value="boolean">Yes/No (Boolean)</option>
                        <option value="number">Number</option>
                      </select>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                        How to display the metafield value in the table
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <button
                      onClick={handleAddFeature}
                      disabled={loading}
                      className="flex-1 min-h-[44px] py-2 px-3 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded text-xs sm:text-sm font-medium transition-colors disabled:opacity-50 touch-manipulation"
                    >
                      {editingFeatureId === 'new' ? 'Add Feature' : 'Update Feature'}
                    </button>
                    <button
                      onClick={resetFeatureForm}
                      disabled={loading}
                      className="flex-1 min-h-[44px] py-2 px-3 bg-zinc-300 dark:bg-zinc-600 hover:bg-zinc-400 active:bg-zinc-500 dark:hover:bg-zinc-500 dark:active:bg-zinc-400 text-zinc-900 dark:text-zinc-100 rounded text-xs sm:text-sm font-medium transition-colors disabled:opacity-50 touch-manipulation"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Features List */}
              {tableData.features.length === 0 ? (
                <div className="text-center py-8 bg-zinc-50 dark:bg-zinc-800 rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">No features yet</p>
                  <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-1">
                    Add features to compare product specifications
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {tableData.features.map((feature) => (
                    <div
                      key={feature.id}
                      className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg overflow-hidden hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors"
                    >
                      <button
                        onClick={() => toggleFeatureExpand(feature.id)}
                        className="w-full min-h-[56px] p-3 flex items-start justify-between hover:bg-zinc-50 active:bg-zinc-100 dark:hover:bg-zinc-700 dark:active:bg-zinc-600 transition-colors touch-manipulation"
                      >
                        <div className="flex-1 text-left">
                          <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                            {feature.feature_name}
                          </p>
                          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                            {feature.feature_key} • {feature.display_type}
                          </p>
                        </div>
                        <ChevronDown
                          className={`h-4 w-4 text-zinc-400 flex-shrink-0 ml-2 transition-transform ${
                            expandedFeatures[feature.id] ? 'rotate-180' : ''
                          }`}
                        />
                      </button>

                      {expandedFeatures[feature.id] && (
                        <div className="px-3 pb-3 pt-0 space-y-3 border-t border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900">
                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-3">
                            <div>
                              <p className="text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                                Display Name
                              </p>
                              <p className="text-sm text-zinc-900 dark:text-zinc-100">
                                {feature.feature_name}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                                Metafield Key
                              </p>
                              <p className="text-sm text-zinc-900 dark:text-zinc-100 font-mono">
                                {feature.feature_key}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                                Display Type
                              </p>
                              <p className="text-sm text-zinc-900 dark:text-zinc-100 capitalize">
                                {feature.display_type}
                              </p>
                            </div>
                          </div>
                          <div className="flex flex-col sm:flex-row gap-2 pt-2">
                            <button
                              onClick={() => handleEditFeature(feature)}
                              disabled={loading}
                              className="flex-1 min-h-[44px] py-2 px-3 bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 active:bg-blue-200 dark:hover:bg-blue-900/50 dark:active:bg-blue-900/70 text-blue-600 dark:text-blue-400 rounded text-xs font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-1 touch-manipulation"
                            >
                              <Edit2 className="h-3 w-3" />
                              Edit
                            </button>
                            <button
                              onClick={() => handleDeleteFeature(feature.id)}
                              disabled={loading}
                              className="flex-1 min-h-[44px] py-2 px-3 bg-red-50 dark:bg-red-900/30 hover:bg-red-100 active:bg-red-200 dark:hover:bg-red-900/50 dark:active:bg-red-900/70 text-red-600 dark:text-red-400 rounded text-xs font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-1 touch-manipulation"
                            >
                              <Trash2 className="h-3 w-3" />
                              Delete
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Products Tab */}
          {activeTab === 'products' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Products to Compare
                </h3>
                <button
                  onClick={handleAddProduct}
                  disabled={loading}
                  className="w-full sm:w-auto min-h-[36px] px-3 py-1.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded text-xs font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-1 touch-manipulation"
                >
                  <Plus className="h-3 w-3" />
                  Add Product
                </button>
              </div>

              {/* Products List */}
              {tableData.products.length === 0 ? (
                <div className="text-center py-8 bg-zinc-50 dark:bg-zinc-800 rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">No products added</p>
                  <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-1">
                    Add products to compare their features
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {tableData.products.map((productGid) => {
                    const product = productDetails[productGid];
                    return (
                      <div
                        key={productGid}
                        className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg p-3 flex items-center justify-between hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors"
                      >
                        <div className="flex-1">
                          {product ? (
                            <>
                              <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                                {product.title}
                              </p>
                              {product.vendor && (
                                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                                  {product.vendor}
                                </p>
                              )}
                            </>
                          ) : (
                            <div className="flex items-center gap-2">
                              <Loader2 className="h-3 w-3 animate-spin text-zinc-400" />
                              <p className="text-xs text-zinc-500 dark:text-zinc-400 font-mono">
                                {productGid}
                              </p>
                            </div>
                          )}
                        </div>
                        <button
                          onClick={() => handleRemoveProduct(productGid)}
                          disabled={loading}
                          className="ml-3 p-2 hover:bg-red-50 active:bg-red-100 dark:hover:bg-red-900/30 dark:active:bg-red-900/50 rounded transition-colors disabled:opacity-50 touch-manipulation"
                          title="Remove product"
                        >
                          <Trash2 className="h-4 w-4 text-red-600 dark:text-red-400" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}

              <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                <p className="text-xs text-blue-700 dark:text-blue-300">
                  Note: Products must have the metafields defined in the Features tab for the comparison to work properly.
                </p>
              </div>
            </div>
          )}
        </div>
      </DialogBody>

      <DialogActions className="px-4 sm:px-6 py-3 sm:py-4 border-t border-zinc-200 dark:border-zinc-700">
        <button
          type="button"
          onClick={onClose}
          disabled={loading || success}
          className="px-4 py-2.5 sm:py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 active:bg-zinc-200 dark:hover:bg-zinc-800 dark:active:bg-zinc-700 rounded-lg disabled:opacity-50 transition-colors touch-manipulation"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={loading || success}
          className="px-6 py-2.5 sm:py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 rounded-lg disabled:opacity-50 transition-colors flex items-center justify-center gap-2 touch-manipulation"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : success ? (
            <>
              ✓ Saved
            </>
          ) : (
            'Save Changes'
          )}
        </button>
      </DialogActions>

      {/* Product Picker Modal */}
      {showProductPicker && (
        <Dialog open={showProductPicker} onClose={() => setShowProductPicker(false)} size="4xl">
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle>Add Products to Compare</DialogTitle>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                Search and select products to include in the comparison table
              </p>
            </div>
            <button
              onClick={() => setShowProductPicker(false)}
              className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors flex-shrink-0"
            >
              <X className="h-5 w-5 text-zinc-500" />
            </button>
          </div>

          <DialogBody className="px-0 py-0">
            <div className="p-6 pb-0">
              {/* Search Input */}
              <div className="relative mb-6">
                <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search products..."
                  value={productSearchQuery}
                  onChange={(e) => setProductSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  autoFocus
                />
              </div>
            </div>

            <div className="p-6 pt-0 overflow-y-auto flex-1" style={{ maxHeight: '500px' }}>
              {searchingProducts ? (
                <LoadingMessage message="Searching products..." className="py-12" />
              ) : !productSearchQuery.trim() ? (
                <div className="text-center py-12">
                  <MagnifyingGlassIcon className="h-12 w-12 text-zinc-300 dark:text-zinc-700 mx-auto mb-4" />
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">
                    Type to search for products
                  </p>
                </div>
              ) : searchedProducts.length === 0 ? (
                <div className="text-center py-12">
                  <PhotoIcon className="h-12 w-12 text-zinc-300 dark:text-zinc-700 mx-auto mb-4" />
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">
                    No products found matching "{productSearchQuery}"
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {searchedProducts.map((product) => {
                    const isAdded = tableData.products.includes(product.id);
                    const price = product.priceRangeV2?.minVariantPrice?.amount;
                    const currencyCode = product.priceRangeV2?.minVariantPrice?.currencyCode || 'CAD';

                    return (
                      <div
                        key={product.id}
                        className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg overflow-hidden hover:shadow-md transition-shadow"
                      >
                        <div className="flex gap-3 p-3">
                          {/* Product Image */}
                          <div className="flex-shrink-0 w-24 h-24 bg-zinc-100 dark:bg-zinc-900 rounded overflow-hidden">
                            {product.imageUrl ? (
                              <img
                                src={product.imageUrl}
                                alt={product.title}
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center">
                                <PhotoIcon className="h-8 w-8 text-zinc-300 dark:text-zinc-600" />
                              </div>
                            )}
                          </div>

                          {/* Product Info */}
                          <div className="flex-1 min-w-0">
                            <h4 className="text-sm font-medium text-zinc-900 dark:text-zinc-100 line-clamp-2 mb-1">
                              {product.title}
                            </h4>
                            {product.vendor && (
                              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-1">
                                {product.vendor}
                              </p>
                            )}
                            {price && (
                              <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                                ${parseFloat(price).toFixed(2)} {currencyCode}
                              </p>
                            )}
                          </div>

                          {/* Add Button */}
                          <div className="flex-shrink-0">
                            <button
                              onClick={() => handleSelectProduct(product)}
                              disabled={isAdded}
                              className={`py-2 px-4 rounded-lg font-medium text-sm transition-colors ${
                                isAdded
                                  ? 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400 cursor-not-allowed'
                                  : 'bg-blue-600 hover:bg-blue-700 text-white'
                              }`}
                            >
                              {isAdded ? (
                                <Check className="h-4 w-4" />
                              ) : (
                                'Add'
                              )}
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </DialogBody>

          <DialogActions>
            <button
              onClick={() => setShowProductPicker(false)}
              className="px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
            >
              Done
            </button>
          </DialogActions>
        </Dialog>
      )}
    </Dialog>
  );
}
