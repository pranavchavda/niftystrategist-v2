# ShopifyQL for Analytics (Beta)

**Status**: Closed Beta (Invitation Only)
**API Version**: `unstable`
**Dataset**: `sales`

## Overview

ShopifyQL for analytics is the next generation of Shop

ifyQL currently in closed beta. It provides simplified access to sales analytics through the GraphQL Admin API with reduced access scope requirements.

### Key Improvements Over Legacy ShopifyQL

| Feature | Legacy (2024-04) | Beta (Unstable) |
|---------|------------------|-----------------|
| **Access Scopes** | 7 scopes required | 1 scope (`read_reports`) |
| **Datasets** | orders, products, payment_attempts | sales |
| **Merchant Tier** | Plus only | All merchants (beta access) |
| **Response Format** | Mixed rowData | Typed field values |
| **Date Functions** | Relative offsets (-3m) | Named functions (startOfYear) |

## Access Requirements

**Required Scope**:
- `read_reports` only

**Additional Requirements**:
- [Protected customer data access](https://shopify.dev/docs/apps/launch/protected-customer-data)
- App must meet [privacy and security requirements](https://shopify.dev/docs/apps/launch/protected-customer-data#requirements)
- Beta program invitation

**To Apply**: Contact Shopify Partner Support for beta access

## Sales Dataset

The `sales` dataset provides comprehensive sales analytics data.

### Available Fields

| Field | Type | Description |
|-------|------|-------------|
| `total_sales` | MONEY | Total sales amount including taxes, shipping, discounts |
| `gross_sales` | MONEY | Gross sales before discounts and returns |
| `net_sales` | MONEY | Sales after discounts and returns |
| `month` | MONTH_TIMESTAMP | Month timestamp for grouping |

*Note: Complete field list available in beta documentation*

## Syntax Differences

### Date Functions

**Legacy Format** (2024-04):
```shopifyql
SINCE -3m
UNTIL yesterday
DURING last_month
```

**Beta Format** (unstable):
```shopifyql
SINCE startOfYear(0y)
SINCE startOfMonth(1m)
SINCE startOfDay(7d)
```

### Response Structure

**Legacy Response**:
```json
{
  "tableData": {
    "rowData": [
      ["Jan 2025", "$123.45"],
      ["Feb 2025", "$234.56"]
    ],
    "unformattedData": [
      ["2025-01-01T00:00:00", 123.45],
      ["2025-02-01T00:00:00", 234.56]
    ]
  }
}
```

**Beta Response**:
```json
{
  "tableData": {
    "rows": [
      {
        "values": [
          { "__typename": "MonthTimestampFieldValue", "value": "2025-01-01" },
          { "__typename": "MoneyFieldValue", "value": "123.456" }
        ]
      }
    ]
  }
}
```

## Example Queries

### Total Sales by Month
```shopifyql
FROM sales
SHOW total_sales
GROUP BY month
SINCE startOfYear(0y)
ORDER BY month
```

**GraphQL Request**:
```graphql
{
  shopifyqlQuery(query: "FROM sales SHOW total_sales GROUP BY month SINCE startOfYear(0y) ORDER BY month") {
    tableData {
      columns {
        name
        dataType
        displayName
      }
      rows {
        values {
          __typename
          ... on MonthTimestampFieldValue { value }
          ... on MoneyFieldValue { value }
        }
      }
    }
    parseErrors
  }
}
```

**Response**:
```json
{
  "data": {
    "shopifyqlQuery": {
      "tableData": {
        "columns": [
          {
            "name": "month",
            "dataType": "MONTH_TIMESTAMP",
            "displayName": "Month"
          },
          {
            "name": "total_sales",
            "dataType": "MONEY",
            "displayName": "Total sales"
          }
        ],
        "rows": [
          {
            "values": [
              {
                "__typename": "MonthTimestampFieldValue",
                "value": "2025-01-01"
              },
              {
                "__typename": "MoneyFieldValue",
                "value": "123.456"
              }
            ]
          }
        ]
      },
      "parseErrors": []
    }
  }
}
```

## Migration from Legacy ShopifyQL

### Checklist

1. **Update API version** from `2024-04` to `unstable`
2. **Update dataset** from `orders`/`products` to `sales`
3. **Update date functions** from `-3m` to `startOfMonth(3m)`
4. **Update response parsing** to handle typed field values
5. **Remove extra access scopes** - only `read_reports` required
6. **Test query compatibility** - not all legacy queries directly translatable

### Common Translations

| Legacy Query | Beta Query |
|--------------|------------|
| `FROM orders SHOW sum(net_sales)` | `FROM sales SHOW net_sales` |
| `SINCE -1y UNTIL today` | `SINCE startOfYear(1y)` |
| `DURING last_month` | `SINCE startOfMonth(1m)` |
| `GROUP BY day ALL` | `GROUP BY day` (implicit ALL) |

### Breaking Changes

- **No `sum()` required** for `sales` dataset aggregates (built-in)
- **Different field names** - mapping required from orders→sales fields
- **Response structure** - must handle typed `FieldValue` union types
- **Date functions** - relative offsets replaced with named functions

## Best Practices

### Error Handling

Always check `parseErrors`:
```graphql
{
  shopifyqlQuery(query: "...") {
    parseErrors {
      code
      message
      range {
        start { line, character }
        end { line, character }
      }
    }
    tableData { ... }
  }
}
```

### Type-Safe Response Parsing

Handle all possible `__typename` values:
```typescript
rows.forEach(row => {
  row.values.forEach(value => {
    switch (value.__typename) {
      case 'MonthTimestampFieldValue':
        // Handle month timestamp
        break;
      case 'MoneyFieldValue':
        // Handle money value
        break;
      // ... other types
    }
  });
});
```

### Performance Optimization

- **Limit date ranges** - Shorter ranges query faster
- **Use appropriate granularity** - Don't GROUP BY hour for yearly data
- **Cache results** - Cache for 15 minutes (Shopify's own cache TTL)
- **Handle timeouts** - Set appropriate timeout values in HTTP client

## Limitations

- **Closed beta only** - Requires invitation
- **Single dataset** - Only `sales` currently available
- **Unstable API** - Subject to change without versioning
- **Limited documentation** - Beta docs may be incomplete
- **No public SLA** - Beta has no uptime guarantees

## Support & Resources

- **Beta Documentation**: Provided upon beta access approval
- **Partner Support**: For beta-specific questions
- **API Status**: [Shopify Status Page](https://status.shopify.com)
- **Feedback**: Share with beta program contact

## Future Roadmap

Expected additions (not confirmed):
- Additional datasets (customers, inventory, etc.)
- More aggregate functions
- Enhanced filtering capabilities
- Improved date/time functions
- Public general availability

---

**Last Updated**: 2025-01-06
**API Version**: unstable (subject to change)
**Status**: Closed Beta
