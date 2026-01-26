/**
 * Test suite for Shopify Rich Text Converter
 * Run with: npm test richTextConverter.test.js
 */

import { shopifyRichTextToMarkdown, markdownToShopifyRichText } from '../richTextConverter';

describe('shopifyRichTextToMarkdown', () => {
  test('converts simple paragraph', () => {
    const input = {
      type: 'root',
      children: [
        {
          type: 'paragraph',
          children: [{ type: 'text', value: 'Hello world' }]
        }
      ]
    };
    const result = shopifyRichTextToMarkdown(input);
    expect(result).toBe('Hello world');
  });

  test('converts heading', () => {
    const input = {
      type: 'root',
      children: [
        {
          type: 'heading',
          level: 3,
          children: [{ type: 'text', value: 'My Heading' }]
        }
      ]
    };
    const result = shopifyRichTextToMarkdown(input);
    expect(result).toBe('### My Heading');
  });

  test('converts bold text', () => {
    const input = {
      type: 'root',
      children: [
        {
          type: 'paragraph',
          children: [
            { type: 'text', value: 'This is ' },
            { type: 'text', value: 'bold', bold: true },
            { type: 'text', value: ' text' }
          ]
        }
      ]
    };
    const result = shopifyRichTextToMarkdown(input);
    expect(result).toBe('This is **bold** text');
  });

  test('converts italic text', () => {
    const input = {
      type: 'root',
      children: [
        {
          type: 'paragraph',
          children: [
            { type: 'text', value: 'This is ' },
            { type: 'text', value: 'italic', italic: true },
            { type: 'text', value: ' text' }
          ]
        }
      ]
    };
    const result = shopifyRichTextToMarkdown(input);
    expect(result).toBe('This is *italic* text');
  });

  test('converts bold and italic text', () => {
    const input = {
      type: 'root',
      children: [
        {
          type: 'paragraph',
          children: [
            { type: 'text', value: 'bold and italic', bold: true, italic: true }
          ]
        }
      ]
    };
    const result = shopifyRichTextToMarkdown(input);
    expect(result).toBe('***bold and italic***');
  });

  test('converts unordered list', () => {
    const input = {
      type: 'root',
      children: [
        {
          type: 'list',
          listType: 'unordered',
          children: [
            { type: 'list-item', children: [{ type: 'text', value: 'First item' }] },
            { type: 'list-item', children: [{ type: 'text', value: 'Second item' }] }
          ]
        }
      ]
    };
    const result = shopifyRichTextToMarkdown(input);
    expect(result).toBe('- First item\n- Second item');
  });

  test('converts ordered list', () => {
    const input = {
      type: 'root',
      children: [
        {
          type: 'list',
          listType: 'ordered',
          children: [
            { type: 'list-item', children: [{ type: 'text', value: 'First item' }] },
            { type: 'list-item', children: [{ type: 'text', value: 'Second item' }] }
          ]
        }
      ]
    };
    const result = shopifyRichTextToMarkdown(input);
    expect(result).toBe('1. First item\n2. Second item');
  });

  test('converts mixed content', () => {
    const input = {
      type: 'root',
      children: [
        {
          type: 'paragraph',
          children: [{ type: 'text', value: 'Introduction text' }]
        },
        {
          type: 'heading',
          level: 3,
          children: [{ type: 'text', value: 'Benefits' }]
        },
        {
          type: 'list',
          listType: 'unordered',
          children: [
            {
              type: 'list-item',
              children: [
                { type: 'text', value: 'Freshness:', bold: true },
                { type: 'text', value: ' Keep beans fresh' }
              ]
            }
          ]
        }
      ]
    };
    const result = shopifyRichTextToMarkdown(input);
    expect(result).toContain('Introduction text');
    expect(result).toContain('### Benefits');
    expect(result).toContain('- **Freshness:** Keep beans fresh');
  });

  test('handles JSON string input', () => {
    const input = JSON.stringify({
      type: 'root',
      children: [
        {
          type: 'paragraph',
          children: [{ type: 'text', value: 'Test' }]
        }
      ]
    });
    const result = shopifyRichTextToMarkdown(input);
    expect(result).toBe('Test');
  });

  test('handles empty input', () => {
    expect(shopifyRichTextToMarkdown('')).toBe('');
    expect(shopifyRichTextToMarkdown(null)).toBe('');
    expect(shopifyRichTextToMarkdown(undefined)).toBe('');
  });

  test('handles malformed JSON gracefully', () => {
    const result = shopifyRichTextToMarkdown('not valid json{');
    expect(result).toBe('not valid json{'); // Falls back to plain text
  });
});

