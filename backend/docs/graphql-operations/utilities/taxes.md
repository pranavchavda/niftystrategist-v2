# Tax Management by Tag

Bulk enable or disable taxes on product variants based on product tags. Essential for running "We Pay the Tax" sales and promotional campaigns.

## Use Cases
- "We Pay the Tax" promotional campaigns (disable taxes for tagged products)
- Tax holiday sales (temporarily disable taxes for specific categories)
- End-of-sale cleanup (re-enable taxes after promotion ends)
- Regional tax exemptions (disable taxes for specific product categories)
- Wholesale pricing adjustments (manage tax settings for B2B products)

## Operations

### Bulk Update Product Variant Taxes

Updates the taxable status for multiple variants of a product in a single operation.

**GraphQL Mutation:**

```graphql
mutation updateVariantTaxes($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    product {
      id
      title
    }
    productVariants {
      id
      sku
      taxable
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
| productId | ID! | Yes | Global ID of the product (gid://shopify/Product/{id}) |
| variants | [ProductVariantsBulkInput!]! | Yes | Array of variant updates with id and taxable status |
| variants[].id | ID! | Yes | Variant ID (gid://shopify/ProductVariant/{id}) |
| variants[].taxable | Boolean! | Yes | New taxable status (true = taxable, false = non-taxable) |

**Required Scopes:** `write_products`, `read_products`

**Example:**

```bash
# Disable taxes for all products with "wptt-sale" tag
python utilities/manage_taxes_by_tag.py --tag "wptt-sale" --action disable

# Re-enable taxes after sale ends
python utilities/manage_taxes_by_tag.py --tag "wptt-sale" --action enable

# Dry run to preview changes
python utilities/manage_taxes_by_tag.py --tag "civic-day" --action disable --dry-run
```

**Notes:**
- Processes products in batches for performance
- Updates only variants that need changes (skips already-correct variants)
- Supports parallel processing with configurable workers
- Generates CSV report of all changes

---

## Script Features

### Product Query with Tag Filter

The script uses GraphQL to fetch products tagged with specific tags:

```graphql
query {
  products(first: 50, query: "tag:wptt-sale") {
    edges {
      node {
        id
        title
        vendor
        tags
        variants(first: 20) {
          edges {
            node {
              id
              sku
              price
              taxable
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

### Batch Processing
- Configurable batch size (default: 50 products per batch)
- Parallel processing within batches (default: 10 workers)
- Pagination support for large product sets
- Progress tracking and status updates

### Error Handling
- Skips variants that are already in desired state
- Continues processing on individual product errors
- Generates detailed CSV report with error messages
- Supports interruption with partial results

---

## Common Workflows

### "We Pay the Tax" Sale Setup

```bash
# Step 1: Tag products for the sale (use Shopify admin or bulk edit)
# Tag: "wptt-black-friday"

# Step 2: Preview changes with dry run
python utilities/manage_taxes_by_tag.py \
  --tag "wptt-black-friday" \
  --action disable \
  --dry-run

# Step 3: Execute tax changes
python utilities/manage_taxes_by_tag.py \
  --tag "wptt-black-friday" \
  --action disable

# Step 4: After sale ends, re-enable taxes
python utilities/manage_taxes_by_tag.py \
  --tag "wptt-black-friday" \
  --action enable
```

### Fast Processing for Large Sales

```bash
# Process with more workers and larger batches
python utilities/manage_taxes_by_tag.py \
  --tag "boxing-day-sale" \
  --action disable \
  --workers 15 \
  --batch-size 100
```

### Tax Holiday by Category

```bash
# Step 1: Tag all products in category
# Example: Tag all espresso machines with "tax-free-weekend"

# Step 2: Disable taxes
python utilities/manage_taxes_by_tag.py \
  --tag "tax-free-weekend" \
  --action disable

# Step 3: After weekend, re-enable
python utilities/manage_taxes_by_tag.py \
  --tag "tax-free-weekend" \
  --action enable
```

---

## Performance Considerations

### Batch Size
- **Small stores (<500 products)**: 50 products per batch (default)
- **Medium stores (500-2000 products)**: 75-100 products per batch
- **Large stores (>2000 products)**: 100-150 products per batch

### Worker Threads
- **Default**: 10 workers (safe for most stores)
- **Fast processing**: 15-20 workers (monitor API rate limits)
- **Conservative**: 5-8 workers (avoid rate limit issues)

### Rate Limiting
- Script automatically handles Shopify API rate limits
- Pauses 2 seconds between batches
- ThreadPoolExecutor prevents overwhelming the API

---

## CSV Report

The script generates a detailed CSV report with the following fields:

| Field | Description |
|-------|-------------|
| Product_Title | Name of the product |
| Vendor | Product vendor/brand |
| Status | success, skipped, or error |
| Variants_Updated | Number of variants modified |
| Message | Details about the operation |

**Example filename:** `tax_disable_wptt-sale_20250103_143022.csv`

---

## Best Practices

1. **Always use dry-run first** - Preview changes before executing
2. **Tag strategically** - Use clear, date-specific tags (e.g., "wptt-2025-blackfriday")
3. **Keep tags clean** - Remove sale tags after re-enabling taxes
4. **Document sales** - Keep CSV reports for audit trail
5. **Test on small set** - Test with a few products before full rollout
6. **Schedule wisely** - Run during low-traffic periods for large updates
7. **Monitor results** - Check CSV report for errors after execution
8. **Coordinate with team** - Ensure no conflicting bulk operations running

---

## Error Handling

Common errors and solutions:

### "No products found"
- Verify tag exists and is spelled correctly
- Check products are actually tagged
- Confirm products are not archived/deleted

### "UserErrors in response"
- Check API permissions (write_products, read_products required)
- Verify product/variant IDs are valid
- Ensure no conflicting operations in progress

### "Rate limit exceeded"
- Reduce worker count (--workers 5)
- Reduce batch size (--batch-size 25)
- Add longer pause between batches

### Partial completion
- Check CSV report for which products succeeded
- Re-run script (already-updated products will be skipped)
- Investigate errors in CSV report

---

## Related Operations

- Tag management: `products/bulk-tag-products.md`
- Product search: `products/search-products.md`
- Variant updates: `products/update-variants.md`
- Bulk operations: `products/bulk-operations.md`

---

## Technical Notes

### GraphQL Optimization
- Uses `productVariantsBulkUpdate` for efficient batch updates
- Fetches only necessary fields to minimize response size
- Implements cursor-based pagination for large result sets

### Thread Safety
- Creates separate ShopifyClient per thread
- No shared state between parallel operations
- Safe for high-concurrency processing

### Memory Efficiency
- Streams products in batches (doesn't load all products into memory)
- Processes and discards each batch before fetching next
- CSV written incrementally (safe for very large operations)
