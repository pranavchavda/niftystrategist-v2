import React, { Fragment } from 'react';
import { Dialog, DialogPanel, DialogTitle, Transition, TransitionChild } from '@headlessui/react';
import { clsx } from 'clsx';
import { X } from 'lucide-react';

/**
 * Modal Component
 *
 * A unified modal component built on Headless UI Dialog with consistent styling.
 *
 * Sizes:
 * - `sm`: 400px max width (confirmations, simple forms)
 * - `md`: 500px max width (standard forms)
 * - `lg`: 640px max width (complex forms)
 * - `xl`: 800px max width (large content)
 * - `full`: 95vw max width (full-screen modals)
 */

type ModalSize = 'sm' | 'md' | 'lg' | 'xl' | 'full';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  size?: ModalSize;
  className?: string;
  showCloseButton?: boolean;
  closeOnOverlayClick?: boolean;
}

const sizeClasses: Record<ModalSize, string> = {
  sm: 'max-w-[400px]',
  md: 'max-w-[500px]',
  lg: 'max-w-[640px]',
  xl: 'max-w-[800px]',
  full: 'max-w-[95vw] w-full',
};

export function Modal({
  isOpen,
  onClose,
  children,
  size = 'md',
  className,
  showCloseButton = true,
  closeOnOverlayClick = true,
}: ModalProps) {
  return (
    <Transition show={isOpen} as={Fragment}>
      <Dialog
        onClose={closeOnOverlayClick ? onClose : () => {}}
        className="relative z-50"
      >
        {/* Backdrop */}
        <TransitionChild
          as={Fragment}
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-sm dark:bg-black/60"
            aria-hidden="true"
          />
        </TransitionChild>

        {/* Modal container */}
        <div className="fixed inset-0 flex items-center justify-center p-4">
          <TransitionChild
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom="opacity-0 scale-95"
            enterTo="opacity-100 scale-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100 scale-100"
            leaveTo="opacity-0 scale-95"
          >
            <DialogPanel
              className={clsx(
                'w-full',
                sizeClasses[size],
                'bg-white/95 dark:bg-zinc-900/95',
                'backdrop-blur-2xl',
                'border border-zinc-200/50 dark:border-zinc-800/50',
                'rounded-2xl',
                'shadow-2xl shadow-zinc-900/20 dark:shadow-black/40',
                'overflow-hidden',
                'relative',
                className
              )}
            >
              {/* Close button */}
              {showCloseButton && (
                <button
                  onClick={onClose}
                  className={clsx(
                    'absolute top-4 right-4 z-10',
                    'p-2 rounded-lg',
                    'text-zinc-400 hover:text-zinc-600',
                    'dark:text-zinc-500 dark:hover:text-zinc-300',
                    'hover:bg-zinc-100 dark:hover:bg-zinc-800',
                    'transition-colors duration-150',
                    'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
                    'dark:focus:ring-offset-zinc-900'
                  )}
                  aria-label="Close modal"
                >
                  <X className="w-5 h-5" />
                </button>
              )}

              {children}
            </DialogPanel>
          </TransitionChild>
        </div>
      </Dialog>
    </Transition>
  );
}

/**
 * ModalHeader - Header section with title and optional description
 */
interface ModalHeaderProps {
  children: React.ReactNode;
  className?: string;
}

export function ModalHeader({ children, className }: ModalHeaderProps) {
  return (
    <div
      className={clsx(
        'px-6 pt-6 pb-4',
        'border-b border-zinc-200/50 dark:border-zinc-800/50',
        className
      )}
    >
      {children}
    </div>
  );
}

/**
 * ModalTitle - Title component (wraps DialogTitle)
 */
interface ModalTitleProps {
  children: React.ReactNode;
  className?: string;
}

export function ModalTitle({ children, className }: ModalTitleProps) {
  return (
    <DialogTitle
      className={clsx(
        'text-xl font-semibold',
        'text-zinc-900 dark:text-zinc-100',
        'pr-10', // Space for close button
        className
      )}
    >
      {children}
    </DialogTitle>
  );
}

