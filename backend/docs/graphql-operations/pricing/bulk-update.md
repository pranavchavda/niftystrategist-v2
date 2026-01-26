# Bulk Price Update from CSV

Update prices for multiple product variants from a CSV file, grouped by product for efficient bulk operations.

## Use Cases
- Apply price changes to multiple variants at once
- Import price updates from external systems
- Seasonal pricing adjustments across product catalog
- Bulk sale price application with compare-at prices

## Operations

### 1. Get Product ID from Variant

**Validated**: ✅ Passed Shopify MCP validation

```graphql
query getProductId($id: ID!) {
  productVariant(id: $id) {
    product {
      id
    }
  }
}
```

**Required Scopes**: `read_products`

**Variables**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| id | ID! | Yes | Variant GID |

**Purpose**: Used to group variants by product before bulk updates.

### 2. Bulk Update Variant Prices

**Validated**: ✅ Passed Shopify MCP validation

```graphql
mutation updateVariants($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
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
| variants[].price | String | Yes | New price |
| variants[].compareAtPrice | String | No | Compare-at price (optional) |

**Example**

```bash
# Preview changes (dry run)
python bulk_price_update.py prices.csv --dry-run

# Apply updates
python bulk_price_update.py prices.csv
```

**Variables Example**:
```json
{
  "productId": "gid://shopify/Product/123",
  "variants": [
    {
      "id": "gid://shopify/ProductVariant/456",
      "price": "99.99",
      "compareAtPrice": "149.99"
    },
    {
      "id": "gid://shopify/ProductVariant/789",
      "price": "119.99",
      "compareAtPrice": "169.99"
    }
  ]
}
```

## CSV Format

**Required Columns**:
- `Variant ID`: Variant GID (e.g., `gid://shopify/ProductVariant/123`)
- `Price`: New price (e.g., `99.99`)

**Optional Columns**:
- `Compare At Price`: Original/sale price
- `Product Title`: For display purposes
- `SKU`: For reference

**Sample CSV**:
```csv
Product ID,Product Title,Variant ID,SKU,Price,Compare At Price
gid://shopify/Product/123,Product Name,gid://shopify/ProductVariant/456,SKU123,99.99,149.99
gid://shopify/Product/789,Another Product,gid://shopify/ProductVariant/012,SKU456,49.99,
```

Generate a sample CSV:
```bash
python bulk_price_update.py --sample
```

## Response Structure

**Update Response**:
- `productVariants[].id`: Updated variant GID
- `productVariants[].price`: New price
- `productVariants[].compareAtPrice`: Compare-at price (or null)
- `userErrors[]`: Validation errors if any

## Processing Strategy

The script optimizes updates by:

1. **Grouping by Product**: Variants are grouped by product ID
2. **Bulk Updates**: All variants for a product are updated in one mutation
3. **Progress Display**: Shows `[N/Total]` progress for each variant
4. **Error Handling**: Continues processing even if some updates fail
5. **Summary Report**: Shows total success/failure counts
6. **Log File**: Creates timestamped log file with results

## Notes
- The script automatically fetches product IDs for each variant
- Updates are grouped by product for better API efficiency
- Use `--dry-run` to preview changes without applying them
- Rate limiting: 0.25s delay between product updates
- Creates log file with timestamp: `price_update_log_YYYYMMDD_HHMMSS.txt`
- Progress indicator: `[current/total]` for each variant
- Handles CSV files with UTF-8 encoding
- Validates required columns before processing
