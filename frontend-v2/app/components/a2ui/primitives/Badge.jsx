/**
 * Badge - Status badge
 *
 * Props:
 * - content: text to display
 * - color: 'green' | 'yellow' | 'red' | 'blue' | 'gray'
 */

import clsx from 'clsx';

export function Badge({ content, label, text, color = 'gray', id, children }) {
  const colorClasses = {
    green: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    yellow: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    red: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    blue: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    gray: 'bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-400',
  };

  // Accept multiple prop names for content (LLMs use various names)
  const displayContent = content || label || text || children;

  return (
    <span
      id={id}
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
        colorClasses[color] || colorClasses.gray
      )}
    >
      {displayContent}
    </span>
  );
}
