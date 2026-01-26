# Delete Product Images

Delete specific product images or all images from a product. **Note**: The script implementation uses an older REST-style mutation that is deprecated. The correct GraphQL mutation is documented here.

## Use Cases
- Remove incorrect or outdated images
- Clear all images before re-uploading
- Remove duplicate images
- Clean up product media

## GraphQL

### Get Product Images

```graphql
query getProductImages($id: ID!) {
  product(id: $id) {
    images(first: 250) {
      edges {
        node {
          id
        }
      }
    }
  }
}
```

### Delete Product Media (CORRECT - Use This)

```graphql
mutation productDeleteMedia($productId: ID!, $mediaIds: [ID!]!) {
  productDeleteMedia(productId: $productId, mediaIds: $mediaIds) {
    deletedMediaIds
    deletedProductImageIds
    product {
      id
    }
    mediaUserErrors {
      field
      message
    }
  }
}
```

### ⚠️ Deprecated Method (Script Uses This)

The script currently uses `productImageRemove` which is deprecated:

```graphql
mutation productImageRemove($id: ID!) {
  productImageRemove(input: {id: $id}) {
    image {
      id
    }
    errors {
      field
      message
    }
  }
}
```

**Recommendation**: Update script to use `productDeleteMedia` mutation.

## Variables

### Get Images Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| id | ID | Yes | Product GID |

### Delete Media Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| productId | ID | Yes | Product GID |
| mediaIds | [ID!] | Yes | Array of media IDs to delete |

## Example

```bash
# Delete all images from product
python products/delete_product_images.py \
  --product-id "gid://shopify/Product/1234567890" \
  --delete-all

# Delete specific images by ID
python products/delete_product_images.py \
  --product-id "gid://shopify/Product/1234567890" \
  --image-ids \
    "gid://shopify/ProductImage/11111" \
    "gid://shopify/ProductImage/22222" \
    "gid://shopify/ProductImage/33333"
```

## Request Examples

### Step 1: Get All Image IDs

```json
{
  "id": "gid://shopify/Product/1234567890"
}
```

Response:
```json
{
  "data": {
    "product": {
      "images": {
        "edges": [
          {"node": {"id": "gid://shopify/ProductImage/11111"}},
          {"node": {"id": "gid://shopify/ProductImage/22222"}},
          {"node": {"id": "gid://shopify/ProductImage/33333"}}
        ]
      }
    }
  }
}
```

### Step 2: Delete Images (RECOMMENDED METHOD)

```json
{
  "productId": "gid://shopify/Product/1234567890",
  "mediaIds": [
    "gid://shopify/ProductImage/11111",
    "gid://shopify/ProductImage/22222",
    "gid://shopify/ProductImage/33333"
  ]
}
```

## Response Structure

### Successful Deletion (productDeleteMedia)

```json
{
  "data": {
    "productDeleteMedia": {
      "deletedMediaIds": [
        "gid://shopify/MediaImage/111",
        "gid://shopify/MediaImage/222",
        "gid://shopify/MediaImage/333"
      ],
      "deletedProductImageIds": [
        "gid://shopify/ProductImage/11111",
        "gid://shopify/ProductImage/22222",
        "gid://shopify/ProductImage/33333"
      ],
      "product": {
        "id": "gid://shopify/Product/1234567890"
      },
      "mediaUserErrors": []
    }
  }
}
```

### Script Output

```bash
# Delete all images
Found 5 images to delete
✓ Deleted image: gid://shopify/ProductImage/11111
✓ Deleted image: gid://shopify/ProductImage/22222
✓ Deleted image: gid://shopify/ProductImage/33333
✓ Deleted image: gid://shopify/ProductImage/44444
✓ Deleted image: gid://shopify/ProductImage/55555

✓ Successfully deleted 5 images
```

## Workflow Options

### Option 1: Delete All Images

```bash
python products/delete_product_images.py \
  --product-id "gid://shopify/Product/1234567890" \
  --delete-all
```

The script:
1. Queries product for all image IDs
2. Iterates through each image
3. Deletes images one by one
4. Reports success count

### Option 2: Delete Specific Images

```bash
python products/delete_product_images.py \
  --product-id "gid://shopify/Product/1234567890" \
  --image-ids "gid://shopify/ProductImage/11111" "gid://shopify/ProductImage/22222"
```

