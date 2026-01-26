/**
 * MultipleChoice - Multiple selection component (checkboxes/radio buttons)
 *
 * Props:
 * - selections: currently selected values (array)
 * - options: array of { label, value }
 * - maxAllowedSelections: max selections (1 = radio buttons, >1 = checkboxes)
 * - label: field label
 * - name: field name for form submission
 * - onInteraction: callback for value changes
 * - onFormChange: callback to register with form state
 */

import { useState, useEffect } from 'react';
import clsx from 'clsx';

export function MultipleChoice({
  selections: initialSelections = [],
  options = [],
  maxAllowedSelections,
  label,
  name,
  onInteraction,
  onFormChange,
  id,
  style,
}) {
  const [selections, setSelections] = useState(
    Array.isArray(initialSelections) ? initialSelections : []
  );

  // Determine the field name for form state
  const fieldName = name || id || 'selections';

  // If max is 1, behave like radio buttons
  const isRadio = maxAllowedSelections === 1;

  const handleChange = (optionValue, checked) => {
    let newSelections;

    if (isRadio) {
      // Radio behavior: only one selection
      newSelections = checked ? [optionValue] : [];
    } else {
      if (checked) {
        // Check if we've reached max selections
        if (maxAllowedSelections && selections.length >= maxAllowedSelections) {
          return; // Don't allow more selections
        }
        newSelections = [...selections, optionValue];
      } else {
        newSelections = selections.filter(v => v !== optionValue);
      }
    }

    setSelections(newSelections);

    // Register with form state
    if (onFormChange) {
      onFormChange(fieldName, newSelections);
    }

    if (onInteraction) {
      onInteraction('selection_change', { [fieldName]: newSelections });
    }
  };

  // Register initial value on mount
  useEffect(() => {
    if (onFormChange && initialSelections.length > 0) {
      onFormChange(fieldName, initialSelections);
    }
  }, []);

  return (
    <div id={id} style={style} className="flex flex-col gap-2">
      {label && (
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          {label}
        </span>
      )}
      <div className="flex flex-col gap-1">
        {options.map((option, index) => {
          const optionLabel = typeof option.label === 'object'
            ? (option.label.literalString || option.label)
            : option.label;
          const optionValue = option.value;
          const isChecked = selections.includes(optionValue);

          return (
            <label
              key={optionValue || index}
              className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors',
                isChecked
                  ? 'bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800'
                  : 'bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-700'
              )}
            >
              <input
                type={isRadio ? 'radio' : 'checkbox'}
                name={isRadio ? fieldName : `${fieldName}[]`}
                value={optionValue}
                checked={isChecked}
                onChange={(e) => handleChange(optionValue, e.target.checked)}
                className="w-4 h-4 text-blue-600 border-zinc-300 focus:ring-blue-500"
              />
              <span className="text-sm text-zinc-700 dark:text-zinc-300">
                {optionLabel}
              </span>
            </label>
          );
        })}
      </div>
      {maxAllowedSelections && maxAllowedSelections > 1 && (
        <span className="text-xs text-zinc-500">
          Select up to {maxAllowedSelections} options
        </span>
      )}
    </div>
  );
}
