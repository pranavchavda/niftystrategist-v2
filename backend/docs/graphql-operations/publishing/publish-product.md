# Publish Product to Sales Channels

Mutation to publish a product to one or more sales channels (publications).

## Use Cases
- Publish products to Online Store, POS, Google Shopping, Facebook/Instagram
- Make products visible on specific sales channels
- Bulk publish products during onboarding or promotions
- Restore visibility after unpublishing
- Multi-channel publishing workflows

## GraphQL

```graphql
mutation publishProduct($id: ID!, $input: [PublicationInput!]!) {
    publishablePublish(id: $id, input: $input) {
        publishable {
            ... on Product {
                id
            }
        }
        userErrors {
            field
            message
        }
    }
}
```

## Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | `ID!` | Yes | Product GID (e.g., `gid://shopify/Product/123456`) |
| `input` | `[PublicationInput!]!` | Yes | Array of publication configurations |
| `input[].publicationId` | `ID!` | Yes | Publication channel GID (e.g., `gid://shopify/Publication/46590273`) |

## Publication Input Schema

```typescript
{
  "id": "gid://shopify/Product/123456",
  "input": [
    {
      "publicationId": "gid://shopify/Publication/46590273"  // Online Store
    },
    {
      "publicationId": "gid://shopify/Publication/46590337"  // Point of Sale
    }
  ]
}
```

## Common Publication IDs

### Main Store (iDrinkCoffee.com)
- **Online Store**: `gid://shopify/Publication/46590273`
- **Point of Sale**: `gid://shopify/Publication/46590337`
- **Google & YouTube**: `gid://shopify/Publication/22067970082`
- **Facebook & Instagram**: `gid://shopify/Publication/44906577954`
- **Shop**: `gid://shopify/Publication/93180952610`
- **Hydrogen**: `gid://shopify/Publication/231226015778`

### Parts Store
- **Parts 2025**: `gid://shopify/Publication/106935648353`

**Note**: Publication IDs are store-specific and environment-dependent. Query `publications` to get current IDs.

## Response Fields

- **publishable**: Published resource (product)
  - **id**: Confirmed product GID
- **userErrors**: Array of errors if operation failed
  - **field**: Field that caused the error
  - **message**: Human-readable error description

## Example

```bash
# Publish to single channel
python core/graphql_mutation.py 'mutation publishProduct($id: ID!, $input: [PublicationInput!]!) { publishablePublish(id: $id, input: $input) { publishable { ... on Product { id } } userErrors { field message } } }' --variables '{"id": "gid://shopify/Product/123456", "input": [{"publicationId": "gid://shopify/Publication/46590273"}]}'

# Publish to multiple channels
python core/graphql_mutation.py 'mutation publishProduct($id: ID!, $input: [PublicationInput!]!) { publishablePublish(id: $id, input: $input) { publishable { ... on Product { id } } userErrors { field message } } }' --variables '{"id": "gid://shopify/Product/123456", "input": [{"publicationId": "gid://shopify/Publication/46590273"}, {"publicationId": "gid://shopify/Publication/46590337"}]}'

# Using publish.py wrapper
python publishing/publish.py --product BRE0001 --channels main
python publishing/publish.py --file products.txt --channels parts --fast
```

## Required OAuth Scopes

- `write_publications`
- `read_products`

## Error Handling

Common errors:
- **"Product not found"**: Invalid product GID or product doesn't exist
- **"Publication not found"**: Invalid publication GID
- **"Product already published"**: Product is already published to this channel (not an error, operation succeeds)
- **"Product must be active"**: Cannot publish DRAFT or ARCHIVED products

## Notes

- Publishing is idempotent - safe to call multiple times
- Product must have ACTIVE status to publish
- Publishing to a channel where already published is a no-op (succeeds silently)
- Use `publishableUnpublish` mutation to remove from channels
- Some channels may have additional requirements (e.g., Google Shopping requires specific fields)
- Rate limits: Standard GraphQL rate limits apply (~50-100 requests/sec)
- For bulk operations (>100 products), use `publish.py --fast` with concurrent workers
