import React from 'react';
import { ExclamationCircleIcon, CheckCircleIcon, InformationCircleIcon } from '@heroicons/react/20/solid';

/**
 * FieldError Component
 * Displays validation messages with appropriate styling and icons
 *
 * @param {string} message - The message to display
 * @param {string} type - Type of message: 'error' | 'warning' | 'info' | 'success'
 * @param {string} className - Additional CSS classes
 */
export default function FieldError({ message, type = 'error', className = '' }) {
  if (!message) return null;

  const styles = {
    error: {
      container: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800',
      text: 'text-red-600 dark:text-red-400',
      icon: <ExclamationCircleIcon className="h-4 w-4 flex-shrink-0" />
    },
    warning: {
      container: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800',
      text: 'text-amber-700 dark:text-amber-400',
      icon: <ExclamationCircleIcon className="h-4 w-4 flex-shrink-0" />
    },
    info: {
      container: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
      text: 'text-blue-700 dark:text-blue-400',
      icon: <InformationCircleIcon className="h-4 w-4 flex-shrink-0" />
    },
    success: {
      container: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800',
      text: 'text-green-700 dark:text-green-400',
      icon: <CheckCircleIcon className="h-4 w-4 flex-shrink-0" />
    }
  };

  const style = styles[type] || styles.error;

  return (
    <div
      className={`mt-1.5 p-2 border rounded-lg flex items-start gap-2 animate-in fade-in slide-in-from-top-1 duration-200 ${style.container} ${className}`}
    >
      <div className={style.text}>
        {style.icon}
      </div>
      <p className={`text-xs leading-relaxed ${style.text}`}>
        {message}
      </p>
    </div>
  );
}

/**
 * CharacterCount Component
 * Displays character count with color coding based on limits
 *
 * @param {number} current - Current character count
 * @param {number} max - Maximum characters
 * @param {number} optimal - Optimal character count (optional)
 */
export function CharacterCount({ current, max, optimal = null }) {
  const getType = () => {
    if (current > max) return 'error';
    if (optimal && current >= optimal) return 'success';
    if (optimal && current < optimal) return 'warning';
    return 'info';
  };

  const getMessage = () => {
    if (current > max) {
      return `${current}/${max} characters - exceeds limit`;
    }
    if (optimal && current >= optimal) {
      return `${current}/${max} characters - optimal length`;
    }
    if (optimal && current < optimal) {
      return `${current}/${max} characters (recommended: ${optimal}+)`;
    }
    return `${current}/${max} characters`;
  };

  const type = getType();
  const message = getMessage();

  const colorClasses = {
    error: 'text-red-600 dark:text-red-400',
    warning: 'text-amber-600 dark:text-amber-400',
    info: 'text-zinc-500 dark:text-zinc-400',
    success: 'text-green-600 dark:text-green-400'
  };

  return (
    <p className={`text-xs mt-1 ${colorClasses[type]}`}>
      {message}
    </p>
  );
}

/**
 * ValidationHint Component
 * Displays a helpful hint before the user starts typing
 *
 * @param {string} hint - The hint message to display
 */
export function ValidationHint({ hint }) {
  if (!hint) return null;

  return (
    <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
      {hint}
    </p>
  );
}
