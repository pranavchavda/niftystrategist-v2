# List All Product Tags

Fetch all unique tags currently in use across the entire Shopify store.

## Use Cases
- Auditing all tags in the store
- Identifying unused or redundant tags
- Tag cleanup and standardization
- Generating tag reports for merchandising
- Finding misspelled or inconsistent tags
- Exporting tag taxonomy

## GraphQL

```graphql
query {
  products(first: 250, query: "status:active OR status:draft") {
    edges {
      node {
        tags
        status
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

## Query Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `first` | 250 | Number of products per page (max: 250) |
| `query` | "status:active OR status:draft" | Filter to exclude archived products |
| Pagination | `after: "cursor"` | Use `endCursor` for next page |

## Response Fields

- `edges[].node.tags` - Array of tag strings for each product
- `edges[].node.status` - Product status (ACTIVE, DRAFT, ARCHIVED)
- `pageInfo.hasNextPage` - Whether more pages exist
- `pageInfo.endCursor` - Cursor for next page

## Example

```bash
# List all unique tags (excludes archived)
python backend/bash-tools/tags/fetch_all_tags.py

# Include archived products
python backend/bash-tools/tags/fetch_all_tags.py --include-archived

# Output as JSON
python backend/bash-tools/tags/fetch_all_tags.py --output json

# Save to file
python backend/bash-tools/tags/fetch_all_tags.py --output markdown --save tags_report.md

# Filter tags containing specific text
python backend/bash-tools/tags/fetch_all_tags.py --filter "icon-" --output csv
```

## Output Formats

### List (Default)
```
besteseller
breville
consumer
espresso-machines
icon-coffee
icon-grinder
sale
under-1000
WAR-1YR
```

### JSON
```json
[
  "bestseller",
  "breville",
  "consumer",
  "espresso-machines"
]
```

### CSV
```csv
"bestseller","breville","consumer","espresso-machines"
```

### Analysis
```json
{
  "total": 432,
  "categories": {
    "warranty": ["WAR-1YR", "WAR-2YR", "WAR-3YR"],
    "icon": ["icon-coffee", "icon-grinder", "icon-espresso"],
    "shipping": ["shipping-free", "shipping-oversized"],
    "price_range": ["under-500", "under-1000", "over-2000"],
    "vendor": ["breville", "delonghi", "jura"],
    "features": ["pid", "e61-group", "dual-boiler"]
  }
}
```

### Markdown Report
```markdown
# Shopify Product Tags Report

**Total Unique Tags:** 432

## Warranty (5 tags)
- `WAR-1YR`
- `WAR-2YR`
- `WAR-3YR`

## Icon (12 tags)
- `icon-coffee`
- `icon-grinder`
...
```

## Tag Categories Detected

The analysis mode automatically categorizes tags:
- **Warranty**: Tags starting with `WAR-`
- **Icon**: Tags starting with `icon-`
- **Shipping**: Tags starting with `shipping-`
- **Price Range**: Tags containing `under-` or `over-`
- **Product Type**: Tags starting with `NC_`
- **Vendor**: Brand-related tags (Jura, Breville, ECM, etc.)
- **Features**: Technical features (PID, E61, dual-boiler, etc.)
- **Other**: Uncategorized tags

## Performance

- **Pagination**: Fetches 250 products per page
- **Speed**: ~2-3 seconds per page
- **Store Size**: For 1000 products, ~8-10 seconds total
- **Memory**: Efficient set-based deduplication
- **API Calls**: `ceil(product_count / 250)` requests

## Notes
- Returns deduplicated, sorted list of all unique tags
- Case-sensitive sorting (lowercase first)
- Excludes archived products by default (use `--include-archived` to include)
- Pagination handles stores with 10,000+ products
- Operation requires `read_products` scope
- Useful for tag auditing and cleanup planning
- Filter option helps find specific tag patterns
