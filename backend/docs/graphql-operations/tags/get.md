# Get Product Tags

Retrieve all tags for a specific product.

## Use Cases
- Listing current tags before modification
- Auditing product categorization
- Verifying tag operations completed successfully
- Exporting product tag data

## GraphQL

```graphql
query getProductTags($id: ID!) {
  product(id: $id) {
    id
    title
    tags
  }
}
```

## Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | ID! | Yes | Product GID (e.g., "gid://shopify/Product/1234567890") |

## Response Fields

- `product.id` - Product GID
- `product.title` - Product title
- `product.tags` - Array of all tag strings

## Example

```bash
# List tags for a single product
python backend/bash-tools/tags/manage_tags.py --product "breville-barista-express" --list

# List tags for multiple products
python backend/bash-tools/tags/manage_tags_parallel.py --list --file products.txt
```

## Example Response

```json
{
  "data": {
    "product": {
      "id": "gid://shopify/Product/1234567890",
      "title": "Breville Barista Express",
      "tags": [
        "espresso-machines",
        "breville",
        "consumer",
        "under-1000",
        "bestseller"
      ]
    }
  }
}
```

## Notes
- Returns all tags in alphabetical order (Shopify default)
- Empty array if product has no tags
- Operation requires `read_products` scope
- Useful for validation after add/remove operations
