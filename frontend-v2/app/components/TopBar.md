# TopBar Component

A translucent top navigation bar with glass morphism effect for EspressoBot, built using Catalyst UI components.

## Overview

The TopBar component provides a sleek, professional header following Linear/Vercel aesthetic principles. It features a glass morphism effect with backdrop blur, making it perfect for modern web applications.

## Features

- **Glass Morphism**: Translucent background with backdrop blur for a modern look
- **Catalyst UI Components**: Built using official Catalyst patterns (Badge, Button, Dropdown, Avatar)
- **Responsive Design**: Adapts to different screen sizes with hidden elements on mobile
- **Keyboard Accessible**: Full keyboard navigation support with Cmd+K search shortcut
- **Status Indicators**: Dynamic status badge with customizable colors
- **User Menu**: Dropdown menu with user info and actions
- **Loading State**: Built-in skeleton component for loading states
- **Dark Mode**: Full dark mode support

## Installation

The component requires the following dependencies (already included in the project):

```bash
npm install @headlessui/react clsx lucide-react
```

## Usage

### Basic Usage

```jsx
import { TopBar } from './components/TopBar'

function App() {
  const user = {
    name: 'John Doe',
    email: 'john@idrinkcoffee.com',
    avatarUrl: null, // Optional: provide image URL
  }

  return (
    <div>
      <TopBar
        status="Ready"
        statusColor="emerald"
        onSearchClick={() => console.log('Search')}
        onLogsClick={() => console.log('Logs')}
        onLogout={() => console.log('Logout')}
        user={user}
      />
      {/* Your app content */}
    </div>
  )
}
```

### With Keyboard Shortcuts

```jsx
import React from 'react'
import { TopBar } from './components/TopBar'

function App() {
  const [isSearchOpen, setIsSearchOpen] = React.useState(false)

  // Handle Cmd/Ctrl + K
  React.useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setIsSearchOpen(true)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return (
    <TopBar
      onSearchClick={() => setIsSearchOpen(true)}
      user={user}
    />
  )
}
```

### Loading State

```jsx
import { TopBar } from './components/TopBar'

function LoadingApp() {
  const [loading, setLoading] = React.useState(true)

  if (loading) {
    return <TopBar.Skeleton />
  }

  return <TopBar {...props} />
}
```

## Props

### TopBar

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `status` | `string` | `"Ready"` | Status text displayed in the badge |
| `statusColor` | `string` | `"emerald"` | Badge color (see Badge Colors below) |
| `onSearchClick` | `function` | `undefined` | Handler for search button click |
| `onLogsClick` | `function` | `undefined` | Handler for logs button click |
| `onLogout` | `function` | `undefined` | Handler for logout action |
| `user` | `object` | See below | User object with name, email, avatarUrl |
| `className` | `string` | `""` | Additional CSS classes |

### User Object

```typescript
{
  name: string,      // User's full name
  email: string,     // User's email address
  avatarUrl: string | null  // Optional avatar image URL
}
```

### Badge Colors

Available colors for the `statusColor` prop:

- `emerald` - Success/Ready state (default)
- `blue` - Processing/Active state
- `amber` - Warning/Busy state
- `red` - Error state
- `zinc` - Neutral/Offline state
- `green`, `orange`, `yellow`, `cyan`, `indigo`, `purple`, `pink`, `rose`

## Component Structure

The TopBar is divided into two main sections:

### Left Section
- **Logo Badge**: Gradient badge with "EB" initials
- **App Name**: "EspressoBot" text
- **Status Badge**: Dynamic status indicator

### Right Section
- **Search Button**: With Cmd+K hint (hidden on mobile)
- **Logs Button**: With optional text label (hidden on smaller screens)
- **User Menu**: Dropdown with avatar and user actions

## Styling

### Glass Morphism Effect

The component uses the following Tailwind classes for the glass effect:

```css
bg-white/70 dark:bg-zinc-900/70 backdrop-blur-xl
```

### Border

Subtle border with reduced opacity:

```css
border-b border-zinc-200/50 dark:border-zinc-800/50
```

### Height

Fixed height of 48px (12 in Tailwind scale):

```css
h-12
```

## Accessibility

The component follows WCAG accessibility guidelines:

- **Semantic HTML**: Uses `<header>` with `role="banner"`
- **ARIA Labels**: All icon-only buttons have `aria-label` attributes
- **Keyboard Navigation**: Full keyboard support via Headless UI
- **Screen Reader**: Proper labeling for assistive technologies
- **Focus Management**: Visible focus indicators with blue ring

## Customization

### Custom Logo

Replace the logo badge by editing the left section:

```jsx
<div className="flex items-center gap-2">
  <img src="/logo.svg" alt="Logo" className="h-7 w-auto" />
  <span className="text-sm font-semibold text-zinc-900 dark:text-white">
    Your App Name
  </span>
</div>
```

### Additional Menu Items

Extend the user dropdown menu:

```jsx
<DropdownMenu anchor="bottom end" className="min-w-56">
  {/* Existing items */}
  <DropdownItem onClick={() => navigate('/billing')}>
    Billing
  </DropdownItem>
  <DropdownItem onClick={() => navigate('/team')}>
    Team
  </DropdownItem>
</DropdownMenu>
```

### Status Updates

Dynamically update status based on application state:

```jsx
const [status, setStatus] = React.useState('Ready')
const [statusColor, setStatusColor] = React.useState('emerald')

// On some action
setStatus('Processing')
setStatusColor('blue')

// On error
setStatus('Error')
setStatusColor('red')

// On completion
setStatus('Ready')
setStatusColor('emerald')
```

## Integration with React Router

```jsx
import { useNavigate } from 'react-router-dom'

function App() {
  const navigate = useNavigate()

  return (
    <TopBar
      onLogsClick={() => navigate('/logs')}
      onLogout={() => {
        // Clear auth tokens
        localStorage.removeItem('token')
        navigate('/login')
      }}
    />
  )
}
```

## Performance

The component is optimized for performance:

- **Lazy Loading**: Only renders visible elements
- **Memoization Ready**: Can be wrapped with `React.memo()` if needed
- **Minimal Re-renders**: Uses efficient event handlers
- **Tree-shaking**: Imports only necessary Lucide icons

## Browser Support

- Chrome/Edge: ✓ Full support
- Firefox: ✓ Full support
- Safari: ✓ Full support
- Backdrop blur may have reduced support on older browsers

## Related Components

- **Badge** (`/components/catalyst/badge.jsx`) - Status indicator
- **Button** (`/components/catalyst/button.jsx`) - Action buttons
- **Dropdown** (`/components/catalyst/dropdown.jsx`) - User menu
- **Avatar** (`/components/catalyst/avatar.jsx`) - User profile picture

## Examples

See `TopBar.example.jsx` for complete usage examples including:

- Basic implementation
- Different status states
- Keyboard shortcuts
- Integration patterns

## Credits

Built with [Catalyst UI](https://catalyst.tailwindui.com/) by Tailwind Labs.
