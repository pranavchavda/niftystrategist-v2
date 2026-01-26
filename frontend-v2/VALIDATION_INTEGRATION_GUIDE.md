# Form Validation Integration Guide

## Overview

This guide demonstrates how to integrate real-time form validation with helpful error messages throughout the CMS interface. The validation system provides:

- Real-time validation with helpful error messages
- Character counters for limited fields
- Visual feedback (red borders for errors, green for valid, amber for warnings)
- Validation hints before user interaction
- Toast notifications for successful saves
- Consistent validation rules across all forms

## Files Created

### 1. Validation Utilities (`app/utils/validation.js`)

Core validation functions:

```javascript
import {
  validateUrlHandle,
  validateTitle,
  validateSeoTitle,
  validateSeoDescription,
  validateRequired,
  validateText,
  validateNumber,
  validateUrl,
  getCharacterCountMessage
} from '../utils/validation';
```

**Available validators:**
- `validateUrlHandle(value)` - Validates URL handles (lowercase, hyphens, no spaces)
- `validateTitle(value, minLength, maxLength)` - Validates title fields
- `validateSeoTitle(value)` - Validates SEO titles with optimal length warnings (50-60 chars)
- `validateSeoDescription(value)` - Validates SEO descriptions (120-160 chars optimal)
- `validateRequired(value, fieldName)` - Generic required field validation
- `validateText(value, options)` - Generic text validation with length constraints
- `validateNumber(value, options)` - Number validation with min/max
- `validateUrl(value, required)` - URL format validation

### 2. Field Error Component (`app/components/FieldError.jsx`)

Display validation messages with appropriate styling:

```jsx
import FieldError, { CharacterCount, ValidationHint } from './FieldError';

// Error message
<FieldError message="URL handle must be lowercase" type="error" />

// Warning message
<FieldError message="Title is short - recommended 50-60 characters" type="warning" />

// Character counter
<CharacterCount current={60} max={160} optimal={120} />

// Hint (shown before validation)
<ValidationHint hint="Use lowercase letters, numbers, and hyphens only" />
```

### 3. Toast Notification (`app/components/Toast.jsx`)

Success notifications with auto-dismiss:

```jsx
import Toast from './Toast';

<Toast
  message="Page saved successfully!"
  show={showToast}
  onClose={() => setShowToast(false)}
  duration={3000}
/>
```

### 4. Validated Input Components (`app/components/ValidatedInput.jsx`)

Pre-built input components with validation:

```jsx
import ValidatedInput, { ValidatedTextarea } from './ValidatedInput';

<ValidatedInput
  name="urlHandle"
  value={formData.urlHandle}
  onChange={handleChange}
  validator={validateUrlHandle}
  label="URL Handle"
  placeholder="e.g., single-dose-grinders"
  hint="Use lowercase letters, numbers, and hyphens only"
  required
  showCharCount
  maxLength={100}
/>
```

## Integration Examples

### Example 1: Category Landing Pages - Create Modal

```jsx
import { useState } from 'react';
import ValidatedInput from '../components/ValidatedInput';
import { validateUrlHandle, validateTitle } from '../utils/validation';
import Toast from '../components/Toast';

export default function CreatePageModal() {
  const [formData, setFormData] = useState({
    urlHandle: '',
    title: ''
  });
  const [showToast, setShowToast] = useState(false);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async () => {
    // Validate before submit
    const urlValidation = validateUrlHandle(formData.urlHandle);
    const titleValidation = validateTitle(formData.title);

    if (!urlValidation.isValid || !titleValidation.isValid) {
      return; // Validation errors will be shown by the ValidatedInput components
    }

    // Submit...
    await saveData();
    setShowToast(true);
  };

  return (
    <>
      <form onSubmit={handleSubmit}>
        <ValidatedInput
          name="urlHandle"
          value={formData.urlHandle}
          onChange={handleChange}
          validator={validateUrlHandle}
          label="URL Handle"
          placeholder="e.g., single-dose-grinders"
          hint="Use lowercase letters, numbers, and hyphens only"
          required
          showCharCount
          maxLength={100}
        />

        <ValidatedInput
          name="title"
          value={formData.title}
          onChange={handleChange}
          validator={(value) => validateTitle(value, 3, 100)}
          label="Page Title"
          placeholder="e.g., Single Dose Coffee Grinders"
          required
          showCharCount
          maxLength={100}
        />
      </form>

      <Toast
        message="Page created successfully!"
        show={showToast}
        onClose={() => setShowToast(false)}
      />
    </>
  );
}
```

