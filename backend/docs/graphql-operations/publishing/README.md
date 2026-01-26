# Publishing Operations

GraphQL operations for managing product visibility across Shopify sales channels.

## Overview

Publishing controls which sales channels display your products. Common channels include Online Store, Point of Sale, Google Shopping, Facebook/Instagram, Shop, and custom channels like Hydrogen storefronts.

## Operations

### Queries

| Operation | File | Description |
|-----------|------|-------------|
| **Get Product Publications** | [get-product-publications.md](./get-product-publications.md) | Check which channels a product is published to |
| **Get Active Products** | [get-active-products.md](./get-active-products.md) | Retrieve all active products with pagination |

### Mutations

| Operation | File | Description |
|-----------|------|-------------|
| **Publish Product** | [publish-product.md](./publish-product.md) | Publish products to one or more sales channels |

## Common Workflows

### 1. Publish Single Product to All Channels

```bash
# Step 1: Get product GID
python search_products.py BRE0001

# Step 2: Publish to main store channels
python publishing/publish.py --product "gid://shopify/Product/123456" --channels main
```

### 2. Bulk Publish from File

```bash
# Create file with product handles/SKUs
echo "BRE0001" > products.txt
echo "ECM0001" >> products.txt

# Publish all products
python publishing/publish.py --file products.txt --channels main
```

### 3. Publish All Active Products (Parts Store)

```bash
# Standard mode (sequential)
python publishing/publish.py --all --channels parts

# Fast mode (concurrent, 50 workers)
python publishing/publish.py --all --channels parts --fast

# Fast mode with custom worker count
python publishing/publish.py --all --channels parts --fast --workers 100
```

### 4. Check Publication Status

```bash
# Query current publications
python core/graphql_query.py 'query getProduct($id: ID!) { product(id: $id) { title resourcePublicationsV2(first: 50) { edges { node { publication { name } isPublished } } } } }' --variables '{"id": "gid://shopify/Product/123456"}'
```

## Publication Channels

### Main Store (iDrinkCoffee.com)
- **Online Store**: `gid://shopify/Publication/46590273`
- **Point of Sale**: `gid://shopify/Publication/46590337`
- **Google & YouTube**: `gid://shopify/Publication/22067970082`
- **Facebook & Instagram**: `gid://shopify/Publication/44906577954`
- **Shop**: `gid://shopify/Publication/93180952610`
- **Hydrogen**: `gid://shopify/Publication/231226015778`

### Parts Store
- **Parts 2025**: `gid://shopify/Publication/106935648353`

**Note**: Publication IDs are environment-specific. Use `publications` query to discover IDs in your store.

## Script Reference

### `publish.py` - Unified Publishing Tool

Replaces legacy scripts: `publish_to_channels.py`, `publish_to_parts_channel.py`, `publish_to_parts_channel_fast.py`

**Features**:
- Publish to main store (6 channels) or parts store
- Single product, batch from file, or all active products
- Fast concurrent mode for parts store (up to 100 workers)
- Dry-run mode for testing
- Automatic product ID resolution (handle/SKU → GID)

**Examples**:
```bash
# Main store
python publishing/publish.py --product BRE0001 --channels main
python publishing/publish.py --file products.txt --channels main --dry-run

# Parts store
python publishing/publish.py --product BRE0001 --channels parts
python publishing/publish.py --all --channels parts --fast --workers 50
```

## Required OAuth Scopes

### For Queries
- `read_products`
- `read_publications`

### For Mutations
- `write_publications`
- `read_products`

## Best Practices

1. **Product Status**: Only ACTIVE products can be published
   - DRAFT products: Activate before publishing
   - ARCHIVED products: Unarchive before publishing

2. **Idempotency**: Publishing is idempotent
   - Safe to retry on failures
   - Already-published products succeed silently

3. **Error Handling**: Always check `userErrors` in mutation responses
   ```python
   result = execute_graphql(mutation, variables)
   errors = result.get("data", {}).get("publishablePublish", {}).get("userErrors", [])
   if errors:
       print(f"Failed: {errors[0]['message']}")
   ```

4. **Rate Limiting**: For bulk operations
   - Use `--fast` mode for >100 products
   - Standard mode adds 0.5s delay every 50 products
   - Fast mode uses ThreadPoolExecutor (default 50 workers)

5. **Channel Requirements**:
   - **Google Shopping**: Requires `product_category`, `google_product_category`
   - **Facebook**: Requires product images, proper descriptions
   - **Shop**: Automatic eligibility based on product quality

6. **Multi-Store Publishing**:
   - Main store: Uses `SHOPIFY_ACCESS_TOKEN` from env
   - Parts store: Uses `SHOPIFY_PARTS_TOKEN` from env
   - Ensure proper tokens are set for target store

## Troubleshooting

### "Product not found"
- Verify product GID format: `gid://shopify/Product/{id}`
- Check product exists in target store
- Ensure API token has access to product

### "Publication not found"
- Publication IDs are store-specific
- Use `publications` query to get current IDs
- Check you're using correct store's token

### "Product already published"
- This is not an error - operation succeeds
- Use get-product-publications.md query to verify

### Rate Limit Errors (429)
- Reduce worker count: `--workers 25`
- Add delays between batches
- Use GraphQL cost analysis to optimize queries

## Related Documentation

- [Shopify Publishing API](https://shopify.dev/docs/api/admin-graphql/latest/objects/publication)
- [Search Syntax](https://shopify.dev/docs/api/usage/search-syntax)
- [GraphQL Pagination](https://shopify.dev/docs/api/usage/pagination-graphql)
- [Rate Limits](https://shopify.dev/docs/api/usage/rate-limits)

## File Locations

- **Script**: `backend/bash-tools/publishing/publish.py`
- **Documentation**: `backend/docs/graphql-operations/publishing/`
- **Base Client**: `backend/bash-tools/base.py`
