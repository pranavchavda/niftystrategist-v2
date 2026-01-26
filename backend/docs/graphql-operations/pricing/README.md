# Pricing GraphQL Operations

Validated GraphQL queries and mutations for product pricing management in Shopify.

## Overview

All GraphQL operations in this directory have been validated against the Shopify Admin API schema using the `@shopify/dev-mcp` validation tools. Each operation includes:

- Validated GraphQL code (✅ passed schema validation)
- Required API scopes
- Variable definitions with types
- Usage examples with the Python scripts
- Response structure documentation
- Implementation notes and best practices

## Operations Index

### [update-variant.md](./update-variant.md)
**Script**: `update_pricing.py`

Update price, compare-at price, and cost for a single product variant.

**Operations**:
- `productVariantsBulkUpdate` - Update variant pricing
- `productVariant` - Get inventory item for cost updates
- `inventoryItemUpdate` - Update inventory cost

**Use Cases**:
- Single variant price adjustments
- Set/clear sale prices (compare-at)
- Update cost of goods sold (COGS)

---

### [bulk-update.md](./bulk-update.md)
**Script**: `bulk_price_update.py`

Bulk update prices for multiple variants from CSV files.

**Operations**:
- `productVariant` - Get product ID from variant
- `productVariantsBulkUpdate` - Bulk update variant prices

**Use Cases**:
- Import price updates from CSV
- Seasonal pricing adjustments
- Mass price changes across catalog

---

### [sales.md](./sales.md)
**Script**: `manage_map_sales.py`

Manage MAP (Minimum Advertised Price) sales with automatic end dates.

**Operations**:
- `products` - Search by SKU
- `productUpdate` - Set sale end date metafield
- `productVariantsBulkUpdate` - Apply/revert sale pricing

**Use Cases**:
- Apply vendor MAP sales (Breville, etc.)
- Set automatic price reversion dates
- Calendar-based sale management

---

### [costs.md](./costs.md)
**Script**: `update_costs_by_sku.py`

Update inventory costs by SKU (single or bulk from CSV).

**Operations**:
- `productVariants` - Search by SKU
- `inventoryItemUpdate` - Update unit cost

**Use Cases**:
- Update COGS for margin tracking
- Import costs from suppliers
- Bulk cost updates from purchase orders

---

### [sale-dates.md](./sale-dates.md)
**Script**: `manage_sale_end_dates.py`

Manage `inventory.ShappifySaleEndDate` metafields for automatic price reversion.

**Operations**:
- `products` - Search with metafield filtering
- `metafieldsSet` - Set sale end date
- `product` - Get metafield ID
- `metafieldsDelete` - Clear sale end date

**Use Cases**:
- Set scheduled sale end dates
- Clear sale dates manually
- List products currently on sale

---

## Common Patterns

### Price Updates
All price operations use `productVariantsBulkUpdate` mutation:
```graphql
mutation updateVariants($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants { id price compareAtPrice }
    userErrors { field message }
  }
}
```

### Cost Updates
Cost updates use `inventoryItemUpdate` on the inventory item:
```graphql
mutation updateCost($id: ID!, $input: InventoryItemInput!) {
  inventoryItemUpdate(id: $id, input: $input) {
    inventoryItem {
      unitCost { amount currencyCode }
    }
    userErrors { field message }
  }
}
```

### Search by SKU
SKU searches use the `query` parameter:
```graphql
query searchBySku($query: String!) {
  products(first: 5, query: $query) {
    edges {
      node {
        variants(first: 10) {
          edges {
            node { sku price compareAtPrice }
          }
        }
      }
    }
  }
}
```

Query string format: `sku:PRODUCT-SKU status:active`

### Metafield Management
Sale end dates use metafields in the `inventory` namespace:
```graphql
mutation setProductMetafield($input: MetafieldsSetInput!) {
  metafieldsSet(metafields: [$input]) {
    metafields { id value }
    userErrors { field message }
  }
}
```

Namespace: `inventory`, Key: `ShappifySaleEndDate`, Type: `single_line_text_field`

## Required API Scopes

| Operation | Scopes |
|-----------|--------|
| Read Products | `read_products` |
| Update Products | `write_products`, `read_products` |
| Read Inventory | `read_inventory` |
| Update Inventory | `write_inventory`, `read_inventory` |
| Metafields | Uses product/inventory permissions |

## Validation Details

All GraphQL operations were validated on **2024-12-03** using:
- Tool: `@shopify/dev-mcp` Shopify MCP server
- API: Admin GraphQL API (latest version)
- Validation: Schema compliance, field existence, type checking
- Status: ✅ All operations passed validation

## Script Locations

All Python scripts are located in:
```
backend/bash-tools/pricing/
```

Scripts use the `ShopifyClient` base class from `../base.py` for API communication.

## Usage Notes

1. **ID Format**: All product/variant IDs must be in GID format:
   - Product: `gid://shopify/Product/123`
   - Variant: `gid://shopify/ProductVariant/456`
   - InventoryItem: `gid://shopify/InventoryItem/789`

2. **Price Format**: Prices are strings, not numbers:
   - ✅ `"29.99"`
   - ❌ `29.99`

3. **Error Handling**: All mutations return `userErrors` array:
   ```json
   {
     "userErrors": [
       {"field": "price", "message": "must be greater than 0"}
     ]
   }
   ```

4. **Rate Limiting**: Scripts include delays (0.25s) between bulk operations

5. **Dry Run**: All scripts support `--dry-run` flag for preview mode

## Related Documentation

- [Shopify Admin API - Products](https://shopify.dev/docs/api/admin-graphql/latest/objects/Product)
- [Shopify Admin API - Variants](https://shopify.dev/docs/api/admin-graphql/latest/objects/ProductVariant)
- [Shopify Admin API - Metafields](https://shopify.dev/docs/api/admin-graphql/latest/objects/Metafield)
- [Search Syntax](https://shopify.dev/docs/api/usage/search-syntax)

---

**Last Updated**: 2024-12-03
**Validation Tool**: Shopify MCP (@shopify/dev-mcp)
**API Version**: Admin GraphQL API (latest)
