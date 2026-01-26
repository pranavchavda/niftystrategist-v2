# Complete Validation Implementation Example

This document shows a complete example of integrating validation into the Create New Page modal from `CategoryLandingPagesPage.jsx`.

## Before (Without Validation)

```jsx
// Original Create Modal (lines 1920-2007 of CategoryLandingPagesPage.jsx)
{showCreateModal && (
  <Dialog open={showCreateModal} onClose={() => setShowCreateModal(false)} size="md">
    <DialogBody className="px-0 py-0">
      <div className="p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
            Page Title <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={newPageTitle}
            onChange={(e) => setNewPageTitle(e.target.value)}
            placeholder="e.g., Single Dose Coffee Grinders"
            className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
            URL Handle <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={newPageUrlHandle}
            onChange={(e) => setNewPageUrlHandle(e.target.value)}
            placeholder="e.g., single-dose-grinders"
            className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
          />
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            The URL slug (lowercase, no spaces). Will be normalized automatically.
          </p>
        </div>
      </div>
    </DialogBody>

    <DialogActions>
      <button
        onClick={handleCreatePage}
        disabled={creating || !newPageTitle.trim() || !newPageUrlHandle.trim()}
      >
        Create Page
      </button>
    </DialogActions>
  </Dialog>
)}
```

## After (With Validation)

### Step 1: Add Imports

```jsx
import ValidatedInput from '../../components/ValidatedInput';
import { validateUrlHandle, validateTitle } from '../../utils/validation';
import Toast from '../../components/Toast';
```

### Step 2: Add Validation State

```jsx
// Inside CategoryLandingPagesPage component
const [showToast, setShowToast] = useState(false);
const [toastMessage, setToastMessage] = useState('');
```

### Step 3: Update Create Page Handler

```jsx
const handleCreatePage = async () => {
  // Validate before submission
  const titleValidation = validateTitle(newPageTitle, 3, 100);
  const urlValidation = validateUrlHandle(newPageUrlHandle);

  if (!titleValidation.isValid || !urlValidation.isValid) {
    setError('Please fix validation errors before creating the page');
    return;
  }

  try {
    setCreating(true);
    setError(null);

    const response = await fetch('/api/cms/category-landing-pages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        urlHandle: newPageUrlHandle.trim(),
        title: newPageTitle.trim(),
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to create page');
    }

    const createdPage = await response.json();

    // Add to pages list
    setPages([...pages, createdPage]);

    // Close modal and reset form
    setShowCreateModal(false);
    setNewPageUrlHandle('');
    setNewPageTitle('');

    // Show success toast
    setToastMessage('Page created successfully!');
    setShowToast(true);
  } catch (err) {
    console.error('Error creating page:', err);
    setError(err.message);
  } finally {
    setCreating(false);
  }
};
```

### Step 4: Replace Modal with Validated Inputs