### Example 2: Manual Integration (Without ValidatedInput)

For existing forms where you want to add validation without refactoring:

```jsx
import { useState } from 'react';
import FieldError, { CharacterCount, ValidationHint } from './FieldError';
import { validateSeoTitle } from '../utils/validation';

export default function SeoTitleField() {
  const [seoTitle, setSeoTitle] = useState('');
  const [touched, setTouched] = useState(false);
  const [validation, setValidation] = useState({ isValid: true });

  const handleBlur = () => {
    setTouched(true);
    const result = validateSeoTitle(seoTitle);
    setValidation(result);
  };

  const handleChange = (e) => {
    setSeoTitle(e.target.value);

    // Real-time validation after first blur
    if (touched) {
      const result = validateSeoTitle(e.target.value);
      setValidation(result);
    }
  };

  const hasError = touched && !validation.isValid;
  const hasWarning = touched && validation.warning;

  return (
    <div>
      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
        SEO Title
      </label>

      <input
        type="text"
        value={seoTitle}
        onChange={handleChange}
        onBlur={handleBlur}
        className={`w-full px-4 py-2 bg-white dark:bg-zinc-800 border rounded-lg text-sm focus:outline-none focus:ring-2 ${
          hasError
            ? 'border-red-500 focus:ring-red-500'
            : hasWarning
            ? 'border-amber-500 focus:ring-amber-500'
            : 'border-zinc-300 focus:ring-amber-500'
        }`}
      />

      {!touched && (
        <ValidationHint hint="Recommended 50-60 characters for optimal SEO" />
      )}

      <CharacterCount
        current={seoTitle.length}
        max={60}
        optimal={50}
      />

      {hasError && <FieldError message={validation.error} type="error" />}
      {hasWarning && <FieldError message={validation.warning} type="warning" />}
    </div>
  );
}
```

### Example 3: SEO Description with Character Limit

```jsx
import ValidatedTextarea from '../components/ValidatedInput';
import { validateSeoDescription } from '../utils/validation';

<ValidatedTextarea
  name="seoDescription"
  value={formData.seoDescription}
  onChange={handleChange}
  validator={validateSeoDescription}
  label="SEO Description"
  placeholder="Brief description for search engines..."
  hint="Recommended 120-160 characters for optimal SEO"
  rows={3}
  showCharCount
  maxLength={160}
  optimalLength={120}
/>
```

## Validation Rules Reference

### URL Handle
- **Pattern:** `^[a-z0-9-]+$`
- **Requirements:**
  - Lowercase only
  - Numbers and hyphens allowed
  - No spaces
  - No consecutive hyphens
  - Cannot start/end with hyphen
  - 2-100 characters
- **Example:** `single-dose-grinders`

### Title
- **Requirements:**
  - 3-100 characters
  - Required field
- **Example:** `Single Dose Coffee Grinders`

### SEO Title
- **Requirements:**
  - Maximum 60 characters
  - Warning if less than 50 characters
  - Optional field
- **Example:** `Single Dose Coffee Grinders - Zero Retention | iDrinkCoffee`

### SEO Description
- **Requirements:**
  - Maximum 160 characters
  - Warning if less than 120 characters
  - Optional field
- **Example:** `Shop the best single dose coffee grinders in Canada. Featuring Profitec, Mahlkonig, Eureka, and more.`

## Visual Feedback States

### Border Colors
- **Default:** Gray border (`border-zinc-300`)
- **Valid (touched):** Green border (`border-green-500`)
- **Warning:** Amber border (`border-amber-500`)
- **Error:** Red border (`border-red-500`)

### Message Types
- **Error:** Red background with error icon
- **Warning:** Amber background with warning icon
- **Info:** Blue background with info icon
- **Success:** Green background with checkmark icon

### Character Counter
- **Error:** Red (exceeds max)
- **Warning:** Amber (below optimal)
- **Success:** Green (at optimal)
- **Info:** Gray (neutral)

## Best Practices

### 1. When to Validate
- On blur (first interaction)
- Real-time after first blur
- On form submit (final check)

### 2. Error Message Guidelines
- Be specific: "URL handle cannot contain spaces" not "Invalid URL"
- Be helpful: Suggest what the user should do
- Be concise: Keep messages under 100 characters
- Be friendly: Avoid technical jargon

