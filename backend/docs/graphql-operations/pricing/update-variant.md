# Update Product Variant Pricing

Update price, compare-at price, and cost for a single product variant.

## Use Cases
- Adjust regular selling price for a variant
- Set or clear compare-at (original) price for sale displays
- Update inventory cost for profit margin tracking
- Single variant price changes with immediate effect

## Operations

### 1. Update Variant Price and Compare-At Price

**Validated**: ✅ Passed Shopify MCP validation

```graphql
mutation updateVariantPricing($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    product {
      id
      title
    }
    productVariants {
      id
      title
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
| productId | ID! | Yes | Product GID (e.g., `gid://shopify/Product/123`) |
| variants | [ProductVariantsBulkInput!]! | Yes | Array of variant inputs with pricing |
| variants[].id | ID! | Yes | Variant GID to update |
| variants[].price | String | No | New price (e.g., "29.99") |
| variants[].compareAtPrice | String | No | Compare-at price or `null` to clear |

**Example**

```bash
python update_pricing.py --product-id 1234567890 --variant-id 9876543210 --price 29.99 --compare-at 39.99
```

**Variables Example**:
```json
{
  "productId": "gid://shopify/Product/1234567890",
  "variants": [{
    "id": "gid://shopify/ProductVariant/9876543210",
    "price": "29.99",
    "compareAtPrice": "39.99"
  }]
}
```

### 2. Get Inventory Item for Cost Update

**Validated**: ✅ Passed Shopify MCP validation

```graphql
query getInventoryItem($id: ID!) {
  productVariant(id: $id) {
    inventoryItem {
      id
    }
  }
}
```

**Required Scopes**: `read_products`, `read_inventory`

**Variables**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| id | ID! | Yes | Variant GID |

### 3. Update Inventory Item Cost

**Validated**: ✅ Passed Shopify MCP validation

```graphql
mutation updateCost($id: ID!, $input: InventoryItemInput!) {
  inventoryItemUpdate(id: $id, input: $input) {
    inventoryItem {
      id
      unitCost {
        amount
        currencyCode
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

**Required Scopes**: `write_inventory`, `read_inventory`, `read_products`

**Variables**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| id | ID! | Yes | InventoryItem GID (from query above) |
| input.cost | String | Yes | Unit cost (e.g., "15.00") |

**Example**

```bash
python update_pricing.py -p 1234567890 -v 9876543210 --cost 15.00
```

**Variables Example**:
```json
{
  "id": "gid://shopify/InventoryItem/456789",
  "input": {
    "cost": "15.00"
  }
}
```

## Response Structure

**Pricing Update Response**:
- `product.id`: Product GID
- `product.title`: Product name
- `productVariants[].id`: Updated variant GID
- `productVariants[].price`: New price
- `productVariants[].compareAtPrice`: Compare-at price (or null)
- `userErrors[]`: Validation errors if any

**Cost Update Response**:
- `inventoryItem.unitCost.amount`: New cost amount
- `inventoryItem.unitCost.currencyCode`: Currency (e.g., "CAD")
- `userErrors[]`: Validation errors if any

## Notes
- Cost updates require a separate mutation to `inventoryItemUpdate`
- Price and compareAtPrice are strings (not numbers) in GraphQL
- Setting `compareAtPrice` to `null` clears the sale price indicator
- The script automatically normalizes IDs to GID format
- Both mutations check for `userErrors` and exit on failure
- Cost updates are optional - only performed if `--cost` is provided
