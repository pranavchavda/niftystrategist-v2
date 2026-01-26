import React, { useState } from 'react';
import { X, Loader2, AlertCircle } from 'lucide-react';
import { Dialog, DialogTitle, DialogBody, DialogActions } from './catalyst/dialog';

/**
 * MetaobjectCreator Component
 * Modal for creating new metaobjects with type-specific form fields
 * Uses Catalyst Dialog component for consistency
 */
export default function MetaobjectCreator({
  metaobjectType,
  onClose,
  onCreate,
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
    ],
    educational_block: [
      { name: 'title', label: 'Title', type: 'text', required: true },
      { name: 'content', label: 'Content', type: 'textarea', required: true },
      { name: 'content_type', label: 'Content Type', type: 'text', required: false },
    ],
    faq_section: [
      { name: 'title', label: 'Title', type: 'text', required: true },
      { name: 'description', label: 'Description', type: 'textarea', required: false },
      { name: '_faq_note', label: 'Note', type: 'text', required: false, disabled: true, value: 'Items can be added after creation' },
    ],
    comparison_table: [
      { name: 'title', label: 'Title', type: 'text', required: true },
      { name: 'description', label: 'Description', type: 'textarea', required: false },
    ],
    faq_item: [
      { name: 'question', label: 'Question', type: 'text', required: true },
      { name: 'answer', label: 'Answer', type: 'textarea', required: true },
    ],
    comparison_feature: [
      { name: 'name', label: 'Feature Name', type: 'text', required: true },
      { name: 'description', label: 'Description', type: 'textarea', required: false },
    ],
  };

  const fields = fieldConfigs[metaobjectType] || [];

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
      // Get auth token from props or localStorage
      const token = authToken || (typeof window !== 'undefined' ? localStorage.getItem('authToken') : null);
      if (!token) {
        throw new Error('Authentication token not found');
      }

      // For FAQ sections, we need to create them with at least one item
      // because Shopify requires the questions field to not be empty
      let fieldsToCreate = { ...formData };

      // Filter out any internal fields (starting with _)
      Object.keys(fieldsToCreate).forEach(key => {
        if (key.startsWith('_')) {
          delete fieldsToCreate[key];
        }
      });

      // Create metaobject (backend handles multi-step creation for FAQ/comparison tables)
      const response = await fetch('/api/cms/metaobjects/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          type: metaobjectType,
          fields: fieldsToCreate
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to create metaobject');
      }

      const finalResult = await response.json();

      setSuccess(true);

      // Notify parent of new metaobject
      setTimeout(() => {
        onCreate(finalResult);
      }, 1000);
    } catch (err) {
      setError(err.message || 'Failed to create metaobject');
      setLoading(false);
    }
  };

  return (
    <Dialog open={true} onClose={onClose} size="5xl">
      <div className="flex items-center justify-between">
        <DialogTitle>Create New {metaobjectType.replace(/_/g, ' ')}</DialogTitle>
        <button
          onClick={onClose}
          disabled={loading}
          className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors disabled:opacity-50 flex-shrink-0"
        >
          <X className="h-6 w-6 text-zinc-600 dark:text-zinc-400" />
        </button>
      </div>

      <DialogBody className="px-0 py-0">
        <form onSubmit={handleSubmit} className="space-y-6 p-6">
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
                Successfully created! Closing...
              </p>
            </div>
          )}

          {/* Form Fields */}
          <div className="space-y-5">
            {fields.map(field => (
              <div key={field.name}>
                <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
                  {field.label}
                  {field.required && <span className="text-red-600 dark:text-red-400">*</span>}
                </label>
                {field.type === 'textarea' ? (
                  <textarea
                    name={field.name}
                    value={formData[field.name] || ''}
                    onChange={handleChange}
                    disabled={loading}
                    rows={4}
                    className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 resize-none"
                  />
                ) : (
                  <input
                    type={field.type}
                    name={field.name}
                    value={formData[field.name] || ''}
                    onChange={handleChange}
                    disabled={loading}
                    className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  />
                )}
              </div>
            ))}
          </div>
        </form>
      </DialogBody>

      <DialogActions className="px-6 py-4 border-t border-zinc-200 dark:border-zinc-700">
        <button
          type="button"
          onClick={onClose}
          disabled={loading}
          className="px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg disabled:opacity-50 transition-colors"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={loading || success}
          className="px-6 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating...
            </>
          ) : success ? (
            <>
              ✓ Created
            </>
          ) : (
            'Create'
          )}
        </button>
      </DialogActions>
    </Dialog>
  );
}
