/**
 * Text - Text display with variants
 *
 * Props:
 * - content: string to display (or use children)
 * - variant: 'h1' | 'h2' | 'h3' | 'body' | 'caption'
 * - level: alternative heading level (1-6)
 * - color: optional color class
 * - style: optional inline styles
 * - children: alternative to content
 */

import clsx from 'clsx';

export function Text({ content, text, variant = 'body', level, color, id, style, children, label }) {
  const variantClasses = {
    h1: 'text-2xl font-bold text-zinc-900 dark:text-zinc-100',
    h2: 'text-xl font-semibold text-zinc-900 dark:text-zinc-100',
    h3: 'text-lg font-medium text-zinc-900 dark:text-zinc-100',
    h4: 'text-base font-medium text-zinc-900 dark:text-zinc-100',
    h5: 'text-sm font-medium text-zinc-900 dark:text-zinc-100',
    h6: 'text-xs font-medium text-zinc-900 dark:text-zinc-100',
    body: 'text-base text-zinc-700 dark:text-zinc-300',
    caption: 'text-sm text-zinc-500 dark:text-zinc-400',
    // Alias variants that LLMs might use
    heading: 'text-lg font-medium text-zinc-900 dark:text-zinc-100', // = h3
    title: 'text-xl font-semibold text-zinc-900 dark:text-zinc-100', // = h2
    subtitle: 'text-base text-zinc-500 dark:text-zinc-400',
    paragraph: 'text-base text-zinc-700 dark:text-zinc-300', // = body
    small: 'text-sm text-zinc-500 dark:text-zinc-400', // = caption
    label: 'text-sm font-medium text-zinc-500 dark:text-zinc-400', // label text
  };

  const colorClasses = {
    primary: 'text-blue-600 dark:text-blue-400',
    secondary: 'text-zinc-500 dark:text-zinc-400',
    success: 'text-green-600 dark:text-green-400',
    warning: 'text-yellow-600 dark:text-yellow-400',
    danger: 'text-red-600 dark:text-red-400',
  };

  // Determine variant from level if provided
  const effectiveVariant = level ? `h${level}` : variant;

  // Determine tag from variant
  const tagMap = { h1: 'h1', h2: 'h2', h3: 'h3', h4: 'h4', h5: 'h5', h6: 'h6', heading: 'h3', title: 'h2' };
  const Tag = tagMap[effectiveVariant] || 'p';

  // Accept multiple prop names for content (LLMs use various names)
  const displayContent = content || text || label || children;

  return (
    <Tag
      id={id}
      style={style}
      className={clsx(
        variantClasses[effectiveVariant] || variantClasses.body,
        color && colorClasses[color]
      )}
    >
      {displayContent}
    </Tag>
  );
}
