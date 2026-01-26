# Tools Index

Complete guide to all reusable tools in the iDrinkCoffee.com toolkit.

**Total Active Tools:** 87 Python scripts organized in subdirectories

**Location:** `backend/bash-tools/` (canonical location for all EspressoBot tools)

**Last Updated:** November 23, 2025

**Recent Consolidation:** 22 scripts consolidated into 6 unified tools (see Consolidated Tools section)

---

## Directory Structure

```
backend/bash-tools/
├── base.py              # Core ShopifyClient - imported by all scripts
├── __init__.py          # Package init
├── products/            # 18 scripts - Product CRUD operations
├── pricing/             # 7 scripts - Price and cost management
├── inventory/           # 11 scripts - Inventory & SkuVault
├── cms/                 # 24 scripts - Metaobjects & content
├── tags/                # 3 scripts - Tag management
├── publishing/          # 1 script - Channel publishing
├── analytics/           # 2 scripts - Reports & analytics
├── integrations/        # 8 scripts - Third-party (Recharge, Yotpo)
├── utilities/           # 7 scripts - Misc tools
├── core/                # 5 scripts - GraphQL tools & tests
├── metaobject_definitions/  # Schema JSON files
└── archive/             # Archived/deprecated scripts
```

---

## 🔀 Consolidated Tools (NEW)

These unified tools replace multiple legacy scripts:

### products/manage_status.py
**Replaces:** archive_products.py, unarchive_products.py, update_product_status.py, update_status.py
```bash
python products/manage_status.py --product BRE0001 --status ACTIVE
python products/manage_status.py --file products.txt --status ARCHIVED --dry-run
python products/manage_status.py --query "tag:clearance" --check
```

### utilities/copy_product.py
**Replaces:** copy_product_to_parts.py, copy_product_to_wholesale.py
```bash
python utilities/copy_product.py BRE0001 --store parts
python utilities/copy_product.py "product-handle" --store wholesale --dry-run
```

### publishing/publish.py
**Replaces:** publish_to_channels.py, publish_to_parts_channel.py, publish_to_parts_channel_fast.py
```bash
python publishing/publish.py --product BRE0001 --channels main
python publishing/publish.py --all --channels parts --fast
```

### inventory/manage_skuvault_pricing.py
**Replaces:** update_skuvault_price.py, update_skuvault_costs_bulk.py
```bash
python inventory/manage_skuvault_pricing.py --sku BRE0001 --price 299.99 --cost 150.00
python inventory/manage_skuvault_pricing.py --file costs.csv --cost-only
```

### inventory/inventory_analysis.py
**Replaces:** fast_reorder_check.py, quick_inventory_insights.py, smart_reorder_analysis.py
```bash
python inventory/inventory_analysis.py --mode quick
python inventory/inventory_analysis.py --mode reorder --vendor Breville --days 30
python inventory/inventory_analysis.py --mode deep --export-csv
```

### cms/manage_header_banner.py
**Replaces:** get_header_banner.py, update_header_banner.py, list_header_links.py, update_header_link.py
```bash
python cms/manage_header_banner.py get
python cms/manage_header_banner.py list-links
python cms/manage_header_banner.py update --position centre_link --link-id "gid://..."
```

### cms/manage_home_banner.py
**Replaces:** get_home_banner.py, list_home_banners.py, update_home_banner.py
```bash
python cms/manage_home_banner.py list
python cms/manage_home_banner.py get primary-banner
python cms/manage_home_banner.py update primary-banner --heading "New Sale" --cta "Shop Now"
```

---

## 🛍️ products/ (18 scripts)

### Product Creation & Setup
- **`create_full_product.py`** - REQUIRED FOR NEW PRODUCTS - Complete product creation
- **`create_product.py`** - Basic single-variant product creation
- **`create_combo.py`** - Machine+grinder combo products with image generation
- **`create_open_box.py`** - Create open box listings from existing products
- **`duplicate_product.py`** - Duplicate products using productDuplicate mutation

### Product Search & Retrieval
- **`search_products.py`** - Search with Shopify syntax, multiple output formats
- **`search_all_products_including_archived.py`** - Include archived in search
- **`get_product.py`** - Get product by ID, handle, SKU, or title
- **`fetch_all_active_products.py`** - Fetch all active products

