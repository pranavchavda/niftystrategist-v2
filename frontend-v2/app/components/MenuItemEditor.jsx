import { useState } from 'react';
import { Dialog, DialogTitle, DialogDescription, DialogBody, DialogActions } from './catalyst/dialog';
import { Field, Label } from './catalyst/fieldset';
import { Input } from './catalyst/input';
import { Textarea } from './catalyst/textarea';
import { Button } from './catalyst/button';
import { Radio, RadioField, RadioGroup } from './catalyst/radio';
import { Checkbox, CheckboxField } from './catalyst/checkbox';

export default function MenuItemEditor({ item, onSave, onClose, isCreating = false }) {
  const [formData, setFormData] = useState({
    type: item.type || 'standard',
    title: item.title || '',
    description: item.description || '',
    url: item.url || '',
    item_type: item.item_type || 'HTTP',
    speciallink: item.speciallink || false,
    hide_us: item.hide_us || false,
    hide_ca: item.hide_ca || false,
  });

  const [errors, setErrors] = useState({});

  function handleChange(field, value) {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error for this field
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: null }));
    }
  }

  function validate() {
    const newErrors = {};

    if (!formData.title.trim()) {
      newErrors.title = 'Title is required';
    }

    if (!formData.url.trim()) {
      newErrors.url = 'URL is required';
    }

    if (formData.type === 'cta' && !formData.description.trim()) {
      newErrors.description = 'Description is required for CTA items';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  function handleSave() {
    if (!validate()) {
      return;
    }

    // Build the updated item
    const updatedItem = {
      ...item, // Preserve existing fields like id, items
      type: formData.type,
      title: formData.title,
      url: formData.url,
      item_type: formData.item_type,
      speciallink: formData.speciallink,
      hide_us: formData.hide_us,
      hide_ca: formData.hide_ca,
    };

    // Only include description for CTA items
    if (formData.type === 'cta') {
      updatedItem.description = formData.description;
    } else {
      updatedItem.description = undefined;
    }

    onSave(updatedItem);
  }

  return (
    <Dialog open={true} onClose={onClose} size="2xl">
      <DialogTitle>{isCreating ? 'Add Menu Item' : 'Edit Menu Item'}</DialogTitle>
      <DialogDescription>
        {isCreating
          ? 'Create a new menu item with title, URL, and special pattern flags'
          : 'Update the menu item details and special pattern flags'}
      </DialogDescription>

      <DialogBody>
        <div className="space-y-6">
          {/* Item Type Selection */}
          <RadioGroup value={formData.type} onChange={(value) => handleChange('type', value)}>
            <Label>Item Type</Label>
            <div className="mt-2 grid grid-cols-3 gap-3">
              <RadioField>
                <Radio value="standard" />
                <Label>Standard</Label>
              </RadioField>
              <RadioField>
                <Radio value="cta" />
                <Label>CTA</Label>
              </RadioField>
              <RadioField>
                <Radio value="button" />
                <Label>Button</Label>
              </RadioField>
            </div>
          </RadioGroup>

          {/* Title */}
          <Field>
            <Label>Title</Label>
            <Input
              value={formData.title}
              onChange={(e) => handleChange('title', e.target.value)}
              invalid={!!errors.title}
            />
            {errors.title && (
              <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.title}</p>
            )}
          </Field>

          {/* Description (CTA only) */}
          {formData.type === 'cta' && (
            <Field>
              <Label>Description</Label>
              <Textarea
                value={formData.description}
                onChange={(e) => handleChange('description', e.target.value)}
                rows={2}
                invalid={!!errors.description}
              />
              {errors.description && (
                <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.description}</p>
              )}
            </Field>
          )}

          {/* URL */}
          <Field>
            <Label>URL</Label>
            <Input
              value={formData.url}
              onChange={(e) => handleChange('url', e.target.value)}
              invalid={!!errors.url}
              placeholder="/collections/coffee"
            />
            {errors.url && (
              <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.url}</p>
            )}
          </Field>

          {/* URL Type */}
          <Field>
            <Label>Link Type</Label>
            <select
              value={formData.item_type}
              onChange={(e) => handleChange('item_type', e.target.value)}
              className="block w-full rounded-md border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-sm focus:border-purple-500 focus:ring-purple-500 sm:text-sm"
            >
              <option value="HTTP">HTTP/HTTPS Link</option>
              <option value="COLLECTION">Collection</option>
              <option value="PRODUCT">Product</option>
            </select>
          </Field>

          {/* Special Flags */}
          <div className="space-y-3 pt-4 border-t border-zinc-200 dark:border-zinc-700">
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Special Flags</p>

            <CheckboxField>
              <Checkbox
                checked={formData.speciallink}
                onChange={(checked) => handleChange('speciallink', checked)}
              />
              <Label>Special Link (SPECIALLINK flag)</Label>
            </CheckboxField>

            <CheckboxField>
              <Checkbox
                checked={formData.hide_us}
                onChange={(checked) => handleChange('hide_us', checked)}
              />
              <Label>Hide from US users (not-us-eg)</Label>
            </CheckboxField>

            <CheckboxField>
              <Checkbox
                checked={formData.hide_ca}
                onChange={(checked) => handleChange('hide_ca', checked)}
              />
              <Label>Hide from Canadian users (not-ca-eg)</Label>
            </CheckboxField>
          </div>

          {/* Preview */}
          {formData.type !== 'standard' && (
            <div className="rounded-lg bg-zinc-50 dark:bg-zinc-900/30 p-4 border border-zinc-200 dark:border-zinc-700">
              <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">Pattern Preview</p>
              <p className="text-xs font-mono text-zinc-600 dark:text-zinc-400 break-all">
                {formData.type === 'cta' && `CTA|${formData.title}|${formData.description}${formData.speciallink ? '|SPECIALLINK' : ''}`}
                {formData.type === 'button' && `Button|${formData.title}${formData.speciallink ? '|SPECIALLINK' : ''}`}
              </p>
            </div>
          )}
        </div>
      </DialogBody>

      <DialogActions>
        <Button plain onClick={onClose}>
          Cancel
        </Button>
        <Button color="purple" onClick={handleSave}>
          {isCreating ? 'Add Item' : 'Save Changes'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
