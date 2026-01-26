import React from 'react';
import { PencilIcon, PhotoIcon } from '@heroicons/react/20/solid';

/**
 * HomeBannerCard Component
 * Displays a preview card for a home page banner
 */
export default function HomeBannerCard({ banner, onEdit }) {
  const isPrimary = banner.type === 'Primary';

  return (
    <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-hidden hover:shadow-md transition-shadow">
      {/* Banner Type Badge */}
      <div className="px-4 py-2 bg-zinc-50 dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-1 rounded text-xs font-medium ${
            isPrimary
              ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
              : 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400'
          }`}>
            {banner.type}
          </span>
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            {banner.image_dimensions || 'No image'}
          </span>
        </div>
        <button
          onClick={() => onEdit(banner)}
          className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors"
        >
          <PencilIcon className="h-3 w-3" />
          Edit
        </button>
      </div>

      {/* Banner Image */}
      <div className={`relative bg-zinc-100 dark:bg-zinc-900 ${
        isPrimary ? 'aspect-[16/9]' : 'aspect-[5/3]'
      }`}>
        {banner.image_url ? (
          <img
            src={banner.image_url}
            alt={banner.heading}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <PhotoIcon className="h-16 w-16 text-zinc-300 dark:text-zinc-600" />
          </div>
        )}
        {/* Overlay with banner info */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent flex flex-col justify-end p-4">
          <h3 className="text-white font-bold text-lg mb-1">{banner.heading}</h3>
          {banner.text && (
            <p className="text-white/90 text-sm line-clamp-2">{banner.text}</p>
          )}
        </div>
      </div>

      {/* Banner Details */}
      <div className="px-4 py-3 space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">CTA:</span>
          <span className="px-2 py-0.5 bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400 rounded text-xs font-medium">
            {banner.cta}
          </span>
        </div>
        <div className="flex items-start gap-2">
          <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400 flex-shrink-0">Link:</span>
          <a
            href={banner.link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline truncate"
          >
            {banner.link}
          </a>
        </div>
        <div className="text-xs text-zinc-500 dark:text-zinc-400 font-mono">
          {banner.handle}
        </div>
      </div>
    </div>
  );
}
