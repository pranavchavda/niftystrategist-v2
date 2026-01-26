# Duplicate Product

Duplicate an existing product with a new title and SKU. Useful for creating color variants, similar products, or product templates.

## Use Cases
- Create color/size variants from existing products
- Duplicate products with slight modifications
- Use existing products as templates for new listings
- Quick product creation with same configuration

## GraphQL

### Get Source Product

```graphql
query getSourceProduct($handle: String!) {
  productByHandle(handle: $handle) {
    id
    title
    handle
    vendor
    variants(first: 1) {
      edges {
        node {
          id
          title
          sku
        }
      }
    }
  }
}
```

### Duplicate Product

```graphql
mutation duplicateProduct($productId: ID!, $newTitle: String!, $newStatus: ProductStatus) {
  productDuplicate(productId: $productId, newTitle: $newTitle, newStatus: $newStatus) {
    newProduct {
      id
      title
      handle
      status
      variants(first: 1) {
        edges {
          node {
            id
            sku
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

### Update SKU

```graphql
mutation updateInventoryItemSku($id: ID!, $input: InventoryItemInput!) {
  inventoryItemUpdate(id: $id, input: $input) {
    inventoryItem {
      id
      sku
    }
    userErrors {
      field
      message
    }
  }
}
```

## Variables

### Duplicate Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| productId | ID | Yes | Source product GID to duplicate |
| newTitle | String | Yes | Title for the duplicated product |
| newStatus | ProductStatus | No | Status for new product (default: DRAFT) |

### SKU Update Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| id | ID | Yes | Inventory item GID |
| input.sku | String | Yes | New SKU for the duplicated product |

## Example

```bash
# Duplicate with new title and SKU
python products/duplicate_product.py \
  --source-handle "breville-barista-express-black" \
  --new-title "Breville Barista Express - Silver" \
  --new-sku "BES870XL-SIL"

# Duplicate and publish immediately
python products/duplicate_product.py \
  --source-handle "delonghi-dedica-black" \
  --new-title "DeLonghi Dedica - Red" \
  --new-sku "EC685R" \
  --publish

# Duplicate with custom handle
python products/duplicate_product.py \
  --source-handle "original-product" \
  --new-title "New Product Variant" \
  --new-sku "NEW-SKU-001" \
  --new-handle "custom-handle-slug"
```

## Workflow

The script follows a 3-step process:

### Step 1: Fetch Original Product
```
📍 Fetching original product: breville-barista-express-black
✅ Found product: Breville Barista Express - Black
   Original SKU: BES870XL-BLK
```

### Step 2: Duplicate Product
```
🔄 Duplicating product...
✅ Product duplicated!
   New Product ID: gid://shopify/Product/9876543210
   New Handle: breville-barista-express-silver
   New Title: Breville Barista Express - Silver
   Status: DRAFT
```

### Step 3: Update SKU
```
✏️  Updating SKU to: BES870XL-SIL
✅ SKU updated: BES870XL-SIL
```

## What Gets Duplicated

### ✅ Copied from Original
- Product description (HTML)
- Vendor
- Product type
- Tags
- SEO settings
- Metafields
- Product options (if multi-variant)
- Variant details (price, weight, barcode)
- Collections (product added to same collections)

### ❌ NOT Copied
- Images (must be added separately)
- Inventory quantities (starts at 0)
- Product status (new product always starts as DRAFT)
- Product handle (auto-generated from new title)

## Request Example

### Step 1: Get Source Product
```json
{
  "handle": "breville-barista-express-black"
}
```

### Step 2: Duplicate
```json
{
  "productId": "gid://shopify/Product/1234567890",
  "newTitle": "Breville Barista Express - Silver",
  "newStatus": "DRAFT"
}
```

### Step 3: Update SKU
```json
{
  "id": "gid://shopify/InventoryItem/1111111111",
  "input": {
    "sku": "BES870XL-SIL"
  }
}
```

## Response Structure

### Successful Duplication

```json
{
  "product_id": "gid://shopify/Product/9876543210",
  "handle": "breville-barista-express-silver",
  "title": "Breville Barista Express - Silver",
  "sku": "BES870XL-SIL",
  "status": "DRAFT"
}
```

## Output Example

```
==================================================
📦 DUPLICATION COMPLETE
==================================================
{
  "product_id": "gid://shopify/Product/9876543210",
  "handle": "breville-barista-express-silver",
  "title": "Breville Barista Express - Silver",
  "sku": "BES870XL-SIL",
  "status": "DRAFT"
}
```

## Post-Duplication Steps

After duplicating a product, you typically need to:

1. **Add Images**
   ```bash
   python products/upload_product_image_staged.py \
     "gid://shopify/Product/9876543210" \
     "/path/to/image.jpg"
   ```

2. **Update Inventory**
   ```bash
   python inventory/set_inventory.py \
     --sku "BES870XL-SIL" \
     --quantity 10
   ```

3. **Activate Product** (when ready)
   ```bash
   python products/manage_status.py \
     --product "BES870XL-SIL" \
     --status ACTIVE
   ```

4. **Update Specific Fields** (if needed)
   - Price differences
   - Variant-specific metafields
   - Color/size options

## Common Use Cases

### Color Variants
```bash
# Create red variant from black original
python products/duplicate_product.py \
  --source-handle "delonghi-dedica-black" \
  --new-title "DeLonghi Dedica - Red" \
  --new-sku "EC685R"
```

### Size Variants
```bash
# Create large size from medium
python products/duplicate_product.py \
  --source-handle "coffee-mug-medium" \
  --new-title "Coffee Mug - Large" \
  --new-sku "MUG-LG"
```

### Product Series
```bash
# Create 2024 model from 2023
python products/duplicate_product.py \
  --source-handle "widget-2023" \
  --new-title "Widget 2024 Edition" \
  --new-sku "WIDGET-2024"
```

## Notes
- The `--publish` flag is deprecated - products always start as DRAFT
- Use `manage_status.py` to activate after duplication
- Handle is auto-generated from title (e.g., "Product Name" → "product-name")
- Custom handle can be specified with `--new-handle` parameter
- SKU must be unique across the store
- Duplicated products start with 0 inventory
- All metafields are copied - review and update if needed
- Images must be added separately after duplication
- The original product is not modified
- Duplication is a server-side operation - very fast even for complex products

## Error Handling

### Source Product Not Found
```
❌ Product not found: invalid-handle
```

### Duplicate SKU
```
❌ SKU update errors: [{'field': ['sku'], 'message': 'SKU must be unique'}]
```

**Solution**: Choose a different SKU that doesn't exist in the store.

### Invalid Product ID
```
❌ Duplicate mutation error: [{'message': 'Product not found'}]
```

**Solution**: Verify the source handle is correct and the product exists.

## Required Scopes
- `write_products`
- `read_products`
- `write_inventory`
- `read_inventory`
