# Remove Tags from Product

Remove one or more tags from a Shopify product.

## Use Cases
- Removing outdated promotional tags
- Cleaning up unused categorization tags
- Removing seasonal or event-specific tags
- Bulk tag cleanup operations

## GraphQL

```graphql
mutation removeTags($id: ID!, $tags: [String!]!) {
  tagsRemove(id: $id, tags: $tags) {
    node {
      ... on Product {
        id
        title
        tags
      }
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
| `id` | ID! | Yes | Product GID (e.g., "gid://shopify/Product/1234567890") |
| `tags` | [String!]! | Yes | Array of tag strings to remove |

## Response Fields

- `node.id` - Product GID
- `node.title` - Product title
- `node.tags` - Complete array of remaining tags after removal
- `userErrors` - Array of errors if operation fails

## Example

```bash
# Remove single tag
python backend/bash-tools/tags/manage_tags.py --action remove --product "breville-barista-express" --tags "clearance"

# Remove multiple tags
python backend/bash-tools/tags/manage_tags.py --action remove --product "1234567890" --tags "old-tag,unused-tag,deprecated"

# Bulk removal with parallel processor
python backend/bash-tools/tags/manage_tags_parallel.py --action remove --file products.txt --tags "holiday-2023"
```

## Notes
- Tags are case-sensitive (must match exactly)
- Removing non-existent tags will not cause errors
- Operation silently succeeds if tag doesn't exist
- Operation requires `write_products` scope
- Validation requires `read_products` scope
