/**
 * Grid - Responsive grid layout
 *
 * Props:
 * - columns: number of columns (default: 3)
 * - gap: gap size ('sm' | 'md' | 'lg' | number)
 * - children: grid items
 */

import clsx from 'clsx';

export function Grid({
  columns = 3,
  gap = 'md',
  children,
  id,
  style,
  renderComponent,
}) {
  const gapClasses = {
    sm: 'gap-2',
    md: 'gap-4',
    lg: 'gap-6',
  };

  // Responsive column classes
  const columnClasses = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
    5: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5',
    6: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6',
  };

  const gapClass = typeof gap === 'string' ? gapClasses[gap] || gapClasses.md : '';
  const gapStyle = typeof gap === 'number' ? { gap: `${gap}px` } : {};

  return (
    <div
      id={id}
      style={{ ...style, ...gapStyle }}
      className={clsx(
        'grid',
        columnClasses[columns] || columnClasses[3],
        gapClass
      )}
    >
      {children}
    </div>
  );
}
