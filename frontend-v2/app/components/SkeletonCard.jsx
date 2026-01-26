import React from 'react';

/**
 * SkeletonCard Component
 * Reusable skeleton loader for card-based layouts (category page cards, product cards, etc.)
 *
 * @param {string} variant - Card variant: 'category' (default), 'product', 'compact'
 * @param {number} count - Number of skeleton cards to render (default: 1)
 */
export default function SkeletonCard({ variant = 'category', count = 1 }) {
  const cards = Array.from({ length: count }, (_, i) => i);

  if (variant === 'category') {
    return (
      <>
        {cards.map((index) => (
          <div
            key={index}
            className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden"
          >
            {/* Image placeholder with shimmer */}
            <div className="relative h-32 bg-zinc-200 dark:bg-zinc-700 overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/50 dark:via-zinc-500/50 to-transparent animate-shimmer"></div>
            </div>

            {/* Content placeholder */}
            <div className="p-4 space-y-3">
              {/* Title */}
              <div className="h-5 bg-zinc-200 dark:bg-zinc-700 rounded w-3/4 animate-pulse"></div>

              {/* Handle */}
              <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-1/2 animate-pulse"></div>

              {/* Hero Title */}
              <div className="space-y-2 pt-2">
                <div className="h-3 bg-zinc-200 dark:bg-zinc-700 rounded w-1/4 animate-pulse"></div>
                <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-full animate-pulse"></div>
              </div>

              {/* Hero Description */}
              <div className="space-y-2 pt-1">
                <div className="h-3 bg-zinc-200 dark:bg-zinc-700 rounded w-1/3 animate-pulse"></div>
                <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-full animate-pulse"></div>
                <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-4/5 animate-pulse"></div>
              </div>

              {/* Button */}
              <div className="h-9 bg-zinc-200 dark:bg-zinc-700 rounded-lg w-full animate-pulse mt-4"></div>
            </div>
          </div>
        ))}
      </>
    );
  }

  if (variant === 'product') {
    return (
      <>
        {cards.map((index) => (
          <div
            key={index}
            className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg overflow-hidden"
          >
            <div className="flex gap-3 p-3">
              {/* Product Image */}
              <div className="flex-shrink-0 w-24 h-24 bg-zinc-200 dark:bg-zinc-700 rounded overflow-hidden relative">
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/50 dark:via-zinc-500/50 to-transparent animate-shimmer"></div>
              </div>

              {/* Product Info */}
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-full animate-pulse"></div>
                <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-3/4 animate-pulse"></div>
                <div className="h-3 bg-zinc-200 dark:bg-zinc-700 rounded w-1/2 animate-pulse"></div>
                <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-1/3 animate-pulse"></div>
              </div>

              {/* Add Button */}
              <div className="flex-shrink-0">
                <div className="h-9 w-16 bg-zinc-200 dark:bg-zinc-700 rounded-lg animate-pulse"></div>
              </div>
            </div>
          </div>
        ))}
      </>
    );
  }

  if (variant === 'compact') {
    return (
      <>
        {cards.map((index) => (
          <div
            key={index}
            className="flex items-center gap-2 p-2 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 rounded-lg"
          >
            {/* Icon/Number placeholder */}
            <div className="w-6 h-6 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>

            {/* Text content */}
            <div className="flex-1 space-y-1">
              <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-3/4 animate-pulse"></div>
            </div>

            {/* Action button */}
            <div className="w-16 h-7 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
          </div>
        ))}
      </>
    );
  }

  return null;
}
