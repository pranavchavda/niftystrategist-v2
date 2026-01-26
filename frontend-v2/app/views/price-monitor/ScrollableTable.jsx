import React, { useRef, useState, useEffect } from 'react';

/**
 * ScrollableTable - A wrapper component that adds visual scroll indicators to tables
 * Shows gradient overlays on left/right edges to indicate scrollable content
 */
export default function ScrollableTable({ children, className = '' }) {
  const scrollContainerRef = useRef(null);
  const [showLeftGradient, setShowLeftGradient] = useState(false);
  const [showRightGradient, setShowRightGradient] = useState(false);
  const [showScrollHint, setShowScrollHint] = useState(false);

  const checkScroll = () => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const { scrollLeft, scrollWidth, clientWidth } = container;

    // Show left gradient if scrolled away from start
    setShowLeftGradient(scrollLeft > 10);

    // Show right gradient if there's more content to the right
    const hasRightContent = scrollLeft < scrollWidth - clientWidth - 10;
    setShowRightGradient(hasRightContent);

    // Show scroll hint only on first render if content is scrollable
    if (hasRightContent && scrollLeft === 0) {
      setShowScrollHint(true);
    } else {
      setShowScrollHint(false);
    }
  };

  useEffect(() => {
    // Check on mount and when children change
    checkScroll();

    // Add resize observer to check when content size changes
    const container = scrollContainerRef.current;
    if (!container) return;

    const resizeObserver = new ResizeObserver(checkScroll);
    resizeObserver.observe(container);

    return () => resizeObserver.disconnect();
  }, [children]);

  useEffect(() => {
    // Auto-hide scroll hint after 3 seconds
    if (showScrollHint) {
      const timer = setTimeout(() => setShowScrollHint(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [showScrollHint]);

  return (
    <div className={`relative ${className}`}>
      {/* Left gradient indicator */}
      {showLeftGradient && (
        <div
          className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-white dark:from-zinc-900 to-transparent pointer-events-none z-10"
          aria-hidden="true"
        />
      )}

      {/* Right gradient indicator */}
      {showRightGradient && (
        <div
          className="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-white dark:from-zinc-900 to-transparent pointer-events-none z-10"
          aria-hidden="true"
        />
      )}

      {/* Scrollable container */}
      <div
        ref={scrollContainerRef}
        onScroll={checkScroll}
        className="overflow-x-auto"
        style={{ WebkitOverflowScrolling: 'touch', touchAction: 'pan-x pan-y' }}
      >
        {children}
      </div>

      {/* Initial scroll hint (appears for 3 seconds on mount) */}
      {showScrollHint && (
        <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none z-10 animate-bounce">
          <div className="bg-blue-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium shadow-lg flex items-center gap-1.5">
            <span>Scroll →</span>
          </div>
        </div>
      )}
    </div>
  );
}
