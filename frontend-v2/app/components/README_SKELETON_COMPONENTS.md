# Skeleton Loading Components - Quick Reference

## Overview

This directory contains reusable skeleton loading components for consistent loading states throughout the application.

## Components

### SkeletonCard

Skeleton loaders for card-based layouts.

```jsx
import SkeletonCard from './components/SkeletonCard';

// Category page cards
<SkeletonCard variant="category" count={6} />

// Product cards
<SkeletonCard variant="product" count={4} />

// Compact list items
<SkeletonCard variant="compact" count={3} />
```

**Variants:**
- `category` - Full category card with image, title, description, button
- `product` - Product card with image and details
- `compact` - Simple list item with icon and text

### SkeletonTable

Skeleton loaders for table and list data.

```jsx
import SkeletonTable from './components/SkeletonTable';

// Traditional table
<SkeletonTable rows={5} columns={3} variant="default" />

// Grid layout
<SkeletonTable rows={6} variant="grid" />

// List layout
<SkeletonTable rows={8} variant="list" />
```

**Variants:**
- `default` - Standard table with headers
- `grid` - Card grid layout
- `list` - Vertical list with avatars

### SkeletonForm

Skeleton loaders for form fields.

```jsx
import SkeletonForm from './components/SkeletonForm';

// Standard form
<SkeletonForm fields={4} showButtons={true} variant="default" />

// Inline form
<SkeletonForm fields={3} variant="inline" />

// Modal form
<SkeletonForm fields={5} variant="modal" />
```

**Variants:**
- `default` - Vertical form with labels
- `inline` - Horizontal inline fields
- `modal` - Modal-style with title and actions

### SkeletonText

Skeleton loaders for text content.

```jsx
import SkeletonText from './components/SkeletonText';

// Paragraphs
<SkeletonText lines={3} variant="paragraph" />

// Headings
<SkeletonText lines={2} variant="heading" />

// Mixed content
<SkeletonText lines={5} variant="mixed" />
```

**Variants:**
- `paragraph` - Standard text lines
- `heading` - Large heading-style text
- `mixed` - Heading + paragraphs

### LoadingMessage

Context-aware loading messages with spinner.

```jsx
import LoadingMessage from './components/LoadingMessage';

// Default (centered)
<LoadingMessage message="Loading category pages..." />

// Inline (small)
<LoadingMessage message="Uploading..." variant="inline" />

// Minimal (spinner only)
<LoadingMessage variant="minimal" />
```

**Variants:**
- `default` - Centered spinner with message
- `inline` - Side-by-side spinner and message
- `minimal` - Spinner only, no text

## Context-Aware Loading Messages

Always use descriptive, action-specific messages:

### Good Examples ✅
```jsx
<LoadingMessage message="Loading category pages..." />
<LoadingMessage message="Regenerating hero image..." />
<LoadingMessage message="Uploading image..." />
<LoadingMessage message="Saving changes..." />
<LoadingMessage message="Fetching images from Shopify CDN..." />
<LoadingMessage message="Searching products..." />
<LoadingMessage message="Creating page..." />
```

### Bad Examples ❌
```jsx
<LoadingMessage message="Loading..." /> // Too generic
<LoadingMessage message="Please wait..." /> // Not descriptive
<LoadingMessage message="Processing..." /> // Vague
```

## Common Patterns

### Full Page Loading
```jsx
{loading ? (
  <div className="h-full flex flex-col">
    {/* Header skeleton */}
    <div className="p-6 border-b border-zinc-200 dark:border-zinc-800">
      <div className="max-w-7xl mx-auto">
        <SkeletonText lines={2} variant="heading" />
      </div>
    </div>

    {/* Content skeleton */}
    <div className="flex-1 overflow-auto p-6">
      <LoadingMessage message="Loading..." className="mb-8" />
      <SkeletonCard variant="category" count={6} />
    </div>
  </div>
) : (
  <ActualContent />
)}
```

### Modal Loading
```jsx
{loadingModalData ? (
  <LoadingMessage message="Fetching details..." className="py-12" />
) : (
  <ModalContent />
)}
```

### Inline Loading
```jsx
{searching ? (
  <LoadingMessage message="Searching..." variant="inline" />
) : (
  <SearchResults />
)}
```

### Button Loading States
```jsx
<button disabled={saving}>
  {saving ? (
    <>
      <Loader2 className="h-4 w-4 animate-spin" />
      Saving changes...
    </>
  ) : (
    'Save'
  )}
</button>
```

## Styling Guidelines

### Colors
- Light mode background: `bg-zinc-200`
- Dark mode background: `bg-zinc-700`
- Shimmer overlay (light): `via-white/50`
- Shimmer overlay (dark): `via-zinc-500/50`

### Animations
- Pulse: `animate-pulse` (2s infinite)
- Shimmer: `animate-shimmer` (2s infinite)
- Spinner: `animate-spin` (1s infinite)

### Sizing
- Match actual component dimensions
- Use natural spacing and gaps
- Vary widths for realistic effect

## Accessibility

### Reduced Motion
All animations respect `prefers-reduced-motion: reduce` via `animations.css`.

### Screen Readers
Consider adding ARIA labels:
```jsx
<div role="status" aria-live="polite" aria-label="Loading content">
  <LoadingMessage message="Loading..." />
</div>
```

## Best Practices

1. **Show Immediately** - Display skeletons instantly, don't wait for API response
2. **Match Dimensions** - Skeleton should match actual content size to prevent layout shift
3. **Be Specific** - Use context-aware messages that describe the actual operation
4. **Consistent Patterns** - Use same skeleton for same content type throughout app
5. **Smooth Transitions** - Consider adding fade-in when transitioning from skeleton to content
6. **Progress Feedback** - For long operations, add progress indicators or percentages
7. **Error Handling** - Replace skeleton with error state, don't leave skeleton hanging

## Testing Checklist

- [ ] Skeleton displays immediately on load
- [ ] Shimmer animation plays smoothly
- [ ] Dark mode skeleton colors are correct
- [ ] Loading message is descriptive and accurate
- [ ] Transition to real content is smooth (no flash)
- [ ] No layout shift (CLS) when content loads
- [ ] Respects `prefers-reduced-motion`
- [ ] Works on mobile devices
- [ ] Looks correct in all supported browsers

## Performance Tips

1. **Memoize Skeletons** - Wrap in `React.memo()` if re-rendering frequently
2. **Limit Count** - Don't render hundreds of skeleton items, use pagination
3. **CSS Animations** - Use CSS animations (not JS) for smooth 60fps
4. **Avoid Re-renders** - Don't trigger re-renders while skeleton is showing

## Examples in Codebase

See these files for real implementations:

- `/views/cms/CategoryLandingPagesPage.jsx` - Full page skeleton with grid
- `/components/MetaobjectPicker.jsx` - Dropdown loading state
- `/components/MetaobjectEditor.jsx` - Modal loading preparation

## Future Enhancements

- Add progress percentages for long operations
- Implement staggered entrance animations
- Create skeleton variants for nested editors
- Add smart skeleton that adapts to content
- Build skeleton component generator tool
