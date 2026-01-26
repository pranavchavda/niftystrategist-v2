import React, { useState } from 'react';
import FieldError, { CharacterCount, ValidationHint } from './FieldError';

/**
 * ValidatedInput Component
 * Text input with built-in real-time validation
 *
 * @param {string} name - Input name
 * @param {string} value - Input value
 * @param {function} onChange - Change handler
 * @param {function} onBlur - Blur handler (optional)
 * @param {function} validator - Validation function that returns { isValid, error, warning }
 * @param {string} label - Field label
 * @param {string} placeholder - Placeholder text
 * @param {string} hint - Helpful hint displayed before user types
 * @param {boolean} required - Whether field is required
 * @param {boolean} disabled - Whether field is disabled
 * @param {number} maxLength - Maximum character length (optional)
 * @param {number} optimalLength - Optimal character length for character count (optional)
 * @param {string} type - Input type (default: 'text')
 * @param {boolean} showCharCount - Whether to show character count
 */
export default function ValidatedInput({
  name,
  value,
  onChange,
  onBlur,
  validator,
  label,
  placeholder = '',
  hint = '',
  required = false,
  disabled = false,
  maxLength = null,
  optimalLength = null,
  type = 'text',
  showCharCount = false,
  className = ''
}) {
  const [touched, setTouched] = useState(false);
  const [validation, setValidation] = useState({ isValid: true, error: null, warning: null });

  const handleBlur = (e) => {
    setTouched(true);

    if (validator) {
      const result = validator(value);
      setValidation(result);
    }

    if (onBlur) {
      onBlur(e);
    }
  };

  const handleChange = (e) => {
    onChange(e);

    // Real-time validation after first blur
    if (touched && validator) {
      const result = validator(e.target.value);
      setValidation(result);
    }
  };

  const hasError = touched && !validation.isValid && validation.error;
  const hasWarning = touched && validation.isValid && validation.warning;

  return (
    <div className={className}>
      {/* Label */}
      {label && (
        <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
          {label}
          {required && <span className="text-red-600 dark:text-red-400 ml-1">*</span>}
        </label>
      )}

      {/* Input */}
      <input
        type={type}
        name={name}
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        placeholder={placeholder}
        disabled={disabled}
        maxLength={maxLength || undefined}
        className={`w-full min-h-[44px] px-4 py-2 bg-white dark:bg-zinc-800 border rounded-lg text-sm focus:outline-none focus:ring-2 disabled:opacity-50 transition-colors ${
          hasError
            ? 'border-red-500 dark:border-red-400 focus:ring-red-500'
            : hasWarning
            ? 'border-amber-500 dark:border-amber-400 focus:ring-amber-500'
            : validation.isValid && touched && value
            ? 'border-green-500 dark:border-green-400 focus:ring-green-500'
            : 'border-zinc-300 dark:border-zinc-700 focus:ring-amber-500'
        }`}
      />

      {/* Hint (shown before user interacts) */}
      {!touched && hint && <ValidationHint hint={hint} />}

      {/* Character Count */}
      {showCharCount && maxLength && (
        <CharacterCount
          current={value?.length || 0}
          max={maxLength}
          optimal={optimalLength}
        />
      )}

      {/* Validation Messages */}
      {hasError && <FieldError message={validation.error} type="error" />}
      {hasWarning && <FieldError message={validation.warning} type="warning" />}
    </div>
  );
}

/**
 * ValidatedTextarea Component
 * Textarea with built-in real-time validation
 */
export function ValidatedTextarea({
  name,
  value,
  onChange,
  onBlur,
  validator,
  label,
  placeholder = '',
  hint = '',
  required = false,
  disabled = false,
  maxLength = null,
  optimalLength = null,
  rows = 4,
  showCharCount = false,
  className = ''
}) {
  const [touched, setTouched] = useState(false);
  const [validation, setValidation] = useState({ isValid: true, error: null, warning: null });

  const handleBlur = (e) => {
    setTouched(true);

    if (validator) {
      const result = validator(value);
      setValidation(result);
    }

    if (onBlur) {
      onBlur(e);
    }
  };

  const handleChange = (e) => {
    onChange(e);

    // Real-time validation after first blur
    if (touched && validator) {
      const result = validator(e.target.value);
      setValidation(result);
    }
  };

  const hasError = touched && !validation.isValid && validation.error;
  const hasWarning = touched && validation.isValid && validation.warning;

  return (
    <div className={className}>
      {/* Label */}
      {label && (
        <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
          {label}
          {required && <span className="text-red-600 dark:text-red-400 ml-1">*</span>}
        </label>
      )}

      {/* Textarea */}
      <textarea
        name={name}
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        placeholder={placeholder}
        disabled={disabled}
        maxLength={maxLength || undefined}
        rows={rows}
        className={`w-full px-4 py-2 bg-white dark:bg-zinc-800 border rounded-lg text-sm focus:outline-none focus:ring-2 disabled:opacity-50 resize-none transition-colors ${
          hasError
            ? 'border-red-500 dark:border-red-400 focus:ring-red-500'
            : hasWarning
            ? 'border-amber-500 dark:border-amber-400 focus:ring-amber-500'
            : validation.isValid && touched && value
            ? 'border-green-500 dark:border-green-400 focus:ring-green-500'
            : 'border-zinc-300 dark:border-zinc-700 focus:ring-amber-500'
        }`}
      />

      {/* Hint (shown before user interacts) */}
      {!touched && hint && <ValidationHint hint={hint} />}

      {/* Character Count */}
      {showCharCount && maxLength && (
        <CharacterCount
          current={value?.length || 0}
          max={maxLength}
          optimal={optimalLength}
        />
      )}

      {/* Validation Messages */}
      {hasError && <FieldError message={validation.error} type="error" />}
      {hasWarning && <FieldError message={validation.warning} type="warning" />}
    </div>
  );
}
