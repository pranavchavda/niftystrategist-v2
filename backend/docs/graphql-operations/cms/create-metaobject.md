# Create Metaobject

Creates a new metaobject of a specified type with custom fields.

## Use Cases
- Create category sections for landing pages
- Create educational content blocks
- Create FAQ sections and individual FAQ items
- Create comparison tables and feature definitions
- Any custom metaobject type defined in your Shopify store

## GraphQL

```graphql
mutation createMetaobject($metaobject: MetaobjectCreateInput!) {
  metaobjectCreate(metaobject: $metaobject) {
    metaobject {
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
            }
          }
          ... on Collection {
            id
            handle
            title
          }
        }
      }
      updatedAt
    }
    userErrors {
      field
      message
    }
  }
}
```

## Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `metaobject.type` | String | Yes | Metaobject type (e.g., `category_section`, `faq_item`) |
| `metaobject.fields` | [MetaobjectFieldInput!]! | Yes | Array of field objects with `key` and `value` |

### Field Input Structure

Each field in the `fields` array:
- `key`: Field identifier (must match metaobject definition)
- `value`: Field value (string, number, or GID for references)

## Required Scopes
- `write_metaobjects`
- `read_metaobjects`
- `read_products` (if querying collection/product references)
- `read_files` (if querying file references)

## Example

### Category Section
```bash
python3 cms/create_metaobject.py --type category_section \
  --title "Featured Products" \
  --subtitle "Discover our best sellers" \
  --theme "light" \
  --collection-handle "best-sellers" \
  --max-products 8 \
  --view-all-link "/collections/best-sellers"
```

### FAQ Item
```bash
python3 cms/create_metaobject.py --type faq_item \
  --question "How long does shipping take?" \
  --answer "2-5 business days for standard shipping." \
  --priority 1
```

### Educational Block
```bash
python3 cms/create_metaobject.py --type educational_block \
  --title "How to Brew Perfect Espresso" \
  --content "Step-by-step brewing guide..." \
  --position 1 \
  --video-embed "https://youtube.com/embed/..." \
  --cta-text "Learn More" \
  --cta-link "/pages/brewing-guide"
```

## Response Format

```json
{
  "success": true,
  "metaobject": {
    "id": "gid://shopify/Metaobject/123456789",
    "handle": "category-section-1",
    "displayName": "Featured Products",
    "type": "category_section",
    "fields": {
      "title": "Featured Products",
      "subtitle": "Discover our best sellers",
      "theme": "light",
      "max_products": "8"
    },
    "updatedAt": "2025-01-06T12:00:00Z"
  }
}
```

## Notes
- The metaobject type must be defined in your Shopify store's metaobject definitions
- Field keys must exactly match the definition (case-sensitive)
- Reference fields (collections, products, files) require GID values
- The script automatically resolves collection handles to GIDs when using `--collection-handle`
- Numeric values are passed as strings in GraphQL
- Always check `userErrors` in the response for validation issues
