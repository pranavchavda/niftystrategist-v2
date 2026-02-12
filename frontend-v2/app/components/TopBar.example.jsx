import React from 'react'
import { TopBar } from './TopBar'

/**
 * Example usage of the TopBar component
 */
export function TopBarExample() {
  const handleSearchClick = () => {
    console.log('Search clicked')
    // Implement your search modal/command palette here
  }

  const handleLogsClick = () => {
    console.log('Logs clicked')
    // Navigate to logs page or open logs panel
  }

  const handleLogout = () => {
    console.log('Logout clicked')
    // Implement logout logic
    // Example: navigate to /logout or clear auth tokens
  }

  const user = {
    name: 'John Doe',
    email: 'john@idrinkcoffee.com',
    avatarUrl: null, // Can provide a URL like: 'https://i.pravatar.cc/150?u=john@example.com'
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      {/* TopBar with default "Ready" status */}
      <TopBar
        status="Ready"
        statusColor="emerald"
        onSearchClick={handleSearchClick}
        onLogsClick={handleLogsClick}
        onLogout={handleLogout}
        user={user}
      />

      {/* Main content */}
      <main className="p-8">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">
          Nifty Strategist Dashboard
        </h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Your content goes here...
        </p>
      </main>
    </div>
  )
}

/**
 * Example with different statuses
 */
export function TopBarStatusExamples() {
  return (
    <div className="space-y-8">
      {/* Ready status */}
      <div>
        <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
          Ready Status
        </h2>
        <TopBar
          status="Ready"
          statusColor="emerald"
          user={{ name: 'User', email: 'user@example.com' }}
        />
      </div>

      {/* Processing status */}
      <div>
        <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
          Processing Status
        </h2>
        <TopBar
          status="Processing"
          statusColor="blue"
          user={{ name: 'User', email: 'user@example.com' }}
        />
      </div>

      {/* Busy status */}
      <div>
        <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
          Busy Status
        </h2>
        <TopBar
          status="Busy"
          statusColor="amber"
          user={{ name: 'User', email: 'user@example.com' }}
        />
      </div>

      {/* Error status */}
      <div>
        <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
          Error Status
        </h2>
        <TopBar
          status="Error"
          statusColor="red"
          user={{ name: 'User', email: 'user@example.com' }}
        />
      </div>

      {/* Offline status */}
      <div>
        <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
          Offline Status
        </h2>
        <TopBar
          status="Offline"
          statusColor="zinc"
          user={{ name: 'User', email: 'user@example.com' }}
        />
      </div>

      {/* Loading skeleton */}
      <div>
        <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
          Loading State
        </h2>
        <TopBar.Skeleton />
      </div>
    </div>
  )
}

/**
 * Keyboard shortcut handler example
 */
export function TopBarWithKeyboardShortcuts() {
  React.useEffect(() => {
    const handleKeyDown = (event) => {
      // Cmd/Ctrl + K for search
      if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
        event.preventDefault()
        console.log('Search triggered via keyboard shortcut')
        // Open your search modal/command palette
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return (
    <TopBar
      status="Ready"
      statusColor="emerald"
      onSearchClick={() => console.log('Search opened')}
      onLogsClick={() => console.log('Logs opened')}
      onLogout={() => console.log('Logging out')}
      user={{
        name: 'John Doe',
        email: 'john@idrinkcoffee.com',
        avatarUrl: null,
      }}
    />
  )
}
