# CMS Interface Style Guide

## Design System Overview

This guide establishes consistent visual hierarchy, button styling, and content organization patterns across the CMS interface. All components should follow these standards for a cohesive user experience.

---

## Button Hierarchy System

### Primary Actions (Most Important - 1 per screen)
**Use for:** Save Changes, Create Page, Publish, Submit

```jsx
<button className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded-lg font-medium text-sm transition-colors shadow-sm">
  Save Changes
</button>
```

**Characteristics:**
- Color: Blue (`bg-blue-600`)
- Size: Larger padding (`px-6 py-2.5`)
- Weight: Font medium
- Optional: Right arrow icon (→) or checkmark (✓)
- Shadow: `shadow-sm` for elevation

### Secondary Actions (Supporting Actions)
**Use for:** Cancel, Back, Close, Done

```jsx
<button className="px-4 py-2 bg-zinc-200 hover:bg-zinc-300 active:bg-zinc-400 dark:bg-zinc-700 dark:hover:bg-zinc-600 dark:active:bg-zinc-500 text-zinc-900 dark:text-zinc-100 rounded-lg font-medium text-sm transition-colors">
  Cancel
</button>
```

**Characteristics:**
- Color: Zinc/Gray (`bg-zinc-200`)
- Size: Standard padding (`px-4 py-2`)
- Weight: Font medium
- No icon (optional text-only)

### Tertiary Actions (Low Priority)
**Use for:** Advanced settings, More options, View details

```jsx
<button className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 underline underline-offset-2 transition-colors">
  Advanced Settings
</button>
```

**Characteristics:**
- No background
- Underlined text
- Smaller size (`text-sm`)
- Color: Muted (`text-zinc-600`)

### Danger Actions (Destructive)
**Use for:** Delete, Remove, Clear, Destroy

```jsx
<button className="px-4 py-2 bg-red-600 hover:bg-red-700 active:bg-red-800 text-white rounded-lg font-medium text-sm transition-colors">
  Delete
</button>
```

**Characteristics:**
- Color: Red (`bg-red-600`)
- Always require confirmation dialog
- Icon: Trash or warning icon
- **Rule:** Never make primary - always secondary or less prominent

### Action Button (Accent - Creative Actions)
**Use for:** AI Generate, Regenerate, Upload, Browse

```jsx
<button className="px-4 py-2 bg-purple-600 hover:bg-purple-700 active:bg-purple-800 text-white rounded-lg font-medium text-sm transition-colors">
  <SparklesIcon className="h-4 w-4" />
  Regenerate with AI
</button>
```

**Characteristics:**
- Color: Purple for AI, Emerald for file operations
- Icon: Always include relevant icon
- Equal weight to secondary actions

### Utility Buttons (Inline Actions)
**Use for:** Edit, Remove chip/tag, Expand/collapse

```jsx
<button className="p-1.5 text-zinc-400 hover:text-blue-600 hover:bg-blue-50 active:bg-blue-100 dark:hover:bg-blue-900/30 dark:active:bg-blue-900/50 rounded transition-colors">
  <Edit2 className="h-4 w-4" />
</button>
```

**Characteristics:**
- Minimal padding (`p-1.5`)
- Icon-only (no text)
- Muted by default, colorful on hover
- Context-specific color (blue for edit, red for delete)

---

## Content Organization Patterns

### Section Headers
Clear separation between major content areas

```jsx
<div className="border-b border-zinc-200 dark:border-zinc-700 pb-3 mb-6">
  <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
    Hero Section
  </h2>
  <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
    Main banner image and title for your category page
  </p>
</div>
```

**Characteristics:**
- Border bottom for visual separation
- Title: `text-lg font-semibold`
- Description: `text-sm` with muted color
- Spacing: `pb-3 mb-6` for rhythm

### Form Groups
Related fields grouped together

```jsx
<div className="space-y-4 p-4 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700">
  <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-4">
    SEO Settings
  </h3>
  {/* Fields */}
</div>
```

**Characteristics:**
- Light background (`bg-zinc-50`)
- Rounded corners (`rounded-lg`)
- Border for definition
- Title: `text-sm font-medium`

### Field Labels
Consistent labeling with required indicators

```jsx
<label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
  Page Title
  <span className="text-red-600 dark:text-red-400 ml-1">*</span>
  <span className="ml-2 text-xs font-normal text-zinc-500">(required)</span>
</label>
```

**Characteristics:**
- Required: Red asterisk + "(required)" text
- Optional: Gray "(optional)" text
- Weight: `font-medium`
- Spacing: `mb-2` below label

