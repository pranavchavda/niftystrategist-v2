# Breadcrumb Navigation Implementation

## Overview
Comprehensive breadcrumb navigation system implemented throughout the CMS interface to improve context awareness and navigation. The system supports nested navigation levels and automatically adapts to mobile screens.

## Components

### 1. Breadcrumb Component
**Location**: `/home/pranav/pydanticebot/frontend-v2/app/components/Breadcrumb.jsx`

Three breadcrumb variants:

#### `Breadcrumb` (Default)
Standard breadcrumb for desktop with full navigation path.

```jsx
<Breadcrumb
  items={[
    { label: 'CMS', href: '/cms' },
    { label: 'Category Pages', href: '/cms/category-pages' },
    { label: 'Edit "Espresso Machines"', current: true }
  ]}
/>
```

#### `MobileBreadcrumb`
Mobile-optimized breadcrumb that collapses middle items for space efficiency.

Pattern: `Home > ... > Current` (when more than 2 items)

```jsx
<MobileBreadcrumb
  items={[
    { label: 'Home', href: '/' },
    { label: 'CMS', href: '/cms' },
    { label: 'Category Pages', href: '/cms/category-pages' },
    { label: 'Edit "Espresso Machines"', current: true }
  ]}
/>
// Renders: Home > ... > Edit "Espresso Machines"
```

#### `ResponsiveBreadcrumb` (Recommended)
Automatically switches between full and mobile breadcrumbs based on screen size.

```jsx
<ResponsiveBreadcrumb
  items={[
    { label: 'CMS', href: '/cms' },
    { label: 'Category Pages', href: '/cms/category-pages' },
    { label: 'Edit "Espresso Machines"', current: true }
  ]}
/>
```

## Integration Points

### 1. CategoryLandingPagesPage
**Location**: `/home/pranav/pydanticebot/frontend-v2/app/views/cms/CategoryLandingPagesPage.jsx`

**States and Breadcrumb Patterns**:

#### View Mode (List)
```
CMS > Category Pages
```

#### Create Mode
```
CMS > Category Pages > Create New
```

#### Edit Mode
```
CMS > Category Pages > Edit "Single Dose Grinders"
```

**Implementation**:
```jsx
const getBreadcrumbItems = () => {
  const base = [
    { label: 'CMS', href: '/cms' },
    { label: 'Category Pages', href: '/cms/category-pages' },
  ];

  if (showCreateModal) {
    return [...base, { label: 'Create New', current: true }];
  }

  if (editingPage) {
    return [...base, { label: `Edit "${editingPage.displayName || editingPage.title}"`, current: true }];
  }

  return base;
};

// Render in toolbar
<ResponsiveBreadcrumb items={getBreadcrumbItems()} />
```

### 2. FAQSectionEditor (Nested)
**Location**: `/home/pranav/pydanticebot/frontend-v2/app/components/FAQSectionEditor.jsx`

**Pattern**:
```
CMS > Category Pages > Edit "Espresso Machines" > FAQ Section
```

**Implementation**:
```jsx
export default function FAQSectionEditor({
  breadcrumbContext = null, // { categoryPageName: string }
  // ... other props
}) {
  const breadcrumbItems = () => {
    const items = [
      { label: 'CMS', href: '/cms' },
      { label: 'Category Pages', href: '/cms/category-pages' },
    ];

    if (breadcrumbContext?.categoryPageName) {
      items.push({ label: `Edit "${breadcrumbContext.categoryPageName}"` });
    }

    items.push({ label: 'FAQ Section', current: true });
    return items;
  };

  return (
    <Dialog>
      <DialogBody>
        {breadcrumbContext && (
          <div className="pb-3 border-b border-zinc-200 dark:border-zinc-800">
            <Breadcrumb items={breadcrumbItems()} />
          </div>
        )}
        {/* ... rest of editor */}
      </DialogBody>
    </Dialog>
  );
}
```

**Usage in CategoryLandingPagesPage**:
```jsx
<MetaobjectPicker
  type="faq-sections"
  breadcrumbContext={{
    categoryPageName: editingPage.displayName || editingPage.title
  }}
/>
```

### 3. ComparisonTableEditor (Nested)
**Location**: `/home/pranav/pydanticebot/frontend-v2/app/components/ComparisonTableEditor.jsx`

**Pattern**:
```
CMS > Category Pages > Edit "Espresso Machines" > Comparison Table
```

**Implementation**: Same pattern as FAQSectionEditor

**Usage**:
```jsx
<MetaobjectPicker
  type="comparison-tables"
  breadcrumbContext={{
    categoryPageName: editingPage.displayName || editingPage.title
  }}
/>
```

