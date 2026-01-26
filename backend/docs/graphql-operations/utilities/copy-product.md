# Copy Product Between Stores

Copy products from the main iDrinkCoffee store to parts or wholesale stores, including all images, variants, and pricing.

## Use Cases
- Duplicate products to parts store for replacement part sales
- Copy products to wholesale store with different pricing
- Maintain consistent product data across multiple stores
- Clone products when launching new store channels
- Sync product updates between stores

## Operations

### Fetch Product from Source Store

Retrieves complete product data including all variants, images, and options.

**GraphQL Query:**

```graphql
query getProduct($id: ID!) {
  product(id: $id) {
    id
    title
    descriptionHtml
    vendor
    productType
    handle
    status
    tags
    seo {
      title
      description
    }
    options {
      name
      position
      values
    }
    images(first: 50) {
      nodes {
        originalSrc
        altText
      }
    }
    variants(first: 100) {
      nodes {
        id
        title
        sku
        price
        compareAtPrice
        barcode
        inventoryPolicy
        inventoryQuantity
        inventoryItem {
          measurement {
            weight {
              value
              unit
            }
          }
        }
        selectedOptions {
          name
          value
        }
      }
    }
  }
}
```

**Variables:**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| id | ID! | Yes | Product GID (gid://shopify/Product/{id}) |

**Required Scopes:** `read_products`, `read_inventory`

---

### Create Product on Target Store

Creates a new product on the destination store with all core attributes.

**GraphQL Mutation:**

```graphql
mutation createProduct($input: ProductInput!) {
  productCreate(input: $input) {
    product {
      id
      handle
      title
    }
    userErrors {
      field
      message
    }
  }
}
```

**Variables:**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| input | ProductInput! | Yes | Product creation input object |
| input.title | String | Yes | Product title |
| input.descriptionHtml | String | No | HTML description |
| input.vendor | String | No | Product vendor |
| input.productType | String | No | Product type/category |
| input.status | ProductStatus | Yes | Product status (DRAFT or ACTIVE) |
| input.tags | [String] | No | Product tags (retail- tags are filtered out) |
| input.seo | SEOInput | No | SEO title and description |
| input.productOptions | [ProductOptionInput] | No | Product options (size, color, etc.) |

**Required Scopes:** `write_products`, `read_products`

**Notes:**
- Product is created as DRAFT initially for safety
- Retail-specific tags are automatically filtered out
- Handle is auto-generated if not provided
- Custom metafields are NOT copied (intentional)

---

### Add Images to Product

Uploads and attaches images to the newly created product.

**GraphQL Mutation:**

```graphql
mutation createProductMedia($productId: ID!, $media: [CreateMediaInput!]!) {
  productCreateMedia(productId: $productId, media: $media) {
    media {
      ... on MediaImage {
        id
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

**Variables:**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| productId | ID! | Yes | Target product GID |
| media | [CreateMediaInput!]! | Yes | Array of media objects to create |
| media[].originalSource | String | Yes | Image URL from source store |
| media[].alt | String | No | Image alt text |
| media[].mediaContentType | MediaContentType | Yes | Media type (IMAGE) |

**Required Scopes:** `write_products`, `read_products`, `read_files`, `read_themes`, `read_orders`, `read_draft_orders`, `read_images`

**Notes:**
- Images are referenced by URL (Shopify copies them automatically)
- Alt text is preserved from source product
- Image order is maintained
- Maximum 50 images per product

---

### Get Product Variants

Fetches variants from the newly created product to match with source variants.

**GraphQL Query:**

```graphql
query getProductVariants($id: ID!) {
  product(id: $id) {
    variants(first: 100) {
      nodes {
        id
        title
        selectedOptions {
          name
          value
        }
      }
    }
  }
}
```

**Variables:**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| id | ID! | Yes | Product GID |

**Required Scopes:** `read_products`

---

### Update Product Variants

Updates variant details including pricing, SKU, barcode, and inventory settings.

**GraphQL Mutation:**

```graphql
mutation updateVariants($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      id
    }
    userErrors {
      field
      message
    }
  }
}
```

**Variables:**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| productId | ID! | Yes | Product GID |
| variants | [ProductVariantsBulkInput!]! | Yes | Array of variant updates |
| variants[].id | ID! | Yes | Variant GID |
| variants[].price | String | No | Variant price |
| variants[].compareAtPrice | String | No | Compare-at price |
| variants[].barcode | String | No | Product barcode |
| variants[].inventoryPolicy | InventoryPolicy | No | DENY or CONTINUE (always DENY) |
| variants[].inventoryItem | InventoryItemInput | No | Inventory and measurement data |
| variants[].inventoryItem.sku | String | No | SKU code |
| variants[].inventoryItem.tracked | Boolean | No | Enable inventory tracking (always true) |
| variants[].inventoryItem.measurement | MeasurementInput | No | Weight and dimensions |

**Required Scopes:** `write_products`, `read_products`

**Notes:**
- Variants matched by selectedOptions (size, color, etc.)
- Inventory policy always set to DENY for safety
- SKU is copied exactly without modification
- Weight and unit are preserved

---

### Publish Product

Activates the product (changes status from DRAFT to ACTIVE).

**GraphQL Mutation:**

```graphql
mutation publishProduct($id: ID!) {
  productUpdate(input: {id: $id, status: ACTIVE}) {
    product {
      id
      status
    }
    userErrors {
      field
      message
    }
  }
}
```

**Variables:**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| id | ID! | Yes | Product GID |

**Required Scopes:** `write_products`, `read_products`

---

## Example Usage

### Copy Product to Parts Store

```bash
# By SKU
python utilities/copy_product.py "BRE0001" --store parts

# By GID
python utilities/copy_product.py "gid://shopify/Product/7293899497506" --store parts

