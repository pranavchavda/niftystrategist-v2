import React from 'react';

/**
 * SkeletonTable Component
 * Reusable skeleton loader for table/list-based data
 *
 * @param {number} rows - Number of rows to display (default: 5)
 * @param {number} columns - Number of columns per row (default: 3)
 * @param {string} variant - Table variant: 'default', 'grid', 'list'
 */
export default function SkeletonTable({ rows = 5, columns = 3, variant = 'default' }) {
  const rowsArray = Array.from({ length: rows }, (_, i) => i);
  const columnsArray = Array.from({ length: columns }, (_, i) => i);

  if (variant === 'grid') {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {rowsArray.map((rowIndex) => (
          <div
            key={rowIndex}
            className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg p-4 space-y-3"
          >
            <div className="h-5 bg-zinc-200 dark:bg-zinc-700 rounded w-3/4 animate-pulse"></div>
            <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-full animate-pulse"></div>
            <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-5/6 animate-pulse"></div>
            <div className="flex gap-2 pt-2">
              <div className="h-8 bg-zinc-200 dark:bg-zinc-700 rounded flex-1 animate-pulse"></div>
              <div className="h-8 bg-zinc-200 dark:bg-zinc-700 rounded flex-1 animate-pulse"></div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (variant === 'list') {
    return (
      <div className="space-y-2">
        {rowsArray.map((rowIndex) => (
          <div
            key={rowIndex}
            className="flex items-center gap-3 p-3 bg-zinc-50 dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700"
          >
            <div className="flex-shrink-0 w-10 h-10 bg-zinc-200 dark:bg-zinc-700 rounded-full animate-pulse"></div>
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-1/2 animate-pulse"></div>
              <div className="h-3 bg-zinc-200 dark:bg-zinc-700 rounded w-3/4 animate-pulse"></div>
            </div>
            <div className="flex gap-2">
              <div className="h-8 w-8 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
              <div className="h-8 w-8 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Default table variant
  return (
    <div className="overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full">
        <thead className="bg-zinc-50 dark:bg-zinc-800 border-b border-zinc-200 dark:border-zinc-700">
          <tr>
            {columnsArray.map((colIndex) => (
              <th key={colIndex} className="px-6 py-3 text-left">
                <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-24 animate-pulse"></div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white dark:bg-zinc-900 divide-y divide-zinc-200 dark:divide-zinc-800">
          {rowsArray.map((rowIndex) => (
            <tr key={rowIndex}>
              {columnsArray.map((colIndex) => (
                <td key={colIndex} className="px-6 py-4">
                  <div className="h-4 bg-zinc-200 dark:bg-zinc-700 rounded w-32 animate-pulse"></div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
