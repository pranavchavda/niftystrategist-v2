/**
 * TextField - Text input
 *
 * Props:
 * - label: field label
 * - placeholder: placeholder text
 * - name: field name for form submission (also used as key in form state)
 * - value: current value
 * - onInteraction: callback for value changes
 * - onFormChange: callback to register value with parent form state
 */

import { useState, useEffect } from 'react';

export function TextField({
  label,
  placeholder = '',
  name,
  value: initialValue = '',
  onInteraction,
  onFormChange,
  id,
}) {
  const [value, setValue] = useState(initialValue);

  // Determine the field name for form state (use name, or fallback to id, or 'query')
  const fieldName = name || id || 'query';

  const handleChange = (e) => {
    const newValue = e.target.value;
    setValue(newValue);

    // Register value with form state on every change
    if (onFormChange) {
      onFormChange(fieldName, newValue);
    }
  };

  const handleBlur = () => {
    if (onInteraction) {
      onInteraction('field_change', { [fieldName]: value });
    }
  };

  // Also register initial value on mount
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
      <input
        type="text"
        name={fieldName}
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        placeholder={placeholder}
        className="px-3 py-2 rounded-md border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
    </div>
  );
}
