import * as Headless from '@headlessui/react'
import clsx from 'clsx'
import React, { forwardRef } from 'react'
import { Link } from './link'

const styles = {
  base: [
    // Base
    'relative isolate inline-flex items-center justify-center gap-x-2 rounded-lg border text-base/6 font-semibold',
    // Sizing
    'px-[calc(theme(spacing[3.5])-1px)] py-[calc(theme(spacing[2.5])-1px)] sm:px-[calc(theme(spacing.3)-1px)] sm:py-[calc(theme(spacing[1.5])-1px)] sm:text-sm/6',
    // Focus
    'focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
    // Disabled
    'data-disabled:opacity-50',
    // Icon
    '*:data-[slot=icon]:-mx-0.5 *:data-[slot=icon]:my-0.5 *:data-[slot=icon]:size-5 sm:*:data-[slot=icon]:my-1 sm:*:data-[slot=icon]:size-4',
  ],
  solid: [
    // Optical border, implemented as the button background to avoid corner artifacts
    'border-transparent bg-zinc-950 text-white data-hover:bg-zinc-800 data-active:bg-zinc-700 dark:bg-white dark:text-zinc-950 dark:data-hover:bg-zinc-200 dark:data-active:bg-zinc-300',
  ],
  outline: [
    // Base
    'border-zinc-950/10 text-zinc-950 data-hover:bg-zinc-950/2.5 data-active:bg-zinc-950/5 dark:border-white/15 dark:text-white dark:data-hover:bg-white/2.5 dark:data-active:bg-white/5',
    // Icon
    '*:data-[slot=icon]:text-zinc-500 dark:*:data-[slot=icon]:text-zinc-400',
  ],
  plain: [
    // Base
    'border-transparent text-zinc-950 data-hover:bg-zinc-950/5 data-active:bg-zinc-950/10 dark:text-white dark:data-hover:bg-white/5 dark:data-active:bg-white/10',
    // Icon
    '*:data-[slot=icon]:text-zinc-500 dark:*:data-[slot=icon]:text-zinc-400',
  ],
}

export const Button = forwardRef(function Button(
  { variant = 'solid', className, ...props },
  ref
) {
  let classes = clsx(className, styles.base, styles[variant])

  return typeof props.href === 'string' ? (
    <Link {...props} className={classes} ref={ref} />
  ) : (
    <Headless.Button {...props} className={classes} ref={ref} />
  )
})

// TouchTarget component for better touch accessibility
export function TouchTarget({ children }) {
  return (
    <>
      <span
        className="absolute left-1/2 top-1/2 size-[max(100%,2.75rem)] -translate-x-1/2 -translate-y-1/2 [@media(pointer:fine)]:hidden"
        aria-hidden="true"
      />
      {children}
    </>
  )
}