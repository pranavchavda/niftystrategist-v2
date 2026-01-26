import * as Headless from '@headlessui/react'
import clsx from 'clsx'

import { Text } from './text'

const sizes = {
  xs: 'w-full sm:max-w-xs',
  sm: 'w-full sm:max-w-sm',
  md: 'w-full sm:max-w-md',
  lg: 'w-full sm:max-w-lg',
  xl: 'w-full sm:max-w-xl',
  '2xl': 'w-full md:max-w-2xl',
  '3xl': 'w-full md:max-w-3xl',
  '4xl': 'w-full md:max-w-4xl lg:max-w-5xl',
  '5xl': 'w-full md:max-w-5xl lg:max-w-6xl',
}

export function Dialog({ size = 'lg', className, children, ...props }) {
  return (
    <Headless.Dialog {...props}>
      <Headless.DialogBackdrop
        transition
        className="fixed inset-0 flex w-screen justify-center overflow-y-auto bg-zinc-950/25 px-0 py-0 transition duration-100 focus:outline-0 data-closed:opacity-0 data-enter:ease-out data-leave:ease-in sm:px-4 sm:py-4 md:px-6 md:py-8 lg:px-8 lg:py-16 dark:bg-zinc-950/50"
      />

      <div className="fixed inset-0 w-screen overflow-y-auto pt-0 sm:pt-0">
        <div className="grid min-h-full grid-rows-[1fr_auto] justify-items-center sm:grid-rows-[1fr_auto_3fr] sm:p-4 w-full">
          <Headless.DialogPanel
            transition
            className={clsx(
              className,
              sizes[size],
              'row-start-2 w-full min-w-0 rounded-t-3xl sm:rounded-2xl bg-white p-(--gutter) shadow-lg ring-1 ring-zinc-950/10 [--gutter:--spacing(4)] sm:[--gutter:--spacing(6)] md:[--gutter:--spacing(8)] sm:mb-auto dark:bg-zinc-900 dark:ring-white/10 forced-colors:outline',
              'transition duration-100 will-change-transform data-closed:translate-y-12 data-closed:opacity-0 data-enter:ease-out data-leave:ease-in sm:data-closed:translate-y-0 sm:data-closed:data-enter:scale-95',
              'flex flex-col max-h-screen sm:max-h-[90vh]'
            )}
          >
            {children}
          </Headless.DialogPanel>
        </div>
      </div>
    </Headless.Dialog>
  )
}

export function DialogTitle({ className, ...props }) {
  return (
    <Headless.DialogTitle
      {...props}
      className={clsx(className, 'text-base/6 sm:text-lg/6 font-semibold text-balance text-zinc-950 dark:text-white')}
    />
  )
}

export function DialogDescription({ className, ...props }) {
  return <Headless.Description as={Text} {...props} className={clsx(className, 'mt-2 text-pretty')} />
}

export function DialogBody({ className, ...props }) {
  return <div {...props} className={clsx(className, 'overflow-y-auto flex-1')} />
}

export function DialogActions({ className, ...props }) {
  return (
    <div
      {...props}
      className={clsx(
        className,
        'mt-6 sm:mt-8 flex flex-col-reverse items-stretch justify-end gap-2 sm:gap-3 *:w-full sm:flex-row sm:items-center sm:*:w-auto *:min-h-[44px] sm:*:min-h-0'
      )}
    />
  )
}
