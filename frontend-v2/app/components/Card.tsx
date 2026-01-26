import React from 'react';
import { clsx } from 'clsx';

/**
 * Card Component
 *
 * A unified card component with multiple variants for consistent styling.
 *
 * Variants:
 * - `default`: Standard card with subtle glass effect
 * - `glass`: Strong glass morphism effect
 * - `solid`: Solid background without glass effect
 * - `elevated`: Higher elevation with larger shadow
 * - `interactive`: Hover effects for clickable cards
 * - `outlined`: Border emphasis, minimal background
 */

type CardVariant = 'default' | 'glass' | 'solid' | 'elevated' | 'interactive' | 'outlined';
type CardSize = 'sm' | 'default' | 'lg';

interface CardProps {
  children: React.ReactNode;
  variant?: CardVariant;
  size?: CardSize;
  className?: string;
  as?: 'div' | 'article' | 'section' | 'button' | 'a';
  onClick?: () => void;
  href?: string;
}

const variantStyles: Record<CardVariant, string> = {
  default: clsx(
    'bg-white/80 backdrop-blur-md',
    'border border-zinc-200/50',
    'shadow-sm',
    'dark:bg-zinc-900/80 dark:border-zinc-800/50'
  ),
  glass: clsx(
    'bg-white/70 backdrop-blur-xl',
    'border border-white/20',
    'shadow-lg shadow-zinc-900/5',
    'dark:bg-zinc-900/70 dark:border-white/10 dark:shadow-black/20'
  ),
  solid: clsx(
    'bg-white',
    'border border-zinc-200',
    'shadow-sm',
    'dark:bg-zinc-900 dark:border-zinc-800'
  ),
  elevated: clsx(
    'bg-white/90 backdrop-blur-lg',
    'border border-zinc-200/30',
    'shadow-xl shadow-zinc-900/10',
    'dark:bg-zinc-900/90 dark:border-zinc-800/30 dark:shadow-black/30'
  ),
  interactive: clsx(
    'bg-white/80 backdrop-blur-md',
    'border border-zinc-200/50',
    'shadow-sm',
    'dark:bg-zinc-900/80 dark:border-zinc-800/50',
    'cursor-pointer',
    'transition-all duration-200',
    'hover:shadow-lg hover:-translate-y-0.5 hover:border-zinc-300/70',
    'dark:hover:border-zinc-700/70',
    'active:scale-[0.99] active:shadow-md'
  ),
  outlined: clsx(
    'bg-transparent',
    'border-2 border-zinc-200',
    'dark:border-zinc-700',
    'hover:border-zinc-300 dark:hover:border-zinc-600',
    'transition-colors duration-150'
  ),
};

const sizeStyles: Record<CardSize, string> = {
  sm: 'p-3 md:p-4 rounded-lg',
  default: 'p-4 md:p-6 rounded-xl',
  lg: 'p-6 md:p-8 rounded-2xl',
};

export function Card({
  children,
  variant = 'default',
  size = 'default',
  className,
  as: Component = 'div',
  onClick,
  href,
  ...props
}: CardProps & React.HTMLAttributes<HTMLElement>) {
  const baseStyles = clsx(
    variantStyles[variant],
    sizeStyles[size],
    className
  );

  // Handle different element types
  if (Component === 'a' && href) {
    return (
      <a href={href} className={baseStyles} {...props}>
        {children}
      </a>
    );
  }

  if (Component === 'button' || onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={baseStyles}
        {...props}
      >
        {children}
      </button>
    );
  }

  return (
    <Component className={baseStyles} {...props}>
      {children}
    </Component>
  );
}

/**
 * CardHeader - Optional header section for cards
 */
interface CardHeaderProps {
  children: React.ReactNode;
  className?: string;
}

export function CardHeader({ children, className }: CardHeaderProps) {
  return (
    <div
      className={clsx(
        'flex items-center justify-between',
        'pb-4 mb-4',
        'border-b border-zinc-200/50 dark:border-zinc-800/50',
        className
      )}
    >
      {children}
    </div>
  );
}

/**
 * CardTitle - Title element for card headers
 */
interface CardTitleProps {
  children: React.ReactNode;
  className?: string;
  as?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
}

export function CardTitle({ children, className, as: Component = 'h3' }: CardTitleProps) {
  return (
    <Component
      className={clsx(
        'text-lg font-semibold text-zinc-900 dark:text-zinc-100',
        className
      )}
    >
      {children}
    </Component>
  );
}

/**
 * CardDescription - Subtitle/description for cards
 */
interface CardDescriptionProps {
  children: React.ReactNode;
  className?: string;
}

export function CardDescription({ children, className }: CardDescriptionProps) {
  return (
    <p
      className={clsx(
        'text-sm text-zinc-500 dark:text-zinc-400',
        'mt-1',
        className
      )}
    >
      {children}
    </p>
  );
}

/**
 * CardContent - Main content area (optional wrapper)
 */
interface CardContentProps {
  children: React.ReactNode;
  className?: string;
}

export function CardContent({ children, className }: CardContentProps) {
  return (
    <div className={clsx('text-zinc-600 dark:text-zinc-300', className)}>
      {children}
    </div>
  );
}

/**
 * CardFooter - Footer section with actions
 */
interface CardFooterProps {
  children: React.ReactNode;
  className?: string;
}

export function CardFooter({ children, className }: CardFooterProps) {
  return (
    <div
      className={clsx(
        'flex items-center justify-end gap-3',
        'pt-4 mt-4',
        'border-t border-zinc-200/50 dark:border-zinc-800/50',
        className
      )}
    >
      {children}
    </div>
  );
}

/**
 * StatCard - Specialized card for displaying statistics
 */
interface StatCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon?: React.ReactNode;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  className?: string;
}

export function StatCard({
  title,
  value,
  description,
  icon,
  trend,
  className,
}: StatCardProps) {
  return (
    <Card variant="default" size="default" className={className}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
            {title}
          </p>
          <p className="mt-2 text-3xl font-bold text-zinc-900 dark:text-zinc-100">
            {value}
          </p>
          {description && (
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              {description}
            </p>
          )}
          {trend && (
            <div className="mt-2 flex items-center gap-1">
              <span
                className={clsx(
                  'text-xs font-medium',
                  trend.isPositive
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : 'text-red-600 dark:text-red-400'
                )}
              >
                {trend.isPositive ? '+' : ''}{trend.value}%
              </span>
              <span className="text-xs text-zinc-400 dark:text-zinc-500">
                vs last period
              </span>
            </div>
          )}
        </div>
        {icon && (
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-100 dark:bg-zinc-800">
            {icon}
          </div>
        )}
      </div>
    </Card>
  );
}
