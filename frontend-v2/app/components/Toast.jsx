import React, { useEffect } from 'react';
import { CheckCircleIcon, XMarkIcon } from '@heroicons/react/20/solid';

/**
 * Toast Component
 * Success notification with auto-dismiss
 *
 * @param {string} message - The success message to display
 * @param {boolean} show - Whether to show the toast
 * @param {function} onClose - Callback when toast is closed
 * @param {number} duration - Auto-dismiss duration in milliseconds (default: 3000)
 */
export default function Toast({ message, show, onClose, duration = 3000 }) {
  useEffect(() => {
    if (show && duration > 0) {
      const timer = setTimeout(() => {
        onClose();
      }, duration);

      return () => clearTimeout(timer);
    }
  }, [show, duration, onClose]);

  if (!show) return null;

  return (
    <div className="fixed top-4 right-4 z-50 animate-in slide-in-from-top-2 duration-300">
      <div className="bg-white dark:bg-zinc-800 border border-green-200 dark:border-green-800 rounded-lg shadow-lg max-w-md">
        <div className="p-4 flex items-start gap-3">
          {/* Success Icon */}
          <div className="flex-shrink-0">
            <div className="w-8 h-8 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center animate-in zoom-in duration-300">
              <CheckCircleIcon className="h-5 w-5 text-green-600 dark:text-green-400" />
            </div>
          </div>

          {/* Message */}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
              Success
            </p>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-0.5">
              {message}
            </p>
          </div>

          {/* Close Button */}
          <button
            onClick={onClose}
            className="flex-shrink-0 p-1 hover:bg-zinc-100 dark:hover:bg-zinc-700 rounded transition-colors"
          >
            <XMarkIcon className="h-5 w-5 text-zinc-400" />
          </button>
        </div>

        {/* Progress Bar */}
        {duration > 0 && (
          <div className="h-1 bg-zinc-100 dark:bg-zinc-700 overflow-hidden">
            <div
              className="h-full bg-green-600 dark:bg-green-400 animate-progress"
              style={{
                animation: `progress ${duration}ms linear`
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// Add CSS animation for progress bar (add to global CSS or component style)
const style = document.createElement('style');
style.textContent = `
  @keyframes progress {
    from {
      width: 100%;
    }
    to {
      width: 0%;
    }
  }
`;
if (typeof document !== 'undefined') {
  document.head.appendChild(style);
}
