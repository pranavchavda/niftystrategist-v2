# Count US Orders by Date

Query orders filtered by date range and country, with pagination support for counting US orders.

## Use Cases
- Count US orders for specific date ranges (yesterday, today, etc.)
- Analyze country distribution of orders
- Monitor daily order volumes by shipping destination
- Track geographic order patterns

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
        createdAt
        shippingAddress {
          countryCode
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
| query | String | No | Shopify query filter (e.g., "created_at:>=2025-11-22") |

## Required Scopes
- `read_orders`
- `read_marketplace_orders`

## Query Filter Format

The `query` parameter uses Shopify's search syntax:

### Date Filtering
```
created_at:>=YYYY-MM-DD
created_at:<=YYYY-MM-DD
created_at:>=YYYY-MM-DD created_at:<=YYYY-MM-DD
```

### Examples
- Orders on or after November 22, 2025: `created_at:>=2025-11-22`
- Orders in date range: `created_at:>=2025-11-22 created_at:<=2025-11-23`

## Example

### Count US Orders for Yesterday and Today

```bash
python backend/bash-tools/analytics/count_us_orders.py
```

The script:
1. Queries orders created on or after yesterday
2. Counts orders by shipping country
3. Separates US orders by date (yesterday vs today)
4. Displays total and country distribution

**Variables used internally:**
```json
{
  "query": "created_at:>=2025-11-22",
  "cursor": null
}
```

### Expected Output
```
Counting US orders for Yesterday (2025-11-22) and Today (2025-11-23)...
Total Orders Found: 45
Country Distribution: {'US': 32, 'CA': 10, 'GB': 3}
US Orders Yesterday (2025-11-22): 18
US Orders Today (2025-11-23): 14
```

## Pagination

The query returns up to 250 orders per page. To fetch all orders:

1. Make initial request with `cursor: null`
2. Check `pageInfo.hasNextPage`
3. If `true`, make next request with `pageInfo.endCursor` as cursor
4. Repeat until `hasNextPage` is `false`

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
            "createdAt": "2025-11-23T14:30:00Z",
            "shippingAddress": {
              "countryCode": "US"
            }
          }
        }
      ]
    }
  }
}
```

## Notes

- Script is designed for daily monitoring of US vs international orders
- Hardcoded dates in the script may need updating for production use
- Orders without shipping addresses are counted as "No Shipping Address"
- The query fetches minimal data for performance (only ID, createdAt, countryCode)
- Useful for quick geographic order distribution analysis

## Related Queries

- [Orders Export (Multi-Store)](backend/docs/graphql-operations/analytics/orders-export.md) - Comprehensive order export with financial details
- [Detailed US Orders](backend/docs/graphql-operations/analytics/orders-detailed.md) - Full US order details with line items and shipping
