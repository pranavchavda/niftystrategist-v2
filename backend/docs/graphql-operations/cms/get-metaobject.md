# Get Metaobject

Fetches a single metaobject by ID with all fields and references expanded.

## Use Cases
- Retrieve full details of a category landing page
- Load FAQ section with all questions
- Fetch comparison table with all features
- Get educational block content for editing
- Inspect metaobject structure and field values

## GraphQL

### Standard Query (Single References)
```graphql
query getMetaobject($id: ID!) {
  metaobject(id: $id) {
    id
    handle
    displayName
    type
    fields {
      key
      value
      type
      reference {
        ... on MediaImage {
          id
          image {
            url
            altText
            width
            height
          }
        }
        ... on Collection {
          id
          handle
          title
        }
        ... on Product {
          id
          handle
          title
        }
        ... on Metaobject {
          id
          handle
          displayName
          type
        }
      }
      references(first: 10) {
        edges {
          node {
            ... on MediaImage {
              id
              image {
                url
                altText
              }
            }
            ... on Collection {
              id
              handle
              title
            }
            ... on Product {
              id
              handle
              title
            }
            ... on Metaobject {
              id
              handle
              displayName
              type
            }
          }
        }
      }
    }
  }
}
```

### Nested Query (With Full Nested Data)
For FAQ sections and comparison tables that contain nested metaobjects:

```graphql
query getMetaobjectFull($id: ID!) {
  metaobject(id: $id) {
    id
    handle
    displayName
    type
    fields {
      key
      value
      type
      reference {
        ... on Metaobject {
          id
          handle
          displayName
          type
          fields {
            key
            value
            type
          }
        }
      }
      references(first: 100) {
        edges {
          node {
            ... on Metaobject {
              id
              handle
              displayName
              type
              fields {
                key
                value
                type
              }
            }
          }
        }
      }
    }
  }
}
```

## Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | ID! | Yes | Metaobject GID (e.g., `gid://shopify/Metaobject/123456`) |

## Required Scopes
- `read_metaobjects`
- `read_products` (for product/collection references)
- `read_files` (for image references)

## Example

### Basic Fetch
```bash
python3 cms/get_metaobject.py --id "gid://shopify/Metaobject/123456"
```

### Pretty Output
```bash
python3 cms/get_metaobject.py \
  --id "gid://shopify/Metaobject/123456" \
  --output-format pretty
```

### Simplified Fields Only
```bash
python3 cms/get_metaobject.py \
  --id "gid://shopify/Metaobject/123456" \
  --fields-only
```

### With Nested Data (FAQ Sections, Comparison Tables)
```bash
python3 cms/get_metaobject.py \
  --id "gid://shopify/Metaobject/123456" \
  --include-nested
```

## Response Format

### Standard Response
```json
{
  "success": true,
  "metaobject": {
    "id": "gid://shopify/Metaobject/123456",
    "handle": "category-section-1",
    "displayName": "Featured Products",
    "type": "category_section",
    "fields": {
      "title": {
        "value": "Featured Products",
        "type": "single_line_text_field"
      },
      "hero_image": {
        "value": "gid://shopify/MediaImage/789012",
        "type": "file_reference",
        "reference": {
          "type": "MediaImage",
          "id": "gid://shopify/MediaImage/789012",
          "url": "https://cdn.shopify.com/...",
          "altText": "Hero image",
          "width": 2048,
          "height": 1024
        }
      },
      "collection": {
        "value": "gid://shopify/Collection/345678",
        "type": "collection_reference",
        "reference": {
          "type": "Collection",
          "id": "gid://shopify/Collection/345678",
          "handle": "best-sellers",
          "title": "Best Sellers"
        }
      }
    },
    "createdAt": "2025-01-01T12:00:00Z",
    "updatedAt": "2025-01-06T12:00:00Z"
  }
}
```

### Nested Response (--include-nested)
```json
{
  "success": true,
  "metaobject": {
    "id": "gid://shopify/Metaobject/123456",
    "handle": "faq-section-1",
    "displayName": "Frequently Asked Questions",
    "type": "faq_section",
    "fields": {
      "title": {
        "value": "FAQ",
        "type": "single_line_text_field"
      },
      "questions": {
        "value": "[\"gid://shopify/Metaobject/111\", \"gid://shopify/Metaobject/222\"]",
        "type": "list.metaobject_reference",
        "references": [
          {
            "id": "gid://shopify/Metaobject/111",
            "handle": "faq-item-1",
            "displayName": "Shipping FAQ",
            "metaobject_type": "faq_item",
            "type": "Metaobject",
            "fields": {
              "question": {
                "value": "How long does shipping take?",
                "type": "single_line_text_field"
              },
              "answer": {
                "value": "2-5 business days",
                "type": "multi_line_text_field"
              }
            }
          }
        ]
      }
    }
  }
}
```

### Fields Only Response (--fields-only)
```json
{
  "title": {
    "value": "Featured Products",
    "type": "single_line_text_field"
  },
  "max_products": {
    "value": "8",
    "type": "number_integer"
  }
}
```

## Notes
- **GID Format**: Must provide full metaobject GID (`gid://shopify/Metaobject/ID`)
- **Reference Expansion**: The query automatically expands references to show full details
- **List References**: Uses `references(first: 10)` for list reference fields (increase limit if needed)
- **Nested Data**: Use `--include-nested` flag for FAQ sections and comparison tables to fetch full nested items
- **Performance**: Standard query fetches first 10 list items; nested query fetches up to 100
- **Error Handling**: Returns clear error if metaobject not found or invalid GID provided
- **Type Detection**: Automatically detects field types and formats responses accordingly
