import React from 'react';
import { Loader2 } from 'lucide-react';

/**
 * LoadingMessage Component
 * Context-aware loading message with spinner and customizable text
 *
 * @param {string} message - Loading message to display
 * @param {string} variant - Display variant: 'default', 'inline', 'minimal'
 * @param {string} className - Additional CSS classes
 */
export default function LoadingMessage({
  message = 'Loading...',
  variant = 'default',
  className = ''
}) {
  if (variant === 'inline') {
    return (
      <div className={`flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400 ${className}`}>
        <Loader2 className="h-4 w-4 animate-spin text-amber-600" />
        <span>{message}</span>
      </div>
    );
  }

  if (variant === 'minimal') {
    return (
      <div className={`flex items-center justify-center ${className}`}>
        <Loader2 className="h-5 w-5 animate-spin text-amber-600" />
      </div>
    );
  }

  // Default centered variant
  return (
    <div className={`flex items-center justify-center h-full ${className}`}>
      <div className="text-center">
        <Loader2 className="h-8 w-8 animate-spin text-amber-600 mx-auto mb-4" />
        <p className="text-sm text-zinc-500 dark:text-zinc-400">{message}</p>
      </div>
    </div>
  );
}