### Product Updates
- **`manage_status.py`** - **CONSOLIDATED** - Change status (DRAFT/ACTIVE/ARCHIVED), archive/unarchive
- **`update_product_description.py`** - Update product descriptions
- **`relist_product.py`** - Update inventory and republish

### Product Features & Images
- **`manage_features_metaobjects.py`** - REQUIRED - Manage product features box
- **`manage_variant_links.py`** - Connect related products
- **`delete_product_images.py`** - Remove product images
- **`upload_product_image_staged.py`** - Upload images via staged uploads
- **`update_sku.py`** - Update product SKU
- **`update_variant_sku.py`** - Update variant SKU via REST API

---

## 💰 pricing/ (7 scripts)

- **`update_pricing.py`** - Update variant prices (price, compare-at, cost)
- **`bulk_price_update.py`** - Bulk update from CSV files
- **`update_costs_by_sku.py`** - Update costs by SKU
- **`update_usd_pricing.py`** - Update USD market prices
- **`manage_map_sales.py`** - Manage Breville MAP sales calendar
- **`manage_miele_sales.py`** - Manage Miele MAP sales
- **`manage_sale_end_dates.py`** - Control sale end date metafields

---

## 📦 inventory/ (11 scripts)

### SkuVault Integration
- **`upload_to_skuvault.py`** - Upload products to SkuVault
- **`update_skuvault_barcode.py`** - Update UPC/barcode
- **`manage_skuvault_pricing.py`** - **CONSOLIDATED** - Update prices/costs (single or bulk)
- **`update_skuvault_prices_v2.py`** - Update CSV with Shopify prices
- **`manage_skuvault_kits.py`** - Manage bundles/kits
- **`generate_skuvault_buffer_csv.py`** - Generate buffer import CSV
- **`generate_skuvault_buffer_csv_selective.py`** - Selective buffer CSV

### Inventory Analysis
- **`manage_inventory_policy.py`** - Toggle oversell (ALLOW/DENY)
- **`inventory_analysis.py`** - **CONSOLIDATED** - Quick insights, reorder, deep analysis
- **`inventory_movement_report.py`** - Movement and velocity reports (pandas)
- **`fetch_parts_costs.py`** - Fetch costs from parts store

---

## 🎨 cms/ (24 scripts)

### Generic Metaobject CRUD
- **`create_metaobject.py`** - Create any metaobject type
- **`update_metaobject.py`** - Update metaobject fields
- **`delete_metaobject.py`** - Delete metaobject by ID
- **`list_metaobjects.py`** - List metaobjects by type
- **`get_metaobject.py`** - Get metaobject details
- **`create_metaobject_type.py`** - Create metaobject definitions
- **`create_metaobject_instance.py`** - Create from JSON config
- **`enable_storefront_access.py`** - Enable Storefront API access

### Category Landing Pages
- **`create_empty_category_landing_page.py`** - Initialize landing page
- **`list_category_landing_pages.py`** - List all landing pages
- **`update_category_landing_page.py`** - Update landing page fields

### Hero Images
- **`upload_hero_image.py`** - Upload to Shopify Files API
- **`set_hero_image.py`** - Set hero image on landing page
- **`regenerate_hero_image.py`** - AI regenerate hero image
- **`list_shopify_files.py`** - List uploaded files

### Home Page & Header Banners
- **`manage_home_banner.py`** - **CONSOLIDATED** - List, get, update home banners
- **`manage_header_banner.py`** - **CONSOLIDATED** - Header banner & text_links

### Menus
- **`get_menu.py`** - Fetch menu structure (3 levels)
- **`parse_menu_patterns.py`** - Parse special menu patterns
- **`update_menu.py`** - Update menu structure

### Pages & FAQs
- **`create_page.py`** - Create/update Shopify pages
- **`update_page.py`** - Update page content
- **`manage_faq_items.py`** - Manage FAQ items

---

## 🏷️ tags/ (3 scripts)

- **`manage_tags.py`** - Add/remove tags on single product
- **`manage_tags_parallel.py`** - High-performance bulk tag operations
- **`fetch_all_tags.py`** - Fetch all unique tags with stats

---

## 📢 publishing/ (1 script)

