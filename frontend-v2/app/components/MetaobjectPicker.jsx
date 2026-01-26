import React, { useState, useEffect } from 'react';
import { Loader2, ChevronDown, Edit2, Trash2, Plus } from 'lucide-react';
import { MagnifyingGlassIcon, XMarkIcon } from '@heroicons/react/20/solid';
import MetaobjectEditor from './MetaobjectEditor';
import MetaobjectCreator from './MetaobjectCreator';
import FAQSectionEditor from './FAQSectionEditor';
import ComparisonTableEditor from './ComparisonTableEditor';
import SkeletonTable from './SkeletonTable';
import LoadingMessage from './LoadingMessage';

/**
 * MetaobjectPicker Component with full CRUD
 * Reusable component for selecting metaobjects with search and filtering
 */
export default function MetaobjectPicker({
  type, // 'categories', 'educational-blocks', 'faq-sections', 'comparison-tables'
  selectedIds = [],
  onSelect,
  isMulti = true,
  authToken,
  placeholder = 'Search metaobjects...',
  breadcrumbContext = null, // Optional breadcrumb context to pass to nested editors
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [metaobjects, setMetaobjects] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedMetaobjects, setSelectedMetaobjects] = useState([]);

  // CRUD state
  const [showEditor, setShowEditor] = useState(false);
  const [showCreator, setShowCreator] = useState(false);
  const [editingMetaobject, setEditingMetaobject] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [error, setError] = useState(null);

  // Nested editor state
  const [showNestedEditor, setShowNestedEditor] = useState(false);
  const [editingNestedData, setEditingNestedData] = useState(null);
  const [nestedEditorType, setNestedEditorType] = useState(null); // 'faq' or 'comparison'
  const [nestedLoading, setNestedLoading] = useState(false);

  // Type-to-endpoint mapping
  const typeMap = {
    'categories': '/api/cms/metaobjects/categories',
    'educational-blocks': '/api/cms/metaobjects/educational-blocks',
    'faq-sections': '/api/cms/metaobjects/faq-sections',
    'comparison-tables': '/api/cms/metaobjects/comparison-tables',
  };

  // Type to metaobject type for API calls
  const typeToMetaobjectType = {
    'categories': 'category_section',
    'educational-blocks': 'educational_block',
    'faq-sections': 'faq_section',
    'comparison-tables': 'comparison_table',
  };

  // Preload metaobjects on mount if we have selectedIds (so titles display immediately)
  useEffect(() => {
    if (selectedIds && selectedIds.length > 0) {
      loadMetaobjects();
    }
  }, []); // Only run once on mount

  // Load metaobjects when picker opens (if not already loaded)
  useEffect(() => {
    if (isOpen && metaobjects.length === 0) {
      loadMetaobjects();
    }
  }, [isOpen]);

  // Initialize selected metaobjects
  useEffect(() => {
    setSelectedMetaobjects(selectedIds || []);
  }, [selectedIds]);

  const loadMetaobjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const endpoint = typeMap[type];
      if (!endpoint) {
        console.error(`Unknown metaobject type: ${type}`);
        return;
      }

      const token = authToken || (typeof window !== 'undefined' ? localStorage.getItem('authToken') : null);
      const response = await fetch(endpoint, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to load metaobjects');
      }

      const data = await response.json();
      setMetaobjects(data.metaobjects || []);
    } catch (err) {
      console.error(`Error loading metaobjects:`, err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const filteredMetaobjects = metaobjects.filter(mo =>
    mo.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    mo.handle?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleSelect = (metaobject) => {
    if (isMulti) {
      const newSelected = selectedMetaobjects.includes(metaobject.id)
        ? selectedMetaobjects.filter(id => id !== metaobject.id)
        : [...selectedMetaobjects, metaobject.id];

      setSelectedMetaobjects(newSelected);
      onSelect(newSelected);
    } else {
      setSelectedMetaobjects([metaobject.id]);
      onSelect(metaobject.id);
      setIsOpen(false);
    }
  };

  const handleRemove = (id) => {
    const newSelected = selectedMetaobjects.filter(sid => sid !== id);
    setSelectedMetaobjects(newSelected);
    onSelect(isMulti ? newSelected : null);
  };

  const getSelectedMetaobjectDetails = () => {
    return selectedMetaobjects
      .map(id => metaobjects.find(mo => mo.id === id))
      .filter(Boolean);
  };

  // CRUD handlers
  const handleCreateNew = () => {
    setShowCreator(true);
  };

  const handleEditMetaobject = async (metaobject, e) => {
    e.stopPropagation();

    // Fetch full metaobject data before editing
    try {
      setLoading(true);
      const token = authToken || (typeof window !== 'undefined' ? localStorage.getItem('authToken') : null);

      const response = await fetch(`/api/cms/metaobjects/full?id=${encodeURIComponent(metaobject.id)}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch metaobject details');
      }

      const fullData = await response.json();
      setEditingMetaobject(fullData);
      setShowEditor(true);
    } catch (err) {
      console.error('Error fetching metaobject for edit:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteMetaobject = (metaobject, e) => {
    e.stopPropagation();
    setDeletingId(metaobject.id);
    setShowDeleteConfirm(true);
  };

  const handleEditNestedItems = async (metaobject, e) => {
    e.stopPropagation();

    // Only allow for FAQ sections and comparison tables
    if (type !== 'faq-sections' && type !== 'comparison-tables') {
      return;
    }

    try {
      setNestedLoading(true);
      setError(null);

      // Get auth token from props or localStorage
      const token = authToken || (typeof window !== 'undefined' ? localStorage.getItem('authToken') : null);
      if (!token) {
        setError('Authentication token not found');
        setNestedLoading(false);
        return;
      }

      // Load full metaobject data with nested items
      const response = await fetch(
        `/api/cms/metaobjects/full?id=${encodeURIComponent(metaobject.id)}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Failed to load metaobject details:', response.status, errorText);
        throw new Error(`Failed to load metaobject details (${response.status}): ${errorText}`);
      }

      const fullData = await response.json();
      console.log('Successfully loaded nested data:', fullData);

      // Transform data to match editor expectations
      let transformedData = fullData;

      if (type === 'faq-sections') {
        // Transform FAQ section data
        const questions = fullData.fields?.questions?.references || [];
        transformedData = {
          id: fullData.id,
          title: fullData.fields?.title?.value || '',
          description: fullData.fields?.description?.value || '',
          items: questions.map(q => ({
            id: q.id,
            question: q.fields?.question?.value || '',
            answer: q.fields?.answer?.value || '',
          }))
        };
        setNestedEditorType('faq');
        setEditingNestedData(transformedData);
        setShowNestedEditor(true);
      } else if (type === 'comparison-tables') {
        // Transform comparison table data
        const features = fullData.fields?.features?.references || [];

        // Parse products from JSON string value
        let products = [];
        if (fullData.fields?.products?.value) {
          try {
            products = JSON.parse(fullData.fields.products.value);
          } catch (e) {
            console.error('Failed to parse products:', e);
          }
        }

        transformedData = {
          id: fullData.id,
          fields: {
            title: { value: fullData.fields?.title?.value || '' },
            features: {
              references: features.map(f => ({
                id: f.id,
                fields: {
                  feature_name: { value: f.fields?.feature_name?.value || '' },
                  feature_key: { value: f.fields?.feature_key?.value || '' },
                  display_type: { value: f.fields?.display_type?.value || 'text' }
                }
              }))
            },
            products: { value: JSON.stringify(products) }
          }
        };
        setNestedEditorType('comparison');
        setEditingNestedData(transformedData);
        setShowNestedEditor(true);
      }
    } catch (err) {
      console.error('Error loading nested data:', err);
      setError(err.message);
    } finally {
      setNestedLoading(false);
    }
  };

  const confirmDelete = async () => {
    if (!deletingId) return;

    setDeleteLoading(true);
    setError(null);

    try {
      const metaobjectType = typeToMetaobjectType[type];
      const token = authToken || (typeof window !== 'undefined' ? localStorage.getItem('authToken') : null);
      const response = await fetch(
        `/api/cms/metaobjects?id=${encodeURIComponent(deletingId)}&type=${metaobjectType}`,
        {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to delete metaobject`);
      }

      // Remove from local state
      setMetaobjects(prev => prev.filter(m => m.id !== deletingId));

      // Remove from selected if present
      if (selectedMetaobjects.includes(deletingId)) {
        const newSelected = selectedMetaobjects.filter(id => id !== deletingId);
        setSelectedMetaobjects(newSelected);
        onSelect(newSelected);
      }

      setShowDeleteConfirm(false);
      setDeletingId(null);
    } catch (err) {
      console.error('Error deleting metaobject:', err);
      setError(err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleSaveEdit = async (updatedData) => {
    if (!editingMetaobject) return;

    try {
      // Get auth token from props or localStorage
      const token = authToken || (typeof window !== 'undefined' ? localStorage.getItem('authToken') : null);
      if (!token) {
        throw new Error('Authentication token not found');
      }

      const response = await fetch(
        `/api/cms/metaobjects?id=${encodeURIComponent(editingMetaobject.id)}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            type: typeToMetaobjectType[type],
            fields: updatedData
          })
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to update metaobject`);
      }

      const result = await response.json();

      // Update in local state
      setMetaobjects(prev =>
        prev.map(m => m.id === editingMetaobject.id ? result : m)
      );

      setShowEditor(false);
      setEditingMetaobject(null);
    } catch (err) {
      console.error('Error updating metaobject:', err);
      throw err;
    }
  };

  const handleCreated = (newMetaobject) => {
    // Add to list
    setMetaobjects(prev => [newMetaobject, ...prev]);

    // Auto-select if in multiple mode
    if (isMulti) {
      const newSelected = [...selectedMetaobjects, newMetaobject.id];
      setSelectedMetaobjects(newSelected);
      onSelect(newSelected);
    } else {
      setSelectedMetaobjects([newMetaobject.id]);
      onSelect([newMetaobject.id]);
    }

    setShowCreator(false);
  };

  const handleSaveNestedData = async (updatedData) => {
    if (!editingNestedData) return;

    try {
      // Get auth token from props or localStorage
      const token = authToken || (typeof window !== 'undefined' ? localStorage.getItem('authToken') : null);
      if (!token) {
        setError('Authentication token not found');
        return;
      }

      // Transform data based on type - only send the parent fields, not nested items
      let fieldsToSend = {};

      if (type === 'faq-sections') {
        // For FAQ sections, only send title and description
        // Nested items are handled separately
        fieldsToSend = {
          title: updatedData.title,
          description: updatedData.description
        };
      } else if (type === 'comparison-tables') {
        // For comparison tables, only send title and description
        fieldsToSend = {
          title: updatedData.title,
          description: updatedData.description
        };
      } else {
        // For other types, send all fields
        fieldsToSend = updatedData;
      }

      const response = await fetch(
        `/api/cms/metaobjects?id=${encodeURIComponent(editingNestedData.id)}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            type: typeToMetaobjectType[type],
            fields: fieldsToSend
          })
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Save error response:', response.status, errorText);
        let errorMsg = 'Failed to save nested data';
        try {
          const errorData = JSON.parse(errorText);
          errorMsg = errorData.detail || JSON.stringify(errorData);
        } catch (e) {
          errorMsg = errorText;
        }
        throw new Error(errorMsg);
      }

      const result = await response.json();

      // Update in local state
      setMetaobjects(prev =>
        prev.map(m => m.id === editingNestedData.id ? result : m)
      );

      setShowNestedEditor(false);
      setEditingNestedData(null);
      setNestedEditorType(null);
    } catch (err) {
      console.error('Error saving nested data:', err);
      setError(err.message);
      throw err;
    }
  };

  const selectedDetails = getSelectedMetaobjectDetails();
  const displayText = selectedDetails.length === 0
    ? placeholder
    : isMulti
    ? `${selectedDetails.length} selected`
    : selectedDetails[0]?.title || placeholder;

  return (
    <>
      <div className="relative">
        {/* Trigger Button */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full min-h-[44px] px-3 py-2.5 sm:py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm text-left focus:outline-none focus:ring-2 focus:ring-amber-500 flex items-center justify-between touch-manipulation"
        >
          <span className="text-zinc-700 dark:text-zinc-300 truncate pr-2">{displayText}</span>
          <ChevronDown className={`h-4 w-4 flex-shrink-0 text-zinc-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {/* Dropdown Menu */}
        {isOpen && (
          <div className="fixed sm:absolute inset-x-0 bottom-0 sm:top-full sm:left-0 sm:right-0 sm:inset-x-auto sm:bottom-auto mt-0 sm:mt-1 bg-white dark:bg-zinc-800 border-t sm:border border-zinc-300 dark:border-zinc-700 rounded-t-2xl sm:rounded-lg shadow-2xl sm:shadow-lg z-50 max-h-[80vh] sm:max-h-96 flex flex-col">
            {/* Mobile drag handle */}
            <div className="sm:hidden flex justify-center pt-2 pb-1">
              <div className="w-12 h-1 bg-zinc-300 dark:bg-zinc-600 rounded-full"></div>
            </div>

            {/* Search Input */}
            <div className="p-3 sm:p-3 border-b border-zinc-200 dark:border-zinc-700 flex-shrink-0">
              <div className="relative">
                <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 sm:h-4 sm:w-4 text-zinc-400" />
                <input
                  type="text"
                  placeholder="Search..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 sm:pl-9 pr-3 py-2.5 sm:py-2 bg-zinc-50 dark:bg-zinc-700 border border-zinc-200 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 min-h-[44px] sm:min-h-0"
                  autoFocus
                />
              </div>
            </div>

            {/* Error message */}
            {error && (
              <div className="p-3 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border-b border-zinc-200 dark:border-zinc-700">
                {error}
              </div>
            )}

            {/* Metaobjects List */}
            <div className="flex-1 overflow-auto">
              {loading ? (
                <LoadingMessage message="Fetching metaobject details..." variant="default" className="py-8" />
              ) : filteredMetaobjects.length === 0 ? (
                <div className="p-6 text-center text-sm text-zinc-500 dark:text-zinc-400">
                  {metaobjects.length === 0 ? 'No metaobjects available' : 'No results found'}
                </div>
              ) : (
                <div className="p-2">
                  {filteredMetaobjects.map((metaobject) => {
                    const isSelected = selectedMetaobjects.includes(metaobject.id);

                    return (
                      <div
                        key={metaobject.id}
                        className="group relative mb-1 rounded hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors"
                      >
                        <button
                          onClick={() => handleSelect(metaobject)}
                          className={`w-full text-left px-3 py-3 sm:py-2 rounded text-sm transition-colors min-h-[48px] sm:min-h-0 touch-manipulation ${
                            isSelected
                              ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-900 dark:text-amber-100'
                              : 'text-zinc-900 dark:text-zinc-100'
                          }`}
                        >
                          <div className="font-medium">{metaobject.title}</div>
                          <div className="text-xs text-zinc-500 dark:text-zinc-400">
                            {renderMetaobjectDescription(metaobject, type)}
                          </div>
                          {isSelected && (
                            <div className="text-xs text-amber-600 dark:text-amber-400 mt-1">✓ Selected</div>
                          )}
                        </button>

                        {/* Action buttons on hover */}
                        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1 opacity-0 sm:group-hover:opacity-100 transition-opacity">
                          {(type === 'faq-sections' || type === 'comparison-tables') && (
                            <button
                              onClick={(e) => handleEditNestedItems(metaobject, e)}
                              disabled={nestedLoading}
                              className="p-2 sm:p-1.5 text-zinc-400 hover:text-purple-600 hover:bg-purple-50 active:bg-purple-100 dark:hover:bg-purple-900/30 dark:active:bg-purple-900/50 rounded transition-colors disabled:opacity-50 touch-manipulation"
                              title="Edit items"
                            >
                              {nestedLoading ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                                </svg>
                              )}
                            </button>
                          )}
                          <button
                            onClick={(e) => handleEditMetaobject(metaobject, e)}
                            className="p-2 sm:p-1.5 text-zinc-400 hover:text-blue-600 hover:bg-blue-50 active:bg-blue-100 dark:hover:bg-blue-900/30 dark:active:bg-blue-900/50 rounded transition-colors touch-manipulation"
                            title="Edit"
                          >
                            <Edit2 className="h-4 w-4" />
                          </button>
                          <button
                            onClick={(e) => handleDeleteMetaobject(metaobject, e)}
                            className="p-2 sm:p-1.5 text-zinc-400 hover:text-red-600 hover:bg-red-50 active:bg-red-100 dark:hover:bg-red-900/30 dark:active:bg-red-900/50 rounded transition-colors touch-manipulation"
                            title="Delete"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Footer with Create button */}
            <div className="p-3 sm:p-3 border-t border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 flex-shrink-0">
              <button
                onClick={handleCreateNew}
                className="w-full min-h-[44px] py-2 px-3 text-sm font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 active:bg-blue-100 dark:hover:bg-blue-900/30 dark:active:bg-blue-900/50 rounded-lg transition-colors flex items-center justify-center gap-2 touch-manipulation"
              >
                <Plus className="h-4 w-4 flex-shrink-0" />
                Create New
              </button>
            </div>
          </div>
        )}

        {/* Selected Tags */}
        {isMulti && selectedDetails.length > 0 && (
          <div className="mt-3 sm:mt-2 flex flex-wrap gap-2">
            {selectedDetails.map((metaobject) => (
              <div
                key={metaobject.id}
                className="inline-flex items-center gap-2 px-3 py-1 bg-amber-100 dark:bg-amber-900/30 text-amber-900 dark:text-amber-100 rounded-full text-xs"
              >
                <span className="font-medium">{metaobject.title}</span>
                <button
                  onClick={() => handleRemove(metaobject.id)}
                  className="hover:opacity-70 active:opacity-50 transition-opacity touch-manipulation min-w-[24px] min-h-[24px] flex items-center justify-center -mr-1"
                >
                  <XMarkIcon className="h-4 w-4 sm:h-3 sm:w-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Single Selection Display */}
        {!isMulti && selectedDetails.length > 0 && (
          <div className="mt-2 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-amber-900 dark:text-amber-100 text-sm">
                  {selectedDetails[0].title}
                </p>
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                  {renderMetaobjectDescription(selectedDetails[0], type)}
                </p>
              </div>
              <button
                onClick={() => handleRemove(selectedDetails[0].id)}
                className="p-1 hover:bg-amber-200 dark:hover:bg-amber-900/40 rounded transition-colors"
              >
                <XMarkIcon className="h-4 w-4 text-amber-600 dark:text-amber-400" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-zinc-900 rounded-lg shadow-xl max-w-md w-full">
            <div className="p-6">
              <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                Confirm Deletion
              </h3>
              <p className="text-zinc-600 dark:text-zinc-400 mb-4">
                Are you sure you want to delete this metaobject? This action cannot be undone.
              </p>

              {error && (
                <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                  <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
                </div>
              )}

              <div className="flex justify-end gap-3">
                <button
                  onClick={() => {
                    setShowDeleteConfirm(false);
                    setDeletingId(null);
                    setError(null);
                  }}
                  disabled={deleteLoading}
                  className="px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmDelete}
                  disabled={deleteLoading}
                  className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                >
                  {deleteLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Deleting...
                    </>
                  ) : (
                    'Delete'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Editor Modal */}
      {showEditor && editingMetaobject && (
        <MetaobjectEditor
          metaobjectType={typeToMetaobjectType[type]}
          metaobject={editingMetaobject}
          onClose={() => {
            setShowEditor(false);
            setEditingMetaobject(null);
          }}
          onSave={handleSaveEdit}
          authToken={authToken}
        />
      )}

      {/* Creator Modal */}
      {showCreator && (
        <MetaobjectCreator
          metaobjectType={typeToMetaobjectType[type]}
          onClose={() => setShowCreator(false)}
          onCreate={handleCreated}
          authToken={authToken}
        />
      )}

      {/* Nested Editors */}
      {showNestedEditor && editingNestedData && nestedEditorType === 'faq' && (
        <FAQSectionEditor
          faqSectionId={editingNestedData.id}
          faqSectionData={editingNestedData}
          onClose={() => {
            setShowNestedEditor(false);
            setEditingNestedData(null);
            setNestedEditorType(null);
          }}
          onSave={handleSaveNestedData}
          authToken={authToken}
          breadcrumbContext={breadcrumbContext}
        />
      )}

      {showNestedEditor && editingNestedData && nestedEditorType === 'comparison' && (
        <ComparisonTableEditor
          comparisonTableId={editingNestedData.id}
          comparisonTableData={editingNestedData}
          onClose={() => {
            setShowNestedEditor(false);
            setEditingNestedData(null);
            setNestedEditorType(null);
          }}
          onSave={handleSaveNestedData}
          authToken={authToken}
          breadcrumbContext={breadcrumbContext}
        />
      )}
    </>
  );
}

/**
 * Helper function to render description based on metaobject type
 */
function renderMetaobjectDescription(metaobject, type) {
  switch (type) {
    case 'categories':
      return metaobject.description || metaobject.collectionHandle || 'No description';
    case 'educational-blocks':
      return metaobject.contentType ? `Type: ${metaobject.contentType}` : 'No content type';
    case 'faq-sections':
      return `${metaobject.questionCount || 0} question${metaobject.questionCount !== 1 ? 's' : ''}`;
    case 'comparison-tables':
      return `${metaobject.productCount || 0} product${metaobject.productCount !== 1 ? 's' : ''}, ${metaobject.featureCount || 0} feature${metaobject.featureCount !== 1 ? 's' : ''}`;
    default:
      return metaobject.handle || 'Metaobject';
  }
}
