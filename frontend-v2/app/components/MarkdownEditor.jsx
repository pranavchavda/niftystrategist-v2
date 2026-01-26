import React, { useState, useEffect, useRef } from 'react';
import { Bold, Italic, List, ListOrdered, Heading3, Eye, Code } from 'lucide-react';

/**
 * MarkdownEditor Component
 * WYSIWYG markdown editor with live preview and formatting toolbar
 *
 * Features:
 * - Split view: Editor (left) | Preview (right)
 * - Toolbar with quick insert buttons
 * - Live preview updates as you type
 * - Character count
 * - Mobile responsive (stacked layout)
 * - Dark mode support
 *
 * @param {object} props
 * @param {string} props.value - Current markdown content
 * @param {function} props.onChange - Callback when content changes
 * @param {string} props.label - Label for the editor
 * @param {string} props.placeholder - Placeholder text
 * @param {number} props.rows - Number of rows for textarea (default: 10)
 * @param {boolean} props.disabled - Disable editing
 * @param {boolean} props.required - Mark as required field
 */
export default function MarkdownEditor({
  value = '',
  onChange,
  label = 'Content',
  placeholder = 'Enter markdown content...',
  rows = 10,
  disabled = false,
  required = false,
}) {
  const [showPreview, setShowPreview] = useState(true);
  const textareaRef = useRef(null);

  const handleChange = (e) => {
    onChange(e.target.value);
  };

  /**
   * Insert markdown formatting at cursor position
   * @param {string} before - Text to insert before selection
   * @param {string} after - Text to insert after selection
   * @param {string} placeholder - Placeholder if no selection
   */
  const insertFormatting = (before, after, placeholder = 'text') => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.substring(start, end);
    const textToInsert = selectedText || placeholder;

    const newValue =
      value.substring(0, start) +
      before +
      textToInsert +
      after +
      value.substring(end);

    onChange(newValue);

    // Set cursor position after inserted text
    setTimeout(() => {
      const newCursorPos = start + before.length + textToInsert.length;
      textarea.focus();
      textarea.setSelectionRange(newCursorPos, newCursorPos);
    }, 0);
  };

  const toolbarButtons = [
    {
      icon: Heading3,
      label: 'Heading',
      action: () => {
        const textarea = textareaRef.current;
        const start = textarea.selectionStart;
        const lineStart = value.lastIndexOf('\n', start - 1) + 1;
        const lineEnd = value.indexOf('\n', start);
        const currentLine = value.substring(
          lineStart,
          lineEnd === -1 ? value.length : lineEnd
        );

        // Toggle heading
        if (currentLine.startsWith('### ')) {
          // Remove heading
          const newValue =
            value.substring(0, lineStart) +
            currentLine.substring(4) +
            value.substring(lineEnd === -1 ? value.length : lineEnd);
          onChange(newValue);
        } else {
          // Add heading
          const newValue =
            value.substring(0, lineStart) +
            '### ' +
            currentLine +
            value.substring(lineEnd === -1 ? value.length : lineEnd);
          onChange(newValue);
        }
      },
    },
    {
      icon: Bold,
      label: 'Bold',
      action: () => insertFormatting('**', '**', 'bold text'),
    },
    {
      icon: Italic,
      label: 'Italic',
      action: () => insertFormatting('*', '*', 'italic text'),
    },
    {
      icon: List,
      label: 'Bullet List',
      action: () => {
        const textarea = textareaRef.current;
        const start = textarea.selectionStart;
        const lineStart = value.lastIndexOf('\n', start - 1) + 1;
        const prefix = lineStart === 0 ? '' : '\n';
        insertFormatting(prefix + '- ', '', 'list item');
      },
    },
    {
      icon: ListOrdered,
      label: 'Numbered List',
      action: () => {
        const textarea = textareaRef.current;
        const start = textarea.selectionStart;
        const lineStart = value.lastIndexOf('\n', start - 1) + 1;
        const prefix = lineStart === 0 ? '' : '\n';
        insertFormatting(prefix + '1. ', '', 'list item');
      },
    },
  ];

  const characterCount = value.length;

  return (
    <div className="space-y-2">
      {/* Label */}
      <div className="flex items-center justify-between">
        <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100">
          {label}
          {required && <span className="text-red-600 dark:text-red-400 ml-1">*</span>}
        </label>
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            {characterCount} characters
          </span>
          <button
            type="button"
            onClick={() => setShowPreview(!showPreview)}
            className="p-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
            title={showPreview ? 'Hide preview' : 'Show preview'}
          >
            <Eye className={`h-4 w-4 ${showPreview ? 'text-blue-600' : 'text-zinc-400'}`} />
          </button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-1 p-2 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-t-lg">
        {toolbarButtons.map((button, index) => {
          const Icon = button.icon;
          return (
            <button
              key={index}
              type="button"
              onClick={button.action}
              disabled={disabled}
              className="p-2 hover:bg-zinc-200 active:bg-zinc-300 dark:hover:bg-zinc-700 dark:active:bg-zinc-600 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title={button.label}
            >
              <Icon className="h-4 w-4 text-zinc-700 dark:text-zinc-300" />
            </button>
          );
        })}
        <div className="mx-2 h-5 w-px bg-zinc-300 dark:bg-zinc-600" />
        <div className="flex items-center gap-1 text-xs text-zinc-500 dark:text-zinc-400 px-2">
          <Code className="h-3 w-3" />
          <span className="hidden sm:inline">Markdown</span>
        </div>
      </div>

      {/* Editor and Preview */}
      <div
        className={`grid ${
          showPreview ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1'
        } gap-4 border border-zinc-200 dark:border-zinc-700 rounded-b-lg overflow-hidden`}
      >
        {/* Editor */}
        <div className="relative">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            placeholder={placeholder}
            disabled={disabled}
            rows={rows}
            className="w-full h-full min-h-[200px] px-3 py-2.5 bg-white dark:bg-zinc-900 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 resize-none border-0"
            style={{ minHeight: `${rows * 24}px` }}
          />
        </div>

        {/* Preview */}
        {showPreview && (
          <div className="border-t lg:border-t-0 lg:border-l border-zinc-200 dark:border-zinc-700">
            <div className="px-3 py-2.5 bg-zinc-50 dark:bg-zinc-900 min-h-[200px] overflow-y-auto prose prose-sm dark:prose-invert max-w-none">
              {value ? (
                <MarkdownPreview content={value} />
              ) : (
                <p className="text-zinc-400 dark:text-zinc-600 italic">
                  Preview will appear here...
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Helper Text */}
      <div className="text-xs text-zinc-500 dark:text-zinc-400 space-y-1">
        <p>
          <strong>Formatting:</strong> **bold**, *italic*, ### heading, - list, 1. numbered list
        </p>
      </div>
    </div>
  );
}

/**
 * MarkdownPreview Component
 * Renders markdown content as HTML with proper styling
 */
function MarkdownPreview({ content }) {
  if (!content) return null;

  const lines = content.split('\n');
  const elements = [];
  let currentList = null;
  let currentListType = null;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Skip empty lines
    if (!trimmed) {
      if (currentList) {
        elements.push(currentList);
        currentList = null;
        currentListType = null;
      }
      continue;
    }

    // Headings
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      if (currentList) {
        elements.push(currentList);
        currentList = null;
        currentListType = null;
      }
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const HeadingTag = `h${level}`;
      elements.push(
        <HeadingTag
          key={i}
          className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mt-4 mb-2"
        >
          {renderInlineFormatting(text)}
        </HeadingTag>
      );
      continue;
    }

    // Unordered list
    const unorderedMatch = trimmed.match(/^[-*]\s+(.+)$/);
    if (unorderedMatch) {
      const text = unorderedMatch[1];
      if (!currentList || currentListType !== 'ul') {
        if (currentList) elements.push(currentList);
        currentList = {
          type: 'ul',
          items: [],
          key: i,
        };
        currentListType = 'ul';
      }
      currentList.items.push({ text, key: i });
      continue;
    }

    // Ordered list
    const orderedMatch = trimmed.match(/^\d+\.\s+(.+)$/);
    if (orderedMatch) {
      const text = orderedMatch[1];
      if (!currentList || currentListType !== 'ol') {
        if (currentList) elements.push(currentList);
        currentList = {
          type: 'ol',
          items: [],
          key: i,
        };
        currentListType = 'ol';
      }
      currentList.items.push({ text, key: i });
      continue;
    }

    // Regular paragraph
    if (currentList) {
      elements.push(currentList);
      currentList = null;
      currentListType = null;
    }
    elements.push(
      <p key={i} className="mb-3 text-zinc-900 dark:text-zinc-100">
        {renderInlineFormatting(trimmed)}
      </p>
    );
  }

  // Push remaining list
  if (currentList) {
    elements.push(currentList);
  }

  return (
    <div className="space-y-2">
      {elements.map((element, index) => {
        if (element.type === 'ul') {
          return (
            <ul key={element.key || index} className="list-disc list-inside mb-3 space-y-1">
              {element.items.map((item) => (
                <li key={item.key} className="text-zinc-900 dark:text-zinc-100">
                  {renderInlineFormatting(item.text)}
                </li>
              ))}
            </ul>
          );
        } else if (element.type === 'ol') {
          return (
            <ol key={element.key || index} className="list-decimal list-inside mb-3 space-y-1">
              {element.items.map((item) => (
                <li key={item.key} className="text-zinc-900 dark:text-zinc-100">
                  {renderInlineFormatting(item.text)}
                </li>
              ))}
            </ol>
          );
        }
        return element;
      })}
    </div>
  );
}

