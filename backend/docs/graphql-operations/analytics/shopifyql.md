# ShopifyQL Analytics Query

Execute ShopifyQL queries for sales, sessions, and traffic analytics data.

> **IMPORTANT: API vs Admin UI Availability**
>
> Not all ShopifyQL datasets are available via the GraphQL Admin API. Some datasets (like `orders`, `products`, `customers`) may only be accessible through the Shopify Admin UI analytics interface.
>
> **Verified working via API**: `sales`, `sessions`, implicit joins
> **Admin UI only**: `orders`, `products`, `customers`, `inventory`

## Use Cases
- Query sales metrics (total_sales, gross_sales, net_sales, revenue trends)
- Analyze traffic sources and landing pages
- Track product performance by sales dimension
- Generate custom reports with time-based grouping
- Compare periods using SINCE/UNTIL
- Combined sales + traffic reports using implicit joins

## GraphQL

```graphql
query($shopifyqlQuery: String!) {
  shopifyqlQuery(query: $shopifyqlQuery) {
    tableData {
      columns {
        name
        dataType
        displayName
      }
      rows
    }
    parseErrors
  }
}
```

## Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| shopifyqlQuery | String! | Yes | ShopifyQL query string (e.g., "FROM sales SHOW total_sales GROUP BY month") |

## Required Scopes
- `read_reports`

## API Version
- Requires Shopify Admin API 2025-10 or later (shopifyqlQuery was added in this version)

## ShopifyQL Query Syntax

### Verified Datasets (API)

#### SALES Dataset
**Metrics**: total_sales, gross_sales, net_sales, orders, average_order_value, discounts, returns, taxes
**Dimensions**: product_title, product_type, product_vendor, billing_country, billing_region, sales_channel, discount_code, day, week, month

#### SESSIONS Dataset
**Metrics**: sessions
**Dimensions**: referrer_source, referrer_name, landing_page_path, utm_campaign, day, week, month

#### Implicit Joins
Combine datasets using `FROM sales, sessions` - join on day/week/month dimensions.

### Common Time Dimensions
- day, week, month (verified working)
- hour_of_day, day_of_week, week_of_year (availability may vary)

### Operators
- **Comparison**: =, !=, <, >, <=, >=
- **Logical**: AND, OR, NOT
- **String**: CONTAINS, STARTS WITH, ENDS WITH, IN

### Query Structure
```
FROM [dataset]
SHOW [columns]
WHERE [conditions]
GROUP BY [dimension]
SINCE [time_period]
UNTIL [time_period]
ORDER BY [column] [ASC|DESC]
LIMIT [number]
```

## Examples

### Monthly Sales (Last 3 Months)
```bash
python backend/bash-tools/analytics/analytics.py "FROM sales SHOW total_sales GROUP BY month SINCE -3m ORDER BY month"
```

**Expected Variables:**
```json
{
  "shopifyqlQuery": "FROM sales SHOW total_sales GROUP BY month SINCE -3m ORDER BY month"
}
```

### Full Sales Metrics Summary
```bash
python backend/bash-tools/analytics/analytics.py "FROM sales SHOW total_sales, gross_sales, net_sales, orders, average_order_value, discounts, returns, taxes SINCE -30d"
```

**Expected Variables:**
```json
{
  "shopifyqlQuery": "FROM sales SHOW total_sales, gross_sales, net_sales, orders, average_order_value, discounts, returns, taxes SINCE -30d"
}
```

### Top Products by Revenue
```bash
python backend/bash-tools/analytics/analytics.py "FROM sales SHOW total_sales, product_title GROUP BY product_title ORDER BY total_sales DESC LIMIT 10 SINCE -30d"
```

**Expected Variables:**
```json
{
  "shopifyqlQuery": "FROM sales SHOW total_sales, product_title GROUP BY product_title ORDER BY total_sales DESC LIMIT 10 SINCE -30d"
}
```

### Sales by Country
```bash
python backend/bash-tools/analytics/analytics.py "FROM sales SHOW total_sales, orders, billing_country GROUP BY billing_country ORDER BY total_sales DESC LIMIT 10 SINCE -30d"
```

