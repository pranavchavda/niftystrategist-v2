/**
 * Select - Dropdown select
 *
 * Props:
 * - label: field label
 * - options: array of { label, value }
 * - name: field name for form submission (also used as key in form state)
 * - value: current value
 * - onInteraction: callback for value changes
 * - onFormChange: callback to register value with parent form state
 */

import { useState, useEffect } from 'react';

export function Select({
  label,
  options = [],
  name,
  value: initialValue = '',
  onInteraction,
  onFormChange,
  id,
}) {
  const [value, setValue] = useState(initialValue);

  // Determine the field name for form state
  const fieldName = name || id || 'select';

  const handleChange = (e) => {
    const newValue = e.target.value;
    setValue(newValue);

    // Register value with form state
    if (onFormChange) {
      onFormChange(fieldName, newValue);
    }

    if (onInteraction) {
      onInteraction('select_change', { [fieldName]: newValue });
    }
  };

  // Register initial value on mount
  useEffect(() => {
    if (onFormChange && initialValue) {
      onFormChange(fieldName, initialValue);
    }
  }, []);

  return (
    <div id={id} className="flex flex-col gap-1">
      {label && (
        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          {label}
        </label>
      )}
      <select
        name={name}
        value={value}
        onChange={handleChange}
        className="px-3 py-2 rounded-md border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      >
        <option value="">Select...</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