```jsx
{showCreateModal && (
  <Dialog open={showCreateModal} onClose={() => setShowCreateModal(false)} size="md">
    <div className="flex items-center justify-between">
      <div>
        <DialogTitle>Create New Landing Page</DialogTitle>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Create a new category landing page
        </p>
      </div>
      <button
        onClick={() => setShowCreateModal(false)}
        disabled={creating}
        className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors disabled:opacity-50 flex-shrink-0"
      >
        <XMarkIcon className="h-5 w-5 text-zinc-500" />
      </button>
    </div>

    <DialogBody className="px-0 py-0">
      <div className="p-6 space-y-4">
        {/* Error Message */}
        {error && (
          <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-2">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-red-800 dark:text-red-200">Error</p>
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          </div>
        )}

        {/* Page Title - WITH VALIDATION */}
        <ValidatedInput
          name="title"
          value={newPageTitle}
          onChange={(e) => setNewPageTitle(e.target.value)}
          validator={(value) => validateTitle(value, 3, 100)}
          label="Page Title"
          placeholder="e.g., Single Dose Coffee Grinders"
          hint="The display title for this landing page"
          required
          disabled={creating}
          showCharCount
          maxLength={100}
        />

        {/* URL Handle - WITH VALIDATION */}
        <ValidatedInput
          name="urlHandle"
          value={newPageUrlHandle}
          onChange={(e) => setNewPageUrlHandle(e.target.value)}
          validator={validateUrlHandle}
          label="URL Handle"
          placeholder="e.g., single-dose-grinders"
          hint="Use lowercase letters, numbers, and hyphens only"
          required
          disabled={creating}
          showCharCount
          maxLength={100}
        />
      </div>
    </DialogBody>

    <DialogActions className="px-6 py-4 border-t border-zinc-200 dark:border-zinc-700">
      <button
        onClick={() => setShowCreateModal(false)}
        disabled={creating}
        className="px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg disabled:opacity-50 transition-colors"
      >
        Cancel
      </button>
      <button
        onClick={handleCreatePage}
        disabled={creating || !newPageTitle.trim() || !newPageUrlHandle.trim()}
        className="px-6 py-2 text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 disabled:bg-amber-400 rounded-lg disabled:opacity-50 transition-colors flex items-center gap-2"
      >
        {creating ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Creating page...
          </>
        ) : (
          <>
            <CheckIcon className="h-4 w-4" />
            Create Page
          </>
        )}
      </button>
    </DialogActions>
  </Dialog>
)}

{/* Toast Notification */}
<Toast
  message={toastMessage}
  show={showToast}
  onClose={() => setShowToast(false)}
  duration={3000}
/>
```

## Complete File Changes Summary

### CategoryLandingPagesPage.jsx

**Add to imports (top of file):**
```jsx
import ValidatedInput, { ValidatedTextarea } from '../../components/ValidatedInput';
import { validateUrlHandle, validateTitle, validateSeoTitle, validateSeoDescription } from '../../utils/validation';
import Toast from '../../components/Toast';
```

**Add to state (after existing state declarations):**
```jsx
const [showToast, setShowToast] = useState(false);
const [toastMessage, setToastMessage] = useState('');
```

**Replace success state logic:**
```jsx
// OLD (lines 197-200):
setSuccess(true);
setTimeout(() => setSuccess(false), 3000);

// NEW:
setToastMessage('Changes saved successfully!');
setShowToast(true);
```

**Update Edit Modal Form Fields:**

Replace lines 1078-1188 with validated inputs:

```jsx
{/* Hero Title - WITH VALIDATION */}
<ValidatedInput
  name="heroTitle"
  value={editingPage.heroTitle}
  onChange={(e) => setEditingPage({ ...editingPage, heroTitle: e.target.value })}
  validator={(value) => validateTitle(value, 0, 100)} // Optional field
  label="Hero Title"
  placeholder="Enter hero title..."
  disabled={saving}
  showCharCount
  maxLength={100}
/>

{/* Hero Description - WITH VALIDATION */}
<ValidatedTextarea
  name="heroDescription"
  value={editingPage.heroDescription}
  onChange={(e) => setEditingPage({ ...editingPage, heroDescription: e.target.value })}
  validator={(value) => ({ isValid: true, error: null })} // Optional, no strict validation
  label="Hero Description"
  placeholder="Enter hero description..."
  disabled={saving}
  rows={4}
/>

{/* Page Title - WITH VALIDATION */}
<ValidatedInput
  name="title"
  value={editingPage.title}
  onChange={(e) => setEditingPage({ ...editingPage, title: e.target.value })}
  validator={(value) => validateTitle(value, 3, 100)}
  label="Page Title"
  placeholder="e.g., Single Dose Coffee Grinders"
  required
  disabled={saving}
  showCharCount
  maxLength={100}
/>

{/* URL Handle - WITH VALIDATION */}
<ValidatedInput
  name="urlHandle"
  value={editingPage.urlHandle}
  onChange={(e) => setEditingPage({ ...editingPage, urlHandle: e.target.value })}
  validator={validateUrlHandle}
  label="URL Handle"
  placeholder="e.g., single-dose-grinders"
  hint="Use lowercase letters, numbers, and hyphens only"
  required
  disabled={saving}
  showCharCount
  maxLength={100}
/>

{/* SEO Title - WITH VALIDATION */}
<ValidatedInput
  name="seoTitle"
  value={editingPage.seoTitle}
  onChange={(e) => setEditingPage({ ...editingPage, seoTitle: e.target.value })}
  validator={validateSeoTitle}
  label="SEO Title"
  placeholder="e.g., Single Dose Coffee Grinders - Zero Retention | iDrinkCoffee"
  hint="Recommended 50-60 characters for optimal SEO"
  disabled={saving}
  showCharCount
  maxLength={60}
  optimalLength={50}
/>

{/* SEO Description - WITH VALIDATION */}
<ValidatedTextarea
  name="seoDescription"
  value={editingPage.seoDescription}
  onChange={(e) => setEditingPage({ ...editingPage, seoDescription: e.target.value })}
  validator={validateSeoDescription}
  label="SEO Description"
  placeholder="e.g., Shop the best single dose coffee grinders in Canada. Featuring Profitec, Mahlkonig, Eureka, and more."
  hint="Recommended 120-160 characters for optimal SEO"
  disabled={saving}
  rows={3}
  showCharCount
  maxLength={160}
  optimalLength={120}
/>
```

