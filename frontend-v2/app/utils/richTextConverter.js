/**
 * Shopify Rich Text Converter
 * Bidirectional conversion between Shopify rich text JSON and Markdown
 *
 * Shopify Rich Text Structure:
 * {
 *   type: "root",
 *   children: [
 *     { type: "paragraph", children: [{ type: "text", value: "...", bold: true }] },
 *     { type: "heading", level: 2-6, children: [...] },
 *     { type: "list", listType: "ordered|unordered", children: [...] }
 *   ]
 * }
 */

/**
 * Convert Shopify rich text JSON to Markdown
 * @param {string|object} jsonInput - Shopify rich text JSON (string or parsed object)
 * @returns {string} Markdown formatted text
 */
export function shopifyRichTextToMarkdown(jsonInput) {
  if (!jsonInput) return '';

  try {
    // Parse JSON if it's a string
    const richText = typeof jsonInput === 'string' ? JSON.parse(jsonInput) : jsonInput;

    if (!richText || !richText.children) {
      // Fallback: if it's plain text, return as-is
      return typeof jsonInput === 'string' && !jsonInput.startsWith('{') ? jsonInput : '';
    }

    const lines = [];

    richText.children.forEach(node => {
      const markdown = nodeToMarkdown(node);
      if (markdown) {
        lines.push(markdown);
      }
    });

    return lines.join('\n\n');
  } catch (error) {
    console.warn('Failed to parse Shopify rich text to markdown:', error);
    // Fallback to plain text
    return typeof jsonInput === 'string' ? jsonInput : '';
  }
}

/**
 * Convert a single rich text node to markdown
 * @param {object} node - Rich text node
 * @param {number} indent - Indentation level for lists
 * @returns {string} Markdown string
 */
function nodeToMarkdown(node, indent = 0) {
  if (!node) return '';

  const indentation = '  '.repeat(indent);

  switch (node.type) {
    case 'paragraph':
      return textChildrenToMarkdown(node.children);

    case 'heading':
      const level = node.level || 3;
      const headingPrefix = '#'.repeat(level);
      return `${headingPrefix} ${textChildrenToMarkdown(node.children)}`;

    case 'list':
      if (!node.children) return '';
      const isOrdered = node.listType === 'ordered';
      return node.children
        .map((item, index) => {
          const prefix = isOrdered ? `${index + 1}.` : '-';
          const content = item.children ? textChildrenToMarkdown(item.children) : '';
          return `${indentation}${prefix} ${content}`;
        })
        .join('\n');

    case 'list-item':
      // Handled by parent list node
      return textChildrenToMarkdown(node.children);

    default:
      // Fallback for unknown node types
      if (node.children) {
        return textChildrenToMarkdown(node.children);
      }
      return node.value || '';
  }
}

/**
 * Convert text children nodes to markdown with formatting
 * @param {array} children - Array of text nodes
 * @returns {string} Formatted markdown text
 */
function textChildrenToMarkdown(children) {
  if (!children) return '';

  return children.map(child => {
    if (child.type === 'text') {
      let text = child.value || '';

      // Apply formatting
      if (child.bold && child.italic) {
        text = `***${text}***`;
      } else if (child.bold) {
        text = `**${text}**`;
      } else if (child.italic) {
        text = `*${text}*`;
      }

      return text;
    }

    // Handle nested structures
    return nodeToMarkdown(child);
  }).join('');
}

/**
 * Convert Markdown to Shopify rich text JSON
 * @param {string} markdown - Markdown formatted text
 * @returns {string} JSON string of Shopify rich text structure
 */
