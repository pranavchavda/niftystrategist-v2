# Validation Visual Reference Guide

## Color Coding & Visual States

### Input Field Border Colors

```
┌─────────────────────────────────────────┐
│ UNTOUCHED (Gray)                        │
│ ┌─────────────────────────────────────┐ │
│ │ single-dose-grinders                │ │ ← border-zinc-300
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ VALID (Green)                           │
│ ┌─────────────────────────────────────┐ │
│ │ single-dose-grinders            ✓   │ │ ← border-green-500
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ WARNING (Amber)                         │
│ ┌─────────────────────────────────────┐ │
│ │ Short Title                     ⚠   │ │ ← border-amber-500
│ └─────────────────────────────────────┘ │
│ ⚠ Title is short - recommended 50-60   │
│   characters for better visibility      │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ ERROR (Red)                             │
│ ┌─────────────────────────────────────┐ │
│ │ MY URL WITH SPACES                  │ │ ← border-red-500
│ └─────────────────────────────────────┘ │
│ ⛔ URL handle cannot contain spaces     │
└─────────────────────────────────────────┘
```

## Error Message Types

### Error (Red)
```
┌──────────────────────────────────────────┐
│ ⛔  URL handle cannot contain spaces     │  ← Red background
└──────────────────────────────────────────┘
```

### Warning (Amber)
```
┌──────────────────────────────────────────┐
│ ⚠  Title is short - recommended 50-60   │  ← Amber background
│    characters for better visibility      │
└──────────────────────────────────────────┘
```

### Info (Blue)
```
┌──────────────────────────────────────────┐
│ ℹ  Use lowercase letters, numbers, and  │  ← Blue background
│    hyphens only                          │
└──────────────────────────────────────────┘
```

### Success (Green)
```
┌──────────────────────────────────────────┐
│ ✓  Valid format                          │  ← Green background
└──────────────────────────────────────────┘
```

## Character Counter States

### Below Optimal (Amber)
```
45/60 characters (recommended: 50+)  ← Amber text
```

### Optimal Range (Green)
```
55/60 characters - optimal length  ← Green text
```

### Exceeds Limit (Red)
```
65/60 characters - exceeds limit  ← Red text
```

### Normal (Gray)
```
30/100 characters  ← Gray text
```

## Toast Notification

```
┌────────────────────────────────────────┐
│  ┌────┐  Success                       │
│  │ ✓  │  Changes saved successfully!   │
│  └────┘                             ✕  │
│  ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░  │ ← Progress bar
└────────────────────────────────────────┘
   ↑                                    ↑
   Green checkmark icon           Close button
   (animated zoom-in)
```

## Complete Form Example (Create New Page Modal)

```
┌──────────────────────────────────────────────────────────────┐
│  Create New Landing Page                                 ✕   │
│  Create a new category landing page                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Page Title *                                                │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Single Dose Coffee Grinders                        ✓   │ │ ← Green (valid)
│  └────────────────────────────────────────────────────────┘ │
│  33/100 characters                                           │
│                                                              │
│  URL Handle *                                                │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ single-dose-grinders                               ✓   │ │ ← Green (valid)
│  └────────────────────────────────────────────────────────┘ │
│  ℹ Use lowercase letters, numbers, and hyphens only         │
│  20/100 characters                                           │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                    Cancel    ✓ Create Page   │
└──────────────────────────────────────────────────────────────┘
```

## Validation Flow States

### State 1: Initial (Untouched)
```
URL Handle *
┌──────────────────────────────────────┐
│ e.g., single-dose-grinders           │ ← Gray border
└──────────────────────────────────────┘
ℹ Use lowercase letters, numbers, and    ← Blue hint
  hyphens only
```

### State 2: User Types Invalid Input
```
URL Handle *
┌──────────────────────────────────────┐
│ MY URL                               │ ← Still gray (not touched/blurred yet)
└──────────────────────────────────────┘
ℹ Use lowercase letters, numbers, and
  hyphens only
```

### State 3: User Blurs (Leaves Field)
```
URL Handle *
┌──────────────────────────────────────┐
│ MY URL                               │ ← Red border (validation triggered)
└──────────────────────────────────────┘
⛔ URL handle cannot contain spaces      ← Red error message
```

### State 4: User Corrects (Real-Time Validation)
```
URL Handle *
┌──────────────────────────────────────┐
│ my-url                           ✓   │ ← Green border (valid!)
└──────────────────────────────────────┘
6/100 characters                         ← Character count
```

## SEO Fields Example

### SEO Title - Short (Warning)
```
SEO Title
┌──────────────────────────────────────┐
│ Coffee Grinders                  ⚠   │ ← Amber border
└──────────────────────────────────────┘
⚠ SEO title is short - recommended       ← Amber warning
  50-60 characters for better visibility
16/60 characters (recommended: 50+)      ← Amber counter
```

### SEO Title - Optimal (Success)
```
SEO Title
┌──────────────────────────────────────────────────────────┐
│ Single Dose Coffee Grinders - Zero Retention | iDC   ✓  │ ← Green border
└──────────────────────────────────────────────────────────┘
55/60 characters - optimal length                           ← Green counter
```

### SEO Title - Too Long (Error)
```
SEO Title
┌──────────────────────────────────────────────────────────┐
│ Single Dose Coffee Grinders - Zero Retention - Best... │ ← Red border
└──────────────────────────────────────────────────────────┘
⛔ SEO title must be 60 characters or less                  ← Red error
65/60 characters - exceeds limit                            ← Red counter
```

