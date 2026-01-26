import React, { useState, useEffect, useRef } from 'react';
import {
  MagnifyingGlassIcon,
  PencilIcon,
  PhotoIcon,
  SparklesIcon,
  CheckIcon,
  XMarkIcon,
  ExclamationTriangleIcon,
  ArrowUpTrayIcon,
  RectangleStackIcon,
} from '@heroicons/react/20/solid';
import { Loader2 } from 'lucide-react';
import { Dialog, DialogTitle, DialogBody, DialogActions } from '../../components/catalyst/dialog';
import MetaobjectPicker from '../../components/MetaobjectPicker';
import SkeletonCard from '../../components/SkeletonCard';
import LoadingMessage from '../../components/LoadingMessage';
import { ResponsiveBreadcrumb } from '../../components/Breadcrumb';

export default function CategoryLandingPagesPage({ authToken }) {
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [editingPage, setEditingPage] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [selectedModel, setSelectedModel] = useState('gpt5-image-mini');
  const [promptMode, setPromptMode] = useState('contextual'); // 'contextual', 'template', 'custom'
  const [selectedTemplate, setSelectedTemplate] = useState('home_barista');
  const [customPrompt, setCustomPrompt] = useState('');
  const [showBrowseModal, setShowBrowseModal] = useState(false);
  const [shopifyFiles, setShopifyFiles] = useState([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const fileInputRef = useRef(null);

  // Featured Products state
  const [showProductPicker, setShowProductPicker] = useState(false);
  const [productSearchQuery, setProductSearchQuery] = useState('');
  const [searchedProducts, setSearchedProducts] = useState([]);
  const [searchingProducts, setSearchingProducts] = useState(false);
  const [draggedProductIndex, setDraggedProductIndex] = useState(null);

  // Sorting Options state
  const [newSortLabel, setNewSortLabel] = useState('');
  const [newSortFilterType, setNewSortFilterType] = useState('price_range');
  const [newSortFilterValue, setNewSortFilterValue] = useState('');
  // Conditional inputs based on filter type
  const [sortPriceMin, setSortPriceMin] = useState('');
  const [sortPriceMax, setSortPriceMax] = useState('');
  const [sortVendor, setSortVendor] = useState('');
  const [sortSpecName, setSortSpecName] = useState('');
  const [sortSpecValue, setSortSpecValue] = useState('');

  // Categories state
  const [newCategoryId, setNewCategoryId] = useState('');

  // Educational Content state
  const [newEducationalBlockId, setNewEducationalBlockId] = useState('');

  // FAQ Section state (single reference)
  const [selectedFaqSectionId, setSelectedFaqSectionId] = useState('');

  // Comparison Table state (single reference)
  const [selectedComparisonTableId, setSelectedComparisonTableId] = useState('');

  // Create new page state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newPageUrlHandle, setNewPageUrlHandle] = useState('');
  const [newPageTitle, setNewPageTitle] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadPages();
  }, [authToken]);

  const loadPages = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch('/api/cms/category-landing-pages', {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to load category pages: ${response.statusText}`);
      }

      const data = await response.json();
      setPages(data.pages || []);
    } catch (err) {
      console.error('Error loading pages:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (page) => {
    setEditingPage({
      id: page.id,
      handle: page.handle,
      displayName: page.displayName,
      // Hero section
      heroImageUrl: page.heroImageUrl || '',
      heroTitle: page.heroTitle || '',
      heroDescription: page.heroDescription || '',
      // Basic fields
      urlHandle: page.urlHandle || '',
      title: page.title || '',
      // SEO fields
      seoTitle: page.seoTitle || '',
      seoDescription: page.seoDescription || '',
      // Settings
      enableSorting: page.enableSorting || false,
      // Featured Products
      featuredProducts: page.featuredProducts || [],
      // Sorting Options
      sortingOptions: page.sortingOptions || [],
      // Categories
      categories: page.categories || [],
      // Educational Content
      educationalContent: page.educationalContent || [],
      // FAQ Section (single reference)
      faqSection: page.faqSection || null,
      // Comparison Table (single reference)
      comparisonTable: page.comparisonTable || null,
    });

    // Reset AI hero image controls to prevent state leakage between pages
    setSelectedModel('gpt5-image-mini');
    setPromptMode('contextual');
    setSelectedTemplate('home_barista');
    setCustomPrompt('');

    setSuccess(false);
    setError(null);
  };

  const handleCancelEdit = () => {
    setEditingPage(null);
    setSuccess(false);
    setError(null);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      const response = await fetch(`/api/cms/category-landing-pages?page_id=${encodeURIComponent(editingPage.id)}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          // Hero section
          heroTitle: editingPage.heroTitle,
          heroDescription: editingPage.heroDescription,
          // Basic fields
          urlHandle: editingPage.urlHandle,
          title: editingPage.title,
          // SEO fields
          seoTitle: editingPage.seoTitle,
          seoDescription: editingPage.seoDescription,
          // Settings
          enableSorting: editingPage.enableSorting,
          // Featured Products (send only IDs)
          featuredProducts: editingPage.featuredProducts.map(p => p.id),
          // Sorting Options (send only IDs - backend will create new ones for temp IDs)
          sortingOptions: editingPage.sortingOptions.map(opt => opt.id),
          // Categories (send only IDs)
          categories: editingPage.categories.map(cat => cat.id),
          // Educational Content (send only IDs)
          educationalContent: editingPage.educationalContent.map(block => block.id),
          // Comparison Table (single ID or null)
          comparisonTable: editingPage.comparisonTable?.id || null,
          // FAQ Section (single ID or null)
          faqSection: editingPage.faqSection?.id || null,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save changes');
      }

      const updatedPage = await response.json();

      // Update the pages list
      setPages(pages.map(p => p.id === updatedPage.id ? updatedPage : p));
      setEditingPage(null);
      setSuccess(true);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('Error saving page:', err);
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerateHeroImage = async (pageId, template, model = 'gpt5-image-mini', heroTitle = null, heroDescription = null, customPromptText = null) => {
    try {
      setSaving(true);
      setError(null);

      const requestBody = {
        template,
        model,
      };

      // Add prompt parameters based on mode
      if (customPromptText) {
        requestBody.customPrompt = customPromptText;
      } else if (heroTitle && heroDescription) {
        requestBody.heroTitle = heroTitle;
        requestBody.heroDescription = heroDescription;
      }

      const response = await fetch(`/api/cms/category-landing-pages/regenerate-hero?page_id=${encodeURIComponent(pageId)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to regenerate hero image');
      }

      const updatedPage = await response.json();

      // Update the pages list and editing state
      setPages(pages.map(p => p.id === updatedPage.id ? updatedPage : p));
      if (editingPage && editingPage.id === updatedPage.id) {
        setEditingPage({
          ...editingPage,
          heroImageUrl: updatedPage.heroImageUrl,
        });
      }
      setSuccess(true);

      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('Error regenerating hero image:', err);
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file || !editingPage) return;

    try {
      setUploadingFile(true);
      setError(null);

      // Validate file type
      if (!file.type.startsWith('image/')) {
        throw new Error('Please select an image file');
      }

      // Create form data
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`/api/cms/category-landing-pages/upload-hero?page_id=${encodeURIComponent(editingPage.id)}`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to upload image');
      }

      const updatedPage = await response.json();

      // Update the pages list and editing state
      setPages(pages.map(p => p.id === updatedPage.id ? updatedPage : p));
      setEditingPage({
        ...editingPage,
        heroImageUrl: updatedPage.heroImageUrl,
      });
      setSuccess(true);

      setTimeout(() => setSuccess(false), 3000);

      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      console.error('Error uploading file:', err);
      setError(err.message);
    } finally {
      setUploadingFile(false);
    }
  };

  const loadShopifyFiles = async () => {
    try {
      setLoadingFiles(true);

      const response = await fetch('/api/cms/shopify-files?file_type=image', {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to load Shopify files');
      }

      const data = await response.json();
      setShopifyFiles(data.files || []);
    } catch (err) {
      console.error('Error loading Shopify files:', err);
      setError(err.message);
    } finally {
      setLoadingFiles(false);
    }
  };

  const handleBrowseImages = () => {
    setShowBrowseModal(true);
    loadShopifyFiles();
  };

  const handleSelectShopifyFile = async (fileId, fileUrl) => {
    if (!editingPage) return;

    try {
      setSaving(true);
      setError(null);

      const response = await fetch(`/api/cms/category-landing-pages/set-hero-image?page_id=${encodeURIComponent(editingPage.id)}&file_id=${encodeURIComponent(fileId)}`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to set hero image');
      }

      const updatedPage = await response.json();

      // Update the pages list and editing state
      setPages(pages.map(p => p.id === updatedPage.id ? updatedPage : p));
      setEditingPage({
        ...editingPage,
        heroImageUrl: updatedPage.heroImageUrl,
      });
      setShowBrowseModal(false);
      setSuccess(true);

      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('Error setting hero image:', err);
      setError(err.message);
    } finally {
      setSaving(false);
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

  const handleAddFeaturedProduct = (product) => {
    if (!editingPage) return;

    // Check if product is already added
    if (editingPage.featuredProducts.some(p => p.id === product.id)) {
      return;
    }

    setEditingPage({
      ...editingPage,
      featuredProducts: [
        ...editingPage.featuredProducts,
        {
          id: product.id,
          title: product.title,
          handle: product.handle,
          imageUrl: product.imageUrl || '',
        },
      ],
    });
  };

  const handleRemoveFeaturedProduct = (productId) => {
    if (!editingPage) return;

    setEditingPage({
      ...editingPage,
      featuredProducts: editingPage.featuredProducts.filter(p => p.id !== productId),
    });
  };

  const handleDragStart = (index) => {
    setDraggedProductIndex(index);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (dropIndex) => {
    if (draggedProductIndex === null || !editingPage) return;

    const products = [...editingPage.featuredProducts];
    const [draggedProduct] = products.splice(draggedProductIndex, 1);
    products.splice(dropIndex, 0, draggedProduct);

    setEditingPage({
      ...editingPage,
      featuredProducts: products,
    });

    setDraggedProductIndex(null);
  };

  const handleOpenProductPicker = () => {
    setShowProductPicker(true);
    setProductSearchQuery('');
    setSearchedProducts([]);
  };

  // Sorting Options handlers
  const buildFilterValue = () => {
    switch (newSortFilterType) {
      case 'price_range':
        if (!sortPriceMin || !sortPriceMax) return null;
        return `price:${sortPriceMin}-${sortPriceMax}`;
      case 'vendor':
        if (!sortVendor.trim()) return null;
        // Convert vendor name to underscore format: "La Marzocco" -> "la_marzocco"
        return `vendor_${sortVendor.trim().toLowerCase().replace(/\s+/g, '_')}`;
      case 'specification':
        if (!sortSpecName.trim() || !sortSpecValue.trim()) return null;
        // Format: "Manufacturer: La Marzocco"
        return `${sortSpecName.trim()}: ${sortSpecValue.trim()}`;
      case 'custom':
        return newSortFilterValue.trim() || null;
      default:
        return null;
    }
  };

  const handleAddSortingOption = () => {
    if (!editingPage || !newSortLabel.trim()) return;

    const filterValue = buildFilterValue();
    if (!filterValue) return; // Don't add if no valid filter value

    const newOption = {
      id: `temp_${Date.now()}`,
      label: newSortLabel.trim(),
      filterType: newSortFilterType,
      filterValue: filterValue,
    };

    setEditingPage({
      ...editingPage,
      sortingOptions: [...editingPage.sortingOptions, newOption],
    });

    // Clear form
    setNewSortLabel('');
    setNewSortFilterType('price_range');
    setNewSortFilterValue('');
    setSortPriceMin('');
    setSortPriceMax('');
    setSortVendor('');
    setSortSpecName('');
    setSortSpecValue('');
  };

  const handleRemoveSortingOption = (optionId) => {
    if (!editingPage) return;

    setEditingPage({
      ...editingPage,
      sortingOptions: editingPage.sortingOptions.filter(opt => opt.id !== optionId),
    });
  };

  // Categories handlers
  const handleSelectCategories = (selectedIds) => {
    if (!editingPage) return;

    // Get the selected metaobject details if available
    // For now, we'll just store the IDs and let the backend resolve them
    const newCategories = selectedIds.map(id => ({
      id,
      title: 'Category', // Placeholder - will be resolved on save
    }));

    setEditingPage({
      ...editingPage,
      categories: newCategories,
    });
  };

  const handleRemoveCategory = (categoryId) => {
    if (!editingPage) return;

    setEditingPage({
      ...editingPage,
      categories: editingPage.categories.filter(cat => cat.id !== categoryId),
    });
  };

  const handleMoveCategoryUp = (index) => {
    if (!editingPage || index === 0) return;
    const categories = [...editingPage.categories];
    [categories[index - 1], categories[index]] = [categories[index], categories[index - 1]];
    setEditingPage({
      ...editingPage,
      categories
    });
  };

  const handleMoveCategoryDown = (index) => {
    if (!editingPage || index === editingPage.categories.length - 1) return;
    const categories = [...editingPage.categories];
    [categories[index], categories[index + 1]] = [categories[index + 1], categories[index]];
    setEditingPage({
      ...editingPage,
      categories
    });
  };

  // Educational Content handlers
  const handleSelectEducationalBlocks = (selectedIds) => {
    if (!editingPage) return;

    const newBlocks = selectedIds.map(id => ({
      id,
      title: 'Educational Block', // Placeholder - will be resolved on save
    }));

    setEditingPage({
      ...editingPage,
      educationalContent: newBlocks,
    });
  };

  const handleRemoveEducationalBlock = (blockId) => {
    if (!editingPage) return;

    setEditingPage({
      ...editingPage,
      educationalContent: editingPage.educationalContent.filter(block => block.id !== blockId),
    });
  };

  const handleMoveEducationalBlockUp = (index) => {
    if (!editingPage || index === 0) return;
    const blocks = [...editingPage.educationalContent];
    [blocks[index - 1], blocks[index]] = [blocks[index], blocks[index - 1]];
    setEditingPage({
      ...editingPage,
      educationalContent: blocks
    });
  };

  const handleMoveEducationalBlockDown = (index) => {
    if (!editingPage || index === editingPage.educationalContent.length - 1) return;
    const blocks = [...editingPage.educationalContent];
    [blocks[index], blocks[index + 1]] = [blocks[index + 1], blocks[index]];
    setEditingPage({
      ...editingPage,
      educationalContent: blocks
    });
  };

  // FAQ Section handlers (single reference)
  const handleSelectFaqSection = (selectedId) => {
    if (!editingPage) return;

    setEditingPage({
      ...editingPage,
      faqSection: selectedId ? {
        id: selectedId,
        title: 'FAQ Section', // Placeholder - will be resolved on save
      } : null,
    });
  };

  const handleRemoveFaqSection = () => {
    if (!editingPage) return;

    setEditingPage({
      ...editingPage,
      faqSection: null,
    });
  };

  // Comparison Table handlers (single reference)
  const handleSelectComparisonTable = (selectedId) => {
    if (!editingPage) return;

    setEditingPage({
      ...editingPage,
      comparisonTable: selectedId ? {
        id: selectedId,
        title: 'Comparison Table', // Placeholder - will be resolved on save
      } : null,
    });
  };

  const handleRemoveComparisonTable = () => {
    if (!editingPage) return;

    setEditingPage({
      ...editingPage,
      comparisonTable: null,
    });
  };

  // Create new page handler
  const handleCreatePage = async () => {
    if (!newPageTitle.trim() || !newPageUrlHandle.trim()) {
      setError('Please provide both URL handle and title');
      return;
    }

    try {
      setCreating(true);
      setError(null);

      const response = await fetch('/api/cms/category-landing-pages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          urlHandle: newPageUrlHandle.trim(),
          title: newPageTitle.trim(),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create page');
      }

      const createdPage = await response.json();

      // Add to pages list
      setPages([...pages, createdPage]);

      // Close modal and reset form
      setShowCreateModal(false);
      setNewPageUrlHandle('');
      setNewPageTitle('');
      setSuccess(true);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('Error creating page:', err);
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const filteredPages = pages.filter(page =>
    !searchTerm ||
    page.displayName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    page.handle?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Breadcrumb items based on current state
  const getBreadcrumbItems = () => {
    const base = [
      { label: 'CMS', href: '/cms' },
      { label: 'Category Pages', href: '/cms/category-pages' },
    ];

    if (showCreateModal) {
      return [...base, { label: 'Create New', current: true }];
    }

    if (editingPage) {
      return [...base, { label: `Edit "${editingPage.displayName || editingPage.title}"`, current: true }];
    }

    return base;
  };

  if (loading) {
    return (
      <div className="h-full flex flex-col">
        <div className="p-6 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                  Category Landing Pages
                </h2>
                <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
                  Edit hero sections for category pages
                </p>
              </div>
              <div className="h-10 w-52 bg-zinc-200 dark:bg-zinc-700 rounded-lg animate-pulse"></div>
            </div>

            {/* Search Bar Skeleton */}
            <div className="h-10 bg-zinc-200 dark:bg-zinc-700 rounded-lg animate-pulse"></div>
          </div>
        </div>

        {/* Pages Grid Skeleton */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-7xl mx-auto">
            <LoadingMessage message="Loading category pages..." className="mb-8" />
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
              <SkeletonCard variant="category" count={6} />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar Section */}
      <div className="p-4 sm:p-6 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
        <div className="max-w-7xl mx-auto">
          {/* Breadcrumb Navigation */}
          <div className="mb-4">
            <ResponsiveBreadcrumb items={getBreadcrumbItems()} />
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 mb-4">
            {/* Search Bar */}
            <div className="relative flex-1 w-full sm:max-w-md">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-400" />
              <input
                type="text"
                placeholder="Search category pages..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 sm:py-2 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent min-h-[44px] sm:min-h-0"
              />
            </div>

            {/* Create Button */}
            <button
              onClick={() => setShowCreateModal(true)}
              className="w-full sm:w-auto min-h-[44px] py-2 px-4 bg-amber-600 hover:bg-amber-700 active:bg-amber-800 text-white rounded-lg font-medium text-sm transition-colors flex items-center justify-center gap-2 whitespace-nowrap touch-manipulation"
            >
              <svg className="h-5 w-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Create New Page
            </button>
          </div>

          {/* Status Messages */}
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-2">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-800 dark:text-red-200">Error</p>
                <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
              </div>
            </div>
          )}

          {success && (
            <div className="p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex items-center gap-2">
              <CheckIcon className="h-5 w-5 text-green-600" />
              <p className="text-sm text-green-800 dark:text-green-200">Changes saved successfully!</p>
            </div>
          )}
        </div>
      </div>

      {/* Pages Grid */}
      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <div className="max-w-7xl mx-auto">
          {filteredPages.length === 0 ? (
            <div className="text-center py-12">
              <PhotoIcon className="h-12 w-12 text-zinc-300 dark:text-zinc-700 mx-auto mb-4" />
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                {searchTerm ? 'No pages found matching your search' : 'No category pages found'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-6">
              {filteredPages.map((page) => (
                <div
                  key={page.id}
                  className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden hover:shadow-lg transition-shadow"
                >
                  {/* Hero Image Preview */}
                  <div className="relative h-32 bg-zinc-100 dark:bg-zinc-800">
                    {page.heroImageUrl ? (
                      <img
                        src={page.heroImageUrl}
                        alt={page.displayName}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <PhotoIcon className="h-12 w-12 text-zinc-300 dark:text-zinc-600" />
                      </div>
                    )}
                  </div>

                  {/* Page Info */}
                  <div className="p-4">
                    <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-1">
                      {page.displayName}
                    </h3>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-3">
                      Handle: {page.handle}
                    </p>

                    <div className="space-y-2 mb-4">
                      <div>
                        <p className="text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                          Hero Title
                        </p>
                        <p className="text-sm text-zinc-900 dark:text-zinc-100 line-clamp-1">
                          {page.heroTitle || <span className="text-zinc-400">No title</span>}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                          Hero Description
                        </p>
                        <p className="text-sm text-zinc-600 dark:text-zinc-300 line-clamp-2">
                          {page.heroDescription || <span className="text-zinc-400">No description</span>}
                        </p>
                      </div>
                    </div>

                    <button
                      onClick={() => handleEdit(page)}
                      className="w-full min-h-[44px] py-2 px-4 bg-amber-600 hover:bg-amber-700 active:bg-amber-800 text-white rounded-lg font-medium text-sm transition-colors flex items-center justify-center gap-2 touch-manipulation"
                    >
                      <PencilIcon className="h-4 w-4 flex-shrink-0" />
                      Edit Category
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Edit Modal */}
      {editingPage && (
        <Dialog open={editingPage !== null} onClose={handleCancelEdit} size="5xl">
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle>Edit Category Page</DialogTitle>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                {editingPage.displayName}
              </p>
            </div>
            <button
              onClick={handleCancelEdit}
              className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors flex-shrink-0"
            >
              <XMarkIcon className="h-5 w-5 text-zinc-500" />
            </button>
          </div>

          <DialogBody className="px-0 py-0">
            <div className="p-6 space-y-6">
              {/* Hero Image Preview */}
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                  Hero Image
                </label>
                <div className="relative h-48 bg-zinc-100 dark:bg-zinc-800 rounded-lg overflow-hidden mb-3">
                  {editingPage.heroImageUrl ? (
                    <img
                      src={editingPage.heroImageUrl}
                      alt="Hero preview"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <PhotoIcon className="h-16 w-16 text-zinc-300 dark:text-zinc-600" />
                    </div>
                  )}
                </div>

                {/* Model Selector */}
                <div className="mb-3">
                  <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                    AI Model
                  </label>
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="gpt5-image-mini">GPT-5-image-mini (OpenAI)</option>
                    <option value="gemini">Gemini 2.5 Flash Image (Google)</option>
                  </select>
                </div>

                {/* Prompt Mode Selector */}
                <div className="mb-3">
                  <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                    Prompt Mode
                  </label>
                  <select
                    value={promptMode}
                    onChange={(e) => setPromptMode(e.target.value)}
                    className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="contextual">Contextual (from hero text)</option>
                    <option value="template">Template</option>
                    <option value="custom">Custom Prompt</option>
                  </select>
                </div>

                {/* Template Selector (shown when promptMode === 'template') */}
                {promptMode === 'template' && (
                  <div className="mb-3">
                    <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                      Template
                    </label>
                    <select
                      value={selectedTemplate}
                      onChange={(e) => setSelectedTemplate(e.target.value)}
                      className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                    >
                      <option value="home_barista">Home Barista</option>
                      <option value="espresso_machines">Espresso Machines</option>
                      <option value="grinders">Grinders</option>
                      <option value="single_dose">Single Dose</option>
                      <option value="commercial">Commercial</option>
                      <option value="la_marzocco">La Marzocco</option>
                      <option value="accessories">Accessories</option>
                    </select>
                  </div>
                )}

                {/* Custom Prompt Input (shown when promptMode === 'custom') */}
                {promptMode === 'custom' && (
                  <div className="mb-3">
                    <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                      Custom Prompt
                    </label>
                    <textarea
                      value={customPrompt}
                      onChange={(e) => setCustomPrompt(e.target.value)}
                      rows={3}
                      className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
                      placeholder="Enter custom prompt for image generation..."
                    />
                  </div>
                )}

                <button
                  onClick={() => handleRegenerateHeroImage(
                    editingPage.id,
                    selectedTemplate,
                    selectedModel,
                    promptMode === 'contextual' ? editingPage.heroTitle : null,
                    promptMode === 'contextual' ? editingPage.heroDescription : null,
                    promptMode === 'custom' ? customPrompt : null
                  )}
                  disabled={saving || uploadingFile || (promptMode === 'custom' && !customPrompt.trim())}
                  className="w-full py-2 px-4 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-400 text-white rounded-lg font-medium text-sm transition-colors flex items-center justify-center gap-2"
                >
                  {saving && !uploadingFile ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Regenerating hero image...
                    </>
                  ) : (
                    <>
                      <SparklesIcon className="h-4 w-4" />
                      Regenerate with AI
                    </>
                  )}
                </button>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-2 mb-4">
                  {promptMode === 'contextual' ? (
                    <>
                      {selectedModel === 'gpt5-image-mini'
                        ? 'Uses OpenAI GPT-5-image-mini to generate contextually relevant hero images based on your title and description'
                        : 'Uses Google Gemini 2.5 Flash Image to generate contextually relevant hero images based on your title and description'
                      }
                    </>
                  ) : promptMode === 'template' ? (
                    <>Generates hero image using the <strong>{selectedTemplate.replace(/_/g, ' ')}</strong> template</>
                  ) : (
                    <>Generates hero image using your custom prompt</>
                  )}
                </p>

                {/* Upload and Browse Buttons */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {/* Hidden file input */}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleFileUpload}
                    className="hidden"
                  />

                  {/* Upload Button */}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={saving || uploadingFile}
                    className="w-full min-h-[44px] py-2 px-4 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:bg-blue-400 text-white rounded-lg font-medium text-sm transition-colors flex items-center justify-center gap-2 touch-manipulation"
                  >
                    {uploadingFile ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Uploading image...
                      </>
                    ) : (
                      <>
                        <ArrowUpTrayIcon className="h-4 w-4" />
                        Upload Image
                      </>
                    )}
                  </button>

                  {/* Browse CDN Button */}
                  <button
                    onClick={handleBrowseImages}
                    disabled={saving || uploadingFile}
                    className="w-full min-h-[44px] py-2 px-4 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 disabled:bg-emerald-400 text-white rounded-lg font-medium text-sm transition-colors flex items-center justify-center gap-2 touch-manipulation"
                  >
                    <RectangleStackIcon className="h-4 w-4" />
                    Browse CDN
                  </button>
                </div>
              </div>

              {/* Hero Title */}
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                  Hero Title
                </label>
                <input
                  type="text"
                  value={editingPage.heroTitle}
                  onChange={(e) => setEditingPage({ ...editingPage, heroTitle: e.target.value })}
                  className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  placeholder="Enter hero title..."
                />
              </div>

              {/* Hero Description */}
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                  Hero Description
                </label>
                <textarea
                  value={editingPage.heroDescription}
                  onChange={(e) => setEditingPage({ ...editingPage, heroDescription: e.target.value })}
                  rows={4}
                  className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"
                  placeholder="Enter hero description..."
                />
              </div>

              {/* Divider */}
              <div className="border-t border-zinc-200 dark:border-zinc-800"></div>

              {/* Basic Information Section */}
              <div>
                <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
                  Basic Information
                </h4>
                <div className="space-y-4">
                  {/* Page Title */}
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                      Page Title
                    </label>
                    <input
                      type="text"
                      value={editingPage.title}
                      onChange={(e) => setEditingPage({ ...editingPage, title: e.target.value })}
                      className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                      placeholder="e.g., Single Dose Coffee Grinders"
                    />
                  </div>

                  {/* URL Handle */}
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                      URL Handle
                    </label>
                    <input
                      type="text"
                      value={editingPage.urlHandle}
                      onChange={(e) => setEditingPage({ ...editingPage, urlHandle: e.target.value })}
                      className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                      placeholder="e.g., single-dose-grinders"
                    />
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                      The URL slug for this page
                    </p>
                  </div>
                </div>
              </div>

              {/* Divider */}
              <div className="border-t border-zinc-200 dark:border-zinc-800"></div>

              {/* SEO Section */}
              <div>
                <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
                  SEO Settings
                </h4>
                <div className="space-y-4">
                  {/* SEO Title */}
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                      SEO Title
                    </label>
                    <input
                      type="text"
                      value={editingPage.seoTitle}
                      onChange={(e) => setEditingPage({ ...editingPage, seoTitle: e.target.value })}
                      className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                      placeholder="e.g., Single Dose Coffee Grinders - Zero Retention | iDrinkCoffee"
                    />
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                      {editingPage.seoTitle.length}/60 characters (optimal: 50-60)
                    </p>
                  </div>

                  {/* SEO Description */}
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                      SEO Description
                    </label>
                    <textarea
                      value={editingPage.seoDescription}
                      onChange={(e) => setEditingPage({ ...editingPage, seoDescription: e.target.value })}
                      rows={3}
                      className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"
                      placeholder="e.g., Shop the best single dose coffee grinders in Canada. Featuring Profitec, Mahlkonig, Eureka, and more."
                    />
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                      {editingPage.seoDescription.length}/160 characters (optimal: 150-160)
                    </p>
                  </div>
                </div>
              </div>

              {/* Divider */}
              <div className="border-t border-zinc-200 dark:border-zinc-800"></div>

              {/* Settings Section */}
              <div>
                <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
                  Page Settings
                </h4>
                <div className="space-y-3">
                  {/* Enable Sorting Toggle */}
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editingPage.enableSorting}
                      onChange={(e) => setEditingPage({ ...editingPage, enableSorting: e.target.checked })}
                      className="w-4 h-4 text-amber-600 border-zinc-300 dark:border-zinc-700 rounded focus:ring-amber-500"
                    />
                    <div>
                      <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                        Enable Sorting
                      </span>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">
                        Allow users to sort products on this category page
                      </p>
                    </div>
                  </label>
                </div>
              </div>

              {/* Divider */}
              <div className="border-t border-zinc-200 dark:border-zinc-800"></div>

              {/* Featured Products Section */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                      Featured Products
                    </h4>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                      {editingPage.featuredProducts.length} {editingPage.featuredProducts.length === 1 ? 'product' : 'products'} selected
                    </p>
                  </div>
                  <button
                    onClick={handleOpenProductPicker}
                    className="py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium text-sm transition-colors"
                  >
                    Add Products
                  </button>
                </div>

                {/* Featured Products Grid */}
                {editingPage.featuredProducts.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {editingPage.featuredProducts.map((product, index) => (
                      <div
                        key={product.id}
                        draggable
                        onDragStart={() => handleDragStart(index)}
                        onDragOver={handleDragOver}
                        onDrop={() => handleDrop(index)}
                        className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg overflow-hidden hover:shadow-md transition-shadow cursor-move"
                      >
                        <div className="relative h-24 bg-zinc-100 dark:bg-zinc-900">
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
                        <div className="p-3">
                          <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100 line-clamp-2 mb-2">
                            {product.title}
                          </p>
                          <button
                            onClick={() => handleRemoveFeaturedProduct(product.id)}
                            className="w-full py-1.5 px-3 bg-red-50 hover:bg-red-100 dark:bg-red-900/20 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400 rounded text-xs font-medium transition-colors flex items-center justify-center gap-1"
                          >
                            <XMarkIcon className="h-3 w-3" />
                            Remove
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 bg-zinc-50 dark:bg-zinc-800 rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700">
                    <PhotoIcon className="h-10 w-10 text-zinc-300 dark:text-zinc-600 mx-auto mb-2" />
                    <p className="text-sm text-zinc-500 dark:text-zinc-400">
                      No featured products yet
                    </p>
                  </div>
                )}
              </div>

              {/* Divider */}
              <div className="border-t border-zinc-200 dark:border-zinc-800"></div>

              {/* Sorting Options Section */}
              <div>
                <div className="mb-4">
                  <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    Sorting Options
                  </h4>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                    Define custom sorting/filtering options for this category
                  </p>
                </div>

                {/* Existing Sorting Options */}
                {editingPage.sortingOptions.length > 0 && (
                  <div className="space-y-2 mb-4">
                    {editingPage.sortingOptions.map((option) => {
                      const filterTypeColors = {
                        price: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
                        availability: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
                        vendor: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
                        spec: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
                      };

                      return (
                        <div
                          key={option.id}
                          className="flex items-center gap-3 p-3 bg-zinc-50 dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors"
                        >
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                              {option.label}
                            </p>
                            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                              Value: {option.filterValue}
                            </p>
                          </div>
                          <span className={`px-2 py-1 rounded text-xs font-medium ${filterTypeColors[option.filterType]}`}>
                            {option.filterType}
                          </span>
                          <button
                            onClick={() => handleRemoveSortingOption(option.id)}
                            className="p-1.5 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
                            title="Remove option"
                          >
                            <XMarkIcon className="h-4 w-4 text-red-600 dark:text-red-400" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Add Sorting Option Form */}
                <div className="space-y-3 p-4 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700">
                  {/* Label Input */}
                  <div>
                    <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                      Display Label
                    </label>
                    <input
                      type="text"
                      value={newSortLabel}
                      onChange={(e) => setNewSortLabel(e.target.value)}
                      placeholder="e.g., 💰 Under $1,000"
                      className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                    />
                  </div>

                  {/* Filter Type Selector */}
                  <div>
                    <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                      Filter Type
                    </label>
                    <select
                      value={newSortFilterType}
                      onChange={(e) => {
                        setNewSortFilterType(e.target.value);
                        // Clear all conditional inputs when type changes
                        setNewSortFilterValue('');
                        setSortPriceMin('');
                        setSortPriceMax('');
                        setSortVendor('');
                        setSortSpecName('');
                        setSortSpecValue('');
                      }}
                      className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                    >
                      <option value="price_range">Price Range</option>
                      <option value="vendor">Vendor/Brand</option>
                      <option value="specification">Product Specification</option>
                      <option value="custom">Custom (Advanced)</option>
                    </select>
                  </div>

                  {/* Conditional Inputs Based on Filter Type */}
                  {newSortFilterType === 'price_range' && (
                    <div className="flex gap-2">
                      <div className="flex-1">
                        <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                          Min Price
                        </label>
                        <input
                          type="number"
                          value={sortPriceMin}
                          onChange={(e) => setSortPriceMin(e.target.value)}
                          placeholder="500"
                          className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                        />
                      </div>
                      <div className="flex-1">
                        <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                          Max Price
                        </label>
                        <input
                          type="number"
                          value={sortPriceMax}
                          onChange={(e) => setSortPriceMax(e.target.value)}
                          placeholder="1000"
                          className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                        />
                      </div>
                    </div>
                  )}

                  {newSortFilterType === 'vendor' && (
                    <div>
                      <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                        Vendor/Brand Name
                      </label>
                      <input
                        type="text"
                        value={sortVendor}
                        onChange={(e) => setSortVendor(e.target.value)}
                        placeholder="e.g., La Marzocco, Breville"
                        className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                      />
                    </div>
                  )}

                  {newSortFilterType === 'specification' && (
                    <div className="space-y-2">
                      <div>
                        <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                          Specification Name
                        </label>
                        <input
                          type="text"
                          value={sortSpecName}
                          onChange={(e) => setSortSpecName(e.target.value)}
                          placeholder="e.g., Manufacturer, Burr Type"
                          className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                          Specification Value
                        </label>
                        <input
                          type="text"
                          value={sortSpecValue}
                          onChange={(e) => setSortSpecValue(e.target.value)}
                          placeholder="e.g., La Marzocco, Flat"
                          className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                        />
                      </div>
                    </div>
                  )}

                  {newSortFilterType === 'custom' && (
                    <div>
                      <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                        Custom Filter Value
                      </label>
                      <input
                        type="text"
                        value={newSortFilterValue}
                        onChange={(e) => setNewSortFilterValue(e.target.value)}
                        placeholder="Advanced: Enter exact filter format"
                        className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                      />
                      <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                        ⚠️ Advanced users only. Must match storefront format exactly.
                      </p>
                    </div>
                  )}

                  {/* Live Preview */}
                  {buildFilterValue() && (
                    <div className="p-2 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded text-xs">
                      <span className="font-medium text-blue-700 dark:text-blue-300">Preview:</span>{' '}
                      <code className="text-blue-600 dark:text-blue-400">{buildFilterValue()}</code>
                    </div>
                  )}

                  {/* Add Button */}
                  <button
                    onClick={handleAddSortingOption}
                    disabled={!newSortLabel.trim() || !buildFilterValue()}
                    className="w-full px-4 py-2 bg-amber-600 hover:bg-amber-700 disabled:bg-amber-400 disabled:cursor-not-allowed text-white rounded-lg font-medium text-sm transition-colors"
                  >
                    Add Sorting Option
                  </button>
                </div>
              </div>

              {/* Divider */}
              <div className="border-t border-zinc-200 dark:border-zinc-800"></div>

              {/* Categories Section */}
              <div>
                <div className="mb-4">
                  <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    Categories
                  </h4>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                    Add category sections to this landing page (order matters)
                  </p>
                </div>

                {/* Current Categories List with Reordering */}
                {editingPage.categories && editingPage.categories.length > 0 && (
                  <div className="mb-3 space-y-2">
                    {editingPage.categories.map((category, index) => (
                      <div
                        key={category.id}
                        className="flex items-center gap-2 p-2 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 rounded-lg"
                      >
                        <div className="flex flex-col gap-1">
                          <button
                            onClick={() => handleMoveCategoryUp(index)}
                            disabled={index === 0}
                            className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                            title="Move up"
                          >
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                            </svg>
                          </button>
                          <button
                            onClick={() => handleMoveCategoryDown(index)}
                            disabled={index === editingPage.categories.length - 1}
                            className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                            title="Move down"
                          >
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </button>
                        </div>
                        <span className="flex-1 text-sm text-zinc-700 dark:text-zinc-300">
                          {index + 1}. {category.title || 'Category'}
                        </span>
                        <button
                          onClick={() => handleRemoveCategory(category.id)}
                          className="px-2 py-1 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <MetaobjectPicker
                  type="categories"
                  selectedIds={editingPage.categories?.map(c => c.id) || []}
                  onSelect={handleSelectCategories}
                  isMulti={true}
                  authToken={authToken}
                  placeholder="Select category sections..."
                />
              </div>

              {/* Divider */}
              <div className="border-t border-zinc-200 dark:border-zinc-800"></div>

              {/* Educational Content Section */}
              <div>
                <div className="mb-4">
                  <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    Educational Content
                  </h4>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                    Add educational blocks to this landing page (order matters)
                  </p>
                </div>

                {/* Current Educational Blocks List with Reordering */}
                {editingPage.educationalContent && editingPage.educationalContent.length > 0 && (
                  <div className="mb-3 space-y-2">
                    {editingPage.educationalContent.map((block, index) => (
                      <div
                        key={block.id}
                        className="flex items-center gap-2 p-2 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 rounded-lg"
                      >
                        <div className="flex flex-col gap-1">
                          <button
                            onClick={() => handleMoveEducationalBlockUp(index)}
                            disabled={index === 0}
                            className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                            title="Move up"
                          >
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                            </svg>
                          </button>
                          <button
                            onClick={() => handleMoveEducationalBlockDown(index)}
                            disabled={index === editingPage.educationalContent.length - 1}
                            className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                            title="Move down"
                          >
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </button>
                        </div>
                        <span className="flex-1 text-sm text-zinc-700 dark:text-zinc-300">
                          {index + 1}. {block.title || 'Educational Block'}
                        </span>
                        <button
                          onClick={() => handleRemoveEducationalBlock(block.id)}
                          className="px-2 py-1 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <MetaobjectPicker
                  type="educational-blocks"
                  selectedIds={editingPage.educationalContent?.map(b => b.id) || []}
                  onSelect={handleSelectEducationalBlocks}
                  isMulti={true}
                  authToken={authToken}
                  placeholder="Select educational blocks..."
                />
              </div>

              {/* Divider */}
              <div className="border-t border-zinc-200 dark:border-zinc-800"></div>

              {/* FAQ Section */}
              <div>
                <div className="mb-4">
                  <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    FAQ Section
                  </h4>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                    Set the FAQ section for this landing page (single reference)
                  </p>
                </div>

                <MetaobjectPicker
                  type="faq-sections"
                  selectedIds={editingPage.faqSection ? [editingPage.faqSection.id] : []}
                  onSelect={handleSelectFaqSection}
                  isMulti={false}
                  authToken={authToken}
                  placeholder="Select an FAQ section..."
                  breadcrumbContext={{
                    categoryPageName: editingPage.displayName || editingPage.title
                  }}
                />
              </div>

              {/* Divider */}
              <div className="border-t border-zinc-200 dark:border-zinc-800"></div>

              {/* Comparison Table Section */}
              <div>
                <div className="mb-4">
                  <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    Comparison Table
                  </h4>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                    Set the comparison table for this landing page (single reference)
                  </p>
                </div>

                <MetaobjectPicker
                  type="comparison-tables"
                  selectedIds={editingPage.comparisonTable ? [editingPage.comparisonTable.id] : []}
                  onSelect={handleSelectComparisonTable}
                  isMulti={false}
                  authToken={authToken}
                  placeholder="Select a comparison table..."
                  breadcrumbContext={{
                    categoryPageName: editingPage.displayName || editingPage.title
                  }}
                />
              </div>
            </div>
          </DialogBody>

          <DialogActions className="px-6 py-4 border-t border-zinc-200 dark:border-zinc-700">
            <button
              onClick={handleCancelEdit}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-6 py-2 text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 disabled:bg-amber-400 rounded-lg disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving changes...
                </>
              ) : (
                <>
                  <CheckIcon className="h-4 w-4" />
                  Save Changes
                </>
              )}
            </button>
          </DialogActions>
        </Dialog>
      )}

      {/* Browse CDN Images Modal */}
      {showBrowseModal && (
        <Dialog open={showBrowseModal} onClose={() => setShowBrowseModal(false)} size="5xl">
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle>Browse Shopify CDN Images</DialogTitle>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                Select an existing image from Shopify Files
              </p>
            </div>
            <button
              onClick={() => setShowBrowseModal(false)}
              className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors flex-shrink-0"
            >
              <XMarkIcon className="h-5 w-5 text-zinc-500" />
            </button>
          </div>

          <DialogBody className="px-0 py-0">
            <div className="p-6">
              {loadingFiles ? (
                <LoadingMessage message="Fetching images from Shopify CDN..." className="py-12" />
              ) : shopifyFiles.length === 0 ? (
                <div className="text-center py-12">
                  <PhotoIcon className="h-12 w-12 text-zinc-300 dark:text-zinc-700 mx-auto mb-4" />
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">
                    No images found in Shopify Files
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {shopifyFiles.map((file) => (
                    <button
                      key={file.id}
                      onClick={() => handleSelectShopifyFile(file.id, file.url)}
                      disabled={saving}
                      className="relative group bg-zinc-100 dark:bg-zinc-800 rounded-lg overflow-hidden hover:ring-2 hover:ring-emerald-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <div className="aspect-video w-full">
                        <img
                          src={file.url}
                          alt={file.alt || 'Shopify image'}
                          className="w-full h-full object-cover"
                        />
                      </div>
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center">
                        <CheckIcon className="h-8 w-8 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                      {file.width && file.height && (
                        <div className="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
                          {file.width} × {file.height}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </DialogBody>

          <DialogActions className="px-6 py-4 border-t border-zinc-200 dark:border-zinc-700">
            <button
              onClick={() => setShowBrowseModal(false)}
              className="px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
            >
              Cancel
            </button>
          </DialogActions>
        </Dialog>
      )}

      {/* Product Picker Modal */}
      {showProductPicker && (
        <Dialog open={showProductPicker} onClose={() => setShowProductPicker(false)} size="4xl">
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle>Add Featured Products</DialogTitle>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                Search and select products to feature
              </p>
            </div>
            <button
              onClick={() => setShowProductPicker(false)}
              className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors flex-shrink-0"
            >
              <XMarkIcon className="h-5 w-5 text-zinc-500" />
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

            <div className="p-6 pt-0 overflow-y-auto flex-1">
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
                    const isAdded = editingPage?.featuredProducts.some(p => p.id === product.id);
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
                              onClick={() => handleAddFeaturedProduct(product)}
                              disabled={isAdded}
                              className={`py-2 px-4 rounded-lg font-medium text-sm transition-colors ${
                                isAdded
                                  ? 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400 cursor-not-allowed'
                                  : 'bg-blue-600 hover:bg-blue-700 text-white'
                              }`}
                            >
                              {isAdded ? (
                                <CheckIcon className="h-4 w-4" />
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

          <DialogActions className="px-6 py-4 border-t border-zinc-200 dark:border-zinc-700">
            <button
              onClick={() => setShowProductPicker(false)}
              className="px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
            >
              Done
            </button>
          </DialogActions>
        </Dialog>
      )}

      {/* Create New Page Modal */}
      {showCreateModal && (
        <Dialog open={showCreateModal} onClose={() => setShowCreateModal(false)} size="md">
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle>Create New Landing Page</DialogTitle>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                Create a new category landing page
              </p>
            </div>
            <button
              onClick={() => setShowCreateModal(false)}
              disabled={creating}
              className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors disabled:opacity-50 flex-shrink-0"
            >
              <XMarkIcon className="h-5 w-5 text-zinc-500" />
            </button>
          </div>

          <DialogBody className="px-0 py-0">
            <div className="p-6 space-y-4">
              {/* Page Title */}
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                  Page Title <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newPageTitle}
                  onChange={(e) => setNewPageTitle(e.target.value)}
                  placeholder="e.g., Single Dose Coffee Grinders"
                  disabled={creating}
                  className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 disabled:opacity-50"
                  autoFocus
                />
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                  The display title for this landing page
                </p>
              </div>

              {/* URL Handle */}
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                  URL Handle <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newPageUrlHandle}
                  onChange={(e) => setNewPageUrlHandle(e.target.value)}
                  placeholder="e.g., single-dose-grinders"
                  disabled={creating}
                  className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 disabled:opacity-50"
                />
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                  The URL slug (lowercase, no spaces). Will be normalized automatically.
                </p>
              </div>
            </div>
          </DialogBody>

          <DialogActions className="px-6 py-4 border-t border-zinc-200 dark:border-zinc-700">
            <button
              onClick={() => setShowCreateModal(false)}
              disabled={creating}
              className="px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleCreatePage}
              disabled={creating || !newPageTitle.trim() || !newPageUrlHandle.trim()}
              className="px-6 py-2 text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 disabled:bg-amber-400 rounded-lg disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              {creating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating page...
                </>
              ) : (
                <>
                  <CheckIcon className="h-4 w-4" />
                  Create Page
                </>
              )}
            </button>
          </DialogActions>
        </Dialog>
      )}
    </div>
  );
}