describe('markdownToShopifyRichText', () => {
  test('converts simple paragraph', () => {
    const markdown = 'Hello world';
    const result = JSON.parse(markdownToShopifyRichText(markdown));
    expect(result.type).toBe('root');
    expect(result.children).toHaveLength(1);
    expect(result.children[0].type).toBe('paragraph');
    expect(result.children[0].children[0].value).toBe('Hello world');
  });

  test('converts heading', () => {
    const markdown = '### My Heading';
    const result = JSON.parse(markdownToShopifyRichText(markdown));
    expect(result.children[0].type).toBe('heading');
    expect(result.children[0].level).toBe(3);
    expect(result.children[0].children[0].value).toBe('My Heading');
  });

  test('converts bold text', () => {
    const markdown = 'This is **bold** text';
    const result = JSON.parse(markdownToShopifyRichText(markdown));
    const children = result.children[0].children;
    expect(children[0].value).toBe('This is ');
    expect(children[1].value).toBe('bold');
    expect(children[1].bold).toBe(true);
    expect(children[2].value).toBe(' text');
  });

  test('converts italic text', () => {
    const markdown = 'This is *italic* text';
    const result = JSON.parse(markdownToShopifyRichText(markdown));
    const children = result.children[0].children;
    expect(children[1].value).toBe('italic');
    expect(children[1].italic).toBe(true);
  });

  test('converts bold and italic text', () => {
    const markdown = '***bold and italic***';
    const result = JSON.parse(markdownToShopifyRichText(markdown));
    const textNode = result.children[0].children[0];
    expect(textNode.value).toBe('bold and italic');
    expect(textNode.bold).toBe(true);
    expect(textNode.italic).toBe(true);
  });

  test('converts unordered list', () => {
    const markdown = '- First item\n- Second item';
    const result = JSON.parse(markdownToShopifyRichText(markdown));
    expect(result.children[0].type).toBe('list');
    expect(result.children[0].listType).toBe('unordered');
    expect(result.children[0].children).toHaveLength(2);
    expect(result.children[0].children[0].children[0].value).toBe('First item');
  });

  test('converts ordered list', () => {
    const markdown = '1. First item\n2. Second item';
    const result = JSON.parse(markdownToShopifyRichText(markdown));
    expect(result.children[0].type).toBe('list');
    expect(result.children[0].listType).toBe('ordered');
    expect(result.children[0].children).toHaveLength(2);
  });

  test('converts mixed content', () => {
    const markdown = `Introduction text

### Benefits

- **Freshness:** Keep beans fresh
- **Variety:** Switch between coffees`;
    const result = JSON.parse(markdownToShopifyRichText(markdown));
    expect(result.children).toHaveLength(3); // paragraph, heading, list
    expect(result.children[0].type).toBe('paragraph');
    expect(result.children[1].type).toBe('heading');
    expect(result.children[2].type).toBe('list');
  });

  test('separates lists properly', () => {
    const markdown = `- Item 1
- Item 2

New paragraph`;
    const result = JSON.parse(markdownToShopifyRichText(markdown));
    expect(result.children).toHaveLength(2); // list, paragraph
    expect(result.children[0].type).toBe('list');
    expect(result.children[1].type).toBe('paragraph');
  });

  test('handles empty input', () => {
    const result = JSON.parse(markdownToShopifyRichText(''));
    expect(result.type).toBe('root');
    expect(result.children).toHaveLength(0);
  });

  test('handles multiple paragraphs', () => {
    const markdown = 'First paragraph\n\nSecond paragraph';
    const result = JSON.parse(markdownToShopifyRichText(markdown));
    expect(result.children).toHaveLength(2);
    expect(result.children[0].children[0].value).toBe('First paragraph');
    expect(result.children[1].children[0].value).toBe('Second paragraph');
  });
});

describe('bidirectional conversion', () => {
  test('markdown -> shopify -> markdown preserves content', () => {
    const original = `Introduction text

### Benefits of Single Dosing

- **Freshness:** Grind only what you need
- *Easy* to use
- Both **bold** and *italic* text

1. First step
2. Second step

Conclusion paragraph`;

    const shopifyJson = markdownToShopifyRichText(original);
    const backToMarkdown = shopifyRichTextToMarkdown(shopifyJson);

    // Check key content is preserved
    expect(backToMarkdown).toContain('Introduction text');
    expect(backToMarkdown).toContain('### Benefits of Single Dosing');
    expect(backToMarkdown).toContain('**Freshness:**');
    expect(backToMarkdown).toContain('*Easy*');
    expect(backToMarkdown).toContain('1. First step');
    expect(backToMarkdown).toContain('Conclusion paragraph');
  });

  test('shopify -> markdown -> shopify preserves structure', () => {
    const original = {
      type: 'root',
      children: [
        {
          type: 'paragraph',
          children: [{ type: 'text', value: 'Test paragraph' }]
        },
        {
          type: 'heading',
          level: 3,
          children: [{ type: 'text', value: 'Test Heading' }]
        },
        {
          type: 'list',
          listType: 'unordered',
          children: [
            {
              type: 'list-item',
              children: [
                { type: 'text', value: 'Bold item', bold: true }
              ]
            }
          ]
        }
      ]
    };

    const markdown = shopifyRichTextToMarkdown(original);
    const backToShopify = JSON.parse(markdownToShopifyRichText(markdown));

    expect(backToShopify.type).toBe('root');
    expect(backToShopify.children).toHaveLength(3);
    expect(backToShopify.children[0].type).toBe('paragraph');
    expect(backToShopify.children[1].type).toBe('heading');
    expect(backToShopify.children[1].level).toBe(3);
    expect(backToShopify.children[2].type).toBe('list');
    expect(backToShopify.children[2].listType).toBe('unordered');
  });
});
