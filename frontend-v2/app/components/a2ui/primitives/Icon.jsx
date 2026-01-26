/**
 * Icon - Lucide icon display
 *
 * Props:
 * - name: icon name (lucide icon names in kebab-case)
 * - size: 'sm' | 'md' | 'lg'
 * - color: optional color class
 */

import clsx from 'clsx';
import * as LucideIcons from 'lucide-react';

// Convert kebab-case to PascalCase for Lucide icon names
function toPascalCase(str) {
  return str
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join('');
}

export function Icon({ name, size = 'md', color, id }) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6',
  };

  const colorClasses = {
    primary: 'text-blue-600 dark:text-blue-400',
    secondary: 'text-zinc-500 dark:text-zinc-400',
    success: 'text-green-600 dark:text-green-400',
    warning: 'text-yellow-600 dark:text-yellow-400',
    danger: 'text-red-600 dark:text-red-400',
  };

  // Try to find the icon component
  const iconName = toPascalCase(name || 'help-circle');
  const IconComponent = LucideIcons[iconName];

  if (!IconComponent) {
    console.warn(`[A2UI Icon] Unknown icon: ${name} (tried: ${iconName})`);
    return (
      <span
        id={id}
        className={clsx(
          sizeClasses[size] || sizeClasses.md,
          'inline-flex items-center justify-center text-zinc-400'
        )}
      >
        ?
      </span>
    );
  }

  return (
    <IconComponent
      id={id}
      className={clsx(
        sizeClasses[size] || sizeClasses.md,
        color ? colorClasses[color] : 'text-zinc-600 dark:text-zinc-400'
      )}
    />
  );
}
