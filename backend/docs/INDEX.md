# EspressoBot Documentation Index

This index provides a navigation map for all EspressoBot documentation. Use this to quickly find relevant information for any task.

---

## 📦 Product Operations

### Product Guidelines (Core Documentation)
**Path:** `product-guidelines/`

These are the **most important** docs for product creation and management:

1. **[Overview](./product-guidelines/01-overview.md)** - High-level product management principles
2. **[Product Creation Basics](./product-guidelines/02-product-creation-basics.md)** - Essential fields, validation, basic workflow
3. **[Metafields Reference](./product-guidelines/03-metafields-reference.md)** - Custom fields, technical specs, product data
4. **[Tags System](./product-guidelines/04-tags-system.md)** - Tagging conventions, categories, filters
5. **[Coffee Products](./product-guidelines/05-coffee-products.md)** - Coffee-specific guidelines (beans, grounds, pods)
6. **[API Technical Reference](./product-guidelines/06-api-technical-reference.md)** - GraphQL mutations, API patterns
7. **[Product Anatomy](./product-guidelines/07-product-anatomy.md)** - Product structure, variants, options
8. **[Variant Linking Guide](./product-guidelines/08-variant-linking-guide.md)** - Cross-product variant relationships
9. **[New Product Workflow](./product-guidelines/09-new-product-workflow.md)** - **START HERE for new products!** Complete step-by-step workflow

**When to use:**
- Creating any new product → Start with `09-new-product-workflow.md`
- Need metafield info → `03-metafields-reference.md`
- GraphQL syntax help → `06-api-technical-reference.md`
- Tagging questions → `04-tags-system.md`

---

## 🛠️ Tools & Scripts

### Bash Tools Index
**Path:** `bash-tools-index.md` (symlink to `../bash-tools/INDEX.md`)

**Complete reference for all 74 Python tools** organized by category:
- 🛍️ Product Management (21 tools) - create, search, update products
- 💰 Pricing & Sales (7 tools) - pricing, MAP, bulk updates
- 📝 Content Management (6 tools) - pages, metaobjects
- 🛠️ Utilities (7 tools) - customer communication, auditing
- And more...

**Most used tools:**
- **`search_products.py`** - Search products with filters (vendor, status, tags, etc.)
- **`get_product.py`** - Get product details by ID/handle/SKU
- **`create_full_product.py`** - Create complete products with metafields
- **`update_pricing.py`** - Update prices, costs, compare-at prices
- **`create_combo.py`** - Create machine+grinder combos

**When to use:**
- Need to know what tools are available → Read `bash-tools-index.md`
- How to use a specific tool → Check tool's section in index
- Find tool for a task → Search by category

**Legacy documentation:** `tools-documentation.md` (older, less organized)

---

## 🎁 Customer Loyalty & Reviews (Yotpo)

### Yotpo Tools Reference
**Path:** `yotpo-tools-reference.md`

Tools for managing customer loyalty points and reviews:
- **yotpo_check_review.py** - Check if customers left reviews
- **yotpo_get_loyalty.py** - View customer loyalty history
- **yotpo_add_points.py** - Add or remove loyalty points

**When to use:**
- Check review status → `yotpo_check_review.py`
- View points balance → `yotpo_get_loyalty.py`
- Award or adjust points → `yotpo_add_points.py`

For complete documentation, see `yotpo-tools-reference.md`

---

## 📊 Analytics & Advertising

### Google Analytics 4 (MCP)
**Path:** `analytics/`

Live GA4 data via Google's official MCP server:
- **[GA4 MCP Tools Reference](./analytics/ga4-mcp-tools.md)** - Complete tool documentation for GA4 reporting
- **[GA4 Query Examples](./analytics/ga4-query-examples.md)** - Common report patterns and use cases

**Available Tools:**
- `get_account_summaries()` - List all properties
- `run_report()` - Custom reports with dimensions/metrics
- `run_realtime_report()` - Live visitor data (last 30 minutes)
- `get_dimensions()` / `get_metrics()` - Discover available fields

**When to use:**
- Website traffic analysis → `run_report()` with sessionSource dimension
- E-commerce performance → `run_report()` with purchaseRevenue metric
- Real-time monitoring → `run_realtime_report()` for current visitors
- Custom dimensions → `get_dimensions()` to discover fields

### Google Ads (MCP)
**Path:** `analytics/`

Campaign and ad data via Google's official MCP server:
- **[Google Ads MCP Tools Reference](./analytics/google-ads-mcp-tools.md)** - Complete GAQL documentation
- **[Google Ads GAQL Examples](./analytics/google-ads-examples.md)** - Sample queries for common tasks

**Available Tools:**
- `search(query, customer_id)` - Query ads data using GAQL
- `list_accessible_customers()` - Get available accounts

**GAQL Query Language:**
```sql
SELECT campaign.name, metrics.clicks, metrics.cost_micros
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
ORDER BY metrics.clicks DESC
```

**When to use:**
- Campaign performance → Query `campaign` resource
- Keyword analysis → Query `keyword_view` resource
- Budget tracking → Query with `metrics.cost_micros`
- Search terms → Query `search_term_view` resource

