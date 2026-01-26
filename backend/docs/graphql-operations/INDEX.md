# Shopify GraphQL Operations Reference

This documentation provides GraphQL queries and mutations for all Shopify Admin API operations. Use these with the `graphql_query.py` and `graphql_mutation.py` tools.

## How to Use

### Query Tool
```bash
python core/graphql_query.py 'QUERY_HERE' --variables '{"var": "value"}'
```

### Mutation Tool
```bash
python core/graphql_mutation.py 'MUTATION_HERE' --variables '{"var": "value"}'
```

## ID Resolution Patterns

Many operations require Shopify GID format. Here are common patterns:

| Type | GID Format | Example |
|------|-----------|---------|
| Product | `gid://shopify/Product/{id}` | `gid://shopify/Product/1234567890` |
| ProductVariant | `gid://shopify/ProductVariant/{id}` | `gid://shopify/ProductVariant/9876543210` |
| Collection | `gid://shopify/Collection/{id}` | `gid://shopify/Collection/555555555` |
| InventoryItem | `gid://shopify/InventoryItem/{id}` | `gid://shopify/InventoryItem/111111111` |
| Metaobject | `gid://shopify/Metaobject/{id}` | `gid://shopify/Metaobject/222222222` |
| File | `gid://shopify/MediaImage/{id}` | `gid://shopify/MediaImage/333333333` |

### Finding Product ID from Handle/SKU
```graphql
# By handle
query { productByHandle(handle: "product-handle") { id } }

# By SKU (search)
query { products(first: 1, query: "sku:ABC123") { edges { node { id } } } }
```

## Operation Categories

### Products
- [Search Products](products/search.md) - Find products by various criteria
- [Get Product](products/get.md) - Get full product details
- [Create Product](products/create.md) - Create new products
- [Update Product](products/update.md) - Update product fields
- [Delete Product Images](products/delete-images.md) - Remove product images
- [Upload Product Image](products/upload-image.md) - Add images via staged upload
- [Duplicate Product](products/duplicate.md) - Clone existing products
- [Manage Status](products/status.md) - Change product status (active/draft/archived)

### Pricing
- [Update Variant Pricing](pricing/update-variant.md) - Update price, compare-at, cost
- [Bulk Price Update](pricing/bulk-update.md) - Update multiple variants
- [Manage Sales](pricing/sales.md) - Apply/remove sale pricing

### Tags
- [Add Tags](tags/add.md) - Add tags to products
- [Remove Tags](tags/remove.md) - Remove tags from products
- [Get Tags](tags/get.md) - List product tags
- [Bulk Tag Management](tags/bulk.md) - Tag multiple products

### CMS (Metaobjects)
- [Create Metaobject](cms/create-metaobject.md) - Create new metaobject instances
- [Update Metaobject](cms/update-metaobject.md) - Update metaobject fields
- [Delete Metaobject](cms/delete-metaobject.md) - Remove metaobjects
- [List Metaobjects](cms/list-metaobjects.md) - Query metaobjects by type
- [Get Metaobject](cms/get-metaobject.md) - Get specific metaobject
- [Upload Files](cms/upload-files.md) - Upload images/files for CMS

### Analytics
- [ShopifyQL Queries](analytics/shopifyql.md) - Run analytics queries
- [Sales Reports](analytics/sales.md) - Revenue and order analytics
- [Inventory Reports](analytics/inventory.md) - Stock level analytics

### Inventory
- [Update Inventory](inventory/update.md) - Adjust inventory quantities
- [Inventory Policy](inventory/policy.md) - Set tracking policies

### Publishing
- [Publish Product](publishing/publish.md) - Publish to sales channels
- [Unpublish Product](publishing/unpublish.md) - Remove from channels

### Utilities
- [URL Redirects](utilities/redirects.md) - Manage URL redirects for SEO
- [Tax Management](utilities/taxes.md) - Bulk enable/disable taxes by tag
- [Copy Product](utilities/copy-product.md) - Copy products between stores

## Common Patterns

### Pagination
```graphql
query ($cursor: String) {
  products(first: 50, after: $cursor) {
    edges { node { id title } }
    pageInfo { hasNextPage endCursor }
  }
}
```

### Error Handling
All mutations return `userErrors`:
```graphql
userErrors {
  field
  message
}
```
Always check this array - empty means success.

### Bulk Operations
For operations on many items, use bulk mutations when available:
- `productVariantsBulkUpdate` - Update many variants
- `tagsAdd` / `tagsRemove` - Works on multiple tags
- `bulkOperationRunMutation` - For very large operations