### Card Styling (For Lists)
Consistent card treatment for all list items

```jsx
<div className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg p-4 hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors">
  <div className="flex items-start justify-between">
    <div className="flex-1 min-w-0">
      <h3 className="font-medium text-zinc-900 dark:text-zinc-100 line-clamp-2">
        {title}
      </h3>
      <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1 line-clamp-2">
        {description}
      </p>
    </div>
    <div className="flex gap-2 ml-4">
      {/* Action buttons */}
    </div>
  </div>
</div>
```

**Characteristics:**
- White background with border
- Hover state changes border color
- Title: `font-medium` (not bold)
- Description: `text-sm` with muted color
- Actions: Right-aligned with gap

---

## Visual Spacing System

### Major Sections
```jsx
className="space-y-8"
```
Use for: Top-level content sections (Hero, SEO, Products, etc.)

### Form Groups
```jsx
className="space-y-6"
```
Use for: Grouped form sections with related fields

### Individual Fields
```jsx
className="space-y-4"
```
Use for: Sequential form inputs within a group

### Inline Elements
```jsx
className="gap-3"
```
Use for: Buttons, chips, inline controls

### Dividers
```jsx
<div className="border-t border-zinc-200 dark:border-zinc-800 my-6"></div>
```
Use between major sections for visual separation

---

## Status Indicators

### Unsaved Changes
```jsx
<div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
  <div className="h-2 w-2 rounded-full bg-amber-600 dark:bg-amber-400"></div>
  <span className="text-sm font-medium">Unsaved changes</span>
</div>
```

### Saving State
```jsx
<div className="flex items-center gap-2 text-blue-600 dark:text-blue-400">
  <Loader2 className="h-4 w-4 animate-spin" />
  <span className="text-sm">Saving...</span>
</div>
```

### Saved Successfully
```jsx
<div className="flex items-center gap-2 text-green-600 dark:text-green-400">
  <CheckIcon className="h-4 w-4" />
  <span className="text-sm font-medium">All changes saved</span>
</div>
```

### Error State
```jsx
<div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-2">
  <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
  <div>
    <p className="text-sm font-medium text-red-800 dark:text-red-200">Error</p>
    <p className="text-sm text-red-600 dark:text-red-400">{errorMessage}</p>
  </div>
</div>
```

---

## Emphasis Techniques

### Required Fields
```jsx
<label>
  Field Name
  <span className="text-red-600 dark:text-red-400 ml-1">*</span>
  <span className="ml-2 text-xs font-normal text-zinc-500">(required)</span>
</label>
```

### Optional Fields
```jsx
<label>
  Field Name
  <span className="ml-2 text-xs font-normal text-zinc-500">(optional)</span>
</label>
```

### Recommended Actions
```jsx
<div className="flex items-center gap-2">
  <InfoIcon className="h-4 w-4 text-blue-500" />
  <span className="text-sm text-blue-600 dark:text-blue-400">Recommended</span>
</div>
```

### Helper Text
```jsx
<p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
  Brief explanation or character count
</p>
```

---

## Mobile Considerations

### Touch Targets
All interactive elements must have minimum 44px height on mobile:

```jsx
className="min-h-[44px] py-2.5 sm:py-2"
```

### Responsive Padding
```jsx
className="p-4 sm:p-6"        // Page/section padding
className="px-3 sm:px-4"      // Horizontal padding
className="py-2.5 sm:py-2"    // Vertical padding
```

### Mobile Modals
Full-screen on mobile, centered on desktop:

```jsx
<div className="fixed sm:absolute inset-x-0 bottom-0 sm:top-full sm:left-0 sm:right-0 sm:inset-x-auto sm:bottom-auto">
  {/* Modal content */}
</div>
```

---

## Common Patterns

### Dialog Actions (Footer Buttons)
```jsx
<DialogActions className="px-4 sm:px-6 py-3 sm:py-4 border-t border-zinc-200 dark:border-zinc-700">
  <button className="px-4 py-2 bg-zinc-200 hover:bg-zinc-300 dark:bg-zinc-700 dark:hover:bg-zinc-600 text-zinc-900 dark:text-zinc-100 rounded-lg font-medium text-sm">
    Cancel
  </button>
  <button className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium text-sm">
    Save Changes
  </button>
</DialogActions>
```

**Order:** Secondary (Cancel) on left, Primary (Save) on right

