import React, { useState, useEffect } from 'react';
import { X, Loader2, AlertCircle } from 'lucide-react';
import { Dialog, DialogTitle, DialogBody, DialogActions } from './catalyst/dialog';
import SkeletonForm from './SkeletonForm';
import MarkdownEditor from './MarkdownEditor';
import { shopifyRichTextToMarkdown, markdownToShopifyRichText } from '../utils/richTextConverter';

/**
 * MetaobjectEditor Component
 * Modal for editing existing metaobjects with type-specific form fields
 * Uses Catalyst Dialog component for consistency
 */
export default function MetaobjectEditor({
  metaobjectType,
  metaobject,
  onClose,
  onSave,
  authToken,
}) {
  const [formData, setFormData] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  // Type-specific field configurations
  const fieldConfigs = {
    category_section: [
      { name: 'title', label: 'Title', type: 'text', required: true },
      { name: 'description', label: 'Description', type: 'textarea', required: false },
      { name: 'collection_handle', label: 'Collection Handle', type: 'text', required: false },
      { name: 'color_theme', label: 'Color Theme', type: 'text', required: false },
      { name: 'max_products', label: 'Max Products to Display', type: 'number', required: false, min: 1, max: 20 },
    ],
    educational_block: [
      { name: 'title', label: 'Title', type: 'text', required: true },
      { name: 'content_type', label: 'Content Type', type: 'select', required: true,
        options: [
          { value: 'buying_guide', label: 'Buying Guide' },
          { value: 'how_to', label: 'How-To Guide' },
          { value: 'comparison', label: 'Product Comparison' }
        ]
      },
      { name: 'position', label: 'Display Position', type: 'select', required: true,
        options: [
          { value: 'after_hero', label: 'After Hero (Top of Page)' },
          { value: 'before_products', label: 'Before Products (Middle)' },
          { value: 'after_products', label: 'After Products (Bottom)' }
        ]
      },
      { name: 'content', label: 'Content', type: 'textarea', required: true },
      { name: 'cta_text', label: 'CTA Button Text', type: 'text', required: false },
      { name: 'cta_link', label: 'CTA Button Link', type: 'text', required: false },
      { name: 'video_url', label: 'Video URL (YouTube/Vimeo)', type: 'text', required: false },
    ],
    faq_section: [
      { name: 'title', label: 'Section Title', type: 'text', required: true },
    ],
    comparison_table: [
      { name: 'title', label: 'Table Title', type: 'text', required: true },
    ],
    faq_item: [
      { name: 'question', label: 'Question', type: 'text', required: true },
      { name: 'answer', label: 'Answer', type: 'textarea', required: true },
      { name: 'priority', label: 'Display Priority', type: 'number', required: false },
    ],
    comparison_feature: [
      { name: 'feature_name', label: 'Feature Name', type: 'text', required: true },
      { name: 'feature_key', label: 'Metafield Key', type: 'text', required: true },
      { name: 'display_type', label: 'Display Type', type: 'select', required: true,
        options: [
          { value: 'text', label: 'Text' },
          { value: 'boolean', label: 'Boolean (Yes/No)' },
          { value: 'number', label: 'Number' }
        ]
      },
    ],
  };

  const fields = fieldConfigs[metaobjectType] || [];

  // Initialize form data from metaobject
  useEffect(() => {
    if (metaobject) {
      const initialData = {};
      fields.forEach(field => {
        // Handle both flat structure (metaobject.title) and nested structure (metaobject.fields.title.value)
        let value = '';
        if (metaobject.fields && metaobject.fields[field.name]) {
          // Nested structure from get_metaobject.py
          value = metaobject.fields[field.name].value || '';
        } else {
          // Flat structure
          value = metaobject[field.name] || '';
        }

        // Special handling for rich text fields - convert to markdown
        if ((field.name === 'content' || field.name === 'answer') && value) {
          value = shopifyRichTextToMarkdown(value);
        }

        initialData[field.name] = value;
      });
      setFormData(initialData);
    }
  }, [metaobject]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    // Validate required fields
    const missingRequired = fields.filter(f => f.required && !formData[f.name]);
    if (missingRequired.length > 0) {
      setError(`Missing required fields: ${missingRequired.map(f => f.label).join(', ')}`);
      setLoading(false);
      return;
    }

    try {
      // Prepare data for save, converting markdown back to Shopify rich text JSON
      const saveData = { ...formData };

      // Convert markdown fields back to Shopify rich text JSON format
      ['content', 'answer'].forEach(fieldName => {
        if (saveData[fieldName] && typeof saveData[fieldName] === 'string') {
          saveData[fieldName] = markdownToShopifyRichText(saveData[fieldName]);
        }
      });

      await onSave(saveData);
      setSuccess(true);
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err) {
      setError(err.message || 'Failed to save metaobject');
      setLoading(false);
    }
  };

  return (
    <Dialog open={true} onClose={onClose} size="5xl">
      <div className="flex items-center justify-between">
        <DialogTitle>Edit {metaobjectType.replace(/_/g, ' ')}</DialogTitle>
        <button
          onClick={onClose}
          disabled={loading}
          className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors disabled:opacity-50 flex-shrink-0"
        >
          <X className="h-6 w-6 text-zinc-600 dark:text-zinc-400" />
        </button>
      </div>

      <DialogBody className="px-0 py-0">
        <form onSubmit={handleSubmit} className="space-y-5 sm:space-y-6 p-4 sm:p-6">
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

          {/* Form Fields */}
          <div className="space-y-4 sm:space-y-5">
            {fields.map(field => (
              <div key={field.name}>
                {/* Use MarkdownEditor for rich text fields (content, answer) */}
                {(field.name === 'content' || field.name === 'answer') ? (
                  <MarkdownEditor
                    value={formData[field.name] || ''}
                    onChange={(value) => setFormData(prev => ({ ...prev, [field.name]: value }))}
                    label={field.label}
                    placeholder={`Enter ${field.label.toLowerCase()} in markdown format...`}
                    rows={10}
                    disabled={loading}
                    required={field.required}
                  />
                ) : (
                  <>
                    <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
                      {field.label}
                      {field.required && <span className="text-red-600 dark:text-red-400 ml-1">*</span>}
                    </label>
                    {field.type === 'select' ? (
                      <select
                        name={field.name}
                        value={formData[field.name] || ''}
                        onChange={handleChange}
                        disabled={loading}
                        className="w-full min-h-[44px] px-3 py-2.5 sm:py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                      >
                        <option value="">Select {field.label}</option>
                        {field.options && field.options.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    ) : field.type === 'textarea' ? (
                      <textarea
                        name={field.name}
                        value={formData[field.name] || ''}
                        onChange={handleChange}
                        disabled={loading}
                        rows={4}
                        className="w-full px-3 py-2.5 sm:py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 resize-none"
                      />
                    ) : field.type === 'number' ? (
                      <input
                        type="number"
                        name={field.name}
                        value={formData[field.name] || ''}
                        onChange={handleChange}
                        disabled={loading}
                        min={field.min}
                        max={field.max}
                        step={field.step || 1}
                        className="w-full min-h-[44px] px-3 py-2.5 sm:py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                      />
                    ) : (
                      <input
                        type={field.type}
                        name={field.name}
                        value={formData[field.name] || ''}
                        onChange={handleChange}
                        disabled={loading}
                        className="w-full min-h-[44px] px-3 py-2.5 sm:py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                      />
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        </form>
      </DialogBody>

      <DialogActions className="px-4 sm:px-6 py-3 sm:py-4 border-t border-zinc-200 dark:border-zinc-700">
        <button
          type="button"
          onClick={onClose}
          disabled={loading}
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
