# Inventory Movement Report

Comprehensive inventory movement analysis for purchase and closeout decisions. Provides detailed insights into stock levels, value, costs, and product lifecycle.

## Use Cases
- Generate comprehensive inventory reports with value calculations
- Identify closeout candidates based on age and movement
- Analyze inventory by vendor and product category
- Track overstock and reorder needs
- Export detailed inventory data to CSV for external analysis

## Operations

### Get Complete Inventory Data

Retrieve comprehensive inventory information including pricing, costs, and product metadata.

**GraphQL Query:**
```graphql
query getInventory($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    edges {
      node {
        id
        title
        handle
        vendor
        productType
        tags
        createdAt
        updatedAt
        status
        totalInventory
        priceRangeV2 {
          minVariantPrice {
            amount
            currencyCode
          }
          maxVariantPrice {
            amount
            currencyCode
          }
        }
        variants(first: 100) {
          edges {
            node {
              id
              title
              sku
              price
              inventoryQuantity
              inventoryPolicy
              inventoryItem {
                id
                unitCost {
                  amount
                  currencyCode
                }
                tracked
              }
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

**Variables:**
| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `first` | `Int!` | Yes | Number of products per page (max 250) |
| `after` | `String` | No | Pagination cursor for next page |

**Required Scopes:** `read_products`, `read_inventory`

**Example:**
```bash
python core/graphql_query.py 'query getInventory($first: Int!, $after: String) { ... }' --variables '{
  "first": 250,
  "after": null
}'
```

---

## Report Components

### Summary Metrics
- Total products and SKUs
- Total inventory units
- Total inventory value and cost
- Potential margin calculation
- Out of stock and overstock counts
- Average days on hand

### Vendor Analysis
- Product count by vendor
- Total units by vendor
- Total value and cost by vendor
- Average days on hand by vendor

### Category Analysis
- Product count by product type
- Total units by category
- Total value by category
- Average days on hand by category

### Actionable Insights

#### Closeout Candidates
Products identified for potential closeout:
- Age >180 days
- Current inventory >0
- Status is ACTIVE
- Sorted by inventory value (highest first)

#### Reorder Alerts
Items needing reorder:
- Velocity category: Critical Low or Low Stock
- Age <180 days (fast-moving)
- Status is ACTIVE
- Sorted by inventory value

#### Overstock Items
Items with excess inventory:
- Velocity category: Overstock (>50 units)
- Sorted by inventory value

#### Balanced Inventory
Best performers with optimal stock:
- Velocity category: Normal
- Age <90 days
- Representative of well-managed inventory

---

## Velocity Categories

Products are automatically categorized based on inventory levels:

| Category | Inventory Range | Description |
|----------|----------------|-------------|
| Out of Stock | 0 | No inventory available |
| Critical Low | 1-5 | Immediate reorder needed |
| Low Stock | 6-20 | Reorder recommended |
| Normal | 21-100 | Healthy stock levels |
| Overstock | >100 | Consider promotions |

---

## Age Categories

Products are categorized by lifecycle stage:

| Category | Age Range | Description |
|----------|-----------|-------------|
| New | <30 days | Recently added |
| Recent | 30-90 days | Current season |
| Standard | 90-180 days | Established product |
| Slow | 180-365 days | Slow mover |
| Stale | >365 days | Closeout candidate |

---

## Value Calculations

The script calculates multiple value metrics:

**Inventory Value:**
```
Sum of (inventoryQuantity × price) for all variants
```

**Inventory Cost:**
```
Sum of (inventoryQuantity × unitCost) for all variants
```

**Margin Potential:**
```
Inventory Value - Inventory Cost
```

---

## Export Options

### Full Inventory Export
Complete dataset with all calculated fields:
- Product details (title, vendor, type)
- Inventory metrics (quantity, value, cost)
- Lifecycle data (age, velocity category)
- Price ranges and variant counts

### Closeout Candidates Export
Filtered list of items >180 days old with current inventory

### Reorder Alerts Export
Filtered list of low stock items needing reorder

---

## Report Focus Options

Use the `--focus` parameter to generate targeted reports:

- `--focus closeout`: Only closeout analysis
- `--focus reorder`: Only reorder alerts
- `--focus overstock`: Only overstock analysis
- `--focus all`: Complete report (default)

---

## Notes

- **Pagination**: Uses cursor-based pagination to handle large product catalogs
- **Cost Data**: Some products may not have cost data; calculations handle missing data gracefully
- **Currency**: Assumes CAD pricing and costs
- **Performance**: Fetches all products; may take several minutes for large catalogs
- **Data Analysis**: Uses pandas for efficient data manipulation and categorization
- **CSV Format**: Exports are compatible with Excel and Google Sheets

## Data Limitations

- **Velocity Without Sales**: This script categorizes velocity based on inventory levels only
- **True Velocity**: For accurate velocity analysis including sales data, use `inventory_analysis.py --mode deep`
- **Cost Data**: Not all variants may have cost data populated
- **Snapshot in Time**: Report represents inventory at the time of execution

## Related Scripts

- **Script:** `backend/bash-tools/inventory/inventory_movement_report.py`
- **Usage:**
  - `python inventory_movement_report.py`
  - `python inventory_movement_report.py --export-csv`
  - `python inventory_movement_report.py --focus closeout`
  - `python inventory_movement_report.py --vendor Breville --export-csv`
