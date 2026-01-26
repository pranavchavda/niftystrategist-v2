import React, { useState } from 'react';
import { ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/20/solid';

export default function BasicInfoEditor({
  title,
  urlHandle,
  seoTitle,
  seoDescription,
  onTitleChange,
  onUrlHandleChange,
  onSeoTitleChange,
  onSeoDescriptionChange,
}) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Basic Information
          </h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
            Page title, URL handle, and SEO settings
          </p>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
          aria-label={expanded ? 'Collapse section' : 'Expand section'}
        >
          {expanded ? (
            <ChevronUpIcon className="h-5 w-5 text-zinc-500" />
          ) : (
            <ChevronDownIcon className="h-5 w-5 text-zinc-500" />
          )}
        </button>
      </div>

      {/* Content */}
      {expanded && (
        <div className="space-y-4 pl-4 border-l-2 border-zinc-200 dark:border-zinc-800">
          {/* Page Title */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
              Page Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => onTitleChange(e.target.value)}
              className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
              placeholder="e.g., Single Dose Coffee Grinders"
            />
          </div>

          {/* URL Handle */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
              URL Handle
            </label>
            <input
              type="text"
              value={urlHandle}
              onChange={(e) => onUrlHandleChange(e.target.value)}
              className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
              placeholder="e.g., single-dose-grinders"
            />
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              The URL slug for this page
            </p>
          </div>

          {/* SEO Title */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
              SEO Title
            </label>
            <input
              type="text"
              value={seoTitle}
              onChange={(e) => onSeoTitleChange(e.target.value)}
              className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
              placeholder="e.g., Single Dose Coffee Grinders - Zero Retention | iDrinkCoffee"
            />
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              {seoTitle.length}/60 characters (optimal: 50-60)
            </p>
          </div>

          {/* SEO Description */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
              SEO Description
            </label>
            <textarea
              value={seoDescription}
              onChange={(e) => onSeoDescriptionChange(e.target.value)}
              rows={3}
              className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"
              placeholder="e.g., Shop the best single dose coffee grinders in Canada. Featuring Profitec, Mahlkonig, Eureka, and more."
            />
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              {seoDescription.length}/160 characters (optimal: 150-160)
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