**Important:**
- Customer ID for iDrinkCoffee.com: `522-285-1423`
- Requires `GOOGLE_ADS_DEVELOPER_TOKEN` environment variable
- Cost values in micros (divide by 1,000,000 for dollars)

---

## 🔍 Shopify API & Technical

### Shopify API Learnings
**Path:** `shopify-api-learnings/`

- **[Adding Product Options](./shopify-api-learnings/adding-product-options.md)** - How to add variants, options, and selections

### ShopifyQL (Analytics Query Language)
**Path:** `shopifyql/`

> **API Availability Note:** Not all ShopifyQL datasets work via GraphQL API. Use `sales` and `sessions` datasets for API queries. The `orders`, `products`, `customers` datasets are Admin UI only.

- **[Overview](./shopifyql/shopifyql-overview.md)** - ⭐ Complete verified reference (API-accessible datasets)
- **[Syntax Reference](./shopifyql/syntax-reference.md)** - Query syntax, operators, functions
- **[Orders Dataset](./shopifyql/orders-dataset.md)** - ⚠️ Admin UI only, not API accessible
- **[Products Dataset](./shopifyql/products-dataset.md)** - ⚠️ Admin UI only, not API accessible
- **[Payment Attempts Dataset](./shopifyql/payment-attempts-dataset.md)** - Query payment data (Shopify Plus)
- **[Field Discovery](./shopifyql/field-discovery.md)** - Find available fields in datasets

**When to use:**
- Need analytics queries → `shopifyql-overview.md` (verified API columns)
- Sales reports → `sales` dataset via `FROM sales SHOW total_sales, product_title`
- Traffic analytics → `sessions` dataset via `FROM sessions SHOW sessions, referrer_source`

---

## 📋 Project Planning & Strategy

- **[Product Specs Standardization Plan](./product-specs-standardization-plan.md)** - Strategy for standardizing product specifications
- **[Q4 Content Refresh Plan](./q4-content-refresh-plan.md)** - Quarterly content strategy
- **[Inventory Fix Documentation (2025-08-08)](./2025-08-08-inventory-fix-documentation.md)** - Historical inventory issue and resolution

---

## 🔬 Product Specs Research

**Path:** `product-specs-research/`

Detailed technical specifications for specific products. Organized by category:

### Espresso Machines
- **Profitec Series** (`espresso-machines/profitec/`)
  - Pro 400, Pro 500 PID, Pro 600 Dual Boiler, Pro 800
  - Profitec Go series (Black, Red, Blue, Yellow)
  - Flow Control variants

### Grinders
**Path:** `grinders/`
- (Directory exists but currently empty)

**When to use:**
- Need exact specs for a specific product
- Creating listings for known brands/models
- Reference for metafield values

---

## 🛠️ Tools Reference

### Available Python Scripts
**Location:** `bash-tools/` (relative to backend directory)

Key scripts for product operations:
- **create_full_product.py** - Complete product creation with variants
- **search_products.py** - Search and filter products
- **update_pricing.py** - Batch pricing updates
- **update_inventory.py** - Inventory management
- **get_sales.py** - Sales reporting

**Usage pattern:**
```bash
python bash-tools/create_full_product.py \
  --title "Product Name" \
  --price 299.99 \
  --vendor "Brand Name" \
  --product-type "Category"
```

---

## 📖 Quick Reference for Common Tasks

### Creating a New Product
1. Read: `product-guidelines/09-new-product-workflow.md`
2. Verify: `product-guidelines/02-product-creation-basics.md`
3. For metafields: `product-guidelines/03-metafields-reference.md`
4. Execute: `python bash-tools/create_full_product.py ...`

### Updating Product Pricing
1. Read: `product-guidelines/` (pricing sections)
2. Execute: `python bash-tools/update_pricing.py ...`

### Product Search & Filtering
1. For API: `shopify-api-learnings/`
2. Execute: `python bash-tools/search_products.py ...`

### Analytics & Reports
1. Read: `shopifyql/shopifyql-overview.md` (verified API-accessible datasets)
2. Use datasets: `sales` (revenue, products, countries) or `sessions` (traffic, referrers)
3. Execute: `python bash-tools/analytics/analytics.py "FROM sales SHOW total_sales GROUP BY month SINCE -3m"`
4. For combined reports: `FROM sales, sessions SHOW total_sales, sessions GROUP BY day`

---

## 💡 Tips for Using This Documentation

1. **Start with the workflow docs** - They tie everything together
2. **Use INDEX.md as a map** - Don't memorize paths, just search here
3. **Technical references are detailed** - Full GraphQL schemas and examples included
4. **Tools documentation is in the scripts themselves** - Run with `--help` flag
5. **Update this index** when adding new documentation

---

## 📊 Documentation Statistics

- **Total markdown files:** 36
- **Product guidelines:** 9 core docs (~40K tokens)
- **Technical references:** 7 docs (API, ShopifyQL)
- **Analytics & Advertising:** 4 docs (GA4, Google Ads MCP)
- **Product specs:** 13+ specific product docs
- **Planning docs:** 3 strategic documents

---

*Last updated: 2025-10-13*
*For the EspressoBot Pydantic AI project*
