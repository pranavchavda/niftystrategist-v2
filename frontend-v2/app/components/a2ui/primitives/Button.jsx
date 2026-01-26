/**
 * Button - Clickable action
 *
 * Props:
 * - label: button text (or use children)
 * - variant: 'primary' | 'secondary' | 'outline'
 * - action: action name to trigger on click
 * - payload: data to send with the action
 * - style: optional inline styles
 * - children: alternative to label
 * - onInteraction: callback from A2UIRenderer
 */

import clsx from 'clsx';

export function Button({
  label,
  text,
  variant = 'primary',
  action,
  payload,
  url,
  href,
  onInteraction,
  id,
  style,
  children,
}) {
  const variantClasses = {
    primary:
      'bg-blue-600 hover:bg-blue-700 text-white shadow-sm',
    secondary:
      'bg-zinc-600 hover:bg-zinc-700 text-white shadow-sm',
    outline:
      'bg-transparent border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800',
  };

  // Accept multiple prop names for label
  const displayLabel = label || text || children;

  // If url/href provided, open it directly
  const targetUrl = url || href;

  // Infer action from label if not explicitly provided
  const inferredAction = (() => {
    if (action) return action;
    const labelLower = (displayLabel || '').toString().toLowerCase();
    if (labelLower.includes('search')) return 'search';
    if (labelLower.includes('submit')) return 'submit';
    if (labelLower.includes('send')) return 'submit';
    if (labelLower.includes('go')) return 'submit';
    if (labelLower.includes('find')) return 'search';
    return 'submit'; // Default to submit for any button click
  })();

  const handleClick = () => {
    if (targetUrl) {
      // Open URL in new tab (handle relative URLs)
      const fullUrl = targetUrl.startsWith('http') ? targetUrl : `https://idrinkcoffee.com${targetUrl}`;
      window.open(fullUrl, '_blank', 'noopener,noreferrer');
    } else if (onInteraction) {
      // Always trigger onInteraction with inferred action
      onInteraction(inferredAction, payload || {});
    }
  };

  return (
    <button
      id={id}
      type="button"
      style={style}
      onClick={handleClick}
      className={clsx(
        'px-3 py-1.5 rounded-md text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
        variantClasses[variant] || variantClasses.primary
      )}
    >
      {displayLabel}
    </button>
  );
}