**Expected Variables:**
```json
{
  "shopifyqlQuery": "FROM sales SHOW total_sales, orders, billing_country GROUP BY billing_country ORDER BY total_sales DESC LIMIT 10 SINCE -30d"
}
```

### Sales by Discount Code
```bash
python backend/bash-tools/analytics/analytics.py "FROM sales SHOW total_sales, discount_code GROUP BY discount_code ORDER BY total_sales DESC LIMIT 10 SINCE -30d"
```

**Expected Variables:**
```json
{
  "shopifyqlQuery": "FROM sales SHOW total_sales, discount_code GROUP BY discount_code ORDER BY total_sales DESC LIMIT 10 SINCE -30d"
}
```

### Traffic by Source
```bash
python backend/bash-tools/analytics/analytics.py "FROM sessions SHOW sessions, referrer_source GROUP BY referrer_source ORDER BY sessions DESC SINCE -7d"
```

**Expected Variables:**
```json
{
  "shopifyqlQuery": "FROM sessions SHOW sessions, referrer_source GROUP BY referrer_source ORDER BY sessions DESC SINCE -7d"
}
```

### Top Landing Pages
```bash
python backend/bash-tools/analytics/analytics.py "FROM sessions SHOW sessions, landing_page_path GROUP BY landing_page_path ORDER BY sessions DESC LIMIT 10 SINCE -7d"
```

**Expected Variables:**
```json
{
  "shopifyqlQuery": "FROM sessions SHOW sessions, landing_page_path GROUP BY landing_page_path ORDER BY sessions DESC LIMIT 10 SINCE -7d"
}
```

### Combined Sales + Traffic (Implicit Join)
```bash
python backend/bash-tools/analytics/analytics.py "FROM sales, sessions SHOW total_sales, sessions GROUP BY day SINCE -7d ORDER BY day"
```

**Expected Variables:**
```json
{
  "shopifyqlQuery": "FROM sales, sessions SHOW total_sales, sessions GROUP BY day SINCE -7d ORDER BY day"
}
```

### UTM Campaign Performance
```bash
python backend/bash-tools/analytics/analytics.py "FROM sessions SHOW sessions, utm_campaign GROUP BY utm_campaign ORDER BY sessions DESC LIMIT 10 SINCE -30d"
```

**Expected Variables:**
```json
{
  "shopifyqlQuery": "FROM sessions SHOW sessions, utm_campaign GROUP BY utm_campaign ORDER BY sessions DESC LIMIT 10 SINCE -30d"
}
```

## Output Formats

The script supports multiple output formats via the `--output` flag:

- **pretty** (default): Formatted ASCII table
- **json**: JSON formatted output
- **pandas**: Pandas DataFrame with info
- **csv**: CSV format (use with `--file` to save)

Example with CSV export:
```bash
python backend/bash-tools/analytics/analytics.py "FROM sales SHOW total_sales GROUP BY month SINCE -3m" --output csv --file sales_report.csv
```

## Response Structure

The query returns a `tableData` object with:
- **columns**: Array of column definitions (name, dataType, displayName)
- **rows**: Array of row objects with data
- **parseErrors**: Array of error messages (if query syntax is invalid)

## Notes

- **API Limitations**: Many columns documented by Shopify are only available in the Admin UI, not via GraphQL API
- Some datasets (`orders`, `products`, `customers`) return "Invalid dataset" when queried via API
- Use `parseErrors` field to debug query syntax issues
- The `shipping` metric in sales is NOT available via API
- Metrics like `unique_visitors`, `conversion_rate`, `bounce_rate` in sessions are NOT available via API
- Comprehensive local documentation available at `backend/docs/shopifyql/shopifyql-overview.md`

## Related Documentation

- [ShopifyQL Overview](../../shopifyql/shopifyql-overview.md) - Complete verified reference
- [ShopifyQL Syntax Reference](../../shopifyql/syntax-reference.md)
- [Official Shopify Docs](https://shopify.dev/docs/api/shopifyql)
