# Manage Sale End Date Metafields

Set and clear `inventory.ShappifySaleEndDate` metafields to control automatic price reversion for sale products.

## Use Cases
- Set automatic sale end dates for scheduled price reversion
- Clear sale end dates when manually ending sales
- List products currently on sale with end dates
- Bulk update sale end dates by product tag or search query

## Operations

### 1. Search Products with Sale End Date

**Validated**: ✅ Passed Shopify MCP validation

```graphql
query searchProducts($query: String!, $first: Int!) {
  products(first: $first, query: $query) {
    nodes {
      id
      title
      handle
      status
      vendor
      priceRangeV2 {
        minVariantPrice {
          amount
          currencyCode
        }
      }
      saleEndDate: metafield(namespace: "inventory", key: "ShappifySaleEndDate") {
        id
        value
      }
    }
  }
}
```

**Required Scopes**: `read_products`

**Variables**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| query | String! | Yes | Shopify search query |
| first | Int! | Yes | Max number of products to return (default: 50) |

**Example Query Strings**:
- `metafield.inventory.ShappifySaleEndDate:*` - All products with sale end dates
- `tag:bremap` - All products with BREMAP tag
- `tag:sale status:active` - Active products tagged as on sale
- `vendor:Breville` - All Breville products

### 2. Set Sale End Date Metafield

**Validated**: ✅ Passed Shopify MCP validation

```graphql
mutation setProductMetafield($input: MetafieldsSetInput!) {
  metafieldsSet(metafields: [$input]) {
    metafields {
      id
      namespace
      key
      value
    }
    userErrors {
      field
      message
    }
  }
}
```

**Required Scopes**: None specified by validation (metafields use product permissions)

**Variables**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| input.namespace | String! | Yes | `"inventory"` |
| input.key | String! | Yes | `"ShappifySaleEndDate"` |
| input.value | String! | Yes | ISO 8601 datetime (e.g., `"2025-07-24T23:59:59Z"`) |
| input.type | String! | Yes | `"single_line_text_field"` |
| input.ownerId | ID! | Yes | Product GID |

**Example**:
```json
{
  "input": {
    "namespace": "inventory",
    "key": "ShappifySaleEndDate",
    "value": "2025-07-24T23:59:59Z",
    "type": "single_line_text_field",
    "ownerId": "gid://shopify/Product/123"
  }
}
```

### 3. Get Product Metafield ID

**Validated**: ✅ Passed Shopify MCP validation

```graphql
query getProductMetafield($id: ID!) {
  product(id: $id) {
    saleEndDate: metafield(namespace: "inventory", key: "ShappifySaleEndDate") {
      id
    }
  }
}
```

**Required Scopes**: `read_products`

**Variables**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| id | ID! | Yes | Product GID |

**Purpose**: Used before clearing to get the metafield ID (optional - can delete by namespace/key).

### 4. Delete Sale End Date Metafield

**Validated**: ✅ Passed Shopify MCP validation

```graphql
mutation deleteMetafields($metafields: [MetafieldIdentifierInput!]!) {
  metafieldsDelete(metafields: $metafields) {
    deletedMetafields {
      ownerId
      namespace
      key
    }
    userErrors {
      field
      message
    }
  }
}
```

**Required Scopes**: None specified by validation (metafields use product permissions)

**Variables**

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| metafields | [MetafieldIdentifierInput!]! | Yes | Array of metafield identifiers |
| metafields[].ownerId | ID! | Yes | Product GID |
| metafields[].namespace | String! | Yes | `"inventory"` |
| metafields[].key | String! | Yes | `"ShappifySaleEndDate"` |

**Example**:
```json
{
  "metafields": [{
    "ownerId": "gid://shopify/Product/123",
    "namespace": "inventory",
    "key": "ShappifySaleEndDate"
  }]
}
```

## Usage Examples

### List Products with Sale End Dates
```bash
# All products with sale end dates
python manage_sale_end_dates.py list

# Search by tag
python manage_sale_end_dates.py list --search "tag:sale"

# Limit results
python manage_sale_end_dates.py list --search "vendor:Breville" --limit 100
```

### Set Sale End Date
```bash
# Set for specific product
python manage_sale_end_dates.py set --product-id "gid://shopify/Product/123" --date "2025-07-24"

# Set for all products with tag
python manage_sale_end_dates.py set --search "tag:bremap" --date "2025-07-24T23:59:59Z"

# Limit number of products
python manage_sale_end_dates.py set --search "tag:sale" --date "2025-07-31" --limit 50
```

### Clear Sale End Dates
```bash
# Clear for specific product
python manage_sale_end_dates.py clear --product-id "gid://shopify/Product/123"

# Clear for all products with tag
python manage_sale_end_dates.py clear --search "tag:mielesale"

# Limit number of products
python manage_sale_end_dates.py clear --search "tag:sale" --limit 50
```

## Response Structure

**Search Response**:
- `products.nodes[].id`: Product GID
- `products.nodes[].title`: Product name
- `products.nodes[].handle`: URL handle
- `products.nodes[].priceRangeV2.minVariantPrice.amount`: Lowest variant price
- `products.nodes[].saleEndDate.id`: Metafield GID (if exists)
- `products.nodes[].saleEndDate.value`: ISO 8601 date string (if exists)

**Set Metafield Response**:
- `metafields[].id`: Created/updated metafield GID
- `metafields[].value`: Set value
- `userErrors[]`: Validation errors if any

**Delete Metafield Response**:
- `deletedMetafields[].ownerId`: Product GID
- `deletedMetafields[].namespace`: "inventory"
- `deletedMetafields[].key`: "ShappifySaleEndDate"
- `userErrors[]`: Validation errors if any

## Date Formatting

The script accepts multiple date formats and converts them to ISO 8601:

**Input Formats**:
- `YYYY-MM-DD` → Converted to 11:59:59 PM EST/EDT
- `YYYY-MM-DDTHH:MM:SS` → Uses provided time
- `YYYY-MM-DDTHH:MM:SSZ` → UTC time preserved
- ISO 8601 with timezone → Converted to UTC

**Output Format**: Always `YYYY-MM-DDTHH:MM:SSZ` (UTC)

**Example Conversions**:
- `2025-07-24` → `2025-07-24T23:59:59Z` (assumes EST/EDT, converts to UTC)
- `2025-07-24T23:59:59` → `2025-07-24T23:59:59Z`
- `2025-07-24T19:59:59-04:00` → `2025-07-24T23:59:59Z`

## Workflow

### Setting Sale End Dates
1. Parse and validate date (convert to ISO 8601 UTC)
2. Find products by ID or search query
3. For each product:
   - Create/update `inventory.ShappifySaleEndDate` metafield
   - Display success/failure
4. Show summary: N/M products updated

### Clearing Sale End Dates
1. Find products by ID or search query
2. For each product:
   - Check if metafield exists
   - Delete metafield by namespace/key
   - Display success/failure
3. Show summary: N/M products updated

## Notes
- Sale end dates are stored in `inventory.ShappifySaleEndDate` metafield
- Shopify automation or apps can read this metafield to auto-revert prices
- Date parsing assumes EST/EDT timezone if not specified
- All dates are converted to UTC for Shopify storage
- The script continues processing even if some updates fail
- No metafield ID required for deletion (can delete by namespace/key)
- `--limit` parameter defaults to 50, max depends on search query
- Summary displays: ✅ success count / ❌ failure count / total
