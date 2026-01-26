# List Metaobjects

Lists all metaobjects of a specific type with pagination support. Used by CMS UI for dropdown pickers.

## Use Cases
- Populate metaobject picker dropdowns in CMS interface
- List all category sections for selection
- Fetch all FAQ items, educational blocks, or comparison features
- Browse metaobjects by type for management
- Export metaobject data for analysis

## GraphQL

```graphql
query listMetaobjects($type: String!, $cursor: String) {
  metaobjects(first: 50, type: $type, after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        handle
        displayName
        fields {
          key
          value
          type
          reference {
            ... on MediaImage {
              image {
                url
                altText
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
| `type` | String! | Yes | Metaobject type to filter by (e.g., `category_section`, `faq_item`) |
| `cursor` | String | No | Pagination cursor for fetching next page |

## Required Scopes
- `read_metaobjects`
- `read_files` (if querying image references)

## Example

### List Category Sections
```bash
python3 cms/list_metaobjects.py --type category_section
```

### List FAQ Items
```bash
python3 cms/list_metaobjects.py --type faq_item
```

### List Educational Blocks
```bash
python3 cms/list_metaobjects.py --type educational_block
```

### List FAQ Sections
```bash
python3 cms/list_metaobjects.py --type faq_section
```

### List Comparison Tables
```bash
python3 cms/list_metaobjects.py --type comparison_table
```

## Response Format

### Category Section Response
```json
{
  "metaobjects": [
    {
      "id": "gid://shopify/Metaobject/123456",
      "handle": "category-section-1",
      "title": "Featured Products",
      "description": "Discover our best sellers",
      "collectionHandle": "best-sellers"
    }
  ],
  "count": 1
}
```

### Educational Block Response
```json
{
  "metaobjects": [
    {
      "id": "gid://shopify/Metaobject/789012",
      "handle": "educational-block-1",
      "title": "How to Brew Espresso",
      "contentType": "video",
      "imageUrl": "https://cdn.shopify.com/..."
    }
  ],
  "count": 1
}
```

### FAQ Section Response
```json
{
  "metaobjects": [
    {
      "id": "gid://shopify/Metaobject/345678",
      "handle": "faq-section-1",
      "title": "Frequently Asked Questions",
      "questionCount": 12
    }
  ],
  "count": 1
}
```

### Comparison Table Response
```json
{
  "metaobjects": [
    {
      "id": "gid://shopify/Metaobject/567890",
      "handle": "comparison-table-1",
      "title": "Espresso Machine Comparison",
      "productCount": 4,
      "featureCount": 8
    }
  ],
  "count": 1
}
```

### Generic Response (Unknown Types)
```json
{
  "metaobjects": [
    {
      "id": "gid://shopify/Metaobject/111222",
      "handle": "custom-type-1",
      "title": "Custom Metaobject"
    }
  ],
  "count": 1
}
```

## Pagination

The script automatically handles pagination and fetches all results:

1. First request fetches up to 50 items
2. If `hasNextPage` is true, script continues with `endCursor`
3. Process repeats until all items are fetched
4. Final response contains all items across all pages

## Response Formatting by Type

The script formats output differently based on metaobject type:

### `category_section`
- `id`, `handle`, `title`, `description`, `collectionHandle`

### `educational_block`
- `id`, `handle`, `title`, `contentType`, `imageUrl`

### `faq_section`
- `id`, `handle`, `title`, `questionCount` (parsed from `questions` JSON field)

### `comparison_table`
- `id`, `handle`, `title`, `productCount`, `featureCount` (parsed from JSON fields)

### Unknown types
- `id`, `handle`, `title` (falls back to `displayName`)

## Notes
- **Automatic Pagination**: Script handles pagination internally and returns all results
- **Type-Specific Formatting**: Response structure adapts based on metaobject type
- **Performance**: Fetches 50 items per page (GraphQL limit)
- **JSON Parsing**: Automatically parses list reference fields stored as JSON strings
- **CMS Integration**: Designed for use by CMS metaobject picker components
- **Image URLs**: Extracts image URLs from file_reference fields for preview
- **Count Calculation**: Returns total count of all fetched metaobjects
- **Error Handling**: Gracefully handles missing or malformed field data
