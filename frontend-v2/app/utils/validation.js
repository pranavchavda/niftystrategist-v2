/**
 * Form Validation Utilities
 * Provides reusable validation functions with helpful error messages
 */

/**
 * Validates URL handle format
 * @param {string} value - The URL handle to validate
 * @returns {{ isValid: boolean, error: string | null }}
 */
export function validateUrlHandle(value) {
  if (!value || !value.trim()) {
    return { isValid: false, error: 'URL handle is required' };
  }

  const trimmed = value.trim();

  // Check for spaces
  if (/\s/.test(trimmed)) {
    return { isValid: false, error: 'URL handle cannot contain spaces' };
  }

  // Check for uppercase letters
  if (/[A-Z]/.test(trimmed)) {
    return { isValid: false, error: 'URL handle must be lowercase' };
  }

  // Check for special characters (only allow lowercase, numbers, and hyphens)
  if (!/^[a-z0-9-]+$/.test(trimmed)) {
    return { isValid: false, error: 'URL handle can only contain lowercase letters, numbers, and hyphens' };
  }

  // Check for consecutive hyphens
  if (/--/.test(trimmed)) {
    return { isValid: false, error: 'URL handle cannot contain consecutive hyphens' };
  }

  // Check if it starts or ends with hyphen
  if (trimmed.startsWith('-') || trimmed.endsWith('-')) {
    return { isValid: false, error: 'URL handle cannot start or end with a hyphen' };
  }

  // Check length
  if (trimmed.length < 2) {
    return { isValid: false, error: 'URL handle must be at least 2 characters' };
  }

  if (trimmed.length > 100) {
    return { isValid: false, error: 'URL handle must be less than 100 characters' };
  }

  return { isValid: true, error: null };
}

/**
 * Validates title field
 * @param {string} value - The title to validate
 * @param {number} minLength - Minimum length (default: 3)
 * @param {number} maxLength - Maximum length (default: 100)
 * @returns {{ isValid: boolean, error: string | null }}
 */
export function validateTitle(value, minLength = 3, maxLength = 100) {
  if (!value || !value.trim()) {
    return { isValid: false, error: 'Title is required' };
  }

  const trimmed = value.trim();

  if (trimmed.length < minLength) {
    return { isValid: false, error: `Title must be at least ${minLength} characters` };
  }

  if (trimmed.length > maxLength) {
    return { isValid: false, error: `Title must be less than ${maxLength} characters` };
  }

  return { isValid: true, error: null };
}

/**
 * Validates SEO title field
 * @param {string} value - The SEO title to validate
 * @returns {{ isValid: boolean, error: string | null, warning: string | null }}
 */
export function validateSeoTitle(value) {
  if (!value || !value.trim()) {
    return { isValid: true, error: null, warning: null };
  }

  const trimmed = value.trim();

  if (trimmed.length > 60) {
    return {
      isValid: false,
      error: 'SEO title must be 60 characters or less',
      warning: null
    };
  }

  if (trimmed.length < 50) {
    return {
      isValid: true,
      error: null,
      warning: 'SEO title is short - recommended 50-60 characters for better visibility'
    };
  }

  return { isValid: true, error: null, warning: null };
}

/**
 * Validates SEO description field
 * @param {string} value - The SEO description to validate
 * @returns {{ isValid: boolean, error: string | null, warning: string | null }}
 */
export function validateSeoDescription(value) {
  if (!value || !value.trim()) {
    return { isValid: true, error: null, warning: null };
  }

  const trimmed = value.trim();

  if (trimmed.length > 160) {
    return {
      isValid: false,
      error: 'SEO description must be 160 characters or less',
      warning: null
    };
  }

  if (trimmed.length < 120) {
    return {
      isValid: true,
      error: null,
      warning: 'SEO description is short - recommended 120-160 characters for better visibility'
    };
  }

  return { isValid: true, error: null, warning: null };
}

/**
 * Validates required field
 * @param {string} value - The value to validate
 * @param {string} fieldName - Display name for the field
 * @returns {{ isValid: boolean, error: string | null }}
 */
