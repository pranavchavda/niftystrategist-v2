/**
 * Tabs - Tabbed content container
 *
 * Props:
 * - tabItems: array of { title, child } or use children with Tab components
 * - defaultTab: index of default active tab (default: 0)
 * - children: tab content (rendered via renderComponent)
 */

import { useState } from 'react';
import clsx from 'clsx';

export function Tabs({
  tabItems = [],
  defaultTab = 0,
  children,
  id,
  style,
  renderComponent,
}) {
  const [activeTab, setActiveTab] = useState(defaultTab);

  // Support both tabItems prop and children
  const tabs = tabItems.length > 0 ? tabItems : [];

  if (tabs.length === 0) {
    return (
      <div className="p-4 bg-zinc-100 dark:bg-zinc-800 rounded-md text-zinc-500">
        No tabs provided
      </div>
    );
  }

  return (
    <div id={id} style={style} className="flex flex-col">
      {/* Tab headers */}
      <div className="flex border-b border-zinc-200 dark:border-zinc-700">
        {tabs.map((tab, index) => {
          const title = typeof tab.title === 'object'
            ? (tab.title.literalString || tab.title)
            : tab.title;

          return (
            <button
              key={index}
              type="button"
              onClick={() => setActiveTab(index)}
              className={clsx(
                'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                activeTab === index
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
              )}
            >
              {title}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div className="py-4">
        {tabs[activeTab]?.child && renderComponent ? (
          // If child is a component definition, render it
          typeof tabs[activeTab].child === 'object'
            ? renderComponent(tabs[activeTab].child)
            : tabs[activeTab].child
        ) : tabs[activeTab]?.content ? (
          // Support content prop as alternative
          <div>{tabs[activeTab].content}</div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
