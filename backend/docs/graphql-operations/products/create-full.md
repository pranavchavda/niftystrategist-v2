# Create Full Product

Create a complete, production-ready product with all metafields, tags, inventory settings, and channel publishing. This is the recommended method for creating products that follow iDrinkCoffee.com conventions.

## Use Cases
- Create fully-configured products following iDC conventions
- Add products with custom metafields (buy box, FAQs, tech specs)
- Create products with automatic tag generation
- Set up products with proper inventory tracking and costs
- Publish products to all sales channels

## Workflow Overview

The `create_full_product.py` script follows a multi-step workflow:

1. **Create Product** - Basic product with title, vendor, type, description
2. **Update Variant Details** - Set SKU, cost (COGS), weight in one operation
3. **Update Variant Price** - Set price, compare-at price, inventory policy
4. **Add Metafields** - Custom data (buy box, FAQs, tech specs, etc.)
5. **Add Tags** - Auto-generated + custom tags
6. **Publish to Channels** - Make product available on all channels (remains DRAFT status)

## GraphQL Operations

### 1. Create Product

```graphql
mutation createProduct($input: ProductInput!) {
  productCreate(input: $input) {
    product {
      id
      title
      handle
      variants(first: 1) {
        edges {
          node {
            id
            inventoryItem {
              id
            }
          }
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

### 2. Update Variant Details (SKU, Cost, Weight)

```graphql
mutation updateVariant($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      id
      sku
      inventoryItem {
        unitCost {
          amount
        }
        measurement {
          weight {
            value
            unit
          }
        }
        tracked
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

### 3. Add Metafields

```graphql
mutation updateProduct($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
    }
    userErrors {
      field
      message
    }
  }
}
```

### 4. Add Tags

```graphql
mutation addTags($id: ID!, $tags: [String!]!) {
  tagsAdd(id: $id, tags: $tags) {
    node {
      id
    }
    userErrors {
      field
      message
    }
  }
}
```

### 5. Update Inventory Settings

```graphql
mutation updateInventoryItem($id: ID!, $input: InventoryItemInput!) {
  inventoryItemUpdate(id: $id, input: $input) {
    inventoryItem {
      id
      tracked
    }
    userErrors {
      field
      message
    }
  }
}
```

### 6. Publish to Channels

```graphql
mutation publishProduct($input: ProductPublishInput!) {
  productPublish(input: $input) {
    product {
      id
    }
    userErrors {
      field
      message
    }
  }
}
```

## Command-Line Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| --title | String | Yes | Product title |
| --vendor | String | Yes | Product vendor/brand |
| --type | String | Yes | Product type/category |
| --price | Decimal | Yes | Product price |
| --description | String | No | Product description (HTML) |
| --handle | String | No | URL handle (auto-generated if not provided) |
| --sku | String | No | Product SKU |
| --cost | Decimal | No | Cost of goods (COGS) |
| --weight | Float | No | Product weight in grams |
| --compare-at | Decimal | No | Compare at price (MSRP) |
| --buybox | String | No | Buy box content (metafield) |
| --faqs | JSON | No | FAQs JSON array |
| --tech-specs | JSON | No | Technical specifications JSON |
| --variant-preview | String | No | Variant preview name (e.g., "Black") |
| --sale-end | String | No | Sale end date (ISO format) |
| --seasonal | Flag | No | Mark as seasonal coffee |
| --tags | String | No | Additional comma-separated tags |
| --status | Enum | No | DRAFT or ACTIVE (default: DRAFT) |
| --no-auto-tags | Flag | No | Skip automatic tag generation |
| --from-json | String | No | Load all settings from JSON file |
| --dry-run | Flag | No | Preview without creating |

## Examples

### Basic Product

```bash
python products/create_full_product.py \
  --title "Breville Barista Express" \
  --vendor "Breville" \
  --type "Espresso Machines" \
  --price "699.99" \
  --sku "BES870XL" \
  --cost "450.00"
```

### Product with Metafields

```bash
python products/create_full_product.py \
  --title "DeLonghi Dedica" \
  --vendor "DeLonghi" \
  --type "Espresso Machines" \
  --price "249.99" \
  --sku "EC685M" \
  --cost "150.00" \
  --buybox "Experience café-quality espresso in a compact design. The DeLonghi Dedica features a slim 15cm width, professional 15-bar pump, and thermoblock heating system for consistent temperature."
```

### Coffee Product

```bash
python products/create_full_product.py \
  --title "Ethiopia Yirgacheffe" \
  --vendor "Escarpment Coffee Roasters" \
  --type "Fresh Coffee" \
  --price "24.99" \
  --sku "ETH-YIRG-001" \
  --tags "ROAST-Light,REGION-Yirgacheffe,NOTES-Floral#Citrus#Tea-like" \
  --seasonal
```

### From JSON File

```bash
python products/create_full_product.py --from-json product_config.json
```

JSON file format:
```json
{
  "title": "Product Name",
  "vendor": "Brand",
  "productType": "Espresso Machines",
  "price": "999.99",
  "sku": "SKU123",
  "cost": "600.00",
  "weight": 15000,
  "description": "Product description...",
  "buybox": "Sales pitch...",
  "faqs": [
    {"question": "What's included?", "answer": "Machine, portafilter, tamper, measuring spoon."}
  ],
  "techSpecs": {
    "manufacturer": "Brand",
    "power": "1200W",
    "boiler": "Thermoblock",
    "pressure": "15 bar"
  },
  "tags": ["additional-tag"],
  "status": "DRAFT"
}
```

## Automatic Tag Generation

The script automatically generates tags based on product type and vendor:

### Product Type Tags

| Product Type | Auto-Generated Tags |
|--------------|---------------------|
| Espresso Machines | `espresso-machines`, `Espresso Machines`, `consumer` |
| Grinders | `grinders`, `grinder`, `consumer`, `burr-grinder` |
| Fresh Coffee | `NC_FreshCoffee`, `coffee` |
| Accessories | `accessories`, `WAR-ACC` |
| Parts | `WAR-PAR` |
| Cleaning | `NC_Cleaning`, `WAR-CON` |

### Vendor Tags

- Vendor name (lowercase) is always added
- VIM vendors (Ascaso, Bezzera, Bellezza, ECM, Gaggia, Profitec, etc.) get `VIM` and `WAR-VIM` tags for machines/grinders

## Metafield Structure

### Buy Box
- **Namespace**: `buybox`
- **Key**: `content`
- **Type**: `multi_line_text_field`
- **Purpose**: Sales pitch displayed prominently on product page

### FAQs
- **Namespace**: `faq`
- **Key**: `content`
- **Type**: `json`
- **Structure**: `{"faqs": [{"question": "Q?", "answer": "A."}]}`

### Technical Specifications
- **Namespace**: `specs`
- **Key**: `techjson`
- **Type**: `json`
- **Structure**: Free-form JSON object with spec key-value pairs

### Variant Preview
- **Namespace**: `ext`
- **Key**: `variantPreviewName`
- **Type**: `single_line_text_field`
- **Purpose**: Display name for variant (e.g., "Black" instead of "Default Title")

### Sale End Date
- **Namespace**: `inventory`
- **Key**: `ShappifySaleEndDate`
- **Type**: `single_line_text_field`
- **Format**: ISO date string

### Coffee Seasonality
- **Namespace**: `coffee`
- **Key**: `seasonality`
- **Type**: `boolean`
- **Purpose**: Mark coffee as seasonal offering

## Channel Publishing

Products are automatically published to these channels:

1. **Online Store** - Main Shopify storefront
2. **Point of Sale** - In-store POS system
3. **Google & YouTube** - Google Shopping integration
4. **Facebook & Instagram** - Social commerce
5. **Shop** - Shopify's Shop app
6. **Hydrogen** - Headless Hydrogen storefronts (multiple instances)
7. **Attentive** - SMS/email marketing

Note: Publishing to channels makes the product visible on those channels, but the product status remains DRAFT until explicitly set to ACTIVE.

## Output Example

```
Creating product: Breville Barista Express...
✓ Created product: Breville Barista Express (ID: gid://shopify/Product/1234567890)
Updating variant details...
✓ Updated variant details
Updating variant price and inventory policy...
✓ Updated variant price
Adding 0 metafields...
Adding 5 tags...
✓ Added tags
Publishing to channels...
✓ Published to 9 channels

✅ Successfully created product!
   ID: gid://shopify/Product/1234567890
   Handle: breville-barista-express
   Admin URL: https://idrinkcoffee.myshopify.com/admin/products/1234567890

💡 To add product features, use: python tools/manage_features_metaobjects.py --product "1234567890" --add "Feature Title" "Feature description"
```

## Notes
- This is the **recommended** script for all product creation at iDrinkCoffee.com
- Products start in DRAFT status but are published to all channels
- Inventory tracking is always enabled with DENY policy (no negative inventory)
- SKU must be unique across the store
- Weight should be in grams (script uses GRAMS unit for consistency)
- Cost (COGS) is used for profit margin calculations
- Use `--dry-run` to preview before creating
- The script follows iDC conventions for tags, metafields, and structure
- Product images must be added separately after creation
- Product features are added using `manage_features_metaobjects.py`

## Required Scopes
- `write_products`
- `read_products`
- `write_inventory`
- `read_inventory`
- `write_publications`