export function validateRequired(value, fieldName = 'This field') {
  if (!value || !value.trim()) {
    return { isValid: false, error: `${fieldName} is required` };
  }

  return { isValid: true, error: null };
}

/**
 * Validates text field with length constraints
 * @param {string} value - The text to validate
 * @param {Object} options - Validation options
 * @param {number} options.minLength - Minimum length
 * @param {number} options.maxLength - Maximum length
 * @param {boolean} options.required - Whether field is required
 * @param {string} options.fieldName - Display name for the field
 * @returns {{ isValid: boolean, error: string | null }}
 */
export function validateText(value, options = {}) {
  const {
    minLength = 0,
    maxLength = null,
    required = false,
    fieldName = 'This field'
  } = options;

  if (required && (!value || !value.trim())) {
    return { isValid: false, error: `${fieldName} is required` };
  }

  if (!value || !value.trim()) {
    return { isValid: true, error: null };
  }

  const trimmed = value.trim();

  if (minLength && trimmed.length < minLength) {
    return { isValid: false, error: `${fieldName} must be at least ${minLength} characters` };
  }

  if (maxLength && trimmed.length > maxLength) {
    return { isValid: false, error: `${fieldName} must be less than ${maxLength} characters` };
  }

  return { isValid: true, error: null };
}

/**
 * Validates number field
 * @param {string|number} value - The number to validate
 * @param {Object} options - Validation options
 * @param {number} options.min - Minimum value
 * @param {number} options.max - Maximum value
 * @param {boolean} options.required - Whether field is required
 * @param {string} options.fieldName - Display name for the field
 * @returns {{ isValid: boolean, error: string | null }}
 */
export function validateNumber(value, options = {}) {
  const {
    min = null,
    max = null,
    required = false,
    fieldName = 'This field'
  } = options;

  if (required && (value === null || value === undefined || value === '')) {
    return { isValid: false, error: `${fieldName} is required` };
  }

  if (value === null || value === undefined || value === '') {
    return { isValid: true, error: null };
  }

  const num = typeof value === 'string' ? parseFloat(value) : value;

  if (isNaN(num)) {
    return { isValid: false, error: `${fieldName} must be a valid number` };
  }

  if (min !== null && num < min) {
    return { isValid: false, error: `${fieldName} must be at least ${min}` };
  }

  if (max !== null && num > max) {
    return { isValid: false, error: `${fieldName} must be at most ${max}` };
  }

  return { isValid: true, error: null };
}

/**
 * Validates URL format
 * @param {string} value - The URL to validate
 * @param {boolean} required - Whether field is required
 * @returns {{ isValid: boolean, error: string | null }}
 */
export function validateUrl(value, required = false) {
  if (required && (!value || !value.trim())) {
    return { isValid: false, error: 'URL is required' };
  }

  if (!value || !value.trim()) {
    return { isValid: true, error: null };
  }

  const trimmed = value.trim();

  try {
    // Allow relative URLs (starting with /) or full URLs
    if (trimmed.startsWith('/')) {
      return { isValid: true, error: null };
    }

    // Try to parse as full URL
    new URL(trimmed);
    return { isValid: true, error: null };
  } catch (e) {
    return { isValid: false, error: 'URL must be a valid URL or start with /' };
  }
}

/**
 * Get character count message with color coding
 * @param {number} current - Current character count
 * @param {number} max - Maximum characters
 * @param {number} optimal - Optimal character count
 * @returns {{ message: string, type: 'success' | 'warning' | 'error' }}
 */
export function getCharacterCountMessage(current, max, optimal = null) {
  if (current > max) {
    return {
      message: `${current}/${max} characters - exceeds limit`,
      type: 'error'
    };
  }

  if (optimal && current >= optimal) {
    return {
      message: `${current}/${max} characters - optimal length`,
      type: 'success'
    };
  }

  if (optimal && current < optimal) {
    return {
      message: `${current}/${max} characters (recommended: ${optimal}+)`,
      type: 'warning'
    };
  }

  return {
    message: `${current}/${max} characters`,
    type: 'success'
  };
}
