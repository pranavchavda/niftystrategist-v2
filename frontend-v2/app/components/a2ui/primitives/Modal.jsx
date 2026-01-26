/**
 * Modal - Modal dialog component
 *
 * Props:
 * - entryPointChild: component that triggers modal open (button, etc.)
 * - contentChild: component to display inside modal
 * - title: optional modal title
 * - open: controlled open state (optional)
 * - onClose: callback when modal closes
 * - children: alternative to contentChild
 */

import { useState, useEffect } from 'react';
import clsx from 'clsx';

export function Modal({
  entryPointChild,
  contentChild,
  title,
  open: controlledOpen,
  onClose,
  children,
  id,
  style,
  renderComponent,
  onInteraction,
}) {
  const [isOpen, setIsOpen] = useState(false);

  // Support controlled mode
  const open = controlledOpen !== undefined ? controlledOpen : isOpen;

  const handleOpen = () => {
    setIsOpen(true);
    onInteraction?.('modal_open', { id });
  };

  const handleClose = () => {
    setIsOpen(false);
    onClose?.();
    onInteraction?.('modal_close', { id });
  };

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && open) {
        handleClose();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [open]);

  return (
    <>
      {/* Entry point / trigger */}
      <div onClick={handleOpen} className="cursor-pointer inline-block">
        {entryPointChild && renderComponent
          ? renderComponent(entryPointChild)
          : entryPointChild}
      </div>

      {/* Modal overlay and content */}
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 animate-in fade-in duration-200"
          onClick={handleClose}
        >
          <div
            id={id}
            style={style}
            className="bg-white dark:bg-zinc-800 rounded-lg shadow-xl max-w-lg w-full max-h-[80vh] overflow-auto animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            {title && (
              <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-200 dark:border-zinc-700">
                <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                  {title}
                </h3>
                <button
                  type="button"
                  onClick={handleClose}
                  className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            )}

            {/* Content */}
            <div className="p-4">
              {contentChild && renderComponent
                ? renderComponent(contentChild)
                : children || contentChild}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
