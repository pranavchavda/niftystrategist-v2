import React from 'react'
import clsx from 'clsx'
import { Search, FileText, ChevronDown } from 'lucide-react'
import { Badge } from './catalyst/badge'
import { Button } from './catalyst/button'
import { Dropdown, DropdownButton, DropdownMenu, DropdownItem, DropdownDivider } from './catalyst/dropdown'
import { Avatar } from './catalyst/avatar'

/**
 * TopBar Component
 *
 * A translucent top navigation bar with glass morphism effect.
 * Following Catalyst UI patterns and Linear/Vercel aesthetic.
 *
 * @param {Object} props
 * @param {string} props.status - Status text (default: "Ready")
 * @param {string} props.statusColor - Badge color for status (default: "emerald")
 * @param {Function} props.onSearchClick - Handler for search button click
 * @param {Function} props.onLogsClick - Handler for logs button click
 * @param {Object} props.user - User object with name, email, and avatarUrl
 * @param {Function} props.onLogout - Handler for logout action
 * @param {string} props.className - Additional CSS classes
 */
export function TopBar({
  status = 'Ready',
  statusColor = 'emerald',
  onSearchClick,
  onLogsClick,
  onLogout,
  user = {
    name: 'User',
    email: 'user@example.com',
    avatarUrl: null,
  },
  className,
  ...props
}) {
  // Get user initials for avatar
  const getInitials = (name) => {
    if (!name) return '?'
    const parts = name.split(' ')
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
    }
    return name.substring(0, 2).toUpperCase()
  }

  return (
    <header
      {...props}
      className={clsx(
        className,
        // Height and layout
        'h-12 flex items-center justify-between px-4',
        // Glass morphism effect
        'bg-white/70 dark:bg-zinc-900/70 backdrop-blur-xl',
        // Border
        'border-b border-zinc-200/50 dark:border-zinc-800/50',
        // Fixed positioning
        'sticky top-0 z-50',
        // Smooth transitions
        'transition-all duration-200'
      )}
      role="banner"
    >
      {/* Left Section: Logo + Status */}
      <div className="flex items-center gap-3">
        {/* Logo Badge */}
        <div className="flex items-center gap-2">
          <div className="flex items-center justify-center size-7 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 text-white font-bold text-sm shadow-sm">
            NS
          </div>
          <span className="text-sm font-semibold text-zinc-900 dark:text-white">
            Nifty Strategist
          </span>
        </div>

        {/* Status Divider */}
        <div
          className="h-4 w-px bg-zinc-300 dark:bg-zinc-700"
          aria-hidden="true"
        />

        {/* Status Badge */}
        <Badge color={statusColor} className="font-normal">
          {status}
        </Badge>
      </div>

      {/* Right Section: Actions + User Menu */}
      <div className="flex items-center gap-2">
        {/* Search Button */}
        <Button
          variant="plain"
          onClick={onSearchClick}
          aria-label="Search"
          className={clsx(
            'flex items-center gap-2 px-3 h-8',
            'text-zinc-600 dark:text-zinc-400',
            'hover:bg-zinc-100 dark:hover:bg-zinc-800',
            'focus:outline-hidden focus:ring-2 focus:ring-blue-500'
          )}
        >
          <Search className="size-4" aria-hidden="true" />
          <span className="hidden sm:inline text-xs text-zinc-500 dark:text-zinc-500">
            <kbd className="font-sans">⌘K</kbd>
          </span>
        </Button>

        {/* Logs Button */}
        <Button
          variant="plain"
          onClick={onLogsClick}
          aria-label="View logs"
          className={clsx(
            'flex items-center gap-2 px-3 h-8',
            'text-zinc-600 dark:text-zinc-400',
            'hover:bg-zinc-100 dark:hover:bg-zinc-800'
          )}
        >
          <FileText className="size-4" aria-hidden="true" />
          <span className="hidden md:inline text-sm">Logs</span>
        </Button>

        {/* Divider before user menu */}
        <div
          className="h-6 w-px bg-zinc-300 dark:bg-zinc-700 mx-1"
          aria-hidden="true"
        />

        {/* User Dropdown Menu */}
        <Dropdown>
          <DropdownButton
            as="button"
            className={clsx(
              'flex items-center gap-2 px-2 py-1 rounded-lg',
              'hover:bg-zinc-100 dark:hover:bg-zinc-800',
              'focus:outline-hidden focus:ring-2 focus:ring-blue-500',
              'transition-colors duration-150'
            )}
            aria-label="User menu"
          >
            <Avatar
              src={user.avatarUrl}
              initials={getInitials(user.name)}
              alt={user.name}
              className="size-7"
            />
            <ChevronDown
              className="size-4 text-zinc-500 dark:text-zinc-400"
              aria-hidden="true"
            />
          </DropdownButton>

          <DropdownMenu anchor="bottom end" className="min-w-56">
            {/* User Info Header */}
            <div className="px-3 py-2.5 border-b border-zinc-200 dark:border-zinc-700">
              <div className="text-sm font-medium text-zinc-900 dark:text-white">
                {user.name}
              </div>
              <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                {user.email}
              </div>
            </div>

            {/* Menu Items */}
            <DropdownItem onClick={() => console.log('Settings clicked')}>
              Settings
            </DropdownItem>
            <DropdownItem onClick={() => console.log('Preferences clicked')}>
              Preferences
            </DropdownItem>
            <DropdownItem onClick={() => console.log('Keyboard shortcuts clicked')}>
              Keyboard shortcuts
            </DropdownItem>

            <DropdownDivider />

            <DropdownItem onClick={onLogout}>
              Sign out
            </DropdownItem>
          </DropdownMenu>
        </Dropdown>
      </div>
    </header>
  )
}

/**
 * TopBar.Skeleton - Loading state component
 */
TopBar.Skeleton = function TopBarSkeleton({ className, ...props }) {
  return (
    <header
      {...props}
      className={clsx(
        className,
        'h-12 flex items-center justify-between px-4',
        'bg-white/70 dark:bg-zinc-900/70 backdrop-blur-xl',
        'border-b border-zinc-200/50 dark:border-zinc-800/50',
        'animate-pulse'
      )}
      aria-busy="true"
      aria-label="Loading navigation"
    >
      <div className="flex items-center gap-3">
        <div className="size-7 rounded-lg bg-zinc-200 dark:bg-zinc-700" />
        <div className="h-4 w-24 rounded bg-zinc-200 dark:bg-zinc-700" />
      </div>
      <div className="flex items-center gap-2">
        <div className="h-8 w-8 rounded-lg bg-zinc-200 dark:bg-zinc-700" />
        <div className="h-8 w-20 rounded-lg bg-zinc-200 dark:bg-zinc-700 hidden sm:block" />
        <div className="size-7 rounded-full bg-zinc-200 dark:bg-zinc-700" />
      </div>
    </header>
  )
}
