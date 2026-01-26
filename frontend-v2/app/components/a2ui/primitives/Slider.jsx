/**
 * Slider - Numeric range slider
 *
 * Props:
 * - value: current value
 * - minValue/min: minimum value (default: 0)
 * - maxValue/max: maximum value (default: 100)
 * - step: step increment (default: 1)
 * - label: field label
 * - name: field name for form submission
 * - showValue: show current value (default: true)
 * - onInteraction: callback for value changes
 * - onFormChange: callback to register with form state
 */

import { useState, useEffect } from 'react';

export function Slider({
  value: initialValue,
  minValue,
  min = 0,
  maxValue,
  max = 100,
  step = 1,
  label,
  name,
  showValue = true,
  onInteraction,
  onFormChange,
  id,
  style,
}) {
  // Support both minValue/maxValue (A2UI spec) and min/max (common convention)
  const minVal = minValue ?? min;
  const maxVal = maxValue ?? max;

  const [value, setValue] = useState(initialValue ?? minVal);

  // Determine the field name for form state
  const fieldName = name || id || 'slider';

  const handleChange = (e) => {
    const newValue = parseFloat(e.target.value);
    setValue(newValue);

    // Register with form state
    if (onFormChange) {
      onFormChange(fieldName, newValue);
    }

    if (onInteraction) {
      onInteraction('slider_change', { [fieldName]: newValue });
    }
  };

  // Register initial value on mount
  useEffect(() => {
    if (onFormChange) {
      onFormChange(fieldName, value);
    }
  }, []);

  // Calculate percentage for gradient fill
  const percentage = ((value - minVal) / (maxVal - minVal)) * 100;

  return (
    <div id={id} style={style} className="flex flex-col gap-2">
      {(label || showValue) && (
        <div className="flex items-center justify-between">
          {label && (
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              {label}
            </label>
          )}
          {showValue && (
            <span className="text-sm font-medium text-blue-600 dark:text-blue-400">
              {value}
            </span>
          )}
        </div>
      )}
      <input
        type="range"
        name={fieldName}
        value={value}
        min={minVal}
        max={maxVal}
        step={step}
        onChange={handleChange}
        className="w-full h-2 bg-zinc-200 dark:bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
        style={{
          background: `linear-gradient(to right, rgb(37 99 235) 0%, rgb(37 99 235) ${percentage}%, rgb(228 228 231) ${percentage}%, rgb(228 228 231) 100%)`,
        }}
      />
      <div className="flex justify-between text-xs text-zinc-500">
        <span>{minVal}</span>
        <span>{maxVal}</span>
      </div>
    </div>
  );
}
