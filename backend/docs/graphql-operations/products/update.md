# Update Product Description

Update a product's description (HTML content) by product handle or ID.

## Use Cases
- Update product descriptions with new information
- Fix typos or improve product copy
- Add or modify HTML formatting
- Bulk description updates

## GraphQL

### Get Product by Handle

```graphql
query GetProductByHandle($handle: String!) {
  productByHandle(handle: $handle) {
    id
    title
    description
  }
}
```

### Update Description

```graphql
mutation updateProductDescription($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      description
    }
    userErrors {
      field
      message
    }
  }
}
```

## Variables

### Query Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| handle | String | Yes | Product handle (URL slug) |

### Mutation Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| input.id | ID | Yes | Product GID |
| input.descriptionHtml | String | Yes | New product description (HTML format) |

## Example

```bash
# Update by handle
python products/update_product_description.py \
  "delonghi-dedica-style" \
  --description "Compact espresso machine with professional 15-bar pump pressure. Features a slim 15cm design perfect for small kitchens."

# Update by product ID
python products/update_product_description.py \
  "gid://shopify/Product/1234567890" \
  --description "<h2>Key Features</h2><ul><li>15 bar pump pressure</li><li>Thermoblock heating system</li><li>Manual frother</li></ul>"

# Update by numeric ID
python products/update_product_description.py \
  "1234567890" \
  --description "Updated description with new features and benefits."
```

## Request Example

### Step 1: Get Product ID (if using handle)

```json
{
  "handle": "delonghi-dedica-style"
}
```

Response:
```json
{
  "data": {
    "productByHandle": {
      "id": "gid://shopify/Product/1234567890",
      "title": "DeLonghi Dedica Style EC685M",
      "description": "Old description text"
    }
  }
}
```

### Step 2: Update Description

```json
{
  "input": {
    "id": "gid://shopify/Product/1234567890",
    "descriptionHtml": "<p>Compact espresso machine with professional features. The slim 15cm design fits perfectly in any kitchen while delivering café-quality espresso with its 15-bar pump and thermoblock heating system.</p><h3>What's Included</h3><ul><li>Espresso machine</li><li>Portafilter</li><li>Measuring spoon</li><li>Tamper</li></ul>"
  }
}
```

## Response Structure

```json
{
  "data": {
    "productUpdate": {
      "product": {
        "id": "gid://shopify/Product/1234567890",
        "title": "DeLonghi Dedica Style EC685M",
        "description": "Compact espresso machine with professional features. The slim 15cm design fits perfectly in any kitchen while delivering café-quality espresso with its 15-bar pump and thermoblock heating system.\n\nWhat's Included\n\nEspresso machine\nPortafilter\nMeasuring spoon\nTamper"
      },
      "userErrors": []
    }
  }
}
```

## HTML Formatting

The `descriptionHtml` field accepts HTML. Common tags:

- `<p>` - Paragraphs
- `<br>` - Line breaks
- `<h2>`, `<h3>` - Headings
- `<ul>`, `<li>` - Unordered lists
- `<ol>`, `<li>` - Ordered lists
- `<strong>`, `<b>` - Bold text
- `<em>`, `<i>` - Italic text
- `<a href="">` - Links

**Note**: The `description` field in the response returns plain text with HTML stripped.

## Script Behavior

The `update_product_description.py` script:

1. Accepts product handle, GID, or numeric ID
2. Resolves handle to product ID using `productByHandle` query (if needed)
3. Shows old description (first 100 characters)
4. Updates with new description
5. Shows new description (first 100 characters)
6. Reports success or errors

## Notes
- The script can accept:
  - Product handle (e.g., "delonghi-dedica")
  - Full GID (e.g., "gid://shopify/Product/1234567890")
  - Numeric ID (e.g., "1234567890")
- HTML must be valid - invalid tags may be stripped by Shopify
- Use `\n` in command line for line breaks, or use proper HTML tags
- Description updates do not affect product status or other fields
- Changes are immediate - no confirmation dialog
- For bulk updates, consider scripting multiple calls or using CSV import

## Common Errors

### Product Not Found
```json
{
  "data": {
    "productByHandle": null
  }
}
```
**Solution**: Check that the handle is correct and the product exists.

### Invalid HTML
```json
{
  "userErrors": [
    {
      "field": ["input", "descriptionHtml"],
      "message": "Description HTML contains invalid markup"
    }
  ]
}
```
**Solution**: Validate HTML before submitting. Use matching opening/closing tags.

## Required Scopes
- `write_products`
- `read_products`
