import React from 'react';

/**
 * SkeletonText Component
 * Reusable skeleton loader for text content (paragraphs, headings, etc.)
 *
 * @param {number} lines - Number of text lines to display (default: 3)
 * @param {string} variant - Text variant: 'heading', 'paragraph', 'mixed'
 * @param {string} className - Additional CSS classes
 */
export default function SkeletonText({ lines = 3, variant = 'paragraph', className = '' }) {
  const linesArray = Array.from({ length: lines }, (_, i) => i);

  if (variant === 'heading') {
    return (
      <div className={`space-y-3 ${className}`}>
        {linesArray.map((index) => (
          <div
            key={index}
            className={`h-7 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse ${
              index === 0 ? 'w-3/4' : index === 1 ? 'w-2/3' : 'w-1/2'
            }`}
          ></div>
        ))}
      </div>
    );
  }

  if (variant === 'mixed') {
    return (
      <div className={`space-y-4 ${className}`}>
        {/* Heading */}
        <div className="h-7 bg-zinc-200 dark:bg-zinc-700 rounded w-1/2 animate-pulse"></div>

        {/* Paragraph lines */}
        <div className="space-y-2">
          {linesArray.map((index) => (
            <div
              key={index}
              className={`h-4 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse ${
                index === linesArray.length - 1 ? 'w-4/5' : 'w-full'
              }`}
            ></div>
          ))}
        </div>
      </div>
    );
  }

  // Default paragraph variant
  return (
    <div className={`space-y-2 ${className}`}>
      {linesArray.map((index) => (
        <div
          key={index}
          className={`h-4 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse ${
            index === linesArray.length - 1 ? 'w-5/6' : 'w-full'
          }`}
        ></div>
      ))}
    </div>
  );
}
