# Add Tags to Product

Add one or more tags to a Shopify product.

## Use Cases
- Categorizing products with new labels
- Adding promotional tags (e.g., "sale", "featured")
- Applying collection or filter tags
- Bulk tagging products for organization

## GraphQL

```graphql
mutation addTags($id: ID!, $tags: [String!]!) {
  tagsAdd(id: $id, tags: $tags) {
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
| `tags` | [String!]! | Yes | Array of tag strings to add |

## Response Fields

- `node.id` - Product GID
- `node.title` - Product title
- `node.tags` - Complete array of all tags after addition
- `userErrors` - Array of errors if operation fails

## Example

```bash
# Single tag
python backend/bash-tools/tags/manage_tags.py --action add --product "breville-barista-express" --tags "bestseller"

# Multiple tags
python backend/bash-tools/tags/manage_tags.py --action add --product "1234567890" --tags "sale,featured,holiday-2024"

# Using parallel processor for bulk operations
python backend/bash-tools/tags/manage_tags_parallel.py --action add --file products.txt --tags "new-collection"
```

## Notes
- Tags are case-sensitive
- Duplicate tags are automatically prevented by Shopify
- Adding existing tags will not cause errors
- Maximum 250 tags per product
- Tags cannot contain commas or special characters
- Operation requires `write_products` scope
- Validation requires `read_products` scope
