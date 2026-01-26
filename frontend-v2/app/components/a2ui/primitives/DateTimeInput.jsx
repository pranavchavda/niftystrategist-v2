/**
 * DateTimeInput - Date and/or time picker
 *
 * Props:
 * - value: current value in ISO 8601 format
 * - enableDate: allow date selection (default: true)
 * - enableTime: allow time selection (default: false)
 * - label: field label
 * - name: field name for form submission
 * - min: minimum date/time
 * - max: maximum date/time
 * - onInteraction: callback for value changes
 * - onFormChange: callback to register with form state
 */

import { useState, useEffect } from 'react';

export function DateTimeInput({
  value: initialValue = '',
  enableDate = true,
  enableTime = false,
  label,
  name,
  min,
  max,
  onInteraction,
  onFormChange,
  id,
  style,
}) {
  const [value, setValue] = useState(initialValue);

  // Determine the field name for form state
  const fieldName = name || id || 'datetime';

  // Determine input type based on what's enabled
  const inputType = enableDate && enableTime
    ? 'datetime-local'
    : enableTime
      ? 'time'
      : 'date';

  const handleChange = (e) => {
    const newValue = e.target.value;
    setValue(newValue);

    // Register with form state
    if (onFormChange) {
      onFormChange(fieldName, newValue);
    }

    if (onInteraction) {
      onInteraction('datetime_change', { [fieldName]: newValue });
    }
  };

  // Register initial value on mount
  useEffect(() => {
    if (onFormChange && initialValue) {
      onFormChange(fieldName, initialValue);
    }
  }, []);

  return (
    <div id={id} style={style} className="flex flex-col gap-1">
      {label && (
        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          {label}
        </label>
      )}
      <input
        type={inputType}
        name={fieldName}
        value={value}
        onChange={handleChange}
        min={min}
        max={max}
        className="px-3 py-2 rounded-md border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
    </div>
  );
}
