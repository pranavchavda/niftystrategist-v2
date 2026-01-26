# Inventory GraphQL Operations

Complete documentation for inventory management GraphQL operations used by EspressoBot.

## Overview

This directory contains validated GraphQL queries and mutations for inventory management, including:
- Inventory policy management (oversell settings)
- Inventory analysis and velocity calculations
- Comprehensive movement reports for purchase decisions

All GraphQL operations have been validated against the Shopify Admin API schema using the Shopify MCP validator.

## Documentation Files

### [policy.md](./policy.md)
**Inventory Policy Management**
- Get product by ID, SKU, handle, or title
- Update inventory policies (CONTINUE/DENY) in bulk
- Control overselling and backorder capabilities
- **Scopes Required:** `read_products`, `write_products`

### [analysis.md](./analysis.md)
**Inventory Analysis Operations**
- Quick inventory overview (low stock, out of stock, overstock)
- Fast reorder recommendations based on sales velocity
- Deep velocity analysis with trend detection
- Statistical analysis with safety stock calculations
- **Scopes Required:** `read_products`, `read_inventory`, `read_orders`, `read_marketplace_orders`

### [movement.md](./movement.md)
**Inventory Movement Report**
- Comprehensive inventory snapshot with value calculations
- Closeout candidate identification
- Vendor and category analysis
- Export capabilities for external analysis
- **Scopes Required:** `read_products`, `read_inventory`

## Related Scripts

All scripts are located in `backend/bash-tools/inventory/`:

| Script | Purpose | Documentation |
|--------|---------|---------------|
| `manage_inventory_policy.py` | Update oversell settings | [policy.md](./policy.md) |
| `inventory_analysis.py` | Multi-mode analysis tool | [analysis.md](./analysis.md) |
| `inventory_movement_report.py` | Comprehensive reporting | [movement.md](./movement.md) |

## Common Use Cases

### 1. Check Low Stock Items
```bash
python inventory_analysis.py --mode quick --vendor Breville
```
Uses: `getProducts` query with `inventory_quantity:1..5` filter

### 2. Get Reorder Recommendations
```bash
python inventory_analysis.py --mode reorder --days 30
```
Uses: `getLowStock` and `getRecentOrders` queries with velocity calculations

### 3. Deep Trend Analysis
```bash
python inventory_analysis.py --mode deep --days 90 --lead-time 21
```
Uses: `getOrders` with pagination for comprehensive sales history

### 4. Update Inventory Policy
```bash
python manage_inventory_policy.py --identifier "SKU123" --policy deny
```
Uses: `findBySku` query and `updateVariants` mutation

### 5. Generate Movement Report
```bash
python inventory_movement_report.py --export-csv --focus closeout
```
Uses: `getInventory` query with full product data pagination

## Search Query Syntax

Common Shopify search patterns used in inventory operations:

```
# By vendor
vendor:"Breville"

# By inventory level
inventory_quantity:>0          # Has stock
inventory_quantity:0           # Out of stock
inventory_quantity:1..5        # Low stock (1-5 units)
inventory_quantity:<50         # Below 50 units
inventory_quantity:>50         # Overstock

# By date
created_at:<2024-06-01         # Older products
created_at:>=2024-11-01        # Recent orders

# By status
status:active                  # Active products only

# Combined queries
vendor:"Breville" inventory_quantity:1..5 status:active
```

## Analysis Modes Comparison

| Feature | Quick Mode | Reorder Mode | Deep Mode |
|---------|-----------|--------------|-----------|
| **Speed** | Fast (<30s) | Fast (<1m) | Slow (2-5m) |
| **Sales Data** | No | Yes (recent) | Yes (full history) |
| **Trend Analysis** | No | No | Yes |
| **Best For** | Quick checks | Daily reordering | Strategic planning |
| **Date Range** | N/A | 30 days default | 90 days default |
| **Output** | Overview | Reorder list | Comprehensive report |

## Required Shopify Scopes

Ensure your Shopify access token has these scopes:

- `read_products` - Required for all inventory queries
- `read_inventory` - Required for cost and tracking data
- `read_orders` - Required for sales velocity analysis
- `read_marketplace_orders` - Required for marketplace order data
- `write_products` - Required for updating inventory policies

## Validation Status

All GraphQL operations in this directory have been validated using:
- Tool: `@shopify/dev-mcp` MCP server
- API: Shopify Admin API
- Date: 2025-12-03
- Status: ✅ All operations validated successfully

## GraphQL Best Practices

1. **Pagination**: Always use cursor-based pagination for large datasets
2. **Field Selection**: Only request fields you need to minimize response size
3. **Error Handling**: Check `userErrors` field in all mutation responses
4. **Rate Limits**: Be mindful of Shopify's rate limits (40 requests/second REST, 2000 points/second GraphQL)
5. **Date Filters**: Use ISO 8601 format (YYYY-MM-DD) for date queries

## Notes

- All mutations return `userErrors` for validation feedback
- Inventory policies use `CONTINUE` (allow overselling) or `DENY` (block when out of stock)
- Cost data (`unitCost`) may not be available for all products
- Cancelled orders are automatically excluded from velocity calculations
- The movement report uses pandas for efficient data analysis

## See Also

- [Complete bash-tools INDEX.md](backend/bash-tools/INDEX.md)
- [GraphQL Operations Main INDEX.md](backend/docs/graphql-operations/INDEX.md)
- [Shopify Search Syntax Documentation](https://shopify.dev/docs/api/usage/search-syntax)