## Design Specifications

### Colors & Typography
```css
/* Link (non-current) */
text-zinc-600 dark:text-zinc-400
hover:text-zinc-900 dark:hover:text-zinc-100

/* Current page */
text-zinc-900 dark:text-zinc-100 font-medium

/* Separator */
text-zinc-400 dark:text-zinc-600

/* Font size */
text-sm
```

### Responsive Behavior
- **Desktop (md+)**: Full breadcrumb with all items visible
- **Mobile (<md)**: Collapsed breadcrumb (First > ... > Current)

### Truncation
- All breadcrumb items have `truncate` class
- Desktop: `max-w-xs` (320px max width per item)
- Mobile: `max-w-[200px]` for current item

## Breadcrumb Context Flow

```
CategoryLandingPagesPage (editing a page)
    |
    | passes breadcrumbContext
    v
MetaobjectPicker (for FAQ sections / Comparison tables)
    |
    | passes breadcrumbContext
    v
FAQSectionEditor / ComparisonTableEditor
    |
    | renders breadcrumb with context
    v
User sees: CMS > Category Pages > Edit "Page Name" > FAQ Section
```

## Future Extensions

### Adding Breadcrumbs to Other CMS Pages
Follow this pattern:

```jsx
// 1. Import
import { ResponsiveBreadcrumb } from '../../components/Breadcrumb';

// 2. Build items based on state
const getBreadcrumbItems = () => {
  const base = [
    { label: 'CMS', href: '/cms' },
    { label: 'Your Section', href: '/cms/your-section' },
  ];

  if (editing) {
    return [...base, { label: 'Edit Item', current: true }];
  }

  return base;
};

// 3. Render
<ResponsiveBreadcrumb items={getBreadcrumbItems()} />
```

### Nested Editor Pattern
For any component that opens within another editor:

```jsx
export default function YourNestedEditor({
  breadcrumbContext = null, // { parentName: string }
  // ... other props
}) {
  const breadcrumbItems = () => {
    const items = [
      { label: 'CMS', href: '/cms' },
      { label: 'Section', href: '/cms/section' },
    ];

    if (breadcrumbContext?.parentName) {
      items.push({ label: `Edit "${breadcrumbContext.parentName}"` });
    }

    items.push({ label: 'Your Editor', current: true });
    return items;
  };

  return (
    <Dialog>
      {breadcrumbContext && (
        <Breadcrumb items={breadcrumbItems()} />
      )}
      {/* ... */}
    </Dialog>
  );
}
```

## Accessibility

- Uses semantic `<nav>` with `aria-label="Breadcrumb"`
- Current page marked with `aria-current="page"`
- Separators marked with `aria-hidden="true"`
- Keyboard navigable (all links are focusable)

## Testing Checklist

- [ ] Breadcrumb shows correct items in list view
- [ ] Breadcrumb updates when entering edit mode
- [ ] Breadcrumb updates when entering create mode
- [ ] Nested breadcrumbs appear in FAQ editor
- [ ] Nested breadcrumbs appear in Comparison Table editor
- [ ] Breadcrumb context includes correct page name
- [ ] Mobile breadcrumb collapses correctly
- [ ] All links navigate correctly
- [ ] Dark mode styling works correctly
- [ ] Truncation prevents layout breaks
- [ ] Screen readers announce breadcrumb navigation

## Files Modified

1. **New Component**: `frontend-v2/app/components/Breadcrumb.jsx`
   - Three breadcrumb variants (standard, mobile, responsive)

2. **Updated**: `frontend-v2/app/views/cms/CategoryLandingPagesPage.jsx`
   - Added breadcrumb state management
   - Renders breadcrumbs based on view/edit/create mode
   - Passes breadcrumb context to nested editors

3. **Updated**: `frontend-v2/app/components/FAQSectionEditor.jsx`
   - Accepts breadcrumbContext prop
   - Renders breadcrumb when context provided

4. **Updated**: `frontend-v2/app/components/ComparisonTableEditor.jsx`
   - Accepts breadcrumbContext prop
   - Renders breadcrumb when context provided

5. **Updated**: `frontend-v2/app/components/MetaobjectPicker.jsx`
   - Accepts breadcrumbContext prop
   - Passes context to nested editors

## Summary

The breadcrumb navigation system provides:

- **Context Awareness**: Users always know where they are in the CMS hierarchy
- **Easy Navigation**: Click any breadcrumb to go back to that level
- **Mobile Optimization**: Intelligent collapsing on small screens
- **Extensibility**: Easy to add to new CMS pages and nested editors
- **Consistency**: Unified design patterns across all CMS interfaces
