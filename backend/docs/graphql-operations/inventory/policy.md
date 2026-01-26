# Inventory Policy Management

Manage inventory policy (oversell settings) for product variants. Control whether variants can be sold when out of stock.

## Use Cases
- Enable/disable overselling for specific products
- Update inventory tracking policies in bulk
- Configure whether customers can purchase out-of-stock items
- Manage backorder capabilities

## Operations

### 1. Get Product by ID

Retrieve a product and its variants' inventory policies by Shopify product ID.

**GraphQL Query:**
```graphql
query getProduct($id: ID!) {
  product(id: $id) {
    id
    title
    handle
    variants(first: 100) {
      edges {
        node {
          id
          sku
          title
          inventoryPolicy
          price
        }
      }
    }
  }
}
```

**Variables:**
| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | `ID!` | Yes | Shopify product GID (e.g., `gid://shopify/Product/123456`) |

**Required Scopes:** `read_products`

**Example:**
```bash
python core/graphql_query.py 'query getProduct($id: ID!) { ... }' --variables '{"id": "gid://shopify/Product/123456"}'
```

---

### 2. Find Product by SKU

Search for products by SKU and retrieve inventory policy information.

**GraphQL Query:**
```graphql
query findBySku($query: String!) {
  productVariants(first: 10, query: $query) {
    edges {
      node {
        id
        sku
        inventoryPolicy
        product {
          id
          title
          handle
          variants(first: 100) {
            edges {
              node {
                id
                sku
                title
                inventoryPolicy
                price
              }
            }
          }
        }
      }
    }
  }
}
```

**Variables:**
| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `query` | `String!` | Yes | Search query (e.g., `sku:BES870XL`) |

**Required Scopes:** `read_products`

**Example:**
```bash
python core/graphql_query.py 'query findBySku($query: String!) { ... }' --variables '{"query": "sku:BES870XL"}'
```

---

### 3. Find Product by Handle or Title

Search for products by handle or title to retrieve inventory policy settings.

**GraphQL Query:**
```graphql
query findProduct($query: String!) {
  products(first: 10, query: $query) {
    edges {
      node {
        id
        title
        handle
        variants(first: 100) {
          edges {
            node {
              id
              sku
              title
              inventoryPolicy
              price
            }
          }
        }
      }
    }
  }
}
```

**Variables:**
| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `query` | `String!` | Yes | Search query (e.g., `handle:bambino-plus` or `title:"Bambino Plus"`) |

**Required Scopes:** `read_products`

**Example:**
```bash
python core/graphql_query.py 'query findProduct($query: String!) { ... }' --variables '{"query": "handle:bambino-plus"}'
```

---

### 4. Update Inventory Policy (Bulk)

Update the inventory policy for one or more variants in a single operation.

**GraphQL Mutation:**
```graphql
mutation updateVariants($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      id
      sku
      inventoryPolicy
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
| `productId` | `ID!` | Yes | Shopify product GID |
| `variants` | `[ProductVariantsBulkInput!]!` | Yes | Array of variant updates with `id` and `inventoryPolicy` |

**Inventory Policy Values:**
- `CONTINUE` - Allow overselling (customers can purchase when out of stock)
- `DENY` - Block sales when out of stock

**Required Scopes:** `write_products`, `read_products`

**Example:**
```bash
python core/graphql_mutation.py 'mutation updateVariants($productId: ID!, $variants: [ProductVariantsBulkInput!]!) { ... }' --variables '{
  "productId": "gid://shopify/Product/123456",
  "variants": [
    {
      "id": "gid://shopify/ProductVariant/789012",
      "inventoryPolicy": "CONTINUE"
    }
  ]
}'
```

---

## Notes

- **Policy Values**: The script accepts `allow`/`ALLOW` as user-friendly aliases and converts them to `CONTINUE` for the API
- **Bulk Updates**: The `productVariantsBulkUpdate` mutation can update multiple variants in a single call
- **Error Handling**: Always check the `userErrors` field in mutation responses for validation errors
- **Status Display**: When displaying to users, `CONTINUE` can be shown as "ALLOW" for better UX
- **Search Syntax**: Supports multiple identifier types (GID, SKU, handle, title) for flexible product lookup

## Related Scripts

- **Script:** `backend/bash-tools/inventory/manage_inventory_policy.py`
- **Usage:** `python manage_inventory_policy.py --identifier "SKU123" --policy deny`
