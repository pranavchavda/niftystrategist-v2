import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronRightIcon } from '@heroicons/react/20/solid';

/**
 * Breadcrumb Component
 * Displays hierarchical navigation with clickable links for non-current items
 *
 * @param {Array} items - Array of breadcrumb items with shape: { label: string, href?: string, current?: boolean }
 * @param {string} className - Optional additional CSS classes
 *
 * Usage:
 * <Breadcrumb
 *   items={[
 *     { label: 'CMS', href: '/cms' },
 *     { label: 'Category Pages', href: '/cms/category-pages' },
 *     { label: 'Edit "Espresso Machines"', current: true }
 *   ]}
 * />
 */
export default function Breadcrumb({ items = [], className = '' }) {
  if (!items.length) return null;

  return (
    <nav
      aria-label="Breadcrumb"
      className={`flex items-center text-sm ${className}`}
    >
      <ol className="flex items-center space-x-2">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          const isCurrent = item.current || isLast;

          return (
            <li key={index} className="flex items-center">
              {/* Separator (not shown before first item) */}
              {index > 0 && (
                <ChevronRightIcon
                  className="h-4 w-4 text-zinc-400 dark:text-zinc-600 mx-2 flex-shrink-0"
                  aria-hidden="true"
                />
              )}

              {/* Breadcrumb Item */}
              {isCurrent ? (
                <span
                  className="text-zinc-900 dark:text-zinc-100 font-medium truncate max-w-xs"
                  aria-current="page"
                >
                  {item.label}
                </span>
              ) : item.href ? (
                <Link
                  to={item.href}
                  className="text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors truncate max-w-xs"
                >
                  {item.label}
                </Link>
              ) : (
                <span className="text-zinc-600 dark:text-zinc-400 truncate max-w-xs">
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/**
 * Mobile-optimized Breadcrumb Component
 * Collapses middle items on mobile, showing only Home > ... > Current
 *
 * Usage:
 * <MobileBreadcrumb
 *   items={[
 *     { label: 'Home', href: '/' },
 *     { label: 'CMS', href: '/cms' },
 *     { label: 'Category Pages', href: '/cms/category-pages' },
 *     { label: 'Edit "Espresso Machines"', current: true }
 *   ]}
 * />
 */
export function MobileBreadcrumb({ items = [], className = '' }) {
  if (!items.length) return null;

  // On mobile, show: First > ... > Last (if more than 2 items)
  const showCollapsed = items.length > 2;

  if (!showCollapsed) {
    return <Breadcrumb items={items} className={className} />;
  }

  const firstItem = items[0];
  const lastItem = items[items.length - 1];

  return (
    <nav
      aria-label="Breadcrumb"
      className={`flex items-center text-sm ${className}`}
    >
      <ol className="flex items-center space-x-2">
        {/* First Item */}
        <li className="flex items-center">
          {firstItem.href ? (
            <Link
              to={firstItem.href}
              className="text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
            >
              {firstItem.label}
            </Link>
          ) : (
            <span className="text-zinc-600 dark:text-zinc-400">
              {firstItem.label}
            </span>
          )}
        </li>

        {/* Ellipsis Separator */}
        <li className="flex items-center">
          <ChevronRightIcon
            className="h-4 w-4 text-zinc-400 dark:text-zinc-600 mx-2 flex-shrink-0"
            aria-hidden="true"
          />
          <span
            className="text-zinc-400 dark:text-zinc-600"
            aria-hidden="true"
          >
            ...
          </span>
        </li>

        {/* Last Item */}
        <li className="flex items-center">
          <ChevronRightIcon
            className="h-4 w-4 text-zinc-400 dark:text-zinc-600 mx-2 flex-shrink-0"
            aria-hidden="true"
          />
          <span
            className="text-zinc-900 dark:text-zinc-100 font-medium truncate max-w-[200px]"
            aria-current="page"
          >
            {lastItem.label}
          </span>
        </li>
      </ol>
    </nav>
  );
}

/**
 * Responsive Breadcrumb Component
 * Automatically switches between full and mobile breadcrumbs based on screen size
 * Uses Tailwind's responsive utilities for seamless breakpoints
 *
 * Usage:
 * <ResponsiveBreadcrumb
 *   items={[
 *     { label: 'Home', href: '/' },
 *     { label: 'CMS', href: '/cms' },
 *     { label: 'Category Pages', href: '/cms/category-pages' },
 *     { label: 'Edit "Espresso Machines"', current: true }
 *   ]}
 * />
 */
export function ResponsiveBreadcrumb({ items = [], className = '' }) {
  if (!items.length) return null;

  return (
    <>
      {/* Mobile Breadcrumb (hidden on md and up) */}
      <div className="block md:hidden">
        <MobileBreadcrumb items={items} className={className} />
      </div>

      {/* Desktop Breadcrumb (hidden on mobile) */}
      <div className="hidden md:block">
        <Breadcrumb items={items} className={className} />
      </div>
    </>
  );
}
