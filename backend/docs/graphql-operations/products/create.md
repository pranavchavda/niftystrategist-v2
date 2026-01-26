# Create Product

Create a basic product with a single variant. This is a simplified creation method suitable for products without extensive configuration.

## Use Cases
- Quick product creation with minimal configuration
- Create draft products for later enhancement
- Add simple products with one variant
- Prototype product listings

## GraphQL

### Main Mutation

```graphql
mutation createProduct($input: ProductInput!) {
  productCreate(input: $input) {
    product {
      id
      title
      handle
      status
      tags
      variants(first: 1) {
        edges {
          node {
            id
            sku
            price
          }
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
```

### Get Default Location (Required for Inventory)

```graphql
query getLocations {
  locations(first: 1) {
    edges {
      node {
        id
        name
        isActive
      }
    }
  }
}
```

## Variables

### ProductInput

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| input.title | String | Yes | Product title |
| input.vendor | String | Yes | Product vendor/brand |
| input.productType | String | Yes | Product category/type |
| input.descriptionHtml | String | No | Product description (HTML) |
| input.tags | [String] | No | Array of product tags |
| input.status | ProductStatus | No | DRAFT, ACTIVE, or ARCHIVED (default: DRAFT) |
| input.variants | [ProductVariantInput] | No | Variant configuration (price, SKU, inventory) |

### ProductVariantInput

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| price | Decimal | Yes | Variant price |
| sku | String | No | Stock Keeping Unit |
| barcode | String | No | Product barcode |
| weight | Float | No | Product weight (in weight unit) |
| weightUnit | WeightUnit | No | GRAMS, KILOGRAMS, OUNCES, or POUNDS |
| inventoryQuantities | [InventoryLevelInput] | No | Initial inventory by location |
| inventoryPolicy | ProductVariantInventoryPolicy | No | DENY (stop at 0) or CONTINUE (allow negatives) |
| inventoryManagement | ProductVariantInventoryManagement | No | SHOPIFY or null (no tracking) |

## Example

```bash
# Basic product
python products/create_product.py \
  --title "Test Product" \
  --vendor "Brand" \
  --type "Category" \
  --price 99.99

# Full configuration
python products/create_product.py \
  --title "DeLonghi Dedica Style EC685M" \
  --vendor "DeLonghi" \
  --type "Espresso Machines" \
  --description "Compact espresso machine with professional features" \
  --tags "espresso-machines,delonghi,consumer" \
  --price 249.99 \
  --sku "EC685M" \
  --barcode "8004399331396" \
  --weight 4.2 \
  --weight-unit KILOGRAMS \
  --inventory 10 \
  --status ACTIVE

# Without inventory tracking
python products/create_product.py \
  --title "Digital Gift Card" \
  --vendor "Store" \
  --type "Gift Cards" \
  --price 50.00 \
  --no-track-inventory
```

## Request Example

```json
{
  "input": {
    "title": "DeLonghi Dedica Style EC685M",
    "vendor": "DeLonghi",
    "productType": "Espresso Machines",
    "descriptionHtml": "<p>Compact espresso machine with professional features</p>",
    "tags": ["espresso-machines", "delonghi", "consumer"],
    "status": "DRAFT",
    "variants": [
      {
        "price": "249.99",
        "sku": "EC685M",
        "barcode": "8004399331396",
        "weight": 4.2,
        "weightUnit": "KILOGRAMS",
        "inventoryQuantities": [
          {
            "availableQuantity": 10,
            "locationId": "gid://shopify/Location/12345"
          }
        ],
        "inventoryManagement": "SHOPIFY"
      }
    ]
  }
}
```

## Response Structure

```json
{
  "data": {
    "productCreate": {
      "product": {
        "id": "gid://shopify/Product/1234567890",
        "title": "DeLonghi Dedica Style EC685M",
        "handle": "delonghi-dedica-style-ec685m",
        "status": "DRAFT",
        "tags": ["espresso-machines", "delonghi", "consumer"],
        "variants": {
          "edges": [
            {
              "node": {
                "id": "gid://shopify/ProductVariant/9876543210",
                "sku": "EC685M",
                "price": "249.99"
              }
            }
          ]
        }
      },
      "userErrors": []
    }
  }
}
```

## Notes
- Products are created in DRAFT status by default
- The handle (URL slug) is auto-generated from the title if not specified
- At least one variant is required - if not provided, a default variant is created
- Inventory location ID must be valid - use `getLocations` query to fetch
- HTML in description must be valid - use `<br>` for line breaks
- Tags are case-sensitive
- For products with complex configuration (metafields, multiple variants, etc.), use `create_full_product.py` instead
- Product images must be added separately after creation
- SKU must be unique across the store

## Common Errors

### Missing Required Fields
```json
{
  "userErrors": [
    {
      "field": ["input", "title"],
      "message": "Title can't be blank"
    }
  ]
}
```

### Invalid Location ID
```json
{
  "userErrors": [
    {
      "field": ["input", "variants", "0", "inventoryQuantities", "0", "locationId"],
      "message": "Location not found"
    }
  ]
}
```

### Duplicate SKU
```json
{
  "userErrors": [
    {
      "field": ["input", "variants", "0", "sku"],
      "message": "SKU must be unique"
    }
  ]
}
```

## Required Scopes
- `write_products`
- `read_products`
