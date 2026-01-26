# New Product Addition Workflow

This document provides a complete step-by-step workflow for adding new products to iDrinkCoffee.com, covering both Shopify and SkuVault integration.

## Prerequisites

### Environment Setup
Ensure these environment variables are set:
```bash
export SHOPIFY_SHOP_URL="https://idrinkcoffee.myshopify.com"
export SHOPIFY_ACCESS_TOKEN="shpat_..."
export SKUVAULT_TENANT_TOKEN="..."
export SKUVAULT_USER_TOKEN="..."
```

### Required Information
Before starting, gather:
- Product details from manufacturer website
- Pricing information
- Cost of goods (COGS)
- Product weight
- Barcode/UPC (if available)
- High-quality product images

## Step-by-Step Workflow

### 1. Research and Planning

#### 1.1 Review Product Guidelines
```bash
# Read the complete guidelines
ls docs/product-guidelines/
```

#### 1.2 Check for Existing Products
```bash
python tools/search_products.py "product name or key terms"
```

#### 1.3 Gather Product Information
- Fetch details from manufacturer website using WebFetch tool
- Note pricing, specifications, features, and available images
- Determine appropriate product type and tags

### 2. Create Base Product

#### 2.1 Create Product with Full Details
```bash
python tools/create_full_product.py \
  --title "Brand Product Name with Descriptors" \
  --vendor "Brand Name" \
  --type "Product Category" \
  --price "00.00" \
  --sku "BRAND-MODEL-CODE" \
  --cost "00.00" \
  --weight 1000 \
  --description "Detailed product description..." \
  --buybox "Compelling sales pitch..." \
  --variant-preview "Color/Model" \
  --tech-specs '{"manufacturer": "Brand", "key": "value"}' \
  --faqs '[{"question": "Q?", "answer": "A."}]' \
  --tags "category,brand,consumer,warranty-tag,feature-tags"
```

**Required Elements:**
- **Title Format:** `{Brand} {Product Name} {Key Descriptors}`
- **SKU Format:** `BRE-MODEL` or `{BRAND}-{MODEL}-{VARIANT}`
- **Tags:** Include category, brand, warranty (WAR-*), and feature tags
- **Status:** Always starts as DRAFT

#### 2.2 Record Product ID
Note the returned product ID for subsequent steps:
```
ID: gid://shopify/Product/8045830570018
```

### 3. Add Product Images

#### 3.1 Upload Main Product Images
```bash
python tools/graphql_mutation.py 'mutation createProductMedia($productId: ID!, $media: [CreateMediaInput!]!) {
  productCreateMedia(productId: $productId, media: $media) {
    media { id alt mediaContentType }
    mediaUserErrors { field message }
  }
}' --variables '{
  "productId": "gid://shopify/Product/PRODUCT_ID",
  "media": [
    {
      "originalSource": "https://example.com/image1.jpg",
      "alt": "Descriptive alt text",
      "mediaContentType": "IMAGE"
    }
  ]
}'
```

### 4. Add Advanced Features

#### 4.1 Create Feature Boxes
```bash
# Add each feature with description
python tools/manage_features_metaobjects.py --product "PRODUCT_ID" --add "Feature Title" "Feature description"
```
IMPORTANT NOTE: Feature metaobjects default to DRAFT and must be individually published to appear on storefront.

#### 4.2 Upload Feature Images
```bash
# Upload feature-specific images first
python tools/graphql_mutation.py 'mutation createProductMedia...' # (same as above)

# Then update features with image IDs
python tools/manage_features_metaobjects.py --product "PRODUCT_ID" --update 1 "Feature Title" "Description" --image "gid://shopify/MediaImage/123456789"
```

#### 4.3 Publish Feature Metaobjects
```bash
# Publish each metaobject individually
python tools/graphql_mutation.py 'mutation publishMetaobject($id: ID!) {
  metaobjectUpdate(id: $id, metaobject: {
    capabilities: { publishable: { status: ACTIVE } }
  }) {
    metaobject { id capabilities { publishable { status } } }
    userErrors { field message }
  }
}' --variables '{"id": "gid://shopify/Metaobject/METAOBJECT_ID"}'
```

