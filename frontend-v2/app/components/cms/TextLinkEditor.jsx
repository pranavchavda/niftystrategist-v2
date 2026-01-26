import React, { useState, useEffect } from 'react';
import { X, Loader2, AlertCircle } from 'lucide-react';
import { Dialog, DialogTitle, DialogBody, DialogActions } from '../catalyst/dialog';

/**
 * TextLinkEditor Component
 * Modal for editing a text_link metaobject (used in header banner)
 */
export default function TextLinkEditor({ textLink, position, onClose, onSave, authToken }) {
  const [formData, setFormData] = useState({
    link_text: '',
    link_location: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (textLink) {
      setFormData({
        link_text: textLink.link_text || '',
        link_location: textLink.link_location || '',
      });
    }
  }, [textLink]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.link_text.trim()) {
      setError('Link text is required');
      return;
    }
    if (!formData.link_location.trim()) {
      setError('Link location is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`/api/cms/text-links/${textLink.handle || textLink.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to update text link');
      }

      const updatedLink = await response.json();
      setSuccess(true);

      // Call parent save handler
      if (onSave) {
        onSave(updatedLink);
      }

      // Close after brief delay
      setTimeout(() => {
        onClose();
      }, 1000);

    } catch (err) {
      setError(err.message || 'Failed to update text link');
      setLoading(false);
    }
  };

  const positionLabel = position ? position.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Text Link';

  return (
    <Dialog open={true} onClose={onClose} size="2xl">
      <div className="flex items-center justify-between">
        <DialogTitle>Edit {positionLabel}</DialogTitle>
        <button
          onClick={onClose}
          disabled={loading}
          className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors disabled:opacity-50"
        >
          <X className="h-6 w-6 text-zinc-600 dark:text-zinc-400" />
        </button>
      </div>

      <DialogBody>
        <form onSubmit={handleSubmit} className="space-y-6">
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
                ✓ Successfully updated! Closing...
              </p>
            </div>
          )}

          {/* Link Text */}
          <div>
            <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
              Link Text <span className="text-red-600 dark:text-red-400">*</span>
            </label>
            <input
              type="text"
              value={formData.link_text}
              onChange={(e) => setFormData({ ...formData, link_text: e.target.value })}
              placeholder="e.g., FREE Shipping Over $75*"
              disabled={loading}
              className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              required
            />
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              This is what visitors will see in the header
            </p>
          </div>

          {/* Link Location */}
          <div>
            <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
              Link Location <span className="text-red-600 dark:text-red-400">*</span>
            </label>
            <input
              type="text"
              value={formData.link_location}
              onChange={(e) => setFormData({ ...formData, link_location: e.target.value })}
              placeholder="/pages/shipping-and-returns"
              disabled={loading}
              className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 font-mono"
              required
            />
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              Use relative paths for internal links (e.g., /pages/shipping) or full URLs for external links
            </p>
          </div>

          {/* Info Note */}
          <div className="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
            <p className="text-xs text-blue-700 dark:text-blue-300">
              <strong>Tip:</strong> Internal links will be automatically cleaned up. If you paste "https://idrinkcoffee.com/collections/espresso", it will be saved as "/collections/espresso".
            </p>
          </div>

          {textLink?.has_image && (
            <div className="p-3 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
              <p className="text-xs text-purple-700 dark:text-purple-300">
                This link has an image/icon attached (likely the country selector flag).
              </p>
            </div>
          )}
        </form>
      </DialogBody>

      <DialogActions>
        <button
          type="button"
          onClick={onClose}
          disabled={loading || success}
          className="px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg disabled:opacity-50 transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          onClick={handleSubmit}
          disabled={loading || success}
          className="px-6 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : success ? (
            '✓ Saved'
          ) : (
            'Save Changes'
          )}
        </button>
      </DialogActions>
    </Dialog>
  );
}