The script:
1. Takes provided image IDs
2. Deletes each image individually
3. Reports success count

## Image ID Retrieval

To get image IDs for selective deletion:

```bash
# Get product with images
python products/get_product.py "1234567890" --field "images"
```

Output:
```json
{
  "edges": [
    {
      "node": {
        "id": "gid://shopify/ProductImage/11111",
        "url": "https://cdn.shopify.com/...",
        "altText": "Front view"
      }
    },
    {
      "node": {
        "id": "gid://shopify/ProductImage/22222",
        "url": "https://cdn.shopify.com/...",
        "altText": "Side view"
      }
    }
  ]
}
```

## Batch Deletion (Recommended Approach)

Instead of deleting images one by one, use `productDeleteMedia` to delete multiple images in a single request:

```python
# Improved approach (modify script)
mutation = """
mutation productDeleteMedia($productId: ID!, $mediaIds: [ID!]!) {
  productDeleteMedia(productId: $productId, mediaIds: $mediaIds) {
    deletedMediaIds
    deletedProductImageIds
    mediaUserErrors {
      field
      message
    }
  }
}
"""

variables = {
    "productId": product_id,
    "mediaIds": all_image_ids  # Pass all IDs at once
}
```

**Advantages**:
- Single API call instead of one per image
- Faster execution
- Fewer rate limit issues
- Uses current API (not deprecated)

## Notes
- ⚠️ **Script uses deprecated `productImageRemove`** - recommend updating to `productDeleteMedia`
- Deletion is **permanent** - images cannot be recovered
- No confirmation dialog - deletions happen immediately
- Featured image is deleted if included in the list
- Product remains active - only images are removed
- After deletion, product has no images until new ones are uploaded
- The script processes images sequentially with the old mutation
- Batch deletion with `productDeleteMedia` is more efficient
- Maximum 250 images can be queried at once
- Use `--delete-all` carefully - double-check product ID first

## Common Use Cases

### Replace All Images
```bash
# Step 1: Delete all existing images
python products/delete_product_images.py \
  --product-id "gid://shopify/Product/1234567890" \
  --delete-all

# Step 2: Upload new images
python products/upload_product_image_staged.py \
  "gid://shopify/Product/1234567890" \
  "new-image-1.jpg"
python products/upload_product_image_staged.py \
  "gid://shopify/Product/1234567890" \
  "new-image-2.jpg"
```

### Remove Duplicates
```bash
# Identify duplicate image IDs first
# Then delete specific duplicates
python products/delete_product_images.py \
  --product-id "gid://shopify/Product/1234567890" \
  --image-ids "gid://shopify/ProductImage/duplicate1" "gid://shopify/ProductImage/duplicate2"
```

### Clean Multiple Products
```bash
# Create a shell script for bulk operations
for product_id in $(cat product_ids.txt); do
  python products/delete_product_images.py \
    --product-id "$product_id" \
    --delete-all
done
```

## Error Handling

### No Images to Delete
```
No images to delete
```
The product has no images or all specified IDs are invalid.

### Image Not Found
```
Error deleting image gid://shopify/ProductImage/11111: [{'message': 'Image not found'}]
```
**Solution**: Verify image ID is correct and belongs to this product.

### Product Not Found
```
Error fetching images: [{'message': 'Product not found'}]
```
**Solution**: Check product ID is correct and product exists.

## Migration Recommendation

The script should be updated to use the modern `productDeleteMedia` mutation:

### Current (Deprecated)
```python
# ❌ Old way - deprecated
mutation = """
mutation {
    productImageRemove(input: {id: "%s"}) {
        image { id }
        errors { field message }
    }
}
""" % image_id
```

### Recommended (Modern)
```python
# ✅ New way - current API
mutation = """
mutation productDeleteMedia($productId: ID!, $mediaIds: [ID!]!) {
  productDeleteMedia(productId: $productId, mediaIds: $mediaIds) {
    deletedProductImageIds
    mediaUserErrors {
      field
      message
    }
  }
}
"""

variables = {
    "productId": product_id,
    "mediaIds": image_ids  # Can delete multiple at once
}
```

## Required Scopes
- `write_products`
- `read_products`
