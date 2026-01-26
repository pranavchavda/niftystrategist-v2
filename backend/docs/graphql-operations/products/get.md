# Get Product Details

Retrieve comprehensive product information including variants, images, metafields, collections, and inventory details.

## Use Cases
- Get complete product data by ID
- Fetch product with all variants and pricing
- Retrieve product metafields for custom data
- Get product images and SEO information
- Check inventory levels and costs
- View product collections and options

## GraphQL

```graphql
query getProduct($id: ID!) {
  product(id: $id) {
    id
    title
    handle
    description
    descriptionHtml
    vendor
    productType
    status
    tags
    createdAt
    updatedAt
    publishedAt
    seo {
      title
      description
    }
    priceRangeV2 {
      minVariantPrice {
        amount
        currencyCode
      }
      maxVariantPrice {
        amount
        currencyCode
      }
    }
    totalInventory
    tracksInventory
    featuredImage {
      url
      altText
    }
    images(first: 5) {
      edges {
        node {
          url
          altText
        }
      }
    }
    variants(first: 100) {
      edges {
        node {
          id
          title
          sku
          barcode
          price
          compareAtPrice
          inventoryQuantity
          availableForSale
          inventoryItem {
            id
            unitCost {
              amount
            }
            measurement {
              weight {
                value
                unit
              }
            }
          }
          selectedOptions {
            name
            value
          }
        }
      }
    }
    options {
      name
      values
    }
    collections(first: 10) {
      edges {
        node {
          id
          title
          handle
        }
      }
    }
    metafields(first: 20) {
      edges {
        node {
          namespace
          key
          value
          type
        }
      }
    }
  }
}
```

## Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| id | ID | Yes | Product GID (e.g., "gid://shopify/Product/1234567890") |

## Example

```bash
# Get product by ID
python core/graphql_query.py 'query getProduct($id: ID!) { product(id: $id) { id title handle vendor status priceRangeV2 { minVariantPrice { amount } } } }' --variables '{"id": "gid://shopify/Product/1234567890"}'

# Using get_product.py script (resolves ID from handle, SKU, or ID)
python products/get_product.py "delonghi-dedica"
python products/get_product.py "EC685M"
python products/get_product.py "1234567890"

# Include metafields
python products/get_product.py "EC685M" --metafields

# Extract specific field
python products/get_product.py "EC685M" --field "priceRangeV2.minVariantPrice.amount"
```

## Response Structure

```json
{
  "data": {
    "product": {
      "id": "gid://shopify/Product/1234567890",
      "title": "DeLonghi Dedica Style EC685M",
      "handle": "delonghi-dedica-ec685m",
      "description": "Compact espresso machine with professional features",
      "descriptionHtml": "<p>Compact espresso machine with professional features</p>",
      "vendor": "DeLonghi",
      "productType": "Espresso Machines",
      "status": "ACTIVE",
      "tags": ["espresso-machines", "delonghi", "consumer", "sale"],
      "createdAt": "2024-01-15T10:30:00Z",
      "updatedAt": "2024-11-20T14:45:00Z",
      "publishedAt": "2024-01-20T09:00:00Z",
      "seo": {
        "title": "DeLonghi Dedica EC685M - Compact Espresso Machine",
        "description": "Professional espresso at home with DeLonghi Dedica"
      },
      "priceRangeV2": {
        "minVariantPrice": {
          "amount": "249.99",
          "currencyCode": "CAD"
        },
        "maxVariantPrice": {
          "amount": "249.99",
          "currencyCode": "CAD"
        }
      },
      "totalInventory": 10,
      "tracksInventory": true,
      "featuredImage": {
        "url": "https://cdn.shopify.com/s/files/1/0001/2345/products/ec685m.jpg",
        "altText": "DeLonghi Dedica EC685M"
      },
      "images": {
        "edges": [
          {
            "node": {
              "url": "https://cdn.shopify.com/s/files/1/0001/2345/products/ec685m-front.jpg",
              "altText": "Front view"
            }
          }
        ]
      },
      "variants": {
        "edges": [
          {
            "node": {
              "id": "gid://shopify/ProductVariant/9876543210",
              "title": "Default Title",
              "sku": "EC685M",
              "barcode": "8004399331396",
              "price": "249.99",
              "compareAtPrice": "299.99",
              "inventoryQuantity": 10,
              "availableForSale": true,
              "inventoryItem": {
                "id": "gid://shopify/InventoryItem/1111111111",
                "unitCost": {
                  "amount": "150.00"
                },
                "measurement": {
                  "weight": {
                    "value": 4.2,
                    "unit": "KILOGRAMS"
                  }
                }
              },
              "selectedOptions": [
                {
                  "name": "Title",
                  "value": "Default Title"
                }
              ]
            }
          }
        ]
      },
      "options": [
        {
          "name": "Title",
          "values": ["Default Title"]
        }
      ],
      "collections": {
        "edges": [
          {
            "node": {
              "id": "gid://shopify/Collection/123456",
              "title": "Espresso Machines",
              "handle": "espresso-machines"
            }
          }
        ]
      },
      "metafields": {
        "edges": [
          {
            "node": {
              "namespace": "specs",
              "key": "techjson",
              "value": "{\"boiler\": \"Thermoblock\", \"pressure\": \"15 bar\"}",
              "type": "json"
            }
          }
        ]
      }
    }
  }
}
```

## Notes
- The `get_product.py` script can resolve products by:
  - Product ID (numeric or GID format)
  - Product handle (URL slug)
  - Product SKU
  - Product title (exact match)
- Metafields are optional - only included if `--metafields` flag is used
- Maximum 100 variants returned (most products have far fewer)
- Images limited to first 5 for performance (increase if needed)
- Product tags are included in this query (unlike search results)
- Use `--field` parameter to extract specific nested values
- Cost information requires `inventoryItem.unitCost` field

## Required Scopes
- `read_products`
- `read_inventory` (for inventory and cost data)
