# **ShopifyQL Dataset Documentation for GraphQL Admin API**

## **Overview**

ShopifyQL is Shopify's query language built for commerce analytics. When using the GraphQL Admin API's `shopifyqlQuery`, you can query datasets to build custom reporting tools.

> **IMPORTANT: API vs Admin UI Availability**
>
> Not all ShopifyQL datasets documented by Shopify are available via the GraphQL Admin API. Some datasets (like `orders`, `products`, `customers`) may only be accessible through the Shopify Admin UI analytics interface.
>
> **Verified working via API (as of 2025-12):**
> - `sales` - Full access to revenue, order, and product metrics
> - `sessions` - Full access to traffic metrics
>
> **Admin UI only (not accessible via API):**
> - `orders` - Returns "Invalid dataset" error
> - `products` - Returns "Invalid dataset" error
> - `customers` - Columns not accessible
> - `inventory_adjustment_history` - Columns not accessible

------

## **Core ShopifyQL Syntax**

### **Query Structure**

All ShopifyQL queries follow this keyword order (only `FROM` and `SHOW` are required):

```sql
FROM <dataset>
SHOW <columns>
WHERE <conditions>
GROUP BY <dimensions>
SINCE <start_date>
UNTIL <end_date>
ORDER BY <column> {ASC|DESC}
LIMIT <number>
```

### **Key Syntax Rules**

- String values must use single quotes `'value'`, not double quotes
- Keywords are case-insensitive but conventionally uppercase
- Queries can be single-line or multi-line
- `WHERE` conditions can only reference dimensions, not metrics
- Pagination uses `LIMIT` with optional `OFFSET`

------

## **1. SALES Dataset** ✅ Verified Working

### **Purpose**

Analyze order data, revenue, and sales performance. This is the primary dataset for commerce analytics.

### **Verified Metrics**

- `total_sales` - Total sales amount
- `gross_sales` - Total before discounts
- `net_sales` - Sales after discounts and returns
- `orders` - Number of orders
- `average_order_value` - Average order size
- `discounts` - Total discount amount
- `returns` - Return amount
- `taxes` - Tax collected

> Note: `shipping` metric is NOT available via API

### **Verified Dimensions**

- `product_title` - Product name
- `product_type` - Product category
- `product_vendor` - Product vendor/brand
- `billing_country` - Customer billing country
- `billing_region` - Customer billing state/province
- `sales_channel` - Where the sale came from (Online Store, POS, etc.)
- `discount_code` - Discount code used
- `day`, `week`, `month` - Time dimensions

> Note: `customer_id`, `customer_name`, `order_id`, `shipping` dimensions are NOT available via API

### **Verified Example Queries**

**Monthly sales for last 3 months:**

```sql
FROM sales
SHOW total_sales
GROUP BY month
SINCE -3m
ORDER BY month
```

**Top products by revenue:**

```sql
FROM sales
SHOW total_sales, product_title
GROUP BY product_title
ORDER BY total_sales DESC
LIMIT 10
SINCE -30d
```

**Sales by country:**

```sql
FROM sales
SHOW total_sales, orders, billing_country
GROUP BY billing_country
ORDER BY total_sales DESC
LIMIT 10
SINCE -30d
```

**Sales by channel:**

```sql
FROM sales
SHOW total_sales, sales_channel
GROUP BY sales_channel
SINCE -7d
```

**Sales by discount code:**

```sql
FROM sales
SHOW total_sales, discount_code
GROUP BY discount_code
ORDER BY total_sales DESC
LIMIT 10
SINCE -30d
```

**Full metrics summary:**

```sql
FROM sales
SHOW total_sales, gross_sales, net_sales, orders, average_order_value, discounts, returns, taxes
SINCE -30d
```

**Daily sales breakdown:**

```sql
FROM sales
SHOW total_sales, orders
GROUP BY day
SINCE -7d
ORDER BY day
```

------

## **2. SESSIONS Dataset** ✅ Verified Working

### **Purpose**

Analyze online store traffic and visitor engagement.

### **Verified Metrics**

- `sessions` - Total session count

> Note: `unique_visitors`, `page_views`, `conversion_rate`, `bounce_rate`, `average_session_duration` are NOT available via API

### **Verified Dimensions**

- `referrer_source` - Traffic source category (direct, search, social, email, paid, unknown)
- `referrer_name` - Specific referrer (google, bing, gmail, etc.)
- `landing_page_path` - Entry page URL path
- `utm_campaign` - UTM campaign parameter
- `day`, `week`, `month` - Time dimensions

> Note: `device_type`, `browser`, `country` dimensions are NOT available via API

### **Verified Example Queries**

**Traffic by source:**

```sql
FROM sessions
SHOW sessions, referrer_source
GROUP BY referrer_source
ORDER BY sessions DESC
SINCE -7d
```

**Top landing pages:**

```sql
FROM sessions
SHOW sessions, landing_page_path
GROUP BY landing_page_path
ORDER BY sessions DESC
LIMIT 10
SINCE -7d
```

**Traffic by referrer name:**

```sql
FROM sessions
SHOW sessions, referrer_name
GROUP BY referrer_name
ORDER BY sessions DESC
LIMIT 10
SINCE -7d
```

**Daily sessions:**

```sql
FROM sessions
SHOW sessions
GROUP BY day
SINCE -7d
ORDER BY day
```

**UTM campaign performance:**

```sql
FROM sessions
SHOW sessions, utm_campaign
GROUP BY utm_campaign
ORDER BY sessions DESC
LIMIT 10
SINCE -30d
```

------

## **3. IMPLICIT JOINS** ✅ Verified Working

### **Purpose**