export function markdownToShopifyRichText(markdown) {
  if (!markdown || typeof markdown !== 'string') {
    return JSON.stringify({ type: 'root', children: [] });
  }

  try {
    const lines = markdown.split('\n');
    const children = [];
    let currentList = null;
    let currentListType = null;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      // Skip empty lines (they separate blocks)
      if (!trimmed) {
        // Close current list if any
        if (currentList) {
          children.push(currentList);
          currentList = null;
          currentListType = null;
        }
        continue;
      }

      // Detect headings (### Heading)
      const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
      if (headingMatch) {
        // Close current list if any
        if (currentList) {
          children.push(currentList);
          currentList = null;
          currentListType = null;
        }

        const level = headingMatch[1].length;
        const text = headingMatch[2];
        children.push({
          type: 'heading',
          level: level,
          children: parseInlineFormatting(text)
        });
        continue;
      }

      // Detect unordered list (- item or * item)
      const unorderedMatch = trimmed.match(/^[-*]\s+(.+)$/);
      if (unorderedMatch) {
        const text = unorderedMatch[1];

        if (!currentList || currentListType !== 'unordered') {
          // Start new unordered list
          if (currentList) {
            children.push(currentList);
          }
          currentList = {
            type: 'list',
            listType: 'unordered',
            children: []
          };
          currentListType = 'unordered';
        }

        currentList.children.push({
          type: 'list-item',
          children: parseInlineFormatting(text)
        });
        continue;
      }

      // Detect ordered list (1. item)
      const orderedMatch = trimmed.match(/^\d+\.\s+(.+)$/);
      if (orderedMatch) {
        const text = orderedMatch[1];

        if (!currentList || currentListType !== 'ordered') {
          // Start new ordered list
          if (currentList) {
            children.push(currentList);
          }
          currentList = {
            type: 'list',
            listType: 'ordered',
            children: []
          };
          currentListType = 'ordered';
        }

        currentList.children.push({
          type: 'list-item',
          children: parseInlineFormatting(text)
        });
        continue;
      }

      // Regular paragraph
      if (currentList) {
        children.push(currentList);
        currentList = null;
        currentListType = null;
      }

      children.push({
        type: 'paragraph',
        children: parseInlineFormatting(trimmed)
      });
    }

    // Close any remaining list
    if (currentList) {
      children.push(currentList);
    }

    return JSON.stringify({
      type: 'root',
      children: children
    });
  } catch (error) {
    console.error('Failed to convert markdown to Shopify rich text:', error);
    // Fallback: create simple paragraph structure
    return JSON.stringify({
      type: 'root',
      children: [{
        type: 'paragraph',
        children: [{ type: 'text', value: markdown }]
      }]
    });
  }
}

/**
 * Parse inline formatting (bold, italic) from markdown text
 * @param {string} text - Text with markdown formatting
 * @returns {array} Array of text nodes with formatting
 */
function parseInlineFormatting(text) {
  if (!text) return [{ type: 'text', value: '' }];

  const nodes = [];
  let remaining = text;

  // Regex to match bold+italic (***), bold (**), or italic (*)
  const formatRegex = /(\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match;

  while ((match = formatRegex.exec(remaining)) !== null) {
    // Add plain text before match
    if (match.index > lastIndex) {
      const plainText = remaining.substring(lastIndex, match.index);
      if (plainText) {
        nodes.push({ type: 'text', value: plainText });
      }
    }

    // Process formatted text
    const formatted = match[0];
    if (formatted.startsWith('***') && formatted.endsWith('***')) {
      // Bold + Italic
      const content = formatted.slice(3, -3);
      nodes.push({ type: 'text', value: content, bold: true, italic: true });
    } else if (formatted.startsWith('**') && formatted.endsWith('**')) {
      // Bold
      const content = formatted.slice(2, -2);
      nodes.push({ type: 'text', value: content, bold: true });
    } else if (formatted.startsWith('*') && formatted.endsWith('*')) {
      // Italic
      const content = formatted.slice(1, -1);
      nodes.push({ type: 'text', value: content, italic: true });
    }

    lastIndex = match.index + formatted.length;
  }

  // Add remaining plain text
  if (lastIndex < remaining.length) {
    const plainText = remaining.substring(lastIndex);
    if (plainText) {
      nodes.push({ type: 'text', value: plainText });
    }
  }

  return nodes.length > 0 ? nodes : [{ type: 'text', value: text }];
}

/**
 * Extract plain text from Shopify rich text JSON (legacy helper)
 * @param {string|object} richTextJson - Shopify rich text JSON
 * @returns {string} Plain text content
 */
export function extractRichTextContent(richTextJson) {
  if (!richTextJson) return '';

  try {
    const parsed = typeof richTextJson === 'string' ? JSON.parse(richTextJson) : richTextJson;

    if (!parsed.children) {
      return typeof richTextJson === 'string' ? richTextJson : '';
    }

    return parsed.children
      .map(child => {
        if (child.children) {
          return child.children.map(c => c.value || '').join('');
        }
        return child.value || '';
      })
      .join('\n');
  } catch (error) {
    console.warn('Failed to extract rich text content:', error);
    return typeof richTextJson === 'string' ? richTextJson : '';
  }
}