# By handle
python utilities/copy_product.py "breville-barista-express" --store parts

# Dry run to preview
python utilities/copy_product.py "BRE0001" --store parts --dry-run
```

### Copy Product to Wholesale Store

```bash
python utilities/copy_product.py "product-handle" --store wholesale
```

---

## Environment Variables Required

The script requires these environment variables:

| Variable | Purpose |
|----------|---------|
| SHOPIFY_SHOP_URL | Main store URL |
| SHOPIFY_ACCESS_TOKEN | Main store access token |
| SHOPIFY_PARTS_TOKEN | Parts store access token (for --store parts) |
| SHOPIFY_WHOLESALE_TOKEN | Wholesale store access token (for --store wholesale) |

**Example .env:**
```bash
SHOPIFY_SHOP_URL=idrinkcoffee.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxxxx
SHOPIFY_PARTS_TOKEN=shpat_yyyyy
SHOPIFY_WHOLESALE_TOKEN=shpat_zzzzz
```

---

## Store Configurations

### Parts Store
- **URL:** https://parts-idrinkcoffee-com.myshopify.com
- **Purpose:** Replacement parts and accessories
- **Token:** SHOPIFY_PARTS_TOKEN

### Wholesale Store
- **URL:** https://idrinkcoffee-wholesale.myshopify.com
- **Purpose:** B2B wholesale orders
- **Token:** SHOPIFY_WHOLESALE_TOKEN

---

## Copy Process Flow

1. **Fetch from main store** - Get complete product data by GID/SKU/handle
2. **Create on target** - Create product as DRAFT with core attributes
3. **Add images** - Upload all product images by URL reference
4. **Match variants** - Get created variants and match to source variants by options
5. **Update variants** - Set pricing, SKU, barcode, weight for each variant
6. **Publish** - Activate product (set status to ACTIVE)

---

## What Gets Copied

### Included
- Title, description (HTML), vendor, product type
- SEO title and description
- Product tags (except retail- tags)
- Product options (size, color, etc.) and values
- All product images with alt text
- Variant SKU, price, compare-at price, barcode
- Variant weight and unit
- Inventory settings (always tracked, always DENY)

### Not Included
- Custom metafields (intentionally excluded)
- Inventory quantities (target store manages separately)
- Product ID (new ID generated on target store)
- Collections (target store organizes differently)
- Reviews and ratings (store-specific)
- Sales history

---

## Best Practices

1. **Always dry-run first** - Preview what will be copied before executing
2. **Verify environment variables** - Ensure correct store tokens are set
3. **Check for duplicates** - Search target store to avoid duplicate products
4. **Review tags** - Remove or modify tags that don't apply to target store
5. **Update pricing** - Modify prices if needed for parts/wholesale
6. **Test variants** - Verify all variants copied correctly
7. **Update inventory** - Set appropriate inventory levels on target store
8. **Check images** - Confirm all images uploaded successfully

---

## Common Workflows

### Copy Single Product

```bash
# Step 1: Find product ID or SKU
python bash-tools/search_products.py --query "Breville Barista Express"

# Step 2: Dry run to preview
python utilities/copy_product.py "BRE0001" --store parts --dry-run

# Step 3: Execute copy
python utilities/copy_product.py "BRE0001" --store parts

# Step 4: Verify on target store
# Visit parts store admin and check product
```

### Batch Copy Multiple Products

```bash
# Create a script to loop through SKUs
#!/bin/bash
SKUS=("BRE0001" "BRE0002" "BRE0003")

for sku in "${SKUS[@]}"; do
  echo "Copying $sku..."
  python utilities/copy_product.py "$sku" --store parts
  sleep 2  # Rate limit protection
done
```

---

## Error Handling

### Common Errors

**"Product not found"**
- Verify product ID/SKU/handle exists in main store
- Check product is not archived or deleted
- Ensure proper GID format if using GID

**"Environment variable must be set"**
- Verify SHOPIFY_PARTS_TOKEN or SHOPIFY_WHOLESALE_TOKEN is set
- Check .env file or export variables in shell
- Confirm token has necessary API permissions

**"Failed to create product"**
- Check for duplicate handles on target store
- Verify API scopes (write_products required)
- Review userErrors in response for specific issues

**"Failed to add some images"**
- Check image URLs are accessible
- Verify image file sizes (Shopify limits apply)
- Review media type is supported (IMAGE)

**"Failed to update some variants"**
- Ensure variants were created (check productCreate response)
- Verify variant matching by options is correct
- Check price format is valid decimal string

---

## Related Operations

- Product search: `products/search-products.md`
- Product creation: `products/create-product.md`
- Variant management: `products/update-variants.md`
- Image uploads: `products/manage-images.md`

---

## Technical Notes

### Product Resolution
Script supports three input formats:
- **GID:** `gid://shopify/Product/7293899497506`
- **SKU:** `BRE0001` (looks up product by variant SKU)
- **Handle:** `breville-barista-express`

### Variant Matching Algorithm
Variants are matched between source and target by comparing `selectedOptions`:
```python
def variants_match(v1, v2):
    options1 = {opt['name']: opt['value'] for opt in v1['selectedOptions']}
    options2 = {opt['name']: opt['value'] for opt in v2['selectedOptions']}
    return options1 == options2
```

### Tag Filtering
Retail-specific tags are automatically removed:
```python
tags = [tag for tag in product_data.get('tags', []) if not tag.startswith('retail-')]
```

### Store Client Switching
Script temporarily overrides environment variables to switch between stores:
```python
os.environ['SHOPIFY_SHOP_URL'] = target_url
os.environ['SHOPIFY_ACCESS_TOKEN'] = target_token
target_client = ShopifyClient()
# Restore original environment
```

This ensures clean client initialization without side effects.
