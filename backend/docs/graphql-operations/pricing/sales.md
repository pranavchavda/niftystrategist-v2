# MAP Sales Management

Manage Minimum Advertised Price (MAP) sales for vendors like Breville, applying sale prices and setting automatic revert dates using metafields.

## Use Cases
- Apply MAP sales based on vendor-approved calendar windows
- Set automatic sale end dates for price reversion
- Search and update products by SKU during sale periods
- Revert prices back to regular after sale ends
- Track which products are on MAP sale with end dates

## Operations

### 1. Search Products by SKU

**Validated**: ✅ Passed Shopify MCP validation

```graphql
query searchBySku($query: String!) {
  products(first: 5, query: $query) {
    edges {
      node {
        id
        title
        handle
        tags
        status
        variants(first: 10) {
          edges {
            node {
              id
              title
              sku
              price
              compareAtPrice
            }
          }
        }
      }
    }
  }
}
```

**Required Scopes**: `read_products`

**Variables**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| query | String! | Yes | Shopify search query (e.g., `sku:BES870XL status:active`) |

**Example Query Strings**:
- `sku:BES870XL status:active` - Search by SKU for active products
- `tag:BREMAP status:active` - Find all active MAP products
- `sku:* tag:BREMAP` - All MAP products with any SKU

### 2. Update Product Metafield (Sale End Date)

**Validated**: ✅ Passed Shopify MCP validation

```graphql
mutation productUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
    }
    userErrors {
      field
      message
    }
  }
}
```

**Required Scopes**: `write_products`, `read_products`

**Variables**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| input.id | ID! | Yes | Product GID |
| input.metafields | [MetafieldInput!] | Yes | Array of metafields to set |
| metafields[].namespace | String! | Yes | `"inventory"` |
| metafields[].key | String! | Yes | `"ShappifySaleEndDate"` |
| metafields[].value | String! | Yes | ISO 8601 datetime (e.g., `"2025-07-24T23:59:59Z"`) |
| metafields[].type | String! | Yes | `"single_line_text_field"` |

**Example - Set Sale End Date**:
```json
{
  "input": {
    "id": "gid://shopify/Product/123",
    "metafields": [{
      "namespace": "inventory",
      "key": "ShappifySaleEndDate",
      "value": "2025-07-24T23:59:59Z",
      "type": "single_line_text_field"
    }]
  }
}
```

**Example - Clear Sale End Date**:
```json
{
  "input": {
    "id": "gid://shopify/Product/123",
    "metafields": [{
      "namespace": "inventory",
      "key": "ShappifySaleEndDate",
      "value": "",
      "type": "single_line_text_field"
    }]
  }
}
```

### 3. Update Variant Pricing (Apply/Revert Sale)

**Validated**: ✅ Passed Shopify MCP validation

```graphql
mutation updateVariantPrice($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      id
      price
      compareAtPrice
    }
    userErrors {
      field
      message
    }
  }
}
```

**Required Scopes**: `write_products`, `read_products`

**Variables**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| productId | ID! | Yes | Product GID |
| variants | [ProductVariantsBulkInput!]! | Yes | Array of variant updates |
| variants[].id | ID! | Yes | Variant GID |
| variants[].price | String! | Yes | Sale price (apply) or regular price (revert) |
| variants[].compareAtPrice | String | No | Regular price (apply) or `null` (revert) |

**Example - Apply Sale**:
```json
{
  "productId": "gid://shopify/Product/123",
  "variants": [{
    "id": "gid://shopify/ProductVariant/456",
    "price": "299.99",
    "compareAtPrice": "349.99"
  }]
}
```

**Example - Revert to Regular Price**:
```json
{
  "productId": "gid://shopify/Product/123",
  "variants": [{
    "id": "gid://shopify/ProductVariant/456",
    "price": "349.99",
    "compareAtPrice": null
  }]
}
```

## Usage Examples

### Check Active Sales
```bash
python manage_map_sales.py check
python manage_map_sales.py check --date 2025-07-15
```

### Apply Sales (with dry run)
```bash
# Preview changes
python manage_map_sales.py --dry-run apply

# Apply sales and set end dates
python manage_map_sales.py apply
```

### Revert Sales
```bash
# Revert specific date range
python manage_map_sales.py revert "11 Jul - 17 Jul"

# Dry run
python manage_map_sales.py --dry-run revert "11 Jul - 17 Jul"
```

### Calendar Summary
```bash
python manage_map_sales.py summary
```

## Response Structure

**Search Response**:
- `products.edges[].node.id`: Product GID
- `products.edges[].node.tags`: Array of tags (check for "BREMAP")
- `products.edges[].node.variants[].price`: Current price
- `products.edges[].node.variants[].compareAtPrice`: Compare-at price (null if not on sale)

**Update Response**:
- `product.id`: Product GID
- `userErrors[]`: Validation errors if any

**Pricing Response**:
- `productVariants[].price`: Updated price
- `productVariants[].compareAtPrice`: Updated compare-at price
- `userErrors[]`: Validation errors if any

## MAP Sales Workflow

1. **Calendar Parsing**: Read sale dates from markdown calendar file
2. **Active Sale Detection**: Check if today falls within any sale period
3. **SKU Search**: Find products by SKU from calendar
4. **Tag Validation**: Verify product has "BREMAP" tag
5. **Price Application**:
   - Set `price` to sale price
   - Set `compareAtPrice` to regular price
   - Set `ShappifySaleEndDate` metafield
6. **Reversion**:
   - Set `price` back to regular price
   - Clear `compareAtPrice` (set to null)
   - Clear `ShappifySaleEndDate` metafield

## Notes
- Calendar file default: `resources/breville_espresso_sales_2025_enhanced.md`
- Sale end dates are stored in `inventory.ShappifySaleEndDate` metafield
- Dates are converted to UTC and formatted as ISO 8601
- Script skips products without "BREMAP" tag
- Shows summary: updated, already on sale, not found, not MAP
- Supports dry-run mode to preview changes
- Automatically groups products by unique product IDs for metafield updates
- Sale end dates trigger automatic price reversion via Shopify automation
