# Orders Export (Multi-Store)

Fetch comprehensive order data from multiple Shopify stores with financial status, fulfillment details, and channel information. Designed for QuickBooks Online (QBO) reconciliation and cross-store reporting.

## Use Cases
- Export orders from multiple Shopify stores (main, parts, wholesale)
- QuickBooks Online reconciliation
- Financial reporting across all stores
- Order status tracking and fulfillment analysis
- Sales channel attribution
- Customer purchase history

## GraphQL

```graphql
query($cursor: String, $query: String) {
  orders(first: 250, after: $cursor, query: $query) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        name
        createdAt
        displayFinancialStatus
        displayFulfillmentStatus
        totalPriceSet {
          shopMoney {
            amount
            currencyCode
          }
        }
        customer {
          email
          displayName
        }
        tags
        cancelledAt
        refundable
        currentTotalPriceSet {
          shopMoney {
            amount
          }
        }
        publication {
          name
        }
        channelInformation {
          channelDefinition {
            channelName
            handle
          }
          app {
            title
          }
        }
      }
    }
  }
}
```

## Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| cursor | String | No | Pagination cursor for fetching next page of results |
| query | String | No | Shopify query filter (e.g., "created_at:>=2025-01-01 created_at:<=2025-01-31") |

## Required Scopes
- `read_orders`
- `read_marketplace_orders`
- `read_customers`

## Query Filter Format

The `query` parameter uses Shopify's search syntax for date range filtering:

### Date Range
```
created_at:>=YYYY-MM-DD created_at:<=YYYY-MM-DD
```

### Examples
- Last 90 days: `created_at:>=2024-11-01 created_at:<=2025-01-30`
- Specific month: `created_at:>=2025-01-01 created_at:<=2025-01-31`

## Example

### Export Orders from All Stores (Last 90 Days)

```bash
python backend/bash-tools/analytics/fetch_all_store_orders.py --start-date 2024-11-01 --end-date 2025-01-30 --output shopify_all_orders.csv
```

**Expected Variables:**
```json
{
  "query": "created_at:>=2024-11-01 created_at:<=2025-01-30",
  "cursor": null
}
```

### Custom Date Range

```bash
python backend/bash-tools/analytics/fetch_all_store_orders.py --start-date 2025-01-01 --end-date 2025-01-31 --output january_orders.csv
```

**Expected Variables:**
```json
{
  "query": "created_at:>=2025-01-01 created_at:<=2025-01-31",
  "cursor": null
}
```

## Store Configuration

The script fetches from three Shopify stores:

| Store | URL | Token Env Var | Store Name |
|-------|-----|---------------|------------|
| Main | idrinkcoffee.myshopify.com | SHOPIFY_ACCESS_TOKEN | iDrinkCoffee.com |
| Parts | idcparts.myshopify.com | SHOPIFY_PARTS_TOKEN | IDC Parts |
| Wholesale | idrinkcoffee-com.myshopify.com | SHOPIFY_WHOLESALE_TOKEN | IDC Wholesale |

## CSV Output

The script exports to CSV with the following columns:

- **store**: Store name (iDrinkCoffee.com, IDC Parts, IDC Wholesale)
- **order_number**: Order name (#1001, etc.)
- **order_id**: Numeric order ID
- **created_at**: ISO 8601 timestamp
- **financial_status**: Payment status (PAID, PENDING, REFUNDED, etc.)
- **fulfillment_status**: Fulfillment status (FULFILLED, UNFULFILLED, PARTIAL, etc.)
- **total**: Original order total
- **currency**: Currency code (USD, CAD, etc.)
- **customer_email**: Customer email address
- **customer_name**: Customer display name
- **tags**: Order tags (comma-separated)
- **cancelled**: Boolean (True if order was cancelled)
- **current_total**: Current order total (after refunds/adjustments)
- **channel**: Sales channel name (Online Store, POS, etc.)
- **channel_handle**: Channel identifier

## Summary Output

After export, the script displays a summary:

```
✅ Saved 456 total orders to shopify_all_orders.csv

Summary by store:
  iDrinkCoffee.com: 385 orders, $127,450.50
  IDC Parts: 52 orders, $8,920.30
  IDC Wholesale: 19 orders, $22,100.75
```

## Pagination

The query returns up to 250 orders per page. The script automatically handles pagination:

1. Makes initial request with `cursor: null`
2. Checks `pageInfo.hasNextPage`
3. If `true`, makes next request with `pageInfo.endCursor`
4. Continues until all orders are fetched

## Response Structure

```json
{
  "data": {
    "orders": {
      "pageInfo": {
        "hasNextPage": true,
        "endCursor": "eyJsYXN0X2lkIjo1ODczNjI..."
      },
      "edges": [
        {
          "node": {
            "id": "gid://shopify/Order/5873628...",
            "name": "#1001",
            "createdAt": "2025-01-15T14:30:00Z",
            "displayFinancialStatus": "PAID",
            "displayFulfillmentStatus": "FULFILLED",
            "totalPriceSet": {
              "shopMoney": {
                "amount": "299.99",
                "currencyCode": "USD"
              }
            },
            "customer": {
              "email": "customer@example.com",
              "displayName": "John Smith"
            },
            "tags": ["wholesale", "priority"],
            "cancelledAt": null,
            "refundable": true,
            "currentTotalPriceSet": {
              "shopMoney": {
                "amount": "299.99"
              }
            },
            "channelInformation": {
              "channelDefinition": {
                "channelName": "Online Store",
                "handle": "online_store"
              }
            }
          }
        }
      ]
    }
  }
}
```

## Financial Status Values

- **AUTHORIZED**: Payment authorized, not captured
- **PAID**: Payment successfully captured
- **PARTIALLY_PAID**: Partial payment received
- **PARTIALLY_REFUNDED**: Partial refund issued
- **PENDING**: Payment pending
- **REFUNDED**: Fully refunded
- **VOIDED**: Payment voided

## Fulfillment Status Values

- **FULFILLED**: All items shipped
- **IN_PROGRESS**: Partially fulfilled
- **ON_HOLD**: Fulfillment paused
- **OPEN**: Not yet fulfilled
- **PARTIALLY_FULFILLED**: Some items shipped
- **PENDING_FULFILLMENT**: Awaiting fulfillment
- **RESTOCKED**: Items returned to inventory
- **SCHEDULED**: Scheduled for fulfillment
- **UNFULFILLED**: No items shipped

## Notes

- Default date range is last 90 days if not specified
- Skips stores where environment variable is not set
- `currentTotalPriceSet` reflects order value after refunds/adjustments
- `totalPriceSet` is the original order total
- Channel information may come from `channelInformation` or fallback to `publication`
- Useful for accounting reconciliation and financial reporting

## Related Queries

- [Count US Orders](backend/docs/graphql-operations/analytics/us-orders.md) - Quick US order counts by date
- [Detailed US Orders](backend/docs/graphql-operations/analytics/orders-detailed.md) - Full US order details with line items