## Dark Mode Equivalents

All colors have dark mode equivalents:

### Light Mode → Dark Mode
- `bg-red-50` → `bg-red-900/20`
- `border-red-200` → `border-red-800`
- `text-red-600` → `text-red-400`
- `bg-amber-50` → `bg-amber-900/20`
- `border-amber-200` → `border-amber-800`
- `text-amber-600` → `text-amber-400`
- `bg-green-50` → `bg-green-900/20`
- `border-green-200` → `border-green-800`
- `text-green-600` → `text-green-400`

## Interactive Elements

### Button States

**Enabled:**
```
┌──────────────────┐
│ ✓ Create Page    │ ← bg-amber-600, cursor-pointer
└──────────────────┘
```

**Disabled (Invalid Form):**
```
┌──────────────────┐
│ ✓ Create Page    │ ← bg-amber-400, opacity-50, cursor-not-allowed
└──────────────────┘
```

**Loading:**
```
┌──────────────────┐
│ ⟳ Creating...    │ ← Spinner icon, bg-amber-600
└──────────────────┘
```

## Accessibility Features

### Screen Reader Announcements
```
<input
  aria-label="URL Handle"
  aria-required="true"
  aria-invalid="true"
  aria-describedby="urlHandle-error urlHandle-hint"
/>

<div id="urlHandle-error" role="alert">
  URL handle cannot contain spaces
</div>

<div id="urlHandle-hint">
  Use lowercase letters, numbers, and hyphens only
</div>
```

### Focus States
```
┌──────────────────────────────────────┐
│ single-dose-grinders                 │ ← Blue ring (focus-ring-2 focus-ring-amber-500)
└──────────────────────────────────────┘
    ↑
    Visible focus indicator
```

## Animation Timings

### Error Message Fade-In
```
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
Duration: 200ms
```

### Toast Slide-In
```
@keyframes slideIn {
  from { transform: translateY(-8px); opacity: 0; }
  to   { transform: translateY(0); opacity: 1; }
}
Duration: 300ms
```

### Success Checkmark
```
@keyframes zoomIn {
  from { transform: scale(0); }
  to   { transform: scale(1); }
}
Duration: 300ms
```

## Common Validation Patterns

### Pattern 1: Required Text Field
```
Title *
┌──────────────────────────────────────┐
│                                      │ ← Empty
└──────────────────────────────────────┘
        ↓ (user blurs)
⛔ Title is required
```

### Pattern 2: URL Handle Format
```
URL Handle *
┌──────────────────────────────────────┐
│ My-Category                          │
└──────────────────────────────────────┘
        ↓ (user blurs)
⛔ URL handle must be lowercase
```

### Pattern 3: Length Constraint
```
Title *
┌──────────────────────────────────────┐
│ Ab                                   │
└──────────────────────────────────────┘
        ↓ (user blurs)
⛔ Title must be at least 3 characters
2/100 characters
```

### Pattern 4: Optimal Range (SEO)
```
SEO Description
┌──────────────────────────────────────┐
│ Shop coffee grinders in Canada.     │
└──────────────────────────────────────┘
        ↓ (user blurs)
⚠ SEO description is short - recommended
  120-160 characters for better visibility
35/160 characters (recommended: 120+)
```

## Mobile Responsive Adaptations

### Desktop (≥640px)
```
┌────────────────────────────────────────────┐
│ URL Handle *                               │
│ ┌──────────────────────────────────────┐  │
│ │ single-dose-grinders             ✓   │  │ ← 44px min height
│ └──────────────────────────────────────┘  │
│ 20/100 characters                          │
└────────────────────────────────────────────┘
```

### Mobile (<640px)
```
┌────────────────────────────────────────┐
│ URL Handle *                           │
│ ┌──────────────────────────────────┐  │
│ │ single-dose-grinders         ✓   │  │ ← 44px min touch target
│ └──────────────────────────────────┘  │
│ 20/100 characters                      │
└────────────────────────────────────────┘
```

## Copy-Paste Integration

### Minimal Integration (5 lines)
```jsx
import ValidatedInput from './ValidatedInput';
import { validateUrlHandle } from '../utils/validation';

<ValidatedInput
  name="urlHandle"
  value={formData.urlHandle}
  onChange={(e) => setFormData({...formData, urlHandle: e.target.value})}
  validator={validateUrlHandle}
  label="URL Handle"
  required
/>
```

### With All Features (10 lines)
```jsx
<ValidatedInput
  name="urlHandle"
  value={formData.urlHandle}
  onChange={(e) => setFormData({...formData, urlHandle: e.target.value})}
  validator={validateUrlHandle}
  label="URL Handle"
  placeholder="e.g., single-dose-grinders"
  hint="Use lowercase letters, numbers, and hyphens only"
  required
  showCharCount
  maxLength={100}
/>
```

## Quick Reference Table

| State | Border | Message | Counter | Icon |
|-------|--------|---------|---------|------|
| Untouched | Gray | Hint (blue) | Gray | - |
| Valid | Green | - | Green/Gray | ✓ |
| Warning | Amber | Warning (amber) | Amber | ⚠ |
| Error | Red | Error (red) | Red | ⛔ |
| Disabled | Gray | - | Gray | - |
| Loading | Gray | - | Gray | ⟳ |
