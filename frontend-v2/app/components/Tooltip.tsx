import React, { useState, useRef, useId, useCallback } from 'react';
import { createPortal } from 'react-dom';

interface TooltipProps {
  /** Content shown in the popover — string or rich node. */
  content: React.ReactNode;
  children: React.ReactNode;
  /** Preferred side. Defaults to top; auto-flips if it would clip. */
  side?: 'top' | 'bottom';
  /** Max width of the bubble in px. */
  width?: number;
}

interface Coords {
  left: number;
  top: number;
  side: 'top' | 'bottom';
}

/**
 * Lightweight hover/focus tooltip. NS has no catalyst Tooltip, so this is a
 * self-contained popover — zinc surface, amber-tinted border, fade-in.
 *
 * The bubble is rendered into a body-level portal with `position: fixed`, so
 * it escapes `overflow-hidden` / `overflow-x-auto` ancestors (e.g. the scroll
 * container around the results table) and never gets clipped or stacked
 * behind sibling content.
 */
export function Tooltip({ content, children, side = 'top', width = 240 }: TooltipProps) {
  const [coords, setCoords] = useState<Coords | null>(null);
  const id = useId();
  const triggerRef = useRef<HTMLSpanElement | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const place = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const margin = 8;
    // Flip to bottom if there isn't room above.
    const wantTop = side === 'top';
    const fitsAbove = r.top > 140;
    const useSide: 'top' | 'bottom' = wantTop && !fitsAbove ? 'bottom' : side;
    let left = r.left + r.width / 2;
    // Keep the bubble within the viewport horizontally.
    const half = width / 2;
    left = Math.min(Math.max(left, half + margin), window.innerWidth - half - margin);
    const top = useSide === 'top' ? r.top - margin : r.bottom + margin;
    setCoords({ left, top, side: useSide });
  }, [side, width]);

  const show = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(place, 120);
  };
  const hide = () => {
    if (timer.current) clearTimeout(timer.current);
    setCoords(null);
  };

  return (
    <>
      <span
        ref={triggerRef}
        className="relative inline-flex items-center"
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        aria-describedby={coords ? id : undefined}
      >
        {children}
      </span>
      {coords &&
        createPortal(
          <span
            role="tooltip"
            id={id}
            style={{
              position: 'fixed',
              left: coords.left,
              top: coords.top,
              width,
              transform:
                coords.side === 'top'
                  ? 'translate(-50%, -100%)'
                  : 'translate(-50%, 0)',
            }}
            className="pointer-events-none z-[9999] animate-[fadeIn_120ms_ease-out] rounded-lg border border-amber-300/40 bg-zinc-900 px-3 py-2 text-left text-xs font-normal leading-relaxed text-zinc-200 shadow-xl shadow-black/40 dark:bg-zinc-800"
          >
            {content}
            <span
              className={`absolute left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 border-amber-300/40 bg-zinc-900 dark:bg-zinc-800 ${
                coords.side === 'top'
                  ? 'top-full -mt-1 border-b border-r'
                  : 'bottom-full -mb-1 border-l border-t'
              }`}
            />
          </span>,
          document.body,
        )}
    </>
  );
}

export default Tooltip;
