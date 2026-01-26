# Product GraphQL Operations

Complete documentation for all product-related GraphQL operations extracted from `backend/bash-tools/products/`.

## Overview

All GraphQL queries and mutations in this directory have been **validated** against the Shopify Admin API schema using the Shopify MCP validation tools. Each operation includes:

- Complete GraphQL query/mutation
- Variable definitions and types
- Usage examples with the corresponding Python scripts
- Request/response structures
- Required API scopes
- Common errors and solutions

## Documentation Files

| File | Script | Description |
|------|--------|-------------|
| [search.md](./search.md) | `search_products.py` | Search products using Shopify's query syntax |
| [get.md](./get.md) | `get_product.py` | Get detailed product information by ID/handle/SKU |
| [create.md](./create.md) | `create_product.py` | Create basic products with single variant |
| [create-full.md](./create-full.md) | `create_full_product.py` | **RECOMMENDED** - Create complete production-ready products |
| [update.md](./update.md) | `update_product_description.py` | Update product descriptions |
| [status.md](./status.md) | `manage_status.py` | Manage product status (ACTIVE/DRAFT/ARCHIVED) |
| [duplicate.md](./duplicate.md) | `duplicate_product.py` | Duplicate products with new title/SKU |
| [upload-image.md](./upload-image.md) | `upload_product_image_staged.py` | Upload images using staged uploads |
| [delete-images.md](./delete-images.md) | `delete_product_images.py` | Delete product images |

## Quick Reference

### Product Discovery

```bash
# Search for products
python products/search_products.py "vendor:Breville tag:sale" --limit 20

# Get full product details
python products/get_product.py "delonghi-dedica" --metafields
```

### Product Creation

```bash
# Quick create (basic)
python products/create_product.py \
  --title "Product Name" \
  --vendor "Brand" \
  --type "Category" \
  --price 99.99

# Full create (RECOMMENDED for production)
python products/create_full_product.py \
  --title "Product Name" \
  --vendor "Brand" \
  --type "Category" \
  --price 99.99 \
  --sku "SKU-001" \
  --cost 50.00 \
  --buybox "Sales pitch content..."
```

### Product Updates

```bash
# Update description
python products/update_product_description.py "product-handle" \
  --description "New description with <strong>HTML</strong>"

# Change status
python products/manage_status.py --product "SKU-001" --status ACTIVE

# Duplicate product
python products/duplicate_product.py \
  --source-handle "original-black" \
  --new-title "Product - Red" \
  --new-sku "SKU-002"
```

### Product Media

```bash
# Upload image
python products/upload_product_image_staged.py \
  "gid://shopify/Product/1234567890" \
  "/path/to/image.jpg" \
  --alt "Product front view"

# Delete all images
python products/delete_product_images.py \
  --product-id "gid://shopify/Product/1234567890" \
  --delete-all
```

## Validation Status

All GraphQL operations documented here were validated on **2024-12-03** using:
- **Tool**: Shopify MCP (`@shopify/dev-mcp`)
- **API**: Admin GraphQL API
- **Status**: ✅ All operations validated successfully

### Validation Results

| Operation | Status | Notes |
|-----------|--------|-------|
| searchProducts | ✅ Valid | Requires `read_products` |
| getProduct | ✅ Valid | Requires `read_products`, `read_inventory` |
| createProduct | ✅ Valid | Requires `write_products`, `read_products` |
| productUpdate | ✅ Valid | Requires `write_products`, `read_products` |
| productVariantsBulkUpdate | ✅ Valid | Requires `write_products`, `read_products`, `read_inventory` |
| tagsAdd | ✅ Valid | No additional scopes |
| publishProduct | ✅ Valid | Requires `write_publications`, `read_products` |
| inventoryItemUpdate | ✅ Valid (Fixed) | Changed `InventoryItemUpdateInput` → `InventoryItemInput` |
| productDuplicate | ✅ Valid | Requires `write_products`, `read_products`, `read_inventory` |
| stagedUploadsCreate | ✅ Valid | No additional scopes |
| productCreateMedia | ✅ Valid | Requires `write_products`, `read_products`, `read_files` |
| productDeleteMedia | ✅ Valid | Requires `write_products`, `read_products` |

### Deprecated Operations Found

⚠️ **Warning**: The `delete_product_images.py` script uses the deprecated `productImageRemove` mutation. The documentation includes the correct `productDeleteMedia` mutation and recommends updating the script.

## Common Patterns

### Product ID Resolution

Most scripts accept multiple identifier formats:
- Numeric ID: `"1234567890"`
- Full GID: `"gid://shopify/Product/1234567890"`
- Handle: `"product-handle-slug"`
- SKU: `"PRODUCT-SKU"`

The `base.py` helper class provides `resolve_product_id()` for automatic resolution.

### Error Handling

All mutations return `userErrors` array:
```graphql
userErrors {
  field
  message
}
```

Scripts check for errors and exit with status 1 on failure.

### Pagination

Search operations support pagination:
```graphql
pageInfo {
  hasNextPage
  endCursor
}
```

Use `after: $cursor` to fetch next page.

## API Scopes Required

Minimum scopes for product operations:

| Scope | Purpose |
|-------|---------|
| `read_products` | Read product data |
| `write_products` | Create/update products |
| `read_inventory` | Read inventory data |
| `write_inventory` | Update inventory settings |
| `write_publications` | Publish to channels |
| `read_files` | Staged uploads (images) |

## Best Practices

1. **Always use `create_full_product.py`** for new products - it follows iDC conventions
2. **Validate products** before activating with `manage_status.py`
3. **Use staged uploads** for images - more reliable than URL uploads
4. **Test with `--dry-run`** when doing bulk operations
5. **Check GraphQL responses** for `userErrors` before proceeding
6. **Use handles** instead of IDs when possible - more readable in scripts

## Related Documentation

- **Bash Tools Index**: `backend/bash-tools/INDEX.md`
- **Base Client**: `backend/bash-tools/base.py`
- **Product Guidelines**: `backend/docs/product-guidelines/`
- **GraphQL Operations Index**: `backend/docs/graphql-operations/INDEX.md`

## Contribution Notes

When adding new product operations:

1. Extract GraphQL from the Python script
2. Validate using Shopify MCP: `mcp__shopify-dev-mcp__validate_graphql_codeblocks`
3. Fix any validation errors
4. Document in this directory following the established format
5. Update this README with the new operation

## Questions or Issues?

- Check the individual documentation files for detailed examples
- Review the source scripts in `backend/bash-tools/products/`
- Refer to Shopify Admin API documentation for GraphQL reference
- Test operations with `--dry-run` flags before production use
