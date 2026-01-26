# ShopifyQL Field Discovery

This document contains the ACTUAL working fields discovered through testing on iDrinkCoffee.com Shopify Plus.

Last updated: 2025-10-02

## Sales Dataset - VERIFIED WORKING FIELDS

### Metrics (use with sum(), avg(), etc.)
- ✅ `total_sales` - Total sales amount
- ✅ `net_sales` - Net sales after discounts/returns
- ✅ `gross_sales` - Gross sales before deductions
- ✅ `average_order_value` - Average order value (aggregate)

### Dimensions (can GROUP BY these)
- ✅ `billing_country` - Billing country
- ✅ `shipping_country` - Shipping country
- ✅ `product_title` - Product name
- ✅ `product_vendor` - Product vendor/brand
- ✅ `product_type` - Product type/category

### Time Dimensions
- ✅ `month` - Group by calendar month
- ✅ `day` - Group by calendar day (likely works)
- ✅ `week` - Group by calendar week (likely works)
- ✅ `year` - Group by calendar year (likely works)

### NOT Available in sales dataset
- ❌ `sku` - SKU not available
- ❌ `orders` - Use sales dataset metrics instead

## Customers Dataset - PARTIALLY VERIFIED

### Dimensions
- ✅ `customer_email` - Customer email address
- ⚠️ `customer_cities` - Mentioned by Sidekick, needs testing
- ⚠️ `customer_segments` - Mentioned by Sidekick, needs testing

### NOT Available
- ❌ `orders_count` - Not found
- ❌ `returning_customer` - Not found
- ❌ `total_sales` - Not found in customers dataset

## Available Datasets (from Shopify Admin autocomplete)

### Confirmed Working
- ✅ `sales` - Revenue and sales metrics (FULLY DOCUMENTED ABOVE)
- ✅ `customers` - Customer data (PARTIALLY DOCUMENTED ABOVE)

### Exist But Need Column Discovery
- ⚠️ `discounts` - Discount data (columns unknown)
- ⚠️ `fulfillments` - Fulfillment data (columns unknown)
- ⚠️ `inventory` - Inventory data (columns unknown)
- ⚠️ `sessions` - Session data (columns unknown)
- ⚠️ `subscriptions` - Subscription data (columns unknown)
- ⚠️ `attributed_sessions` - Attribution data (columns unknown)
- ⚠️ `searches` - Search data (columns unknown)
- ⚠️ `web_performance` - Performance metrics (columns unknown)
- ⚠️ `ORGANIZATION` - Organization data (columns unknown, all caps in autocomplete)

## Legacy Datasets (Don't Work in 2025-10 API)
- ❌ `orders` - Legacy API only (sunset 2024-07)
- ❌ `products` - Legacy API only (sunset 2024-07)
- ❌ `payment_attempts` - Legacy API only (sunset 2024-07)
- ❌ `marketing` - Invalid dataset
- ❌ `fulfillment` - Invalid dataset

## Working Query Patterns

### Sales by country
```shopifyql
FROM sales
SHOW sum(total_sales) AS revenue
GROUP BY shipping_country
ORDER BY revenue DESC
LIMIT 10
```

### Sales by vendor
```shopifyql
FROM sales
SHOW product_vendor, average_order_value
GROUP BY product_vendor
ORDER BY average_order_value DESC
LIMIT 10
```

### Product performance
```shopifyql
FROM sales
SHOW product_title, sum(total_sales) AS revenue
GROUP BY product_title
ORDER BY revenue DESC
LIMIT 20
```

### Monthly trends
```shopifyql
FROM sales
SHOW total_sales, net_sales, gross_sales
GROUP BY month
SINCE -12m
ORDER BY month
```

### Year-over-year comparison (TIMESERIES + COMPARE TO)
```shopifyql
FROM sales
SHOW total_sales
TIMESERIES day
SINCE yesterday
COMPARE TO 2024-10-01
```

**Note**: Use `TIMESERIES` keyword instead of `GROUP BY` when using `COMPARE TO` with time dimensions.

## To Do - Fields to Test

### Sales dataset
- [ ] `sales_channel` - Online Store vs POS
- [ ] `billing_region` / `shipping_region`
- [ ] `billing_city` / `shipping_city`
- [ ] `discounts`
- [ ] `taxes`
- [ ] `shipping`
- [ ] `returns`
- [ ] `product_id`
- [ ] `variant_id`
- [ ] `quarter` (time dimension)
- [ ] `hour` (time dimension)
- [ ] `day_of_week` (time dimension)

### Customers dataset
- [ ] `customer_id`
- [ ] `customer_name`
- [ ] `customer_tags`
- [ ] `amount_spent`
- [ ] `number_of_orders`
- [ ] `first_order_date`
- [ ] `last_order_date`

### Inventory dataset
- [ ] All fields need discovery
