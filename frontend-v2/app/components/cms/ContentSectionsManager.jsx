import React, { useState } from 'react';
import { ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/20/solid';
import MetaobjectPicker from '../MetaobjectPicker';

export default function ContentSectionsManager({
  categories,
  educationalContent,
  faqSection,
  comparisonTable,
  onSelectCategories,
  onRemoveCategory,
  onMoveCategoryUp,
  onMoveCategoryDown,
  onSelectEducationalBlocks,
  onRemoveEducationalBlock,
  onMoveEducationalBlockUp,
  onMoveEducationalBlockDown,
  onSelectFaqSection,
  onSelectComparisonTable,
  authToken,
}) {
  const [expandedSections, setExpandedSections] = useState({
    categories: true,
    educational: true,
    faq: true,
    comparison: true,
  });

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  return (
    <div className="space-y-6">
      {/* Categories Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Categories
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              Add category sections to this landing page (order matters)
            </p>
          </div>
          <button
            onClick={() => toggleSection('categories')}
            className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
            aria-label={expandedSections.categories ? 'Collapse section' : 'Expand section'}
          >
            {expandedSections.categories ? (
              <ChevronUpIcon className="h-5 w-5 text-zinc-500" />
            ) : (
              <ChevronDownIcon className="h-5 w-5 text-zinc-500" />
            )}
          </button>
        </div>

        {expandedSections.categories && (
          <div className="pl-4 border-l-2 border-zinc-200 dark:border-zinc-800 space-y-3">
            {/* Current Categories List with Reordering */}
            {categories && categories.length > 0 && (
              <div className="space-y-2">
                {categories.map((category, index) => (
                  <div
                    key={category.id}
                    className="flex items-center gap-2 p-2 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 rounded-lg"
                  >
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={() => onMoveCategoryUp(index)}
                        disabled={index === 0}
                        className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                        title="Move up"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                        </svg>
                      </button>
                      <button
                        onClick={() => onMoveCategoryDown(index)}
                        disabled={index === categories.length - 1}
                        className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                        title="Move down"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>
                    </div>
                    <span className="flex-1 text-sm text-zinc-700 dark:text-zinc-300">
                      {index + 1}. {category.title || 'Category'}
                    </span>
                    <button
                      onClick={() => onRemoveCategory(category.id)}
                      className="px-2 py-1 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}

            <MetaobjectPicker
              type="categories"
              selectedIds={categories?.map(c => c.id) || []}
              onSelect={onSelectCategories}
              isMulti={true}
              authToken={authToken}
              placeholder="Select category sections..."
            />
          </div>
        )}
      </div>

      {/* Educational Content Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Educational Content
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              Add educational blocks to this landing page (order matters)
            </p>
          </div>
          <button
            onClick={() => toggleSection('educational')}
            className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
            aria-label={expandedSections.educational ? 'Collapse section' : 'Expand section'}
          >
            {expandedSections.educational ? (
              <ChevronUpIcon className="h-5 w-5 text-zinc-500" />
            ) : (
              <ChevronDownIcon className="h-5 w-5 text-zinc-500" />
            )}
          </button>
        </div>

        {expandedSections.educational && (
          <div className="pl-4 border-l-2 border-zinc-200 dark:border-zinc-800 space-y-3">
            {/* Current Educational Blocks List with Reordering */}
            {educationalContent && educationalContent.length > 0 && (
              <div className="space-y-2">
                {educationalContent.map((block, index) => (
                  <div
                    key={block.id}
                    className="flex items-center gap-2 p-2 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 rounded-lg"
                  >
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={() => onMoveEducationalBlockUp(index)}
                        disabled={index === 0}
                        className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                        title="Move up"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                        </svg>
                      </button>
                      <button
                        onClick={() => onMoveEducationalBlockDown(index)}
                        disabled={index === educationalContent.length - 1}
                        className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                        title="Move down"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>
                    </div>
                    <span className="flex-1 text-sm text-zinc-700 dark:text-zinc-300">
                      {index + 1}. {block.title || 'Educational Block'}
                    </span>
                    <button
                      onClick={() => onRemoveEducationalBlock(block.id)}
                      className="px-2 py-1 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}

            <MetaobjectPicker
              type="educational-blocks"
              selectedIds={educationalContent?.map(b => b.id) || []}
              onSelect={onSelectEducationalBlocks}
              isMulti={true}
              authToken={authToken}
              placeholder="Select educational blocks..."
            />
          </div>
        )}
      </div>

      {/* FAQ Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              FAQ Section
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              Set the FAQ section for this landing page (single reference)
            </p>
          </div>
          <button
            onClick={() => toggleSection('faq')}
            className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
            aria-label={expandedSections.faq ? 'Collapse section' : 'Expand section'}
          >
            {expandedSections.faq ? (
              <ChevronUpIcon className="h-5 w-5 text-zinc-500" />
            ) : (
              <ChevronDownIcon className="h-5 w-5 text-zinc-500" />
            )}
          </button>
        </div>

        {expandedSections.faq && (
          <div className="pl-4 border-l-2 border-zinc-200 dark:border-zinc-800">
            <MetaobjectPicker
              type="faq-sections"
              selectedIds={faqSection ? [faqSection.id] : []}
              onSelect={onSelectFaqSection}
              isMulti={false}
              authToken={authToken}
              placeholder="Select an FAQ section..."
            />
          </div>
        )}
      </div>

      {/* Comparison Table Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Comparison Table
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              Set the comparison table for this landing page (single reference)
            </p>
          </div>
          <button
            onClick={() => toggleSection('comparison')}
            className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
            aria-label={expandedSections.comparison ? 'Collapse section' : 'Expand section'}
          >
            {expandedSections.comparison ? (
              <ChevronUpIcon className="h-5 w-5 text-zinc-500" />
            ) : (
              <ChevronDownIcon className="h-5 w-5 text-zinc-500" />
            )}
          </button>
        </div>

        {expandedSections.comparison && (
          <div className="pl-4 border-l-2 border-zinc-200 dark:border-zinc-800">
            <MetaobjectPicker
              type="comparison-tables"
              selectedIds={comparisonTable ? [comparisonTable.id] : []}
              onSelect={onSelectComparisonTable}
              isMulti={false}
              authToken={authToken}
              placeholder="Select a comparison table..."
            />
          </div>
        )}
      </div>
    </div>
  );
}
