/**
 * Column - Vertical flex container
 *
 * Props:
 * - gap: 1-6 (maps to tailwind gap)
 * - align: 'start' | 'center' | 'end'
 * - style: optional inline styles
 * - children: nested components
 */

import clsx from 'clsx';

export function Column({ gap = 2, align = 'start', children, id, style }) {
  const gapClasses = {
    1: 'gap-1',
    2: 'gap-2',
    3: 'gap-3',
    4: 'gap-4',
    5: 'gap-5',
    6: 'gap-6',
  };

  const alignClasses = {
    start: 'items-start',
    center: 'items-center',
    end: 'items-end',
  };

  return (
    <div
      id={id}
      style={style}
      className={clsx(
        'flex flex-col',
        gapClasses[gap] || 'gap-2',
        alignClasses[align] || 'items-start'
      )}
    >
      {children}
    </div>
  );
}