### Empty States
```jsx
<div className="text-center py-12 bg-zinc-50 dark:bg-zinc-800 rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700">
  <PhotoIcon className="h-12 w-12 text-zinc-300 dark:text-zinc-600 mx-auto mb-4" />
  <p className="text-sm text-zinc-500 dark:text-zinc-400">
    No items yet
  </p>
  <button className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm">
    Add First Item
  </button>
</div>
```

### Loading States
```jsx
<div className="flex items-center justify-center py-12">
  <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
  <span className="ml-3 text-sm text-zinc-600 dark:text-zinc-400">
    Loading content...
  </span>
</div>
```

---

## Color Palette

### Action Colors
- **Primary (Save/Submit):** `blue-600` → `blue-700` → `blue-800`
- **Secondary (Cancel):** `zinc-200` → `zinc-300` → `zinc-400`
- **Danger (Delete):** `red-600` → `red-700` → `red-800`
- **AI/Creative:** `purple-600` → `purple-700` → `purple-800`
- **File Operations:** `emerald-600` → `emerald-700` → `emerald-800`
- **Warning:** `amber-600` → `amber-700` → `amber-800`

### Text Colors
- **Primary Text:** `zinc-900` / `dark:zinc-100`
- **Secondary Text:** `zinc-600` / `dark:zinc-400`
- **Muted Text:** `zinc-500` / `dark:zinc-500`
- **Disabled Text:** `zinc-400` / `dark:zinc-600`

### Background Colors
- **Page Background:** `zinc-50` / `dark:zinc-900`
- **Card Background:** `white` / `dark:zinc-800`
- **Form Group:** `zinc-50` / `dark:zinc-800/50`
- **Hover:** `zinc-100` / `dark:zinc-700`

### Border Colors
- **Default:** `zinc-200` / `dark:zinc-700`
- **Hover:** `zinc-300` / `dark:zinc-600`
- **Focus:** `blue-500` (ring)

---

## Accessibility Guidelines

1. **Focus States:** All interactive elements must have visible focus ring
   ```jsx
   focus:outline-none focus:ring-2 focus:ring-blue-500
   ```

2. **Color Contrast:** Maintain WCAG AA standards (4.5:1 for normal text)

3. **Button Labels:** Always include descriptive text or `aria-label`

4. **Loading States:** Include text alternatives for spinners

5. **Error Messages:** Provide specific, actionable error text

---

## Examples by Component

### CategoryLandingPagesPage
- **Primary:** "Save Changes" (blue)
- **Secondary:** "Cancel" (gray)
- **Action:** "Create New Page" (blue), "Regenerate with AI" (purple)
- **Tertiary:** "Advanced Settings" (text link)

### MetaobjectPicker
- **Primary:** None (selection-based)
- **Secondary:** "Create New" (blue text button)
- **Utility:** Edit/Delete icons (icon buttons)

### FAQSectionEditor
- **Primary:** "Save Changes" (blue)
- **Secondary:** "Cancel" (gray), "Done" (gray)
- **Inline:** "Add Item" (blue), "Edit" (blue bg-light), "Delete" (red bg-light)

### MetaobjectEditor
- **Primary:** "Save Changes" (blue)
- **Secondary:** "Cancel" (gray)

---

## Implementation Checklist

When creating or updating a CMS component:

- [ ] Primary action is blue and prominent
- [ ] Secondary actions are gray with less visual weight
- [ ] Danger actions are red and require confirmation
- [ ] All buttons have proper hover/active states
- [ ] Touch targets are minimum 44px on mobile
- [ ] Labels clearly indicate required vs optional fields
- [ ] Empty states provide guidance
- [ ] Loading states have text + spinner
- [ ] Error messages are specific and actionable
- [ ] Spacing follows the system (4, 6, 8)
- [ ] Color palette is consistent
- [ ] Dark mode is properly supported
- [ ] Focus rings are visible

---

## Anti-Patterns to Avoid

1. **Multiple primary buttons** - Only one primary action per screen
2. **Inconsistent button sizes** - Use standard padding system
3. **Missing disabled states** - Always handle loading/disabled
4. **Vague labels** - "Submit" vs "Save Changes" (be specific)
5. **No hover states** - All interactive elements need hover feedback
6. **Inconsistent spacing** - Follow the 4-6-8 system
7. **Missing dark mode** - All colors must have dark variants
8. **Poor mobile UX** - Remember touch targets and responsive padding
9. **Unclear required fields** - Always mark required fields explicitly
10. **Generic error messages** - "Error occurred" vs "Failed to save: Invalid title"

---

## Version History

- **v1.0** (2025-10-20): Initial style guide based on CMS interface requirements
