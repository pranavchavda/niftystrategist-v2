import * as Headless from '@headlessui/react'
import clsx from 'clsx'
import React, { forwardRef } from 'react'

export const Input = forwardRef(function Input({ className, ...props }, ref) {
  return (
    <span
      data-slot="control"
      className={clsx([
        // Basic layout
        'relative block w-full',
        // Background color + shadow applied to inset pseudo element, so shadow blends with border in light mode
        'before:absolute before:inset-px before:rounded-[calc(theme(borderRadius.lg)-1px)] before:bg-white before:shadow',
        // Background color is moved to control and shadow is removed in dark mode so hide `before` pseudo
        'dark:before:hidden',
        // Focus ring
        'after:pointer-events-none after:absolute after:inset-0 after:rounded-lg after:ring-inset after:ring-transparent sm:after:focus-within:ring-2 sm:after:focus-within:ring-blue-500',
        // Disabled state
        'has-disabled:opacity-50 before:has-disabled:bg-zinc-950/5 before:has-disabled:shadow-none',
        className,
      ])}
    >
      <Headless.Input
        ref={ref}
        {...props}
        className={clsx([
          // Date and time inputs have a white background in dark mode, which would show through translucent border.
          (props.type === 'date' || props.type === 'datetime-local' || props.type === 'time') &&
            'dark:[color-scheme:light]',
          // Basic layout
          'relative block w-full appearance-none rounded-lg px-[calc(theme(spacing[3.5])-1px)] py-[calc(theme(spacing[2.5])-1px)] sm:px-[calc(theme(spacing.3)-1px)] sm:py-[calc(theme(spacing[1.5])-1px)]',
          // Typography
          'text-base/6 text-zinc-950 placeholder:text-zinc-500 sm:text-sm/6 dark:text-white dark:placeholder:text-zinc-400',
          // Border
          'border border-zinc-950/10 hover:border-zinc-950/20 dark:border-white/10 dark:hover:border-white/20',
          // Background color
          'bg-transparent dark:bg-white/5',
          // Hide default focus styles
          'focus:outline-none focus:border-zinc-950/20 dark:focus:border-white/20',
          // Invalid state
          'invalid:border-red-500 invalid:hover:border-red-500 dark:invalid:border-red-500 dark:invalid:hover:border-red-500',
          // Disabled state
          'disabled:border-zinc-950/20 disabled:bg-zinc-950/5 dark:disabled:border-white/15 dark:disabled:bg-white/[2.5%] disabled:opacity-50',
        ])}
      />
    </span>
  )
})