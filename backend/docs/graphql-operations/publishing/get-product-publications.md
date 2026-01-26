# Get Product Publications

Query to retrieve a product's publication status across all sales channels.

## Use Cases
- Check which sales channels a product is currently published to
- Verify publication status before publishing/unpublishing
- Audit product visibility across channels
- Display current publication status in admin interfaces

## GraphQL

```graphql
query getProduct($id: ID!) {
    product(id: $id) {
        id
        title
        status
        resourcePublicationsV2(first: 50) {
            edges {
                node {
                    publication {
                        id
                        name
                    }
                    isPublished
                }
            }
        }
    }
}
```

## Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | `ID!` | Yes | Product GID (e.g., `gid://shopify/Product/123456`) |

## Response Fields

- **id**: Product GID
- **title**: Product name
- **status**: Product status (ACTIVE, DRAFT, ARCHIVED)
- **resourcePublicationsV2**: List of publication channels
  - **publication.id**: Publication channel GID
  - **publication.name**: Channel name (e.g., "Online Store", "POS")
  - **isPublished**: Boolean indicating if product is published to this channel

## Example

```bash
# Get product by GID
python core/graphql_query.py 'query getProduct($id: ID!) { product(id: $id) { id title status resourcePublicationsV2(first: 50) { edges { node { publication { id name } isPublished } } } } }' --variables '{"id": "gid://shopify/Product/123456"}'

# Get product by handle (requires resolution first)
python search_products.py BRE0001  # Get GID
python core/graphql_query.py 'query getProduct($id: ID!) { ... }' --variables '{"id": "gid://shopify/Product/..."}'
```

## Required OAuth Scopes

- `read_products`
- `read_publications`

## Notes

- Returns up to 50 publications per query (configurable with `first` parameter)
- Use `resourcePublicationsV2` (not deprecated `publications` field)
- Product must exist and be accessible to the API token
- Publication IDs are store-specific and vary between environments
- Common publications: Online Store, POS, Google & YouTube, Facebook & Instagram, Shop, Hydrogen
