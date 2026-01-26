/**
 * Row - Horizontal flex container
 *
 * Props:
 * - gap: 1-6 (maps to tailwind gap)
 * - align: 'start' | 'center' | 'end'
 * - justify: 'start' | 'center' | 'end' | 'between'
 * - style: optional inline styles
 * - children: nested components
 */

import clsx from 'clsx';

export function Row({ gap = 2, align = 'center', justify = 'start', children, id, style }) {
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

  const justifyClasses = {
    start: 'justify-start',
    center: 'justify-center',
    end: 'justify-end',
    between: 'justify-between',
  };

  return (
    <div
      id={id}
      style={style}
      className={clsx(
        'flex flex-row flex-wrap',
        gapClasses[gap] || 'gap-2',
        alignClasses[align] || 'items-center',
        justifyClasses[justify] || 'justify-start'
      )}
    >
      {children}
    </div>
  );
}