**Important:** Feature metaobjects default to DRAFT and must be individually published to appear on storefront.

### 5. Update Product Details

#### 5.1 Add Barcode (if available)
```bash
python tools/graphql_mutation.py 'mutation updateVariantBarcode($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants { id barcode }
    userErrors { field message }
  }
}' --variables '{
  "productId": "gid://shopify/Product/PRODUCT_ID",
  "variants": [{
    "id": "gid://shopify/ProductVariant/VARIANT_ID",
    "barcode": "123456789012"
  }]
}'
```

#### 5.2 Update SKU (if needed)
Update in Shopify admin interface, then proceed to SkuVault sync.

### 6. SkuVault Integration

#### 6.1 Upload to SkuVault
```bash
python tools/upload_to_skuvault.py --sku "FINAL-SKU"
```

This automatically:
- Creates the SKU in SkuVault
- Syncs product data from Shopify
- Sets up cost and pricing information

### 7. Quality Assurance

#### 7.1 Verify Product Data
```bash
python tools/get_product.py PRODUCT_ID
```

#### 7.2 Check Features Display
```bash
python tools/manage_features_metaobjects.py --product "PRODUCT_ID" --list
```

#### 7.3 Verify SkuVault Sync
Check SkuVault dashboard for the new SKU.

### 8. Final Steps

#### 8.1 Review Product Page
- Check product in Shopify admin
- Verify all metafields are populated
- Ensure feature boxes display correctly
- Confirm images are properly uploaded

#### 8.2 Publish When Ready
```bash
# Only when fully reviewed and approved
python tools/graphql_mutation.py 'mutation publishProduct($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id status }
    userErrors { field message }
  }
}' --variables '{
  "input": {
    "id": "gid://shopify/Product/PRODUCT_ID",
    "status": "ACTIVE"
  }
}'
```

## Common Issues and Solutions

### Feature Boxes Not Displaying
**Problem:** Features created but not visible on storefront.
**Solution:** Ensure all metaobjects are published (status: ACTIVE).

### Images Not Uploading
**Problem:** GraphQL errors when adding images.
**Solution:** Ensure `mediaContentType: "IMAGE"` is included in mutation.

### SkuVault Sync Failures
**Problem:** Product not appearing in SkuVault.
**Solution:** Check environment variables and ensure SKU format is correct.

### Tag Organization
**Problem:** Product not appearing in correct collections.
**Solution:** Review tag system documentation and ensure proper category/feature tags.

## Template Commands

### Quick Product Creation (Accessories)
```bash
python tools/create_full_product.py \
  --title "Brand Product Name" \
  --vendor "Brand" \
  --type "Accessories" \
  --price "59.99" \
  --sku "BRE-MODEL" \
  --cost "36.00" \
  --weight 300 \
  --description "Product description..." \
  --buybox "Sales pitch..." \
  --variant-preview "Color/Model" \
  --faqs '[{"question":"What is included?","answer":"Complete product details."}]' \
  --tags "accessories,brand,consumer,WAR-ACC,NC_Accessories"
```

### Feature Box Template
```bash
# Standard 4-feature setup for appliances
python tools/manage_features_metaobjects.py --product "ID" --add "Key Feature 1" "Description of primary benefit"
python tools/manage_features_metaobjects.py --product "ID" --add "Technical Feature" "Specific technical capability"
python tools/manage_features_metaobjects.py --product "ID" --add "Design Feature" "Design or usability benefit"
python tools/manage_features_metaobjects.py --product "ID" --add "Convenience Feature" "Ease of use or maintenance benefit"
```

## Best Practices

1. **Always start with DRAFT status** - Review before publishing
2. **Use consistent SKU format** - Follow established patterns
3. **Include comprehensive FAQs** - Address common customer questions
4. **Tag systematically** - Use both category and feature tags
5. **Verify SkuVault sync** - Ensure inventory management is ready
6. **Test feature display** - Confirm metaobjects are published
7. **Document any variations** - Note special cases for future reference

## Related Documentation

- [Product Creation Basics](./02-product-creation-basics.md)
- [Metafields Reference](./03-metafields-reference.md)
- [Tags System](./04-tags-system.md)
- [Main Tools Documentation](../tools-documentation.md)