**Add Toast at end of component (before closing div):**
```jsx
{/* Toast Notification */}
<Toast
  message={toastMessage}
  show={showToast}
  onClose={() => setShowToast(false)}
  duration={3000}
/>
```

## Visual Results

### Before Validation
- No visual feedback on invalid input
- Generic error messages
- No character counting
- No helpful hints

### After Validation
- **Red border** when invalid (e.g., "URL HANDLE" with spaces)
- **Green border** when valid and touched
- **Amber border** for warnings (e.g., SEO title under 50 chars)
- **Character counter** updates in real-time
- **Specific error messages**: "URL handle cannot contain spaces"
- **Helpful hints**: "Use lowercase letters, numbers, and hyphens only"
- **Toast notification** on successful save with auto-dismiss

## Testing Scenarios

### Test Case 1: URL Handle Validation
1. Type "MY-URL" (uppercase)
   - **Expected:** Red border, error "URL handle must be lowercase"
2. Type "my url" (space)
   - **Expected:** Red border, error "URL handle cannot contain spaces"
3. Type "my-url" (valid)
   - **Expected:** Green border, no error

### Test Case 2: Title Length
1. Type "Ab" (too short)
   - **Expected:** Red border, error "Title must be at least 3 characters"
2. Type "ABC" (valid)
   - **Expected:** Green border, no error

### Test Case 3: SEO Title Optimization
1. Type 40 characters
   - **Expected:** Amber border, warning "SEO title is short - recommended 50-60 characters"
2. Type 55 characters (optimal)
   - **Expected:** Green border, message "optimal length"
3. Type 65 characters (too long)
   - **Expected:** Red border, error "SEO title must be 60 characters or less"

### Test Case 4: Character Counter
1. SEO Description field
   - Type 100 characters: "100/160 characters (recommended: 120+)" in amber
   - Type 140 characters: "140/160 characters - optimal length" in green
   - Type 165 characters: "165/160 characters - exceeds limit" in red

### Test Case 5: Toast Notification
1. Successfully save changes
   - **Expected:** Green toast appears top-right
   - Shows checkmark icon and "Changes saved successfully!"
   - Auto-dismisses after 3 seconds
   - Can be manually closed with X button

## Performance Considerations

- **Debouncing:** Not needed for validation (only validates on blur + after touch)
- **Validation cost:** All validators are synchronous and fast (<1ms)
- **Re-renders:** Minimal - validation state is isolated per field
- **Memory:** Negligible - validation functions are pure with no state

## Accessibility

- Error messages are associated with inputs via proximity
- Red/green/amber colors have sufficient contrast ratios
- Error messages use clear, human-readable language
- Character counters provide real-time feedback for screen readers
- All inputs have proper labels with required indicators

## Browser Compatibility

- Modern browsers (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)
- Uses standard CSS transitions and animations
- No vendor prefixes needed
- Works with dark mode automatically
