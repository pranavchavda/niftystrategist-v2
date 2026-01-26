# Detailed US Orders with Line Items

Query comprehensive US order data including shipping addresses, line items, and pricing details. Designed for detailed order analysis, shipping reports, and customer service.

## Use Cases
- Fetch detailed US orders with full shipping information
- Analyze line items and product performance
- Generate shipping reports by state/city
- Customer service order lookup
- Revenue analysis by product
- Shipping logistics and fulfillment planning

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
        shippingAddress {
          city
          provinceCode
          countryCode
          zip
          address1
        }
        lineItems(first: 10) {
          edges {
            node {
              title
              quantity
              originalUnitPriceSet {
                shopMoney {
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
- January 2025: `created_at:>=2025-01-01 created_at:<=2025-01-31`
- Last week: `created_at:>=2025-01-20 created_at:<=2025-01-27`

## Example

### Get US Orders with Details

```bash
python backend/bash-tools/analytics/get_us_orders_detailed.py --start-date 2025-01-01 --end-date 2025-01-31
```

**Expected Variables:**
```json
{
  "query": "created_at:>=2025-01-01 created_at:<=2025-01-31",
  "cursor": null
}
```

### Expected Output
```
US Orders from 2025-01-01 to 2025-01-31
================================================================================

📦 Order: #1001 (ID: 5873628...)
   Date: 2025-01-15T14:30:00Z
   Total: $299.99 USD
   Customer: John Smith (john@example.com)
   Shipping: Los Angeles, CA 90001
   Address: 123 Main Street
   Financial: PAID
   Fulfillment: FULFILLED

   Line Items:
     • Breville Barista Express (Qty: 1) - $299.99
--------------------------------------------------------------------------------

✅ Total US Orders: 15
💰 Total Revenue: $4,499.85
```

## Order Filtering

The script automatically filters for US orders by checking:
```
shippingAddress.countryCode == 'US'
```

Only orders with US shipping addresses are included in the results.

## Line Items

Each order includes up to 10 line items with:
- **title**: Product name
- **quantity**: Number of units ordered
- **originalUnitPriceSet**: Unit price before discounts

**Note**: The query fetches first 10 line items. For orders with more than 10 items, additional pagination would be needed on the `lineItems` field.

## Pagination

The query returns up to 250 orders per page. The script automatically handles pagination:

1. Makes initial request with `cursor: null`
2. Checks `pageInfo.hasNextPage`
3. If `true`, makes next request with `pageInfo.endCursor`
4. Continues until all orders in date range are fetched
5. Filters for US orders only after fetching

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
              "email": "john@example.com",
              "displayName": "John Smith"
            },
            "shippingAddress": {
              "city": "Los Angeles",
              "provinceCode": "CA",
              "countryCode": "US",
              "zip": "90001",
              "address1": "123 Main Street"
            },
            "lineItems": {
              "edges": [
                {
                  "node": {
                    "title": "Breville Barista Express",
                    "quantity": 1,
                    "originalUnitPriceSet": {
                      "shopMoney": {
                        "amount": "299.99"
                      }
                    }
                  }
                }
              ]
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

## Shipping Address Fields

The `shippingAddress` object includes:
- **address1**: Street address
- **city**: City name
- **provinceCode**: State/province code (e.g., "CA", "NY")
- **countryCode**: Country code (e.g., "US", "CA")
- **zip**: Postal/ZIP code

## Use Cases by Field

### Revenue Analysis
- Use `totalPriceSet.shopMoney.amount` for order totals
- Sum `lineItems` quantities and prices for product performance

### Shipping Logistics
- Group by `shippingAddress.provinceCode` for state-level analysis
- Use `shippingAddress.city` for local delivery optimization
- Filter by `shippingAddress.zip` for zone-based shipping

### Customer Service
- Look up by `customer.email` or `name` (order number)
- Check `displayFinancialStatus` and `displayFulfillmentStatus`
- Review `lineItems` for order composition

### Product Performance
- Aggregate `lineItems.title` for best-sellers
- Calculate revenue per product using `quantity` × `originalUnitPriceSet`

## Notes

- Only fetches orders with US shipping addresses (`countryCode == 'US'`)
- Line items limited to first 10 per order (pagination needed for more)
- `originalUnitPriceSet` shows price before discounts are applied
- Date range parameters are required
- Output includes summary statistics (total orders, total revenue)
- Useful for detailed order analysis and reporting

## Related Queries

- [Count US Orders](backend/docs/graphql-operations/analytics/us-orders.md) - Quick US order counts by date
- [Orders Export (Multi-Store)](backend/docs/graphql-operations/analytics/orders-export.md) - Comprehensive export from all stores
- [ShopifyQL Analytics](backend/docs/graphql-operations/analytics/shopifyql.md) - Advanced analytics queries
