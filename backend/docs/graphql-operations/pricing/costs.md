# Update Product Costs by SKU

Update inventory item unit costs for profit margin tracking, supporting both single SKU and bulk CSV updates.

## Use Cases
- Update cost of goods sold (COGS) for profit tracking
- Import cost updates from suppliers or inventory systems
- Maintain accurate margin calculations
- Bulk cost updates from purchase orders

## Operations

### 1. Get Variant and Inventory Item by SKU

**Validated**: ✅ Passed Shopify MCP validation

```graphql
query getVariantBySku($query: String!) {
  productVariants(first: 1, query: $query) {
    edges {
      node {
        id
        sku
        product {
          id
          title
        }
        inventoryItem {
          id
          unitCost {
            amount
            currencyCode
          }
        }
      }
    }
  }
}
```

**Required Scopes**: `read_products`, `read_inventory`

**Variables**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| query | String! | Yes | Shopify search query (e.g., `sku:COFFEE-001`) |

**Purpose**: Finds variant and its inventory item ID by SKU, also returns current cost.

**Example Query Strings**:
- `sku:COFFEE-001` - Exact SKU match
- `sku:BES870*` - SKU prefix match (wildcard)

### 2. Update Inventory Item Cost

**Validated**: ✅ Passed Shopify MCP validation
(Same mutation as in `update-variant.md`)

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
| input.cost | String! | Yes | Unit cost (e.g., "15.00") |

## Usage Examples

### Single SKU Update
```bash
# Update cost for one SKU
python update_costs_by_sku.py --sku "COFFEE-001" --cost 12.50

# Dry run to preview
python update_costs_by_sku.py --sku "COFFEE-001" --cost 12.50 --dry-run
```

**Variables Example**:
```json
{
  "query": "sku:COFFEE-001"
}
```

Then:
```json
{
  "id": "gid://shopify/InventoryItem/456789",
  "input": {
    "cost": "12.50"
  }
}
```

### Bulk CSV Update
```bash
# Update from CSV file
python update_costs_by_sku.py --csv costs.csv

# Dry run to preview
python update_costs_by_sku.py --csv costs.csv --dry-run
```

**CSV Format**:
```csv
sku,cost
COFFEE-001,12.50
COFFEE-002,15.00
BES870XL,450.00
```

**Requirements**:
- Must have headers: `sku`, `cost`
- SKU values must match exact Shopify SKUs
- Cost values are numeric (no currency symbols)

## Response Structure

**Variant Lookup Response**:
- `productVariants.edges[].node.id`: Variant GID
- `productVariants.edges[].node.sku`: Variant SKU
- `productVariants.edges[].node.product.title`: Product name
- `productVariants.edges[].node.inventoryItem.id`: Inventory item GID
- `productVariants.edges[].node.inventoryItem.unitCost.amount`: Current cost
- `productVariants.edges[].node.inventoryItem.unitCost.currencyCode`: Currency

**Cost Update Response**:
- `inventoryItem.id`: Updated inventory item GID
- `inventoryItem.unitCost.amount`: New cost amount
- `inventoryItem.unitCost.currencyCode`: Currency code
- `userErrors[]`: Validation errors if any

## Processing Strategy

### Single SKU Mode
1. Query by SKU to find variant and inventory item
2. Display current cost vs new cost
3. Update inventory item cost (if not dry run)
4. Display success/failure

### Bulk CSV Mode
1. Read and validate CSV file
2. For each row:
   - Query by SKU to find inventory item
   - Display current → new cost
   - Update cost (if not dry run)
   - Add 0.25s rate limit delay
3. Display summary: success count, failure count, total

## Notes
- Cost is stored at inventory item level, not variant level
- Cost must be fetched via `inventoryItem.unitCost` on the variant
- Rate limiting: 0.25s delay between bulk updates
- Dry run mode validates SKUs exist without making changes
- Summary includes counts: ✓ updated/would update, ✗ failed, total
- Cost values are strings in GraphQL (e.g., "12.50" not 12.50)
- If SKU not found, displays "NOT FOUND" and continues to next
- Currency is automatically set based on shop's default currency
