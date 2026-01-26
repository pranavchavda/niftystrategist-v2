# Product Search

Search for products using Shopify's powerful search query syntax with support for filters, tags, price ranges, inventory, and more.

## Use Cases
- Find products by title, vendor, or SKU
- Search products with specific tags (e.g., "tag:sale", "tag:featured")
- Filter by status (ACTIVE, DRAFT, ARCHIVED)
- Filter by price range
- Find products with/without inventory
- Combine multiple search criteria

## GraphQL

```graphql
query searchProducts($query: String!, $first: Int!) {
  products(first: $first, query: $query) {
    edges {
      node {
        id
        title
        handle
        vendor
        status
        productType
        priceRangeV2 {
          minVariantPrice {
            amount
            currencyCode
          }
        }
        compareAtPriceRange {
          minVariantCompareAtPrice {
            amount
            currencyCode
          }
        }
        totalInventory
        variants(first: 5) {
          edges {
            node {
              id
              title
              sku
              price
              compareAtPrice
              inventoryQuantity
            }
          }
        }
        seo {
          title
          description
        }
      }
    }
    pageInfo {
      hasNextPage
    }
  }
}
```

## Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| query | String | Yes | Search query using Shopify search syntax |
| first | Int | Yes | Maximum number of products to return (limit) |

## Search Syntax Examples

### Basic Search
- `"coffee"` - Search for "coffee" in title/description
- `"espresso machine"` - Multiple words

### Tags
- `"tag:sale"` - Products with "sale" tag
- `"tag:featured tag:new"` - Multiple tags (AND)
- `"-tag:discontinued"` - Exclude tag

### Filters
- `"vendor:Breville"` - Filter by vendor
- `"product_type:Grinders"` - Filter by product type
- `"status:active"` - Filter by status (ACTIVE, DRAFT, ARCHIVED)

### Price
- `"price:>100"` - Price greater than $100
- `"price:10..100"` - Price between $10 and $100
- `"price:<50"` - Price less than $50

### Inventory
- `"inventory_quantity:>0"` - In stock
- `"inventory_quantity:0"` - Out of stock

### SKU/Handle
- `"sku:BRE870XL"` - Find by SKU
- `"handle:delonghi-dedica"` - Find by handle

### Combinations
- `"coffee tag:premium price:>20"` - Multiple criteria
- `"vendor:DeLonghi tag:sale status:active"` - Complex search

## Example

```bash
# Search for active sale products from Breville
python core/graphql_query.py 'query searchProducts($query: String!, $first: Int!) { products(first: $first, query: $query) { edges { node { id title handle vendor status priceRangeV2 { minVariantPrice { amount currencyCode } } } } pageInfo { hasNextPage } } }' --variables '{"query": "vendor:Breville tag:sale status:active", "first": 10}'

# Using search_products.py script
python products/search_products.py "vendor:Breville tag:sale" --limit 10
```

## Response Structure

```json
{
  "data": {
    "products": {
      "edges": [
        {
          "node": {
            "id": "gid://shopify/Product/1234567890",
            "title": "Breville Barista Express",
            "handle": "breville-barista-express",
            "vendor": "Breville",
            "status": "ACTIVE",
            "productType": "Espresso Machines",
            "priceRangeV2": {
              "minVariantPrice": {
                "amount": "699.99",
                "currencyCode": "CAD"
              }
            },
            "compareAtPriceRange": {
              "minVariantCompareAtPrice": {
                "amount": "899.99",
                "currencyCode": "CAD"
              }
            },
            "totalInventory": 5,
            "variants": {
              "edges": [
                {
                  "node": {
                    "id": "gid://shopify/ProductVariant/9876543210",
                    "title": "Default Title",
                    "sku": "BRE870XL",
                    "price": "699.99",
                    "compareAtPrice": "899.99",
                    "inventoryQuantity": 5
                  }
                }
              ]
            },
            "seo": {
              "title": "Breville Barista Express Espresso Machine",
              "description": "Professional espresso machine for home use"
            }
          }
        }
      ],
      "pageInfo": {
        "hasNextPage": false
      }
    }
  }
}
```

## Notes
- The `query` parameter uses Shopify's search syntax, not GraphQL filters
- Maximum 250 products per query (paginate for more)
- Use `pageInfo.hasNextPage` to check if more results exist
- Product tags are NOT included in search results - use `get_product.py` to fetch detailed product information with tags
- Search is case-insensitive for most fields
- Wildcards are not supported - use partial matches instead

## Required Scopes
- `read_products`
