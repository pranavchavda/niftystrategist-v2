# Manage Product Status

Unified tool for managing product status (ACTIVE, DRAFT, ARCHIVED) for single products, bulk operations from files, or search-based updates.

## Use Cases
- Activate draft products for sale
- Draft products temporarily (hide from storefront)
- Archive discontinued products
- Bulk status changes from file
- Status changes based on search criteria (e.g., all products with specific tag)

## GraphQL

### Get Product Status

```graphql
query getProductStatus($id: ID!) {
  product(id: $id) {
    id
    title
    status
  }
}
```

### Update Product Status

```graphql
mutation updateProductStatus($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      status
    }
    userErrors {
      field
      message
    }
  }
}
```

### Search Products by Query

```graphql
query searchProducts($query: String!, $first: Int!, $after: String) {
  products(first: $first, query: $query, after: $after) {
    edges {
      node {
        id
        title
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

## Variables

### Status Update Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| input.id | ID | Yes | Product GID |
| input.status | ProductStatus | Yes | ACTIVE, DRAFT, or ARCHIVED |

### Search Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| query | String | Yes | Shopify search query |
| first | Int | Yes | Products per page (max 50) |
| after | String | No | Pagination cursor |

## Status Types

| Status | Description | Visibility |
|--------|-------------|------------|
| ACTIVE | Product is live and available for sale | Visible on storefront, available for purchase |
| DRAFT | Product exists but is not published | Hidden from storefront, visible in admin only |
| ARCHIVED | Product is discontinued/removed | Hidden from storefront, kept for historical records |

## Examples

### Single Product

```bash
# Activate a product
python products/manage_status.py --product "BRE0001" --status ACTIVE

# Draft a product (by handle)
python products/manage_status.py -p "delonghi-dedica" -s DRAFT

# Archive a product
python products/manage_status.py -p "old-product-handle" -s ARCHIVED

# Check current status
python products/manage_status.py --product "BRE0001" --check
```

### Bulk Operations from File

```bash
# Archive multiple products (one ID/SKU/handle per line)
python products/manage_status.py --file products.txt --status ARCHIVED

# Draft products with dry run (preview only)
python products/manage_status.py -f to_draft.txt -s DRAFT --dry-run
```

Example file (`products.txt`):
```
BRE0001
delonghi-dedica-ec685m
gid://shopify/Product/1234567890
discontinued-grinder
```

### Bulk by Search Query

```bash
# Archive all discontinued products
python products/manage_status.py --query "tag:discontinued" --status ARCHIVED

# Activate all sale products
python products/manage_status.py -q "tag:sale" -s ACTIVE

# Draft products from specific vendor
python products/manage_status.py -q "vendor:Pesado tag:old-model" -s DRAFT --dry-run
```

## Request Example

### Single Product Update

```json
{
  "input": {
    "id": "gid://shopify/Product/1234567890",
    "status": "ACTIVE"
  }
}
```

### Search Query Example

```json
{
  "query": "vendor:Breville tag:discontinued",
  "first": 50
}
```

## Response Structure

### Successful Update

```json
{
  "data": {
    "productUpdate": {
      "product": {
        "id": "gid://shopify/Product/1234567890",
        "title": "DeLonghi Dedica Style EC685M",
        "status": "ACTIVE"
      },
      "userErrors": []
    }
  }
}
```

### Already at Target Status

Script output:
```
[1/1] BRE0001... SKIPPED: Already ACTIVE
```

### Product Not Found

Script output:
```
[1/1] invalid-handle... NOT FOUND
```

## Script Output Examples

### Single Product

```
Breville Barista Express: Changed DRAFT -> ACTIVE
```

### Bulk from File

```
Processing 10 products from products.txt

[1/10] BRE0001... OK: Changed DRAFT -> ARCHIVED
[2/10] EC685M... SKIPPED: Already ARCHIVED
[3/10] invalid-sku... NOT FOUND
[4/10] old-grinder... OK: Changed ACTIVE -> ARCHIVED
...

Summary:
  Success: 7
  Skipped: 2
  Failed:  1

Failed products:
  - invalid-sku: Not found
```

### Bulk by Search Query

```
Searching for products matching: tag:discontinued
Found 15 products: 12 to update, 3 already ARCHIVED

[1/12] Old Espresso Machine... OK: Changed ACTIVE -> ARCHIVED
[2/12] Discontinued Grinder... OK: Changed DRAFT -> ARCHIVED
...

Summary:
  Success: 12
  Skipped: 3
  Failed:  0
```

## Dry Run Mode

Preview changes without actually making them:

```bash
python products/manage_status.py \
  --query "vendor:OldBrand" \
  --status ARCHIVED \
  --dry-run
```

Output:
```
DRY RUN - No changes will be made

Searching for products matching: vendor:OldBrand
Found 20 products: 20 to update, 0 already ARCHIVED

[1/20] Product 1... OK: Would change ACTIVE -> ARCHIVED
[2/20] Product 2... OK: Would change DRAFT -> ARCHIVED
...

DRY RUN Summary:
  Success: 20
  Skipped: 0
  Failed:  0
```

## Notes
- This script **replaces** the old separate scripts:
  - `archive_products.py`
  - `unarchive_products.py`
  - `update_status.py`
  - `update_product_status.py`
- Product identifiers can be:
  - Product ID (numeric or GID)
  - Product handle
  - Product SKU
- Status changes are immediate (no undo)
- Use `--dry-run` to preview changes before committing
- Bulk operations process up to 50 products at a time
- Search queries support full Shopify search syntax
- Products already at target status are skipped (counted but not updated)
- Status changes do not affect product data, variants, or inventory

## Status Change Effects

### DRAFT → ACTIVE
- Product becomes visible on storefront
- Available for purchase (if inventory available)
- Appears in search results and collections

### ACTIVE → DRAFT
- Product hidden from storefront immediately
- Not available for purchase
- Removed from search results and collections
- Existing cart items remain (until checkout)

### ACTIVE/DRAFT → ARCHIVED
- Product completely removed from storefront
- Not available for purchase
- Kept in admin for historical/reporting purposes
- Cannot be restored to ACTIVE without manual intervention

### ARCHIVED → DRAFT/ACTIVE
- Restores product to specified status
- Re-publishes to channels if needed
- Inventory and data remain intact

## Common Use Cases

### Seasonal Products
```bash
# Draft seasonal products at end of season
python products/manage_status.py -q "tag:seasonal tag:summer" -s DRAFT

# Activate for next season
python products/manage_status.py -q "tag:seasonal tag:summer" -s ACTIVE
```

### Discontinued Products
```bash
# Archive discontinued items
python products/manage_status.py -q "tag:discontinued" -s ARCHIVED
```

### Sale Events
```bash
# Activate sale products
python products/manage_status.py -q "tag:black-friday-2024" -s ACTIVE

# Draft after sale ends
python products/manage_status.py -q "tag:black-friday-2024" -s DRAFT
```

## Required Scopes
- `write_products`
- `read_products`
