import React from 'react';

/**
 * SkeletonForm Component
 * Reusable skeleton loader for form fields and input areas
 *
 * @param {number} fields - Number of form fields to display (default: 4)
 * @param {boolean} showButtons - Whether to show action buttons (default: true)
 * @param {string} variant - Form variant: 'default', 'inline', 'modal'
 */
export default function SkeletonForm({ fields = 4, showButtons = true, variant = 'default' }) {
  const fieldsArray = Array.from({ length: fields }, (_, i) => i);

  if (variant === 'inline') {
    return (
      <div className="flex items-end gap-3">
        {fieldsArray.map((index) => (
          <div key={index} className="flex-1">
            <div className="h-3 bg-zinc-200 dark:bg-zinc-700 rounded w-24 mb-2 animate-pulse"></div>
            <div className="h-10 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
          </div>
        ))}
        {showButtons && (
          <div className="h-10 w-24 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
        )}
      </div>
    );
  }

  if (variant === 'modal') {
    return (
      <div className="space-y-6">
        {/* Title */}
        <div className="space-y-2">
          <div className="h-6 bg-zinc-200 dark:bg-zinc-700 rounded w-1/3 animate-pulse"></div>
          <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-2/3 animate-pulse"></div>
        </div>

        {/* Form fields */}
        <div className="space-y-4">
          {fieldsArray.map((index) => (
            <div key={index}>
              <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-32 mb-2 animate-pulse"></div>
              <div className="h-10 bg-zinc-200 dark:bg-zinc-700 rounded w-full animate-pulse"></div>
            </div>
          ))}
        </div>

        {/* Buttons */}
        {showButtons && (
          <div className="flex justify-end gap-3 pt-4 border-t border-zinc-200 dark:border-zinc-700">
            <div className="h-10 w-24 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
            <div className="h-10 w-32 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
          </div>
        )}
      </div>
    );
  }

  // Default form variant
  return (
    <div className="space-y-5">
      {fieldsArray.map((index) => (
        <div key={index} className="space-y-2">
          {/* Label */}
          <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-32 animate-pulse"></div>

          {/* Input field - alternate between text and textarea heights */}
          {index % 3 === 0 ? (
            <div className="h-24 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
          ) : (
            <div className="h-10 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
          )}
        </div>
      ))}

      {/* Action buttons */}
      {showButtons && (
        <div className="flex justify-end gap-3 pt-6">
          <div className="h-10 w-24 bg-zinc-200 dark:bg-zinc-700 rounded-lg animate-pulse"></div>
          <div className="h-10 w-32 bg-zinc-200 dark:bg-zinc-700 rounded-lg animate-pulse"></div>
        </div>
      )}
    </div>
  );
}
