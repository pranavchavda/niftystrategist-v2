# Inventory Analysis Operations

GraphQL operations for comprehensive inventory analysis including stock levels, sales velocity, and reorder calculations.

## Use Cases
- Quick inventory status overview (low stock, out of stock, overstock)
- Fast reorder recommendations based on recent sales
- Deep velocity analysis with trend detection
- Identify closeout candidates and overstock items

## Operations

### 1. Get Products with Inventory Data

Retrieve products with detailed inventory information for quick insights analysis.

**GraphQL Query:**
```graphql
query getProducts($query: String!, $first: Int!) {
  products(first: $first, query: $query) {
    edges {
      node {
        id
        title
        vendor
        productType
        totalInventory
        createdAt
        variants(first: 5) {
          edges {
            node {
              sku
              inventoryQuantity
              price
            }
          }
        }
      }
    }
  }
}
```

**Variables:**
| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `query` | `String!` | Yes | Shopify search query (e.g., `vendor:"Breville" inventory_quantity:>0`) |
| `first` | `Int!` | Yes | Number of products to retrieve (max 250) |

**Required Scopes:** `read_products`

**Common Query Patterns:**
- Closeout candidates: `inventory_quantity:>0 created_at:<2024-06-01`
- Low stock: `inventory_quantity:1..5 status:active`
- Out of stock: `inventory_quantity:0 status:active`
- Overstock: `inventory_quantity:>50`

**Example:**
```bash
python core/graphql_query.py 'query getProducts($query: String!, $first: Int!) { ... }' --variables '{
  "query": "vendor:\"Breville\" inventory_quantity:1..5 status:active",
  "first": 50
}'
```

---

### 2. Get Low Stock Products with Cost Data

Retrieve products with low inventory levels including cost information for reorder analysis.

**GraphQL Query:**
```graphql
query getLowStock($query: String!, $first: Int!) {
  products(first: $first, query: $query) {
    edges {
      node {
        id
        title
        vendor
        productType
        totalInventory
        variants(first: 10) {
          edges {
            node {
              id
              sku
              title
              inventoryQuantity
              price
              inventoryItem {
                unitCost {
                  amount
                }
              }
            }
          }
        }
      }
    }
  }
}
```

**Variables:**
| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `query` | `String!` | Yes | Shopify search query for low stock items |
| `first` | `Int!` | Yes | Number of products to retrieve |

**Required Scopes:** `read_products`, `read_inventory`

**Example:**
```bash
python core/graphql_query.py 'query getLowStock($query: String!, $first: Int!) { ... }' --variables '{
  "query": "inventory_quantity:>0 inventory_quantity:<50 status:active",
  "first": 100
}'
```

---

### 3. Get Recent Orders for Sales Velocity

Retrieve recent orders to analyze sales velocity and calculate reorder recommendations.

**GraphQL Query:**
```graphql
query getRecentOrders($query: String!, $first: Int!) {
  orders(first: $first, query: $query) {
    edges {
      node {
        createdAt
        cancelledAt
        lineItems(first: 100) {
          edges {
            node {
              sku
              quantity
            }
          }
        }
      }
    }
  }
}
```

**Variables:**
| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `query` | `String!` | Yes | Date filter (e.g., `created_at:>=2024-11-01`) |
| `first` | `Int!` | Yes | Number of orders to retrieve (max 250) |

**Required Scopes:** `read_orders`, `read_marketplace_orders`

**Example:**
```bash
python core/graphql_query.py 'query getRecentOrders($query: String!, $first: Int!) { ... }' --variables '{
  "query": "created_at:>=2024-11-01",
  "first": 250
}'
```

---

### 4. Get Orders with Full Line Item Details

Retrieve orders with complete product and variant information for deep velocity analysis.

**GraphQL Query:**
```graphql
query getOrders($query: String!, $first: Int!, $after: String) {
  orders(first: $first, query: $query, after: $after) {
    edges {
      node {
        id
        name
        createdAt
        cancelledAt
        lineItems(first: 100) {
          edges {
            node {
              id
              title
              sku
              quantity
              variant {
                id
                inventoryQuantity
                product {
                  id
                  title
                  vendor
                  productType
                }
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
| `query` | `String!` | Yes | Date filter query |
| `first` | `Int!` | Yes | Number of orders per page |
| `after` | `String` | No | Pagination cursor |

**Required Scopes:** `read_orders`, `read_marketplace_orders`, `read_products`

**Example:**
```bash
python core/graphql_query.py 'query getOrders($query: String!, $first: Int!, $after: String) { ... }' --variables '{
  "query": "created_at:>=2024-09-01",
  "first": 100,
  "after": null
}'
```

---

## Analysis Modes

The inventory analysis script supports three modes:

### Quick Mode
- Fast overview of inventory status
- Identifies closeout candidates (>180 days old)
- Flags low stock and out of stock items
- Detects overstock situations

### Reorder Mode
- Quick reorder recommendations based on recent sales (default: 30 days)
- Calculates daily velocity and urgency levels
- Estimates reorder quantities and costs
- Prioritizes by urgency (CRITICAL, HIGH, MEDIUM)

### Deep Mode
- Deep velocity analysis with trend detection (default: 90 days)
- Calculates safety stock and reorder points
- Detects sales trends (increasing/decreasing)
- Statistical analysis with standard deviation
- Customizable lead time and safety stock parameters

## Velocity Categories

**Sales Velocity:**
- **FAST**: ≥1 unit/day → 60-day reorder quantity
- **MEDIUM**: 0.3-1 unit/day → 90-day reorder quantity
- **SLOW**: <0.3 unit/day → 120-day reorder quantity

**Urgency Levels:**
- **CRITICAL**: ≤7 days until stockout
- **HIGH**: 7-14 days until stockout
- **MEDIUM**: 14-30 days until stockout
- **LOW**: >30 days until stockout

## Notes

- **Pagination**: Deep analysis mode uses cursor-based pagination for large order datasets
- **Cancelled Orders**: The script filters out cancelled orders from velocity calculations
- **Cost Data**: Unit cost is optional; some variants may not have cost data available
- **Date Filters**: Use ISO 8601 date format (YYYY-MM-DD) in search queries
- **Performance**: Quick mode is optimized for speed; deep mode provides comprehensive insights

## Related Scripts

- **Script:** `backend/bash-tools/inventory/inventory_analysis.py`
- **Usage:**
  - `python inventory_analysis.py --mode quick`
  - `python inventory_analysis.py --mode reorder --vendor Breville --days 30`
  - `python inventory_analysis.py --mode deep --days 90 --export-csv`
