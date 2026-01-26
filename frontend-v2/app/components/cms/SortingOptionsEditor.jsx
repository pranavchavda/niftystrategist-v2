import React, { useState } from 'react';
import { ChevronDownIcon, ChevronUpIcon, XMarkIcon } from '@heroicons/react/20/solid';

export default function SortingOptionsEditor({
  enableSorting,
  sortingOptions,
  onEnableSortingChange,
  onAddSortingOption,
  onRemoveSortingOption,
}) {
  const [expanded, setExpanded] = useState(true);
  const [newSortLabel, setNewSortLabel] = useState('');
  const [newSortFilterType, setNewSortFilterType] = useState('price_range');
  const [newSortFilterValue, setNewSortFilterValue] = useState('');
  const [sortPriceMin, setSortPriceMin] = useState('');
  const [sortPriceMax, setSortPriceMax] = useState('');
  const [sortVendor, setSortVendor] = useState('');
  const [sortSpecName, setSortSpecName] = useState('');
  const [sortSpecValue, setSortSpecValue] = useState('');

  const buildFilterValue = () => {
    switch (newSortFilterType) {
      case 'price_range':
        if (!sortPriceMin || !sortPriceMax) return null;
        return `price:${sortPriceMin}-${sortPriceMax}`;
      case 'vendor':
        if (!sortVendor.trim()) return null;
        return `vendor_${sortVendor.trim().toLowerCase().replace(/\s+/g, '_')}`;
      case 'specification':
        if (!sortSpecName.trim() || !sortSpecValue.trim()) return null;
        return `${sortSpecName.trim()}: ${sortSpecValue.trim()}`;
      case 'custom':
        return newSortFilterValue.trim() || null;
      default:
        return null;
    }
  };

  const handleAddOption = () => {
    if (!newSortLabel.trim()) return;

    const filterValue = buildFilterValue();
    if (!filterValue) return;

    const newOption = {
      id: `temp_${Date.now()}`,
      label: newSortLabel.trim(),
      filterType: newSortFilterType,
      filterValue: filterValue,
    };

    onAddSortingOption(newOption);

    // Clear form
    setNewSortLabel('');
    setNewSortFilterType('price_range');
    setNewSortFilterValue('');
    setSortPriceMin('');
    setSortPriceMax('');
    setSortVendor('');
    setSortSpecName('');
    setSortSpecValue('');
  };

  const filterTypeColors = {
    price: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    availability: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    vendor: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
    spec: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Sorting Options
          </h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
            Configure sorting and filtering for this category
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
          {/* Enable Sorting Toggle */}
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={enableSorting}
              onChange={(e) => onEnableSortingChange(e.target.checked)}
              className="w-4 h-4 text-amber-600 border-zinc-300 dark:border-zinc-700 rounded focus:ring-amber-500"
            />
            <div>
              <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                Enable Sorting
              </span>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Allow users to sort products on this category page
              </p>
            </div>
          </label>

          {/* Existing Sorting Options */}
          {sortingOptions.length > 0 && (
            <div className="space-y-2">
              {sortingOptions.map((option) => (
                <div
                  key={option.id}
                  className="flex items-center gap-3 p-3 bg-zinc-50 dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {option.label}
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                      Value: {option.filterValue}
                    </p>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${filterTypeColors[option.filterType]}`}>
                    {option.filterType}
                  </span>
                  <button
                    onClick={() => onRemoveSortingOption(option.id)}
                    className="p-1.5 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
                    title="Remove option"
                  >
                    <XMarkIcon className="h-4 w-4 text-red-600 dark:text-red-400" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Add Sorting Option Form */}
          <div className="space-y-3 p-4 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700">
            <p className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
              Add New Sorting Option
            </p>

            {/* Label Input */}
            <div>
              <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                Display Label
              </label>
              <input
                type="text"
                value={newSortLabel}
                onChange={(e) => setNewSortLabel(e.target.value)}
                placeholder="e.g., 💰 Under $1,000"
                className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

            {/* Filter Type Selector */}
            <div>
              <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                Filter Type
              </label>
              <select
                value={newSortFilterType}
                onChange={(e) => {
                  setNewSortFilterType(e.target.value);
                  setNewSortFilterValue('');
                  setSortPriceMin('');
                  setSortPriceMax('');
                  setSortVendor('');
                  setSortSpecName('');
                  setSortSpecValue('');
                }}
                className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
              >
                <option value="price_range">Price Range</option>
                <option value="vendor">Vendor/Brand</option>
                <option value="specification">Product Specification</option>
                <option value="custom">Custom (Advanced)</option>
              </select>
            </div>

            {/* Conditional Inputs Based on Filter Type */}
            {newSortFilterType === 'price_range' && (
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                    Min Price
                  </label>
                  <input
                    type="number"
                    value={sortPriceMin}
                    onChange={(e) => setSortPriceMin(e.target.value)}
                    placeholder="500"
                    className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
                <div className="flex-1">
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                    Max Price
                  </label>
                  <input
                    type="number"
                    value={sortPriceMax}
                    onChange={(e) => setSortPriceMax(e.target.value)}
                    placeholder="1000"
                    className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
              </div>
            )}

            {newSortFilterType === 'vendor' && (
              <div>
                <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                  Vendor/Brand Name
                </label>
                <input
                  type="text"
                  value={sortVendor}
                  onChange={(e) => setSortVendor(e.target.value)}
                  placeholder="e.g., La Marzocco, Breville"
                  className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>
            )}

            {newSortFilterType === 'specification' && (
              <div className="space-y-2">
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                    Specification Name
                  </label>
                  <input
                    type="text"
                    value={sortSpecName}
                    onChange={(e) => setSortSpecName(e.target.value)}
                    placeholder="e.g., Manufacturer, Burr Type"
                    className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                    Specification Value
                  </label>
                  <input
                    type="text"
                    value={sortSpecValue}
                    onChange={(e) => setSortSpecValue(e.target.value)}
                    placeholder="e.g., La Marzocco, Flat"
                    className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
              </div>
            )}

            {newSortFilterType === 'custom' && (
              <div>
                <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                  Custom Filter Value
                </label>
                <input
                  type="text"
                  value={newSortFilterValue}
                  onChange={(e) => setNewSortFilterValue(e.target.value)}
                  placeholder="Advanced: Enter exact filter format"
                  className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                  ⚠️ Advanced users only. Must match storefront format exactly.
                </p>
              </div>
            )}

            {/* Live Preview */}
            {buildFilterValue() && (
              <div className="p-2 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded text-xs">
                <span className="font-medium text-blue-700 dark:text-blue-300">Preview:</span>{' '}
                <code className="text-blue-600 dark:text-blue-400">{buildFilterValue()}</code>
              </div>
            )}

            {/* Add Button */}
            <button
              onClick={handleAddOption}
              disabled={!newSortLabel.trim() || !buildFilterValue()}
              className="w-full px-4 py-2 bg-amber-600 hover:bg-amber-700 disabled:bg-amber-400 disabled:cursor-not-allowed text-white rounded-lg font-medium text-sm transition-colors"
            >
              Add Sorting Option
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