Combine multiple datasets in a single query for unified reporting.

### **Syntax**

```sql
FROM sales, sessions
SHOW total_sales, sessions
GROUP BY <shared_dimension>
```

### **Requirements**

- Join field must have the same name in all joined schemas
- Join field must be in `GROUP BY`
- Works with time dimensions (day, week, month)

### **Verified Example Query**

**Combined sales and traffic by day:**

```sql
FROM sales, sessions
SHOW total_sales, sessions
GROUP BY day
SINCE -7d
ORDER BY day
```

This returns both revenue and session counts aligned by date, perfect for analyzing traffic-to-sales correlation.

------

## **4. CUSTOMERS Dataset** ⚠️ Limited API Access

> **Warning**: This dataset's columns are not accessible via the GraphQL Admin API. Use the Shopify Admin UI analytics instead.

### **Documented Metrics (Admin UI only)**

- `customers` - Customer count
- `new_customers` - New customer count
- `returning_customers` - Returning customer count
- `total_spent` - Lifetime customer spend

------

## **5. ORDERS Dataset** ❌ Not Available via API

> **Warning**: This dataset returns "Invalid dataset in FROM clause" when queried via the GraphQL Admin API. Use the Shopify Admin UI analytics instead.

### **Alternative**

Use the `sales` dataset which provides order counts and revenue metrics:
```sql
FROM sales SHOW orders, total_sales, average_order_value SINCE -30d
```

------

## **6. PRODUCTS Dataset** ❌ Not Available via API

> **Warning**: This dataset returns "Invalid dataset in FROM clause" when queried via the GraphQL Admin API. Use the Shopify Admin UI analytics instead.

### **Alternative**

Use the `sales` dataset with `product_title` dimension:
```sql
FROM sales
SHOW total_sales, product_title
GROUP BY product_title
ORDER BY total_sales DESC
LIMIT 10
SINCE -30d
```

------

## **7. INVENTORY_ADJUSTMENT_HISTORY Dataset** ⚠️ Limited API Access

> **Warning**: This dataset's columns are not accessible via the GraphQL Admin API. Use the Shopify Admin UI analytics instead.

------

## **Date Functions Reference**

### **Relative Date Offsets**

```
-30d    // 30 days ago
-7d     // 7 days ago
-1w     // 1 week ago
-3m     // 3 months ago
-1y     // 1 year ago
```

### **Date Functions**

```
startOfDay(-30d)    // 30 days ago, start of day
endOfDay(-1d)       // Yesterday, end of day
startOfWeek(-2w)    // 2 weeks ago, start of week
startOfMonth(-3m)   // 3 months ago, start of month
today               // Today
```

### **Named Date Ranges (DURING)**

```
today
yesterday
last_week
last_month
last_quarter
last_year
this_week
this_month
this_quarter
this_year
```

------

## **Operators Reference**

### **Comparison Operators**

- `=` Equal to
- `!=` Not equal to
- `>` Greater than
- `>=` Greater than or equal
- `<` Less than
- `<=` Less than or equal

### **Logical Operators**

- `AND` - Both conditions must be true
- `OR` - Either condition must be true
- `NOT` - Negates condition

### **String/Array Matching**

- `CONTAINS` - Contains substring/value
- `STARTS WITH` - Begins with substring
- `ENDS WITH` - Ends with substring
- `IN` - Value in list

### **Example with operators:**

```sql
FROM sales
SHOW total_sales, product_title, billing_country
WHERE (billing_country = 'Canada' OR billing_country = 'United States')
  AND product_type CONTAINS 'Espresso'
SINCE -30d
```

------

## **GraphQL Admin API Integration**

### **Query Structure**

```graphql
query {
  shopifyqlQuery(query: "FROM sales SHOW total_sales, orders SINCE -30d") {
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

### **API Version**

ShopifyQL requires Admin API version **2025-10** or later.

### **Best Practices**

- Always handle `parseErrors` in responses
- Use `LIMIT` to control result size
- Test queries in Shopify Analytics UI first to verify column availability
- Cache results when appropriate for performance

### **Limitations**

- Metafields are NOT supported in ShopifyQL
- Not all datasets documented by Shopify are available via API
- Real-time data may have slight delays
- Some columns are available only in Admin UI

------

## **EspressoBot Integration**

### **Orchestrator Tool**

Use `execute_shopifyql(query, output_format)` for direct analytics queries:

```python
# Monthly sales
execute_shopifyql("FROM sales SHOW total_sales GROUP BY month SINCE -3m ORDER BY month")

# Combined sales + traffic
execute_shopifyql("FROM sales, sessions SHOW total_sales, sessions GROUP BY day SINCE -7d ORDER BY day")

# Traffic sources
execute_shopifyql("FROM sessions SHOW sessions, referrer_source GROUP BY referrer_source ORDER BY sessions DESC SINCE -7d")
```

### **CLI Tool**

Use `bash-tools/analytics/analytics.py` for standalone queries:

```bash
python analytics.py "FROM sales SHOW total_sales GROUP BY month SINCE -3m ORDER BY month"
python analytics.py "FROM sales, sessions SHOW total_sales, sessions GROUP BY day SINCE -7d" --output pandas
```

------

## **Common Use Cases**

### **Sales Analytics**

- Revenue dashboards and KPI tracking
- Product performance analysis
- Geographic sales distribution
- Discount effectiveness analysis
- Channel performance comparison

### **Traffic Analytics**

- Traffic source attribution
- Landing page performance
- Campaign effectiveness (UTM tracking)
- Referrer analysis

### **Combined Reporting**

- Traffic-to-sales correlation
- Daily/weekly performance dashboards
- Channel ROI analysis
