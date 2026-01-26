import React, { useState, useEffect } from 'react';
import { X, Loader2, AlertCircle, Plus, Trash2, Edit2, ChevronDown } from 'lucide-react';
import { Dialog, DialogTitle, DialogBody, DialogActions } from './catalyst/dialog';
import Breadcrumb from './Breadcrumb';
import MarkdownEditor from './MarkdownEditor';
import { shopifyRichTextToMarkdown, markdownToShopifyRichText } from '../utils/richTextConverter';

/**
 * FAQSectionEditor Component
 * Modal for editing an FAQ section and managing its FAQ items
 * Allows add/edit/delete of individual FAQ questions and answers
 */
export default function FAQSectionEditor({
  faqSectionId,
  faqSectionData,
  onClose,
  onSave,
  authToken,
  breadcrumbContext = null, // Optional breadcrumb context: { categoryPageName: string }
}) {
  const [sectionData, setSectionData] = useState({
    title: '',
    description: '',
    items: [],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [editingItemId, setEditingItemId] = useState(null);
  const [expandedItems, setExpandedItems] = useState({});

  // Form state for new/editing item
  const [itemForm, setItemForm] = useState({
    question: '',
    answer: '',
  });

  // Initialize with provided data
  useEffect(() => {
    if (faqSectionData) {
      // Convert rich text from items' answer fields to markdown
      const processedItems = (faqSectionData.items || []).map(item => ({
        ...item,
        answer: shopifyRichTextToMarkdown(item.answer)
      }));

      setSectionData({
        title: faqSectionData.title || '',
        description: faqSectionData.description || '',
        items: processedItems,
      });
    }
  }, [faqSectionData]);

  const resetItemForm = () => {
    setItemForm({ question: '', answer: '' });
    setEditingItemId(null);
  };

  const handleAddItem = () => {
    if (!itemForm.question.trim() || !itemForm.answer.trim()) {
      setError('Question and answer are required');
      return;
    }

    const newItem = {
      id: editingItemId || `temp_${Date.now()}`,
      question: itemForm.question,
      answer: itemForm.answer, // Keep as plain text in state for editing
    };

    if (editingItemId && editingItemId !== 'new') {
      // Update existing item
      setSectionData(prev => ({
        ...prev,
        items: prev.items.map(item => item.id === editingItemId ? newItem : item),
      }));
    } else {
      // Add new item
      setSectionData(prev => ({
        ...prev,
        items: [...prev.items, newItem],
      }));
    }

    resetItemForm();
    setError(null);
  };

  const handleEditItem = (item) => {
    setItemForm({
      question: item.question,
      answer: item.answer,
    });
    setEditingItemId(item.id);
  };

  const handleDeleteItem = (itemId) => {
    setSectionData(prev => ({
      ...prev,
      items: prev.items.filter(item => item.id !== itemId),
    }));
  };

  const handleSubmit = async () => {
    if (!sectionData.title.trim()) {
      setError('Section title is required');
      return;
    }

    if (sectionData.items.length === 0) {
      setError('Add at least one FAQ item');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Prepare data for backend
      const fields = {
        title: sectionData.title,
        description: sectionData.description,
      };

      // Convert markdown answers back to Shopify rich text JSON for backend
      const itemsWithRichText = sectionData.items.map(item => ({
        ...item,
        answer: markdownToShopifyRichText(item.answer)
      }));

      await onSave({
        ...fields,
        items: itemsWithRichText, // Pass items with rich text JSON
      });

      setSuccess(true);
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err) {
      setError(err.message || 'Failed to save FAQ section');
      setLoading(false);
    }
  };

  const toggleItemExpand = (itemId) => {
    setExpandedItems(prev => ({
      ...prev,
      [itemId]: !prev[itemId],
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

    items.push({ label: 'FAQ Section', current: true });
    return items;
  };

  return (
    <Dialog open={true} onClose={onClose} size="5xl">
      <div className="flex items-center justify-between">
        <DialogTitle>Edit FAQ Section</DialogTitle>
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

          {/* Section Title */}
          <div>
            <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
              Section Title <span className="text-red-600 dark:text-red-400">*</span>
            </label>
            <input
              type="text"
              value={sectionData.title}
              onChange={(e) => setSectionData({ ...sectionData, title: e.target.value })}
              placeholder="e.g., Frequently Asked Questions"
              disabled={loading}
              className="w-full min-h-[44px] px-3 py-2.5 sm:py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
          </div>

          {/* Section Description */}
          <div>
            <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
              Section Description
            </label>
            <textarea
              value={sectionData.description}
              onChange={(e) => setSectionData({ ...sectionData, description: e.target.value })}
              placeholder="Optional description for this FAQ section"
              disabled={loading}
              rows={3}
              className="w-full px-3 py-2.5 sm:py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 resize-none"
            />
          </div>

          <div className="border-t border-zinc-200 dark:border-zinc-800"></div>

          {/* FAQ Items Section */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                FAQ Items ({sectionData.items.length})
              </h3>
              {!editingItemId && (
                <button
                  onClick={() => setEditingItemId('new')}
                  disabled={loading}
                  className="w-full sm:w-auto min-h-[36px] px-3 py-1.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded text-xs font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-1 touch-manipulation"
                >
                  <Plus className="h-3 w-3" />
                  Add Item
                </button>
              )}
            </div>

            {/* Add/Edit Item Form */}
            {editingItemId && (
              <div className="mb-4 p-4 bg-zinc-50 dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700">
                <div className="space-y-3 mb-3">
                  <div>
                    <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                      Question
                    </label>
                    <input
                      type="text"
                      value={itemForm.question}
                      onChange={(e) => setItemForm({ ...itemForm, question: e.target.value })}
                      placeholder="Enter question"
                      disabled={loading}
                      className="w-full min-h-[44px] px-3 py-2.5 sm:py-2 bg-white dark:bg-zinc-700 border border-zinc-300 dark:border-zinc-600 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                    />
                  </div>
                  <div>
                    <MarkdownEditor
                      value={itemForm.answer}
                      onChange={(value) => setItemForm({ ...itemForm, answer: value })}
                      label="Answer"
                      placeholder="Enter answer in markdown format..."
                      rows={6}
                      disabled={loading}
                      required={true}
                    />
                  </div>
                </div>
                <div className="flex flex-col sm:flex-row gap-2">
                  <button
                    onClick={handleAddItem}
                    disabled={loading}
                    className="flex-1 min-h-[44px] py-2 px-3 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded text-xs sm:text-sm font-medium transition-colors disabled:opacity-50 touch-manipulation"
                  >
                    {editingItemId === 'new' ? 'Add Item' : 'Update Item'}
                  </button>
                  <button
                    onClick={resetItemForm}
                    disabled={loading}
                    className="flex-1 min-h-[44px] py-2 px-3 bg-zinc-300 dark:bg-zinc-600 hover:bg-zinc-400 active:bg-zinc-500 dark:hover:bg-zinc-500 dark:active:bg-zinc-400 text-zinc-900 dark:text-zinc-100 rounded text-xs sm:text-sm font-medium transition-colors disabled:opacity-50 touch-manipulation"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {/* Items List */}
            {sectionData.items.length === 0 ? (
              <div className="text-center py-8 bg-zinc-50 dark:bg-zinc-800 rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700">
                <p className="text-sm text-zinc-500 dark:text-zinc-400">No FAQ items yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {sectionData.items.map((item) => (
                  <div
                    key={item.id}
                    className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg overflow-hidden hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors"
                  >
                    <button
                      onClick={() => toggleItemExpand(item.id)}
                      className="w-full min-h-[56px] p-3 sm:p-3 flex items-start justify-between hover:bg-zinc-50 active:bg-zinc-100 dark:hover:bg-zinc-700 dark:active:bg-zinc-600 transition-colors touch-manipulation"
                    >
                      <div className="flex-1 text-left min-w-0">
                        <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100 line-clamp-2">
                          {item.question}
                        </p>
                        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 line-clamp-1">
                          {item.answer}
                        </p>
                      </div>
                      <ChevronDown
                        className={`h-4 w-4 text-zinc-400 flex-shrink-0 ml-2 transition-transform ${
                          expandedItems[item.id] ? 'rotate-180' : ''
                        }`}
                      />
                    </button>

                    {expandedItems[item.id] && (
                      <div className="px-3 pb-3 pt-0 space-y-3 border-t border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900">
                        <div>
                          <p className="text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                            Full Answer
                          </p>
                          <p className="text-sm text-zinc-900 dark:text-zinc-100 whitespace-pre-wrap">
                            {item.answer}
                          </p>
                        </div>
                        <div className="flex flex-col sm:flex-row gap-2 pt-2">
                          <button
                            onClick={() => handleEditItem(item)}
                            disabled={loading}
                            className="flex-1 min-h-[44px] py-2 px-3 bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 active:bg-blue-200 dark:hover:bg-blue-900/50 dark:active:bg-blue-900/70 text-blue-600 dark:text-blue-400 rounded text-xs font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-1 touch-manipulation"
                          >
                            <Edit2 className="h-3 w-3" />
                            Edit
                          </button>
                          <button
                            onClick={() => handleDeleteItem(item.id)}
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
    </Dialog>
  );
}
