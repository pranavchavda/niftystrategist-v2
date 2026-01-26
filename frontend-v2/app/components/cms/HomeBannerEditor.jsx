import React, { useState, useEffect } from 'react';
import { X, Loader2, AlertCircle } from 'lucide-react';
import { Dialog, DialogTitle, DialogBody, DialogActions } from '../catalyst/dialog';

/**
 * HomeBannerEditor Component
 * Modal for editing a home page banner
 */
export default function HomeBannerEditor({ banner, onClose, onSave, authToken }) {
  const [formData, setFormData] = useState({
    heading: '',
    text: '',
    cta: '',
    link: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [newImage, setNewImage] = useState(null); // File object
  const [newImagePreview, setNewImagePreview] = useState(null); // Data URL for preview
  const [uploadingImage, setUploadingImage] = useState(false);
  const [uploadedImageId, setUploadedImageId] = useState(null);

  const isPrimary = banner?.banner_type === 'primary' || banner?.type === 'Primary';

  useEffect(() => {
    if (banner) {
      // Handle both nested structure from API and flat structure from list
      setFormData({
        heading: banner.fields?.heading?.value || banner.heading || '',
        text: banner.fields?.text?.value || banner.text || '',
        cta: banner.fields?.cta?.value || banner.cta || '',
        link: banner.fields?.link?.value || banner.link || '',
      });
    }
  }, [banner]);

  const handleImageSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setError('Please select an image file');
      return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      setError('Image must be smaller than 10MB');
      return;
    }

    setNewImage(file);
    setError(null);

    // Create preview
    const reader = new FileReader();
    reader.onloadend = () => {
      setNewImagePreview(reader.result);
    };
    reader.readAsDataURL(file);
  };

  const uploadImage = async () => {
    if (!newImage) return null;

    try {
      setUploadingImage(true);
      setError(null);

      const formData = new FormData();
      formData.append('file', newImage);

      const response = await fetch('/api/cms/upload-image', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to upload image');
      }

      const result = await response.json();
      setUploadedImageId(result.file_id);
      return result.file_id;

    } catch (err) {
      setError(err.message || 'Failed to upload image');
      throw err;
    } finally {
      setUploadingImage(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.heading.trim()) {
      setError('Heading is required');
      return;
    }
    if (!formData.cta.trim()) {
      setError('CTA button text is required');
      return;
    }
    if (!formData.link.trim()) {
      setError('Link URL is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Upload new image if selected
      let imageId = uploadedImageId; // Use already uploaded image if exists
      if (newImage && !uploadedImageId) {
        imageId = await uploadImage();
        if (!imageId) {
          throw new Error('Failed to upload image');
        }
      }

      // Prepare update data
      const updateData = { ...formData };
      if (imageId) {
        updateData.imageId = imageId;
      }

      const response = await fetch(`/api/cms/home-banners/${banner.handle || banner.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify(updateData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to update banner');
      }

      const updatedBanner = await response.json();
      setSuccess(true);

      // Call parent save handler
      if (onSave) {
        onSave(updatedBanner);
      }

      // Close after brief delay
      setTimeout(() => {
        onClose();
      }, 1000);

    } catch (err) {
      setError(err.message || 'Failed to update banner');
      setLoading(false);
    }
  };

  const imageUrl = banner?.fields?.primary_image?.reference?.image?.url || banner?.image_url;
  const imageDimensions = banner?.image_dimensions ||
    (banner?.fields?.primary_image?.reference?.image ?
      `${banner.fields.primary_image.reference.image.width}x${banner.fields.primary_image.reference.image.height}`
      : null);

  return (
    <Dialog open={true} onClose={onClose} size="3xl">
      <div className="flex items-center justify-between">
        <DialogTitle>Edit {isPrimary ? 'Primary' : 'Secondary'} Banner</DialogTitle>
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
                ✓ Successfully updated banner! Closing...
              </p>
            </div>
          )}

          {/* Current Image Preview */}
          {imageUrl && (
            <div className="space-y-2">
              <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100">
                Current Image
              </label>
              <div className={`relative bg-zinc-100 dark:bg-zinc-900 rounded-lg overflow-hidden ${
                isPrimary ? 'aspect-[16/9]' : 'aspect-[5/3]'
              }`}>
                <img
                  src={imageUrl}
                  alt={formData.heading}
                  className="w-full h-full object-cover"
                />
                {imageDimensions && (
                  <div className="absolute top-2 right-2 px-2 py-1 bg-black/60 text-white text-xs rounded">
                    {imageDimensions}
                  </div>
                )}
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Recommended: {isPrimary ? '1609x902px' : '780x468px'}
              </p>
            </div>
          )}

          {/* New Image Upload */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100">
              Upload New Image {newImagePreview && '✓'}
            </label>
            <input
              type="file"
              accept="image/*"
              onChange={handleImageSelect}
              disabled={loading || uploadingImage}
              className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-blue-900/30 dark:file:text-blue-400"
            />
            {newImagePreview && (
              <div className={`relative bg-zinc-100 dark:bg-zinc-900 rounded-lg overflow-hidden ${
                isPrimary ? 'aspect-[16/9]' : 'aspect-[5/3]'
              }`}>
                <img
                  src={newImagePreview}
                  alt="New banner preview"
                  className="w-full h-full object-cover"
                />
                <div className="absolute top-2 left-2 px-2 py-1 bg-green-600 text-white text-xs rounded font-medium">
                  New Image
                </div>
                {uploadingImage && (
                  <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                    <Loader2 className="h-8 w-8 text-white animate-spin" />
                  </div>
                )}
                {uploadedImageId && (
                  <div className="absolute bottom-2 left-2 px-2 py-1 bg-green-600 text-white text-xs rounded font-medium">
                    ✓ Uploaded
                  </div>
                )}
              </div>
            )}
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Supports JPG, PNG, WebP, GIF. Max 10MB. Recommended: {isPrimary ? '1609x902px' : '780x468px'}
            </p>
          </div>

          {/* Heading */}
          <div>
            <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
              Heading <span className="text-red-600 dark:text-red-400">*</span>
            </label>
            <input
              type="text"
              value={formData.heading}
              onChange={(e) => setFormData({ ...formData, heading: e.target.value })}
              placeholder="e.g., Clearance Sale"
              disabled={loading}
              className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              required
            />
          </div>

          {/* Text / Description */}
          <div>
            <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
              Description
            </label>
            <textarea
              value={formData.text}
              onChange={(e) => setFormData({ ...formData, text: e.target.value })}
              placeholder="e.g., Huge savings. Limited Stock"
              rows={3}
              disabled={loading}
              className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
          </div>

          {/* CTA Button Text */}
          <div>
            <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
              CTA Button Text <span className="text-red-600 dark:text-red-400">*</span>
            </label>
            <input
              type="text"
              value={formData.cta}
              onChange={(e) => setFormData({ ...formData, cta: e.target.value })}
              placeholder="e.g., Shop Now"
              disabled={loading}
              className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              required
            />
          </div>

          {/* Link URL */}
          <div>
            <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
              Link URL <span className="text-red-600 dark:text-red-400">*</span>
            </label>
            <input
              type="url"
              value={formData.link}
              onChange={(e) => setFormData({ ...formData, link: e.target.value })}
              placeholder="https://idrinkcoffee.com/collections/..."
              disabled={loading}
              className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 font-mono"
              required
            />
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              Internal links will be automatically cleaned up (domain removed)
            </p>
          </div>

          {/* Info Note */}
          <div className="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
            <p className="text-xs text-blue-700 dark:text-blue-300">
              <strong>Tip:</strong> Images are automatically converted to WebP format and optimized for Shopify. The image will be uploaded when you save the banner.
            </p>
          </div>
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
          disabled={loading || success || uploadingImage}
          className="px-6 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          {uploadingImage ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Uploading Image...
            </>
          ) : loading ? (
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
