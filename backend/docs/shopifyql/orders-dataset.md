# Orders Dataset

Use ShopifyQL to access the dataset to explore data about order value and volume.

This page outlines the definition, type, and utility of each ShopifyQL column including numeric values, aggregates, and dimensional attributes.

## Notes about this dataset

This dataset contains one order per row, and has data available starting August 1, 2018. Refunds, returns, and exchanges are captured, deleted orders are removed entirely. All gift card sale items are excluded from this dataset as well. This is because gift cards are considered a liability/payment method rather than actual goods/services sold. The date assigned to each order is the date of the first sales event within that order.

All money values are shown in the registered currency of the shop. All metrics are fully additive, which means they are summable with any dimension in the dataset and are always the same.

**This dataset is available for Plus merchants.**

⚠️ **IMPORTANT**: Despite Shopify documentation showing these queries, some columns and dimensions may not be available in all Shopify plans or API versions. If queries from the official docs fail with "Column Not Found" errors, the columns may not be accessible on your plan. The `sales` dataset appears to be more universally available.

## Numeric values

Numeric values are the base numbers in the dataset. They're typically aggregated using ShopifyQL functions like sum.

| Name | Type | Definition |
|------|------|------------|
| additional_fees | price | The additional fees applied to the order in the shop's currency |
| discounts | price | The value of discounts applied to the order |
| duties | price | The duties applied when shipping internationally |
| gross_sales | price | The total value of items sold in the order |
| net_sales | price | The total value of items sold, subtracting any discounts applied and items returned |
| ordered_product_quantity | number | The number of products ordered |
| returned_product_quantity | number | The number of products returned |
| net_product_quantity | number | The quantity of products ordered, subtracts returns |
| orders | number | The count of orders, used to aggregate over time periods |
| shipping | price | The amount charged for shipping, subtracts any shipping discounts or refunds |
| taxes | price | The total amount of taxes charged based on the orders |
| tips | price | The value of tips |
| returns | price | The value of returned items |
| gross_sales_adjustments | price | The adjustments to gross sales after the initial order, includes order edits and exchanges |
| discounts_adjustments | price | The adjustments to discounts after the initial order, includes order edits and exchanges |

## Aggregates

Aggregates are predefined calculations of numeric values, to replicate metrics that are available throughout Shopify. Aggregates can be grouped or filtered by any of the dimensional attributes.

| Name | Type | Definition |
|------|------|------------|
| average_order_value | price | The average order value, which equates to gross sales (excluding adjustments) minus discounts (excluding adjustments), divided by the number of orders. Formula: `SUM((gross_sales - gross_sales_adjustments) + (discounts - discounts_adjustments))/SUM(orders)` |

## Dimensional attributes

| Name | Type | Definition |
|------|------|------------|
| billing_city | string | The city from the customer's billing address |
| billing_country | string | The country from the customer's billing address |
| billing_region | string | The region, state or province, from the customer's billing address |
| order_id | number | The order identifier used in Shopify |
| sales_channel | string | The channel where the sale came from, like online store |
| shipping_city | string | The city where the order shipped |
| shipping_country | string | The country where the order shipped |
| shipping_region | string | The state or province where the order shipped |

## Sample Queries

### 1. Show net sales by month

Note: The query will need to SUM() the net_sales metric. This is because the dataset contains net sales per order, and has to be aggregated.

```shopifyql
FROM orders SHOW sum(net_sales) AS monthly_net_sales
GROUP BY month
SINCE -3m
ORDER BY month
```

### 2. Show the number of orders per day over a time period

```shopifyql
FROM orders
VISUALIZE sum(orders) AS orders
TYPE line
GROUP BY day
SINCE last_month UNTIL yesterday LIMIT 100
```

### 3. Show average order value per day over a time period

```shopifyql
FROM orders
VISUALIZE average_order_value
TYPE line
GROUP BY day ALL
SINCE last_month UNTIL yesterday LIMIT 100
```
