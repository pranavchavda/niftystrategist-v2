# Analytics GraphQL Operations

Documentation for GraphQL queries used in the analytics bash tools. All queries have been validated against the Shopify Admin GraphQL schema.

## Overview

This directory contains validated GraphQL operations for:
- **ShopifyQL Analytics**: Execute ShopifyQL queries for sales and traffic metrics
- **Order Queries**: Fetch order data with various filters and detail levels
- **Multi-Store Operations**: Query across multiple Shopify stores

All GraphQL queries are validated using the Shopify MCP validation tools to ensure schema compliance.

> **Note**: Not all ShopifyQL datasets are available via GraphQL API. The `orders`, `products`, and `customers` datasets are only accessible in Shopify Admin UI. Use `sales` and `sessions` datasets for API queries.

## Operations Index

### 1. [ShopifyQL Analytics](./shopifyql.md)
**Script**: `backend/bash-tools/analytics/analytics.py`

Execute ShopifyQL queries for sales and traffic analytics.

**Key Features**:
- Sales metrics (total_sales, gross_sales, net_sales, orders, average_order_value)
- Traffic metrics (sessions, referrer_source, landing_page_path)
- Product performance via sales dimensions (product_title, product_type)
- Time-based grouping (day, week, month)
- Implicit joins (combine sales + sessions by date)

**Required Scopes**: `read_reports`

**Example**:
```bash
python backend/bash-tools/analytics/analytics.py "FROM sales SHOW total_sales GROUP BY month SINCE -3m"
```

---

### 2. [Count US Orders](./us-orders.md)
**Script**: `backend/bash-tools/analytics/count_us_orders.py`

Quick order counting by date and country with minimal data fetching.

**Key Features**:
- Count orders by shipping country
- Filter by date range
- Daily US order monitoring
- Country distribution analysis

**Required Scopes**: `read_orders`, `read_marketplace_orders`

**Example**:
```bash
python backend/bash-tools/analytics/count_us_orders.py
```

---

### 3. [Orders Export (Multi-Store)](./orders-export.md)
**Script**: `backend/bash-tools/analytics/fetch_all_store_orders.py`

Comprehensive order export from multiple Shopify stores for accounting reconciliation.

**Key Features**:
- Query three stores (main, parts, wholesale)
- Financial status tracking
- Fulfillment status monitoring
- Sales channel attribution
- CSV export for QuickBooks Online

**Required Scopes**: `read_orders`, `read_marketplace_orders`, `read_customers`

**Example**:
```bash
python backend/bash-tools/analytics/fetch_all_store_orders.py --start-date 2025-01-01 --end-date 2025-01-31 --output january_orders.csv
```

---

### 4. [Detailed US Orders](./orders-detailed.md)
**Script**: `backend/bash-tools/analytics/get_us_orders_detailed.py`

Fetch US orders with complete shipping addresses and line items.

**Key Features**:
- Full shipping information (address, city, state, ZIP)
- Line item details (product, quantity, price)
- US-only filtering
- Revenue analysis by product
- Shipping logistics support

**Required Scopes**: `read_orders`, `read_marketplace_orders`, `read_customers`

**Example**:
```bash
python backend/bash-tools/analytics/get_us_orders_detailed.py --start-date 2025-01-01 --end-date 2025-01-31
```

---

## API Requirements

### Version
All queries require **Shopify Admin API 2025-10 or later**.

### Authentication
Set the following environment variables:
```bash
# Main store
SHOPIFY_ACCESS_TOKEN=shpat_...

# Parts store (for multi-store operations)
SHOPIFY_PARTS_TOKEN=shpat_...

# Wholesale store (for multi-store operations)
SHOPIFY_WHOLESALE_TOKEN=shpat_...
```

### Access Scopes

Different operations require different scopes:

| Operation | Required Scopes |
|-----------|----------------|
| ShopifyQL Analytics | `read_reports` |
| Count US Orders | `read_orders`, `read_marketplace_orders` |
| Orders Export | `read_orders`, `read_marketplace_orders`, `read_customers` |
| Detailed US Orders | `read_orders`, `read_marketplace_orders`, `read_customers` |

## Query Patterns

### Date Filtering
All order queries support date range filtering using Shopify's query syntax:

```
created_at:>=YYYY-MM-DD created_at:<=YYYY-MM-DD
```

**Examples**:
- Last 90 days: `created_at:>=2024-11-01 created_at:<=2025-01-30`
- Specific month: `created_at:>=2025-01-01 created_at:<=2025-01-31`
- On or after date: `created_at:>=2025-01-15`

### Pagination
All queries use cursor-based pagination:

```graphql
query($cursor: String) {
  orders(first: 250, after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        # ... fields
      }
    }
  }
}
```

**Pattern**:
1. Initial request: `cursor: null`
2. Check `pageInfo.hasNextPage`
3. If `true`, use `pageInfo.endCursor` as next cursor
4. Repeat until `hasNextPage` is `false`

## Validation

All GraphQL queries in this documentation have been validated using:
- **Tool**: `mcp__shopify-dev-mcp__validate_graphql_codeblocks`
- **API**: `admin` (Shopify Admin GraphQL API)
- **Validation Date**: 2025-12-03

### Validation Status

| Query | Status | Artifact ID |
|-------|--------|-------------|
| ShopifyQL Analytics | ✅ VALID | artifact-ed7a8a85-900e-4dac-b35b-abf0e6de4d72 |
| Count US Orders | ✅ VALID | artifact-9a489957-9f84-4646-ab59-77261370152d |
| Orders Export | ✅ VALID | artifact-5eea51a4-4b08-4c26-b02e-76dfd88d7ad0 |
| Detailed US Orders | ✅ VALID | artifact-6c0924b9-ca46-4d60-a16d-014c90e05676 |

## Common Use Cases

### Financial Reporting
- **Orders Export**: Multi-store financial data for QBO reconciliation
- **ShopifyQL**: Sales trends and revenue analysis

### Shipping & Fulfillment
- **Detailed US Orders**: Shipping addresses and logistics planning
- **Count US Orders**: Geographic order distribution

### Customer Service
- **Detailed US Orders**: Order lookup with full details
- **Orders Export**: Order status and history

### Product Analysis
- **ShopifyQL**: Product performance metrics
- **Detailed US Orders**: Line item analysis and best-sellers

### Geographic Analysis
- **Count US Orders**: Country distribution
- **Detailed US Orders**: State/city-level analysis

## Related Documentation

- [ShopifyQL Syntax Reference](backend/docs/shopifyql/syntax-reference.md)
- [Orders Dataset](backend/docs/shopifyql/orders-dataset.md)
- [Products Dataset](backend/docs/shopifyql/products-dataset.md)
- [Shopify Admin API](https://shopify.dev/docs/api/admin-graphql)
- [Shopify Search Syntax](https://shopify.dev/docs/api/usage/search-syntax)

## Support

For questions or issues:
1. Check individual operation documentation
2. Review GraphQL validation errors
3. Verify API scopes and authentication
4. Consult Shopify API documentation

## Last Updated
2025-12-03