### 3. Required Fields
- Mark with red asterisk (`*`)
- Validate immediately on blur
- Show clear "This field is required" message

### 4. Optional Fields with Limits
- Show character counter
- Warn if approaching limit
- Error when exceeding limit

### 5. SEO Fields
- Show optimal ranges (50-60 for titles, 120-160 for descriptions)
- Use warnings, not errors, for suboptimal lengths
- Provide helpful context about why length matters

## Migration Path for Existing Forms

### Step 1: Add Validation Utilities
Import validation functions at the top of your component:

```jsx
import { validateUrlHandle, validateTitle } from '../utils/validation';
```

### Step 2: Add Validation State
```jsx
const [errors, setErrors] = useState({});
```

### Step 3: Add Blur Handlers
```jsx
const handleBlur = (field) => {
  const validation = validators[field](formData[field]);
  setErrors(prev => ({
    ...prev,
    [field]: validation.error
  }));
};
```

### Step 4: Update Input Styling
```jsx
className={errors.urlHandle ? 'border-red-500' : 'border-zinc-300'}
```

### Step 5: Add Error Messages
```jsx
{errors.urlHandle && <FieldError message={errors.urlHandle} />}
```

### Step 6: Replace Success Alerts with Toast
```jsx
<Toast
  message="Changes saved successfully!"
  show={success}
  onClose={() => setSuccess(false)}
/>
```

## Testing Checklist

- [ ] URL handle rejects uppercase letters
- [ ] URL handle rejects spaces
- [ ] URL handle accepts valid format (lowercase-with-hyphens)
- [ ] Title validates length constraints
- [ ] SEO title shows warning under 50 characters
- [ ] SEO title shows error over 60 characters
- [ ] SEO description shows warning under 120 characters
- [ ] SEO description shows error over 160 characters
- [ ] Character counters update in real-time
- [ ] Validation triggers on blur
- [ ] Real-time validation works after first blur
- [ ] Form submit is blocked if validation fails
- [ ] Toast appears on successful save
- [ ] Toast auto-dismisses after 3 seconds
- [ ] Error messages are clear and helpful

## Common Patterns

### Pattern 1: Simple Required Field
```jsx
<ValidatedInput
  name="title"
  value={formData.title}
  onChange={handleChange}
  validator={(value) => validateRequired(value, 'Title')}
  label="Title"
  required
/>
```

### Pattern 2: Field with Length Limits
```jsx
<ValidatedInput
  name="title"
  value={formData.title}
  onChange={handleChange}
  validator={(value) => validateTitle(value, 3, 100)}
  label="Title"
  required
  showCharCount
  maxLength={100}
/>
```

### Pattern 3: Optional Field with Optimal Range
```jsx
<ValidatedTextarea
  name="seoDescription"
  value={formData.seoDescription}
  onChange={handleChange}
  validator={validateSeoDescription}
  label="SEO Description"
  showCharCount
  maxLength={160}
  optimalLength={120}
  rows={3}
/>
```

### Pattern 4: URL/Handle Field
```jsx
<ValidatedInput
  name="urlHandle"
  value={formData.urlHandle}
  onChange={handleChange}
  validator={validateUrlHandle}
  label="URL Handle"
  hint="Use lowercase letters, numbers, and hyphens only"
  required
  showCharCount
  maxLength={100}
/>
```

## Troubleshooting

### Issue: Validation not triggering
**Solution:** Ensure `validator` prop is passed and returns `{ isValid, error }` object

### Issue: Character count not showing
**Solution:** Set `showCharCount={true}` and provide `maxLength` prop

### Issue: Toast not appearing
**Solution:** Check that `show` prop is true and component is rendered

### Issue: Validation state persisting
**Solution:** Reset validation state when form is submitted or closed

### Issue: Real-time validation too aggressive
**Solution:** Use `touched` state to only validate after first blur

## Future Enhancements

- [ ] Add debounced validation for async checks (unique handle validation)
- [ ] Add field-level validation summary at form level
- [ ] Add "Save anyway" option for warnings (not errors)
- [ ] Add keyboard shortcuts (Ctrl+S to save)
- [ ] Add unsaved changes warning
- [ ] Add batch validation for all fields on submit
- [ ] Add custom validation rule builder
- [ ] Add internationalization for error messages
