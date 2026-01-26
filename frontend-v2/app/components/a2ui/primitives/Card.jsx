/**
 * Card - Container with border/shadow
 *
 * Props:
 * - variant: 'default' | 'elevated' | 'bordered'
 * - padding: 1-6 (maps to tailwind spacing)
 * - style: optional inline styles
 * - children: nested components (full primitive tree format)
 *
 * Simplified format props (alternative to children):
 * - title: string - renders as h3 heading
 * - body: string - renders as body text
 * - actions: array of {type, label, action, payload} - renders as buttons
 */

import clsx from 'clsx';

export function Card({
  variant = 'default',
  padding = 4,
  children,
  id,
  style,
  // Simplified format props
  title,
  body,
  actions,
  onInteraction,
  renderComponent,
}) {
  const paddingClasses = {
    1: 'p-1',
    2: 'p-2',
    3: 'p-3',
    4: 'p-4',
    5: 'p-5',
    6: 'p-6',
  };

  const variantClasses = {
    default: 'bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700',
    elevated: 'bg-white dark:bg-zinc-800 shadow-lg shadow-zinc-200/50 dark:shadow-zinc-900/50',
    bordered: 'bg-transparent border-2 border-zinc-300 dark:border-zinc-600',
  };

  // Render simplified format if title/body/actions are provided and no children
  const hasSimplifiedContent = (title || body || actions) && !children;

  return (
    <div
      id={id}
      style={style}
      className={clsx(
        'rounded-lg overflow-hidden',
        paddingClasses[padding] || 'p-4',
        variantClasses[variant] || variantClasses.default
      )}
    >
      {hasSimplifiedContent ? (
        <div className="flex flex-col gap-3">
          {title && (
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              {title}
            </h3>
          )}
          {body && (
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              {body}
            </p>
          )}
          {actions && actions.length > 0 && (
            <div className="flex flex-row flex-wrap gap-2 mt-2">
              {actions.map((action, idx) => {
                // If action has children (nested components), render them
                if (action.children && renderComponent) {
                  return action.children.map(renderComponent);
                }
                // Otherwise render as button
                const handleClick = () => {
                  if (action.action && onInteraction) {
                    onInteraction(action.action, action.payload || {});
                  }
                };
                return (
                  <button
                    key={action.id || `action-${idx}`}
                    type="button"
                    onClick={handleClick}
                    className={clsx(
                      'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                      'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
                      action.variant === 'secondary'
                        ? 'bg-zinc-600 hover:bg-zinc-700 text-white'
                        : action.variant === 'outline'
                        ? 'bg-transparent border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                        : 'bg-blue-600 hover:bg-blue-700 text-white'
                    )}
                  >
                    {action.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        children
      )}
    </div>
  );
}