/**
 * Render inline formatting (bold, italic)
 * @param {string} text - Text with markdown formatting
 * @returns {JSX.Element|string}
 */
function renderInlineFormatting(text) {
  if (!text) return '';

  const parts = [];
  let remaining = text;
  let key = 0;

  // Match bold+italic (***), bold (**), or italic (*)
  const formatRegex = /(\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match;

  while ((match = formatRegex.exec(remaining)) !== null) {
    // Plain text before match
    if (match.index > lastIndex) {
      parts.push(remaining.substring(lastIndex, match.index));
    }

    const formatted = match[0];
    if (formatted.startsWith('***') && formatted.endsWith('***')) {
      // Bold + Italic
      const content = formatted.slice(3, -3);
      parts.push(
        <strong key={key++} className="font-bold italic">
          {content}
        </strong>
      );
    } else if (formatted.startsWith('**') && formatted.endsWith('**')) {
      // Bold
      const content = formatted.slice(2, -2);
      parts.push(
        <strong key={key++} className="font-bold">
          {content}
        </strong>
      );
    } else if (formatted.startsWith('*') && formatted.endsWith('*')) {
      // Italic
      const content = formatted.slice(1, -1);
      parts.push(
        <em key={key++} className="italic">
          {content}
        </em>
      );
    }

    lastIndex = match.index + formatted.length;
  }

  // Remaining plain text
  if (lastIndex < remaining.length) {
    parts.push(remaining.substring(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}
