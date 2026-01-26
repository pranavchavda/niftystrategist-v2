# Utility Operations

GraphQL operations for store management utilities including redirects, tax management, and product copying between stores.

## Operations Index

### [URL Redirect Management](./redirects.md)
Manage URL redirects to maintain SEO and handle legacy URLs.

**Operations:**
- `urlRedirectCreate` - Create 301 redirects from old paths to new targets
- `urlRedirects` - List all URL redirects in the store
- `urlRedirectDelete` - Delete existing redirects

**Use Cases:**
- SEO maintenance when changing URLs
- Product URL migrations
- Store restructuring
- Handling deleted products

**Script:** `utilities/manage_redirects.py`

**Example:**
```bash
python utilities/manage_redirects.py --action create \
  --from "/old-path" --to "/new-path"
```

---

### [Tax Management by Tag](./taxes.md)
Bulk enable/disable taxes on products by tag for promotional campaigns.

**Operations:**
- `productVariantsBulkUpdate` - Update taxable status for multiple variants

**Use Cases:**
- "We Pay the Tax" promotional sales
- Tax holiday campaigns
- Regional tax exemptions
- End-of-sale cleanup

**Script:** `utilities/manage_taxes_by_tag.py`

**Example:**
```bash
# Disable taxes for sale
python utilities/manage_taxes_by_tag.py --tag "wptt-sale" --action disable

# Re-enable after sale
python utilities/manage_taxes_by_tag.py --tag "wptt-sale" --action enable
```

**Features:**
- Batch processing with parallel workers
- Dry-run mode for previewing changes
- CSV report generation
- Progress tracking
- Error handling and recovery

---

### [Copy Product Between Stores](./copy-product.md)
Duplicate products from main store to parts or wholesale stores.

**Operations:**
- `product` - Fetch complete product data from source
- `productCreate` - Create product on target store
- `productCreateMedia` - Add images to product
- `productVariantsBulkUpdate` - Update variant details
- `productUpdate` - Publish product (set to ACTIVE)

**Use Cases:**
- Copy to parts store for replacement parts
- Copy to wholesale store with different pricing
- Maintain consistent product data across stores
- Launch new store channels

**Script:** `utilities/copy_product.py`

**Example:**
```bash
# Copy by SKU
python utilities/copy_product.py "BRE0001" --store parts

# Copy by GID
python utilities/copy_product.py "gid://shopify/Product/123" --store wholesale

# Dry run
python utilities/copy_product.py "product-handle" --store parts --dry-run
```

**Environment Required:**
- `SHOPIFY_PARTS_TOKEN` - Parts store access token
- `SHOPIFY_WHOLESALE_TOKEN` - Wholesale store access token

**What Gets Copied:**
- Product title, description, vendor, type
- SEO settings
- Tags (retail- tags filtered out)
- Options and variants
- All images with alt text
- Pricing, SKU, barcode, weight
- Inventory settings (tracked, DENY policy)

**Not Copied:**
- Custom metafields
- Inventory quantities
- Collections
- Reviews/ratings
- Sales history

---

## Common Workflows

### SEO Maintenance
```bash
# Step 1: Create redirect for renamed product
python utilities/manage_redirects.py --action create \
  --from "/products/old-machine" \
  --to "/products/new-machine"

# Step 2: Verify redirect
python utilities/manage_redirects.py --action list
```

### "We Pay the Tax" Sale
```bash
# Step 1: Tag products in Shopify admin
# Tag: "wptt-black-friday"

# Step 2: Preview changes
python utilities/manage_taxes_by_tag.py \
  --tag "wptt-black-friday" \
  --action disable \
  --dry-run

# Step 3: Disable taxes
python utilities/manage_taxes_by_tag.py \
  --tag "wptt-black-friday" \
  --action disable

# Step 4: After sale, re-enable taxes
python utilities/manage_taxes_by_tag.py \
  --tag "wptt-black-friday" \
  --action enable
```

### Multi-Store Product Sync
```bash
# Step 1: Create product on main store (or find existing)
python bash-tools/search_products.py --query "Breville"

# Step 2: Copy to parts store
python utilities/copy_product.py "BRE0001" --store parts

# Step 3: Copy to wholesale store
python utilities/copy_product.py "BRE0001" --store wholesale

# Step 4: Update pricing on each store as needed
```

---

## API Scopes Required

### URL Redirects
- `read_online_store_navigation` - List redirects
- `write_online_store_navigation` - Create/delete redirects

### Tax Management
- `read_products` - Fetch product data
- `write_products` - Update variant tax settings

### Product Copying
- `read_products` - Fetch source product
- `write_products` - Create and update products
- `read_inventory` - Fetch inventory data
- `read_images` - For image operations
- `read_files` - For media operations

---

## Best Practices

### Redirects
1. Always use relative paths starting with "/"
2. Avoid redirect chains (A → B → C)
3. Test redirects before publishing
4. Document why redirects were created
5. Review and clean up old redirects periodically

### Tax Management
1. **Always dry-run first** to preview changes
2. Use clear, date-specific tags (e.g., "wptt-2025-blackfriday")
3. Remove sale tags after re-enabling taxes
4. Keep CSV reports for audit trail
5. Schedule during low-traffic periods
6. Test on small set before full rollout

### Product Copying
1. Dry-run to preview what will be copied
2. Verify correct store tokens are set
3. Check for duplicates on target store
4. Review and adjust tags for target store
5. Update inventory levels after copying
6. Verify all images uploaded successfully

---

## Performance Considerations

### Tax Management
- **Batch size:** 50-150 products depending on store size
- **Workers:** 10-20 parallel threads (monitor rate limits)
- **Pause:** 2 seconds between batches
- **Memory:** Streams in batches, no full dataset in memory

### Product Copying
- **Rate limiting:** Add 2s delay between copies for batch operations
- **Images:** Up to 50 images per product supported
- **Variants:** Up to 100 variants per product

---

## Troubleshooting

### "Rate limit exceeded"
- Reduce worker count in tax management (--workers 5)
- Add delays between operations
- Process during off-peak hours

### "Product not found"
- Verify ID/SKU/handle is correct
- Check product is not archived
- Ensure proper GID format

### "Environment variable must be set"
- Check .env file has required tokens
- Export variables in current shell
- Verify token permissions and scopes

### "UserErrors in response"
- Review error messages for specifics
- Check API scopes are sufficient
- Verify data format (prices, IDs, etc.)

---

## Related Documentation

- [Product Operations](../products/) - Product CRUD operations
- [Collections](../collections/) - Collection management
- [Inventory](../inventory/) - Inventory management
- [Metaobjects](../cms/) - CMS and metaobject operations

---

## Scripts Location

All utility scripts are in: `backend/bash-tools/utilities/`

- `manage_redirects.py` - URL redirect management
- `manage_taxes_by_tag.py` - Tax enable/disable by tag
- `copy_product.py` - Copy products between stores

---

## Support

For questions or issues:
1. Check script `--help` for usage details
2. Review script source code for implementation details
3. Check CSV reports for operation results
4. Consult Shopify API docs for GraphQL schema details