- **`publish.py`** - **CONSOLIDATED** - Publish to main store channels or parts store

---

## 📊 analytics/ (2 scripts)

- **`analytics.py`** - Query ShopifyQL (sales, orders, products)
- **`fetch_all_store_orders.py`** - Fetch orders from all 3 stores

---

## 🔌 integrations/ (8 scripts)

### Recharge Subscriptions
- **`recharge_subscriptions.py`** - Fetch/filter subscriptions
- **`recharge_bundle_search.py`** - Search bundle subscriptions
- **`recharge_bundle_contents.py`** - Search bundles for SKUs
- **`get_bundle_customers_with_sku.py`** - Find bundle customers

### Yotpo
- **`yotpo_get_loyalty.py`** - Get loyalty points
- **`yotpo_add_points.py`** - Add loyalty points
- **`yotpo_check_review.py`** - Check review status

### Other
- **`pplx.py`** - Perplexity API CLI wrapper

---

## 🛠️ utilities/ (7 scripts)

- **`copy_product.py`** - **CONSOLIDATED** - Copy product to parts or wholesale store
- **`upload_pdf_to_shopify.py`** - Upload PDFs to CDN
- **`manage_redirects.py`** - Create/list/delete URL redirects
- **`manage_taxes_by_tag.py`** - Enable/disable taxes by tag
- **`audit_draft_order_tags.py`** - Audit draft order tags
- **`send_review_request.py`** - Send Yotpo review requests
- **`run_with_timeout.py`** - Run commands with timeout

---

## 🔧 core/ (6 scripts)

- **`graphql_query.py`** - Generic GraphQL query executor
- **`graphql_mutation.py`** - Generic GraphQL mutation executor
- **`get_collection.py`** - Fetch collection details
- **`hide_collection.py`** - Hide collection from all channels
- **`test_connection.py`** - Test Shopify API connection
- **`test_openrouter.py`** - Test OpenRouter API

---

## 📁 Other Directories

### metaobject_definitions/
Schema JSON files for metaobject types (category_landing_page, faq_section, etc.)

### archive/
Archived scripts organized by project:
- `consolidated/` - Scripts replaced by consolidated tools (22 scripts)
- `autumn2025/` - Autumn 2025 sales scripts
- `bfcm_2024/` - Black Friday 2024 analysis
- `bfcm_2025/` - Black Friday 2025 collections
- `coffee_day_2025/` - Coffee Day promotion
- `deprecated/` - Superseded versions
- `one_time_fixes/` - One-off fixes
- `openbox_ob2507/` - July 2025 openbox
- `parts_store_setup/` - Parts store setup
- `pro_ecm_migration/` - PRO to ECM migration
- `product_specific/` - Product-specific scripts
- `temp_fixes/` - Temporary fixes
- `usd_market_setup/` - USD market config

---

## Quick Reference: Most Used Tools

1. **`products/search_products.py`** - Search and filter products
2. **`pricing/update_pricing.py`** - Update prices and costs
3. **`tags/manage_tags.py`** - Add/remove product tags
4. **`products/manage_features_metaobjects.py`** - REQUIRED for new products
5. **`products/create_full_product.py`** - Create complete products
6. **`products/manage_status.py`** - Archive/unarchive/status changes
7. **`publishing/publish.py`** - Publish to all channels
8. **`analytics/analytics.py`** - Query sales and analytics
9. **`products/get_product.py`** - Get detailed product info
10. **`pricing/manage_map_sales.py`** - Manage MAP sales

---

## Running Scripts

All scripts can be run from the `backend/bash-tools/` directory:

```bash
cd backend/bash-tools

# Products
python products/search_products.py "tag:sale" --limit 20
python products/get_product.py BRE0001 --metafields
python products/manage_status.py --product BRE0001 --status ARCHIVED

# Pricing
python pricing/update_pricing.py --sku BRE0001 --price 299.99

# CMS
python cms/manage_home_banner.py list
python cms/manage_header_banner.py get

# Publishing
python publishing/publish.py --product BRE0001 --channels main

# Inventory Analysis
python inventory/inventory_analysis.py --mode reorder --days 30

# All scripts support --help
python products/manage_status.py --help
```

---

## API Version

All scripts use **Shopify Admin API 2025-10** (migrated November 2025).
