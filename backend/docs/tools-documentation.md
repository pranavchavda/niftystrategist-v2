# iDrinkCoffee.com Tools Documentation

This document contains comprehensive documentation for all tools available in the iDrinkCoffee.com e-commerce management system. These Python tools interact with the Shopify Admin API and other e-commerce platforms.

**Total Active Tools:** 86 Python scripts organized in subdirectories

**Location:** `backend/bash-tools/` (canonical location for all EspressoBot tools)

**Last Updated:** November 23, 2025

## Table of Contents

1. [Quick Start](#quick-start)
2. [Directory Structure](#directory-structure)
3. [Consolidated Tools](#consolidated-tools)
4. [Available Tools by Category](#available-tools-by-category)
5. [Common Workflows](#common-workflows)
6. [Product Features System](#product-features-system)
7. [GraphQL Examples](#graphql-examples)
8. [Product Conventions](#product-conventions-idrinkcoffeecom)
9. [Error Handling](#error-handling)
10. [Best Practices](#best-practices)
11. [Temporary Scripts for One-Off Tasks](#temporary-scripts-for-one-off-tasks)
12. [Advanced Usage](#advanced-usage)
13. [Troubleshooting](#troubleshooting)
14. [Security Notes](#security-notes)

## Quick Start

1. **Set Environment Variables** (required):
```bash
export SHOPIFY_SHOP_URL="idrinkcoffee.myshopify.com"  # NO https:// prefix!
export SHOPIFY_ACCESS_TOKEN="shpat_00000000000000000000000000000000"
```

2. **Test Connection**:
```bash
cd backend/bash-tools
python core/test_connection.py
```

3. **Run Scripts from bash-tools directory**:
```bash
cd backend/bash-tools
python products/search_products.py "tag:sale" --limit 20
python pricing/update_pricing.py --sku BRE0001 --price 299.99
```

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

## Consolidated Tools

These unified tools replace multiple legacy scripts (22 scripts consolidated into 6):

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

## Available Tools by Category

### Products (18 scripts)

#### Product Creation & Setup
- **`products/create_full_product.py`** - REQUIRED FOR NEW PRODUCTS - Complete product creation
- **`products/create_product.py`** - Basic single-variant product creation
- **`products/create_combo.py`** - Machine+grinder combo products with image generation
- **`products/create_open_box.py`** - Create open box listings from existing products
- **`products/duplicate_product.py`** - Duplicate products using productDuplicate mutation

#### Product Search & Retrieval
- **`products/search_products.py`** - Search with Shopify syntax, multiple output formats
- **`products/search_all_products_including_archived.py`** - Include archived in search
- **`products/get_product.py`** - Get product by ID, handle, SKU, or title
- **`products/fetch_all_active_products.py`** - Fetch all active products

#### Product Updates
- **`products/manage_status.py`** - **CONSOLIDATED** - Change status (DRAFT/ACTIVE/ARCHIVED), archive/unarchive
- **`products/update_product_description.py`** - Update product descriptions
- **`products/relist_product.py`** - Update inventory and republish

#### Product Features & Images
- **`products/manage_features_metaobjects.py`** - REQUIRED - Manage product features box
- **`products/manage_variant_links.py`** - Connect related products
- **`products/delete_product_images.py`** - Remove product images
- **`products/upload_product_image_staged.py`** - Upload images via staged uploads
- **`products/update_sku.py`** - Update product SKU
- **`products/update_variant_sku.py`** - Update variant SKU via REST API

### Pricing (7 scripts)

- **`pricing/update_pricing.py`** - Update variant prices (price, compare-at, cost)
- **`pricing/bulk_price_update.py`** - Bulk update from CSV files
- **`pricing/update_costs_by_sku.py`** - Update costs by SKU
- **`pricing/update_usd_pricing.py`** - Update USD market prices
- **`pricing/manage_map_sales.py`** - Manage Breville MAP sales calendar
- **`pricing/manage_miele_sales.py`** - Manage Miele MAP sales
- **`pricing/manage_sale_end_dates.py`** - Control sale end date metafields

### Inventory (11 scripts)

#### SkuVault Integration
- **`inventory/upload_to_skuvault.py`** - Upload products to SkuVault
- **`inventory/update_skuvault_barcode.py`** - Update UPC/barcode
- **`inventory/manage_skuvault_pricing.py`** - **CONSOLIDATED** - Update prices/costs (single or bulk)
- **`inventory/update_skuvault_prices_v2.py`** - Update CSV with Shopify prices
- **`inventory/manage_skuvault_kits.py`** - Manage bundles/kits
- **`inventory/generate_skuvault_buffer_csv.py`** - Generate buffer import CSV
- **`inventory/generate_skuvault_buffer_csv_selective.py`** - Selective buffer CSV

#### Inventory Analysis
- **`inventory/manage_inventory_policy.py`** - Toggle oversell (ALLOW/DENY)
- **`inventory/inventory_analysis.py`** - **CONSOLIDATED** - Quick insights, reorder, deep analysis
- **`inventory/inventory_movement_report.py`** - Movement and velocity reports (pandas)
- **`inventory/fetch_parts_costs.py`** - Fetch costs from parts store

### CMS (24 scripts)

#### Generic Metaobject CRUD
- **`cms/create_metaobject.py`** - Create any metaobject type
- **`cms/update_metaobject.py`** - Update metaobject fields
- **`cms/delete_metaobject.py`** - Delete metaobject by ID
- **`cms/list_metaobjects.py`** - List metaobjects by type
- **`cms/get_metaobject.py`** - Get metaobject details
- **`cms/create_metaobject_type.py`** - Create metaobject definitions
- **`cms/create_metaobject_instance.py`** - Create from JSON config
- **`cms/enable_storefront_access.py`** - Enable Storefront API access

#### Category Landing Pages
- **`cms/create_empty_category_landing_page.py`** - Initialize landing page
- **`cms/list_category_landing_pages.py`** - List all landing pages
- **`cms/update_category_landing_page.py`** - Update landing page fields

#### Hero Images
- **`cms/upload_hero_image.py`** - Upload to Shopify Files API
- **`cms/set_hero_image.py`** - Set hero image on landing page
- **`cms/regenerate_hero_image.py`** - AI regenerate hero image
- **`cms/list_shopify_files.py`** - List uploaded files

#### Home Page & Header Banners
- **`cms/manage_home_banner.py`** - **CONSOLIDATED** - List, get, update home banners
- **`cms/manage_header_banner.py`** - **CONSOLIDATED** - Header banner & text_links

#### Menus
- **`cms/get_menu.py`** - Fetch menu structure (3 levels)
- **`cms/parse_menu_patterns.py`** - Parse special menu patterns
- **`cms/update_menu.py`** - Update menu structure

#### Pages & FAQs
- **`cms/create_page.py`** - Create/update Shopify pages
- **`cms/update_page.py`** - Update page content
- **`cms/manage_faq_items.py`** - Manage FAQ items

### Tags (3 scripts)

- **`tags/manage_tags.py`** - Add/remove tags on single product
- **`tags/manage_tags_parallel.py`** - High-performance bulk tag operations
- **`tags/fetch_all_tags.py`** - Fetch all unique tags with stats

### Publishing (1 script)

- **`publishing/publish.py`** - **CONSOLIDATED** - Publish to main store channels or parts store

### Analytics (2 scripts)

- **`analytics/analytics.py`** - Query ShopifyQL (sales, orders, products)
- **`analytics/fetch_all_store_orders.py`** - Fetch orders from all 3 stores

### Integrations (8 scripts)

#### Recharge Subscriptions
- **`integrations/recharge_subscriptions.py`** - Fetch/filter subscriptions
- **`integrations/recharge_bundle_search.py`** - Search bundle subscriptions
- **`integrations/recharge_bundle_contents.py`** - Search bundles for SKUs
- **`integrations/get_bundle_customers_with_sku.py`** - Find bundle customers

#### Yotpo
- **`integrations/yotpo_get_loyalty.py`** - Get loyalty points
- **`integrations/yotpo_add_points.py`** - Add loyalty points
- **`integrations/yotpo_check_review.py`** - Check review status

#### Other
- **`integrations/pplx.py`** - Perplexity API CLI wrapper

### Utilities (7 scripts)

- **`utilities/copy_product.py`** - **CONSOLIDATED** - Copy product to parts or wholesale store
- **`utilities/upload_pdf_to_shopify.py`** - Upload PDFs to CDN
- **`utilities/manage_redirects.py`** - Create/list/delete URL redirects
- **`utilities/manage_taxes_by_tag.py`** - Enable/disable taxes by tag
- **`utilities/audit_draft_order_tags.py`** - Audit draft order tags
- **`utilities/send_review_request.py`** - Send Yotpo review requests
- **`utilities/run_with_timeout.py`** - Run commands with timeout

### Core (5 scripts)

- **`core/graphql_query.py`** - Generic GraphQL query executor
- **`core/graphql_mutation.py`** - Generic GraphQL mutation executor
- **`core/get_collection.py`** - Fetch collection details
- **`core/test_connection.py`** - Test Shopify API connection
- **`core/test_openrouter.py`** - Test OpenRouter API

### Task Management with Taskwarrior
Taskwarrior (v3.4.1) is installed and syncs with Google. EspressoBot can help manage tasks and reminders using these commands:
- `task add <description>` - Add a new task
- `task list` - View current tasks
- `task <ID> done` - Mark task as complete
- `task <ID> modify <changes>` - Modify task details
- `task <ID> delete` - Delete a task
- `task sync` - Sync with Google
- `task due:today` - View tasks due today
- `task due:tomorrow` - View tasks due tomorrow
- `task active` - View active tasks

Common task attributes:
- `due:YYYY-MM-DD` - Set due date
- `priority:H/M/L` - Set priority (High/Medium/Low)
- `project:<name>` - Assign to project
- `+tag` - Add tags
- `wait:YYYY-MM-DD` - Hide until date

Example: `task add "Review Q1 sales data" due:2025-06-20 priority:H project:analytics`

## Common Workflows

### 1. Product Search and Update
```bash
cd backend/bash-tools

# Search for products
python products/search_products.py "tag:sale status:active"

# Get specific product details
python products/get_product.py "gid://shopify/Product/123456789" --metafields

# Update pricing
python pricing/update_pricing.py --sku BRE0001 --price 299.99 --compare-at 399.99

# Add tags
python tags/manage_tags.py --action add --product-id "123456789" --tags "sale,featured"

# Fetch all unique tags
python tags/fetch_all_tags.py                                      # List all tags alphabetically
python tags/fetch_all_tags.py --output markdown --save tags.md     # Generate comprehensive report
python tags/fetch_all_tags.py --output json                        # Get JSON format
python tags/fetch_all_tags.py --filter "icon-"                     # Filter specific tags

# Toggle oversell settings
python inventory/manage_inventory_policy.py --identifier "SKU123" --policy deny

# Update product status (consolidated tool)
python products/manage_status.py --product "SKU123" --status ACTIVE
python products/manage_status.py --product "product-handle" --status DRAFT

# Manage product features (ALWAYS use metaobjects for new products)
python products/manage_features_metaobjects.py --product "profitec-move" --list
python products/manage_features_metaobjects.py --product "PRO-MOVE-B" --add "E61 Group Head" "Commercial-grade temperature stability"
python products/manage_features_metaobjects.py --product "7779055304738" --update 2 "Updated Feature" "New description"
python products/manage_features_metaobjects.py --product "product-handle" --remove 3
python products/manage_features_metaobjects.py --product "SKU123" --reorder 3,1,2,4,5

# IMPORTANT: Features must be added one at a time, not as a batch
# Correct:
python products/manage_features_metaobjects.py --product "7991004168226" --add "SCA Certified" "Meets specialty coffee standards"
python products/manage_features_metaobjects.py --product "7991004168226" --add "Custom Brewing" "Control temperature and flow rate"

# Incorrect (will combine all into one feature):
python products/manage_features_metaobjects.py --product "7991004168226" --add "Feature 1" "Desc 1" "Feature 2" "Desc 2"
```

### 2. Creating Products
```bash
cd backend/bash-tools

# Simple product (basic tool)
python products/create_product.py --title "Product Name" --vendor "Brand" --type "Category" --price "99.99"

# Complete product with all metafields (recommended)
python products/create_full_product.py \
  --title "DeLonghi Dedica Style" \
  --vendor "DeLonghi" \
  --type "Espresso Machines" \
  --price "249.99" \
  --sku "EC685M" \
  --cost "150.00" \
  --buybox "Experience cafe-quality espresso in a compact design..." \
  --tags "icon-Steam-Wand,icon-Single-Boiler"

# IMPORTANT: Features should be added AFTER product creation using manage_features_metaobjects.py
# The create_full_product.py tool does NOT support features parameter

# From JSON configuration file
python products/create_full_product.py --from-json product_config.json

# After creating the product, add features one by one:
python products/manage_features_metaobjects.py --product "EC685M" --add "15 Bar Pressure" "Professional-grade extraction pressure"
python products/manage_features_metaobjects.py --product "EC685M" --add "Thermoblock Heating" "Rapid heat-up time for quick brewing"
```

### 3. Open Box Listings
```bash
cd backend/bash-tools

# Create with automatic 10% discount
python products/create_open_box.py --identifier "EC685M" --serial "ABC123" --condition "Excellent"

# Create with specific discount percentage
python products/create_open_box.py --identifier "BES870XL" --serial "XYZ789" --condition "Good" --discount 20

# Create with specific price
python products/create_open_box.py --identifier "7234567890123" --serial "DEF456" --condition "Fair" --price 899.99

# Add a note about condition
python products/create_open_box.py --identifier "delonghi-dedica" --serial "GHI789" --condition "Scratch & Dent" --discount 25 --note "Minor cosmetic damage on side panel"

# Create and publish immediately
python products/create_open_box.py --identifier "EC685M" --serial "JKL012" --condition "Like New" --discount 5 --publish
```

The tool uses `productDuplicate` to efficiently copy all product data including:
- All images and media
- All metafields
- SEO settings
- Product description (with optional note prepended)

It automatically:
- Generates SKU: `OB-{YYMM}-{Serial}-{OriginalSKU}`
- Formats title: `{Original Title} |{Serial}| - {Condition}`
- Adds tags: `open-box`, `ob-{YYMM}`
- Sets status to DRAFT (unless --publish is used)

### 4. Creating Combo Products
```bash
cd backend/bash-tools

# Create single combo with fixed discount
python products/create_combo.py --product1 breville-barista-express --product2 eureka-mignon-specialita --discount 200

# Create combo with percentage discount
python products/create_combo.py --product1 BES870XL --product2 EUREKA-SPEC --discount-percent 15

# Create combo with custom SKU suffix and publish
python products/create_combo.py --product1 7234567890123 --product2 9876543210987 --sku-suffix A1 --publish

# Create combo with custom prefix and serial number
python products/create_combo.py --product1 BES870XL --product2 EUREKA-SPEC --prefix CD25 --serial 001

# Create multiple combos from CSV
python products/create_combo.py --from-csv combos.csv

# Generate sample CSV template
python products/create_combo.py --sample
```

### 5. Bulk Operations
```bash
cd backend/bash-tools

# Bulk price update from CSV
python pricing/bulk_price_update.py price_updates.csv

# Preview price changes (dry run)
python pricing/bulk_price_update.py price_updates.csv --dry-run

# Create sample CSV template
python pricing/bulk_price_update.py --sample
```

### 6. SkuVault Integration
```bash
cd backend/bash-tools

# Upload single product to SkuVault
python inventory/upload_to_skuvault.py --sku "COFFEE-001"

# Upload multiple products (comma-separated)
python inventory/upload_to_skuvault.py --sku "COFFEE-001,GRINDER-002,MACHINE-003"

# Update price and cost (consolidated tool)
python inventory/manage_skuvault_pricing.py --sku "BEZ-LUCE" --price 2499.00 --cost 1177.50

# Bulk cost updates from CSV
python inventory/manage_skuvault_pricing.py --file costs.csv --cost-only

# Generate buffer CSV for SkuVault import
python inventory/generate_skuvault_buffer_csv.py
python inventory/generate_skuvault_buffer_csv.py --output my_buffers.csv --channel "Parts Site"
```

### 7. URL Redirect Management
```bash
cd backend/bash-tools

# Create a redirect
python utilities/manage_redirects.py --action create --from "/old-product" --to "/new-product"

# List all redirects
python utilities/manage_redirects.py --action list

# Delete a redirect
python utilities/manage_redirects.py --action delete --id "gid://shopify/UrlRedirect/123456789"
```

### 8. MAP Sales Management
```bash
cd backend/bash-tools

# Check what sales should be active today
python pricing/manage_map_sales.py check

# Check sales for a specific date
python pricing/manage_map_sales.py check --date 2025-07-11

# Apply sales with dry run (preview changes)
python pricing/manage_map_sales.py --dry-run apply

# Apply sales for real
python pricing/manage_map_sales.py apply

# Revert sales when they end
python pricing/manage_map_sales.py revert "11 Jul - 17 Jul"

# Show all sale periods in calendar
python pricing/manage_map_sales.py summary
```

### 9. Publishing to Channels
```bash
cd backend/bash-tools

# Publish to main store (consolidated tool)
python publishing/publish.py --product "EC685M" --channels main

# Publish to parts store
python publishing/publish.py --product "BES870XL" --channels parts

# Fast bulk publish
python publishing/publish.py --all --channels parts --fast
```

### 10. Sale End Date Management
```bash
cd backend/bash-tools

# List products with sale end dates
python pricing/manage_sale_end_dates.py list --search "tag:sale"

# Set sale end date for specific product
python pricing/manage_sale_end_dates.py set --product-id "gid://shopify/Product/123" --date "2025-07-24"

# Clear sale end dates for products
python pricing/manage_sale_end_dates.py clear --search "tag:mielesale"
```

### 11. Inventory Analysis
```bash
cd backend/bash-tools

# Quick inventory insights
python inventory/inventory_analysis.py --mode quick

# Reorder analysis for specific vendor
python inventory/inventory_analysis.py --mode reorder --vendor Breville --days 30

# Deep analysis with CSV export
python inventory/inventory_analysis.py --mode deep --export-csv
```

### 12. CMS Banner Management
```bash
cd backend/bash-tools

# Home banners (consolidated tool)
python cms/manage_home_banner.py list
python cms/manage_home_banner.py get primary-banner
python cms/manage_home_banner.py update primary-banner --heading "New Sale" --cta "Shop Now"

# Header banner (consolidated tool)
python cms/manage_header_banner.py get
python cms/manage_header_banner.py list-links
python cms/manage_header_banner.py update --position centre_link --link-id "gid://..."
```

### 13. Store Copy Operations
```bash
cd backend/bash-tools

# Copy product to parts store (consolidated tool)
python utilities/copy_product.py BRE0001 --store parts

# Copy product to wholesale store with dry run
python utilities/copy_product.py "product-handle" --store wholesale --dry-run
```

## Product Features System

### IMPORTANT: JSON Features are Deprecated
The JSON-based features system is **DEPRECATED** and should NOT be used for new products. All new products MUST use the metaobjects-based features system.

### Using the Metaobjects Features System
Product features are stored as metaobjects and linked to products via the `content.product_features` metafield. Features must be added **one at a time** after product creation:

```bash
cd backend/bash-tools

# List current features
python products/manage_features_metaobjects.py --product "SKU123" --list

# Add features (one at a time - this is critical!)
python products/manage_features_metaobjects.py --product "7991004168226" --add "SCA Golden Cup Certified" "Meets Specialty Coffee Association standards"
python products/manage_features_metaobjects.py --product "7991004168226" --add "Customizable Brewing" "Control temperature, bloom time, and flow rate"

# Update a feature (by position number)
python products/manage_features_metaobjects.py --product "SKU123" --update 2 "Updated Title" "New description"

# Remove a feature (by position number)
python products/manage_features_metaobjects.py --product "SKU123" --remove 3

# Reorder features
python products/manage_features_metaobjects.py --product "SKU123" --reorder 3,1,2,4,5
```

### Common Pitfalls to Avoid
1. **Do NOT use manage_features_json.py for new products** - it's deprecated
2. **Do NOT try to add multiple features in one command** - they will be combined into a single feature
3. **Do NOT use the --features parameter in create_full_product.py** - it doesn't exist
4. **Always add features AFTER creating the product**, not during creation

### Migrating Legacy Products
If you encounter a product still using the JSON features system, migrate it:
```bash
python products/manage_features_metaobjects.py --product "product-handle" --migrate-from-json
```

## GraphQL Examples

### Query Examples
```bash
cd backend/bash-tools

# Get shop info
python core/graphql_query.py '{ shop { name currencyCode } }'

# Get products with variants
python core/graphql_query.py '{
  products(first: 10, query: "status:active") {
    edges {
      node {
        id
        title
        variants(first: 5) {
          edges {
            node {
              id
              price
              sku
            }
          }
        }
      }
    }
  }
}'
```

### Mutation Examples
```bash
# Update product SEO
python core/graphql_mutation.py \
  --mutation 'mutation updateSEO($input: ProductInput!) {
    productUpdate(input: $input) {
      product { id }
      userErrors { field message }
    }
  }' \
  --variables '{
    "input": {
      "id": "gid://shopify/Product/123",
      "seo": {
        "title": "SEO Title",
        "description": "SEO Description"
      }
    }
  }'
```

## Product Conventions (iDrinkCoffee.com)

### Product Naming
- Format: `{Brand} {Product Name} {Descriptors}`
- Example: "Breville Barista Express Espresso Machine - Brushed Stainless Steel"

### Tagging System

**Important**: Use `python tags/fetch_all_tags.py` to see all 2000+ existing tags before adding new ones!

#### Tag Categories:
- **Product Type**: `espresso-machines`, `grinders`, `accessories` (lowercase)
- **Brand**: Lowercase vendor name (e.g., `breville`, `delonghi`, `jura`, `bezzera`)
- **Warranty**:
  - `WAR-COM` - Commercial warranty
  - `WAR-ACC` - Accessories warranty
  - `WAR-CON` - Consumables warranty
  - `WAR-PAR` - Parts warranty (small parts only)
  - `WAR-VIM` - VIM eligible products
  - `WAR-FIN`, `WAR-GC`, `WAR-GLA`, `WAR-SG` - Other warranty types
- **Navigation Categories**: `NC_EspressoMachines`, `NC_Grinders`, `NC_Accessories`
- **Icons**: `icon-pid`, `icon-e61`, `icon-2l-boiler`, `icon-4l-tank` (lowercase)
- **Price Ranges**: `under-50`, `under-100`, `over-900`, `over-2500`
- **Shipping**: `shipping-nis-{timeframe}` (many outdated ones exist - avoid creating new ones)
- **Combos**: `combine-save-3perc`, `combine-save-4perc`
- **Special**: `not-us-eg`, `consumer`, `commercial`, `prosumer`, `vim-espresso-machine`
- **Status**: `clearance`, `sale`, `featured`, `new-arrival`

### Open Box Convention
- **SKU**: `OB-{YYMM}-{Serial}-{OriginalSKU}`
- **Title**: `{Original Title} |{Serial}| - {Condition}`
- **Tags**: Auto-added `open-box`, `ob-YYMM`

### Metafields
- **Namespace**: `content`
- **Common Keys**:
  - `features_box` - Product features HTML
  - `faqs` - FAQ accordion HTML
  - `buy_box` - Purchase information
  - `technical_specifications` - Specs table

## Error Handling

All tools follow these patterns:
1. Validate inputs before API calls
2. Check for GraphQL userErrors in responses
3. Provide clear error messages
4. Support multiple identifier formats (ID, GID, SKU, handle, title)
5. Exit with appropriate codes (0=success, 1=error)

## Best Practices

1. **Always test with --dry-run** before running bulk operations
2. **Use DRAFT status** when creating products
3. **Include field selections** in GraphQL queries for object types
4. **Check userErrors** in mutation responses
5. **Use proper GID format** for Shopify IDs: `gid://shopify/Product/123456`
6. **Follow naming conventions** for consistency
7. **Document changes** in commit messages
8. **Run from backend/bash-tools/** directory for proper imports

## Temporary Scripts for One-Off Tasks

When you need to create a script for a one-time task (data migration, bulk fix, special promotion, etc.), follow this workflow:

### 1. Create in the `temp/` Directory
```bash
cd backend/bash-tools
mkdir -p temp  # Create if doesn't exist
```

All temporary/one-off scripts should be created in `backend/bash-tools/temp/`:
```bash
# Example: Create a script to fix a specific batch of products
touch temp/fix_breville_costs_nov2025.py
```

### 2. Script Template
```python
#!/usr/bin/env python3
"""
One-off script: Fix Breville costs for November 2025 promotion
Created: 2025-11-23
Author: EspressoBot
Purpose: Update costs for specific SKUs affected by supplier price change

IMPORTANT: This is a temporary script. Move to archive/ when complete.
"""
import sys
sys.path.insert(0, '..')  # Import from parent bash-tools directory
from base import ShopifyClient

def main():
    client = ShopifyClient()
    # Your one-off logic here
    pass

if __name__ == "__main__":
    main()
```

### 3. Run from the `temp/` Directory
```bash
cd backend/bash-tools/temp
python fix_breville_costs_nov2025.py --dry-run  # Always test first
python fix_breville_costs_nov2025.py            # Run for real
```

### 4. Archive When Complete
Once the task is done and verified, move the script to the appropriate archive subdirectory:

```bash
cd backend/bash-tools
mv temp/fix_breville_costs_nov2025.py archive/one_time_fixes/
```

### Archive Subdirectories
The `archive/` directory is organized by project/purpose:
- `archive/consolidated/` - Scripts replaced by consolidated tools
- `archive/one_time_fixes/` - General one-off fixes
- `archive/product_specific/` - Product-specific scripts
- `archive/temp_fixes/` - Temporary workarounds
- `archive/deprecated/` - Superseded script versions
- `archive/bfcm_2024/`, `archive/bfcm_2025/` - Black Friday campaigns
- `archive/autumn2025/`, `archive/coffee_day_2025/` - Seasonal promotions
- `archive/pro_ecm_migration/` - Migration projects
- `archive/parts_store_setup/`, `archive/usd_market_setup/` - Store setup scripts

### Best Practices for Temporary Scripts
1. **Always include a docstring** with date, purpose, and author
2. **Use descriptive filenames** with date context (e.g., `fix_issue_nov2025.py`)
3. **Test with --dry-run** before running destructive operations
4. **Log your actions** for audit trail
5. **Move to archive/** immediately after completion - don't leave scripts in `temp/`
6. **Never delete** - archive instead, you may need to reference or rerun later

### Why This Matters
- Keeps the main tool directories clean and focused on reusable tools
- Provides historical record of one-off operations
- Makes it easy to find and adapt previous scripts for similar tasks
- Prevents confusion about which scripts are actively maintained

## Advanced Usage

### Custom Scripts
Create custom Python scripts that import from the bash-tools:

```python
import sys
sys.path.insert(0, 'backend/bash-tools')

from products.search_products import search
from pricing.update_pricing import update_price
from tags.manage_tags import add_tags

# Find sale items and update pricing
products = search("tag:sale")
for product in products:
    for variant in product['variants']:
        update_price(
            product_id=product['id'],
            variant_id=variant['id'],
            price=variant['price'] * 0.9  # 10% off
        )
    add_tags(product['id'], ['flash-sale'])
```

### Environment Management
Use `.env` file for local development:
```bash
SHOPIFY_SHOP_URL=idrinkcoffee.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxx
DEBUG=true
```

## Troubleshooting

### Common Issues

1. **401 Unauthorized**: Check your access token and permissions
2. **400 Bad Request**: Verify GraphQL syntax and field selections
3. **Product Not Found**: Try different identifiers (ID, SKU, handle)
4. **Rate Limiting**: Add delays between bulk operations
5. **Import Errors**: Make sure you're running from `backend/bash-tools/` directory

### Debug Mode
Set `DEBUG=true` to see detailed API requests and responses.

### Getting Help
- Check tool help: `python products/search_products.py --help`
- API Reference: https://shopify.dev/docs/api/admin-graphql
- Use the shopify-dev MCP server's tools for graphql introspection
- Use `integrations/pplx.py` for quick answers when stuck

## Security Notes

- Never commit `.env` files or credentials
- Use read-only tokens when possible
- Validate all inputs before API calls
- Log operations for audit trail

## API Version

All scripts use **Shopify Admin API 2025-10** (migrated November 2025).

## Rule of Thumb

If, when using a tool, or running a graphql query for shopify, you get an error, first, use the shopify-dev mcp server to look up the correct syntax, never try again before you look it up first, next use its introspection tool to verify and only retry afterwards. If it was a tool that threw an error, fix the tool so future tool calls don't have this issue.
