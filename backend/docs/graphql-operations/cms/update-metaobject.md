# Update Metaobject

Updates existing metaobject fields by ID. Only modifies the fields you provide - other fields remain unchanged.

## Use Cases
- Update category section details (title, description, max products)
- Modify educational block content or CTA
- Update FAQ item questions/answers
- Change comparison feature definitions
- Patch any metaobject field without replacing entire object

## GraphQL

```graphql
mutation updateMetaobject($id: ID!, $metaobject: MetaobjectUpdateInput!) {
  metaobjectUpdate(id: $id, metaobject: $metaobject) {
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
| `id` | ID! | Yes | Metaobject GID (e.g., `gid://shopify/Metaobject/123456`) |
| `metaobject.fields` | [MetaobjectFieldInput!]! | Yes | Array of field objects with `key` and `value` to update |

### Field Input Structure

Each field in the `fields` array:
- `key`: Field identifier (must match metaobject definition)
- `value`: New field value (string, number, or GID for references)

## Required Scopes
- `write_metaobjects`
- `read_metaobjects`
- `read_products` (if querying collection/product references)
- `read_files` (if querying file references)

## Example

### Update Category Section
```bash
python3 cms/update_metaobject.py \
  --id "gid://shopify/Metaobject/123456" \
  --type category_section \
  --title "New Title" \
  --max-products 12
```

### Update FAQ Item
```bash
python3 cms/update_metaobject.py \
  --id "gid://shopify/Metaobject/789012" \
  --type faq_item \
  --answer "Updated answer with more details." \
  --priority 5
```

### Update Educational Block CTA
```bash
python3 cms/update_metaobject.py \
  --id "gid://shopify/Metaobject/345678" \
  --type educational_block \
  --cta-text "Watch Now" \
  --cta-link "/pages/video-guide"
```

### Update Collection Reference
```bash
python3 cms/update_metaobject.py \
  --id "gid://shopify/Metaobject/567890" \
  --type category_section \
  --collection-handle "new-arrivals"
```

## Response Format

```json
{
  "success": true,
  "metaobject": {
    "id": "gid://shopify/Metaobject/123456",
    "handle": "category-section-1",
    "displayName": "New Title",
    "type": "category_section",
    "fields": {
      "title": "New Title",
      "subtitle": "Discover our best sellers",
      "theme": "light",
      "max_products": "12"
    },
    "updatedAt": "2025-01-06T12:30:00Z"
  }
}
```

## Notes
- **Partial Updates**: Only the fields you provide are updated - omitted fields remain unchanged
- **GID Required**: Must provide full metaobject GID in the format `gid://shopify/Metaobject/ID`
- **Type Validation**: The `--type` parameter is used to determine which fields are valid (must match the actual metaobject type)
- **Reference Resolution**: Collection handles are automatically resolved to GIDs when using `--collection-handle`
- **Numeric Values**: Numbers are converted to strings for GraphQL
- **Error Handling**: Always check `userErrors` in response for validation issues
- **Idempotent**: Running the same update multiple times produces the same result