/**
 * ModalDescription - Description/subtitle text
 */
interface ModalDescriptionProps {
  children: React.ReactNode;
  className?: string;
}

export function ModalDescription({ children, className }: ModalDescriptionProps) {
  return (
    <p
      className={clsx(
        'mt-1 text-sm',
        'text-zinc-600 dark:text-zinc-400',
        className
      )}
    >
      {children}
    </p>
  );
}

/**
 * ModalBody - Main content area
 */
interface ModalBodyProps {
  children: React.ReactNode;
  className?: string;
}

export function ModalBody({ children, className }: ModalBodyProps) {
  return (
    <div
      className={clsx(
        'px-6 py-6',
        'max-h-[60vh] overflow-y-auto',
        'custom-scrollbar',
        className
      )}
    >
      {children}
    </div>
  );
}

/**
 * ModalFooter - Footer with action buttons
 */
interface ModalFooterProps {
  children: React.ReactNode;
  className?: string;
}

export function ModalFooter({ children, className }: ModalFooterProps) {
  return (
    <div
      className={clsx(
        'px-6 py-4',
        'border-t border-zinc-200/50 dark:border-zinc-800/50',
        'bg-zinc-50/50 dark:bg-zinc-900/50',
        'flex items-center justify-end gap-3',
        className
      )}
    >
      {children}
    </div>
  );
}

/**
 * ConfirmModal - Specialized modal for confirmations
 */
interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'default' | 'danger';
  isLoading?: boolean;
}

export function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'default',
  isLoading = false,
}: ConfirmModalProps) {
  const confirmButtonStyles = variant === 'danger'
    ? 'bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-500/25'
    : 'bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 hover:bg-zinc-800 dark:hover:bg-zinc-200 shadow-lg';

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="sm" showCloseButton={false}>
      <ModalHeader>
        <ModalTitle>{title}</ModalTitle>
        {description && <ModalDescription>{description}</ModalDescription>}
      </ModalHeader>

      <ModalFooter>
        <button
          onClick={onClose}
          disabled={isLoading}
          className={clsx(
            'px-4 py-2 rounded-lg',
            'text-sm font-medium',
            'text-zinc-700 dark:text-zinc-300',
            'hover:bg-zinc-100 dark:hover:bg-zinc-800',
            'transition-colors duration-150',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          {cancelText}
        </button>
        <button
          onClick={onConfirm}
          disabled={isLoading}
          className={clsx(
            'px-4 py-2 rounded-lg',
            'text-sm font-medium',
            confirmButtonStyles,
            'transition-all duration-150',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'flex items-center gap-2'
          )}
        >
          {isLoading && (
            <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
                fill="none"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          )}
          {confirmText}
        </button>
      </ModalFooter>
    </Modal>
  );
}

/**
 * AlertModal - Specialized modal for alerts/notifications
 */
interface AlertModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  buttonText?: string;
  variant?: 'info' | 'success' | 'warning' | 'error';
}

export function AlertModal({
  isOpen,
  onClose,
  title,
  description,
  buttonText = 'OK',
  variant = 'info',
}: AlertModalProps) {
  const variantStyles = {
    info: 'text-blue-600 dark:text-blue-400',
    success: 'text-emerald-600 dark:text-emerald-400',
    warning: 'text-amber-600 dark:text-amber-400',
    error: 'text-red-600 dark:text-red-400',
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="sm" showCloseButton={false}>
      <ModalHeader>
        <ModalTitle className={variantStyles[variant]}>{title}</ModalTitle>
        {description && <ModalDescription>{description}</ModalDescription>}
      </ModalHeader>

      <ModalFooter>
        <button
          onClick={onClose}
          className={clsx(
            'px-4 py-2 rounded-lg',
            'text-sm font-medium',
            'bg-zinc-900 dark:bg-zinc-100',
            'text-white dark:text-zinc-900',
            'hover:bg-zinc-800 dark:hover:bg-zinc-200',
            'shadow-lg',
            'transition-all duration-150'
          )}
        >
          {buttonText}
        </button>
      </ModalFooter>
    </Modal>
  );
}
