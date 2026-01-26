# Get Active Products with Pagination

Query to retrieve all active products from a store with cursor-based pagination.

## Use Cases
- Bulk publishing workflows (publish all active products to a channel)
- Inventory audits and reports
- Product exports and backups
- Finding products for batch operations
- Parts store synchronization

## GraphQL

```graphql
query getProducts($cursor: String) {
    products(first: 250, after: $cursor, query: "status:active") {
        edges {
            node {
                id
            }
        }
        pageInfo {
            hasNextPage
            endCursor
        }
    }
}
```

## Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `cursor` | `String` | No | Pagination cursor from previous query's `pageInfo.endCursor` |

## Response Fields

- **edges**: Array of product nodes
  - **node.id**: Product GID
- **pageInfo**: Pagination metadata
  - **hasNextPage**: Boolean indicating if more results exist
  - **endCursor**: Cursor for next page of results

## Query Parameters

The `query` parameter supports Shopify's search syntax:
- `status:active` - Only active products
- `status:draft` - Only draft products
- `status:archived` - Only archived products
- Multiple filters: `status:active AND vendor:Breville`

See: [Shopify Search Syntax](https://shopify.dev/docs/api/usage/search-syntax)

## Pagination Example

```python
# First page
result1 = execute_graphql(query, {"cursor": None})
product_ids = [edge["node"]["id"] for edge in result1["data"]["products"]["edges"]]

# Check if more pages
if result1["data"]["products"]["pageInfo"]["hasNextPage"]:
    cursor = result1["data"]["products"]["pageInfo"]["endCursor"]

    # Second page
    result2 = execute_graphql(query, {"cursor": cursor})
    product_ids += [edge["node"]["id"] for edge in result2["data"]["products"]["edges"]]

    # Continue until hasNextPage is False
```

## Example

```bash
# Get first page of active products
python core/graphql_query.py 'query getProducts($cursor: String) { products(first: 250, after: $cursor, query: "status:active") { edges { node { id } } pageInfo { hasNextPage endCursor } } }' --variables '{}'

# Get next page using cursor
python core/graphql_query.py 'query getProducts($cursor: String) { products(first: 250, after: $cursor, query: "status:active") { edges { node { id } } pageInfo { hasNextPage endCursor } } }' --variables '{"cursor": "eyJsYXN0X2lkIjo4..."}'

# Using publish.py to publish all active products
python publishing/publish.py --all --channels parts --fast
```

## Required OAuth Scopes

- `read_products`

## Performance Notes

- **Maximum per page**: 250 products (Shopify GraphQL limit)
- **Recommended page size**: 100-250 for balance of speed vs. memory
- **Rate limits**: ~50 requests/second with GraphQL API
- **Cursor caching**: Cursors expire after ~24 hours

## Advanced Filtering

```graphql
# Active products from specific vendor
query: "status:active AND vendor:Breville"

# Products with inventory > 0
query: "status:active AND inventory_total:>0"

# Products in price range
query: "status:active AND price:>100 AND price:<500"

# Products by tag
query: "status:active AND tag:espresso-machine"
```

## Notes

- Always check `hasNextPage` to determine if pagination should continue
- Store the `endCursor` to fetch the next page
- Cursors are opaque strings - do not attempt to parse or modify
- Empty results: `edges` will be empty array when no products match
- Use smaller page sizes (`first: 50`) for complex queries with many fields
- For very large stores (>10,000 products), consider implementing checkpoint/resume logic
- The `id` field returns GIDs suitable for mutations (e.g., `publishablePublish`)
