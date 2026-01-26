# Bulk Tag Management (Parallel)

High-performance parallel tag management for multiple products simultaneously.

## Use Cases
- Adding tags to 100+ products at once
- Seasonal tag updates across entire collections
- Bulk tag cleanup operations
- Migration or reorganization of product categorization
- Event-based tagging (sales, promotions)

## GraphQL Operations

This uses the same `tagsAdd` and `tagsRemove` mutations but executes them in parallel with worker pools:

### Add Tags (Parallel Execution)

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

### Remove Tags (Parallel Execution)

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

### Product Search (For ID Resolution)

```graphql
query searchProduct($query: String!) {
  products(first: 1, query: $query) {
    edges {
      node {
        id
        title
      }
    }
  }
}
```

## Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | ID! | Yes | Product GID (e.g., "gid://shopify/Product/1234567890") |
| `tags` | [String!]! | Yes | Array of tag strings to add/remove |
| `query` | String! | Yes (search only) | Search query to find products |

## Performance Features

- **Worker Pools**: Configurable parallel workers (default: 10)
- **Batch Processing**: Processes products in batches (default: 50)
- **Rate Limiting**: Small delays between batches to respect API limits
- **Timeout Handling**: 30-second timeout per operation
- **Progress Tracking**: Real-time updates on success/failure
- **Error Recovery**: Continues processing even if individual products fail

## Example

```bash
# Add tags to multiple products (10 workers, 50 per batch)
python backend/bash-tools/tags/manage_tags_parallel.py \
  --action add \
  --products "prod1,prod2,prod3" \
  --tags "sale,featured"

# Remove tags from products in a file (high performance)
python backend/bash-tools/tags/manage_tags_parallel.py \
  --action remove \
  --file products.txt \
  --tags "old-tag" \
  --workers 20 \
  --batch 100

# Process 1000+ products
python backend/bash-tools/tags/manage_tags_parallel.py \
  --action add \
  --file large_product_list.txt \
  --tags "new-collection,winter-2024"
```

## Example Output

```
🚀 Starting parallel tag management
📊 Products: 500
⚡ Workers: 10
📦 Batch size: 50
🏷️  Action: add
🏷️  Tags: sale, featured
--------------------------------------------------
🔍 Resolving 500 product identifiers...
✅ Resolved 498 products (2 unresolved)
🔄 Processing batch 1 (50 products)...
🔄 Processing batch 2 (50 products)...
...

==================================================
📊 PROCESSING SUMMARY
==================================================
✅ Successful: 495
❌ Failed: 3
❓ Unresolved: 2
⏱️  Time: 45.23 seconds
📈 Rate: 11.02 products/second
```

## Input File Format

Product identifiers (one per line):
```
gid://shopify/Product/1234567890
breville-barista-express
EC685M
7896543210
delonghi-dedica
```

## Notes
- **Performance**: Processes ~10-15 products/second with default settings
- **Scalability**: Can handle 1000+ products efficiently
- **ID Resolution**: Supports product IDs, handles, SKUs, and titles
- **Error Handling**: Failed products don't stop the batch
- **API Limits**: Automatic rate limiting to stay within Shopify's API limits
- **Scope Required**: `write_products` (add/remove), `read_products` (validation)
- **Timeout**: 30 seconds per product operation
- **Unresolved Products**: Products not found are skipped with warning
