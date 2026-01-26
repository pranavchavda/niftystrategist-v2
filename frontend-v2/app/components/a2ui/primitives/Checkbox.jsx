/**
 * Checkbox - Boolean input
 *
 * Props:
 * - label: checkbox label
 * - name: field name for form submission (also used as key in form state)
 * - checked: current state
 * - onInteraction: callback for value changes
 * - onFormChange: callback to register value with parent form state
 */

import { useState, useEffect } from 'react';

export function Checkbox({
  label,
  name,
  checked: initialChecked = false,
  onInteraction,
  onFormChange,
  id,
}) {
  const [checked, setChecked] = useState(initialChecked);

  // Determine the field name for form state
  const fieldName = name || id || 'checkbox';

  const handleChange = (e) => {
    const newValue = e.target.checked;
    setChecked(newValue);

    // Register value with form state
    if (onFormChange) {
      onFormChange(fieldName, newValue);
    }

    if (onInteraction) {
      onInteraction('checkbox_change', { [fieldName]: newValue });
    }
  };

  // Register initial value on mount
  useEffect(() => {
    if (onFormChange) {
      onFormChange(fieldName, initialChecked);
    }
  }, []);

  return (
    <label id={id} className="flex items-center gap-2 cursor-pointer">
      <input
        type="checkbox"
        name={name}
        checked={checked}
        onChange={handleChange}
        className="w-4 h-4 rounded border-zinc-300 dark:border-zinc-600 text-blue-600 focus:ring-blue-500 dark:bg-zinc-800"
      />
      <span className="text-sm text-zinc-700 dark:text-zinc-300">{label}</span>
    </label>
  );
}
